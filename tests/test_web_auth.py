import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from contextlib import closing
from unittest.mock import patch

from services import database, field_staff, field_permissions, web_auth as auth

PASSWORD = 'Contraseña ficticia 12345'
NEW_PASSWORD = 'Nueva contraseña ficticia 6789'


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'auth.db'
        self.patch = patch.object(database, 'DB_PATH', self.path)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute('CREATE TABLE profiles(id INTEGER PRIMARY KEY, name TEXT)')
            conn.execute('CREATE TABLE territorial_action_plans(id INTEGER PRIMARY KEY)')
        field_staff.initialize_staff()
        auth.initialize_auth()
        self.worker = field_staff.create_worker('Persona de campo')
        self.admin = auth.bootstrap_admin('Administración', 'admin', PASSWORD)
        self.token = auth.login('admin', PASSWORD)

    def create_field_login(self):
        auth.set_account(self.token, self.worker, 'campo', PASSWORD)
        temporary = auth.login('campo', PASSWORD)
        auth.change_password(temporary, PASSWORD, NEW_PASSWORD)
        return auth.login('campo', NEW_PASSWORD)

    def test_bootstrap_preserves_existing_role_and_cannot_repeat(self):
        self.assertEqual(field_staff.list_workers()[1]['role_key'], 'field')
        with self.assertRaises(ValueError):
            auth.bootstrap_admin('Otra cuenta', 'other', PASSWORD)
        self.assertIsNone(auth.login('admin', 'incorrecta'))
        self.assertIsNone(auth.login('inexistente', PASSWORD))
        self.assertEqual(auth.current_user(self.token)['id'], self.admin)

    def test_passwords_and_session_tokens_are_not_stored_in_clear(self):
        raw = self.path.read_bytes()
        self.assertNotIn(PASSWORD.encode(), raw)
        self.assertNotIn(self.token.encode(), raw)
        with closing(sqlite3.connect(self.path)) as conn:
            hashed = conn.execute('SELECT password_hash FROM web_accounts').fetchone()[0]
        self.assertTrue(hashed.startswith('scrypt$'))
        self.assertTrue(auth.verify_password(PASSWORD, hashed))

    def test_lockout_and_expiration(self):
        for _ in range(5):
            self.assertIsNone(auth.login('admin', 'incorrecta'))
        self.assertIsNone(auth.login('admin', PASSWORD))
        with patch.object(auth.time, 'time', return_value=time.time()+301):
            self.assertIsNotNone(auth.login('admin', PASSWORD))
        with patch.object(auth.time, 'time', return_value=time.time()+auth.SESSION_SECONDS+1):
            self.assertIsNone(auth.current_user(self.token))

    def test_temporary_password_must_change_and_reset_revokes(self):
        token = self.create_field_login()
        self.assertEqual(auth.current_user(token)['must_change'], 0)
        auth.set_account(self.token, self.worker, 'campo', PASSWORD)
        self.assertIsNone(auth.current_user(token))
        token = auth.login('campo', PASSWORD)
        with closing(database.connection()) as conn:
            with self.assertRaises(PermissionError):
                auth.require_user(token, conn)

    def test_non_admin_cannot_create_accounts_or_fake_a_session(self):
        token = self.create_field_login()
        with self.assertRaises(PermissionError):
            auth.set_account(token, self.admin, 'admin', NEW_PASSWORD)
        self.assertIsNone(auth.current_user('invented'))
        with self.assertRaises(PermissionError):
            auth.set_account('invented', self.worker, 'campo', NEW_PASSWORD)

    def test_role_changes_and_deactivation_revoke_sessions(self):
        token = self.create_field_login()
        field_permissions.save_access(self.worker, 'supervisor')
        self.assertIsNone(auth.current_user(token))
        token = auth.login('campo', NEW_PASSWORD)
        field_staff.set_worker_active(self.worker, False)
        field_staff.set_worker_active(self.worker, True)
        self.assertIsNone(auth.current_user(token))

    def test_last_admin_cannot_be_disabled_or_demoted(self):
        with self.assertRaises(ValueError):
            field_staff.set_worker_active(self.admin, False)
        with self.assertRaises(ValueError):
            field_permissions.save_access(self.admin, 'field')
        self.assertEqual(auth.current_user(self.token)['role_key'], 'administrator')

    def test_logout_and_password_validation(self):
        with self.assertRaises(ValueError):
            auth.hash_password('corta')
        with self.assertRaises(ValueError):
            auth.change_password(self.token, 'incorrecta', NEW_PASSWORD)
        self.assertIsNotNone(auth.current_user(self.token))
        auth.logout(self.token)
        self.assertIsNone(auth.current_user(self.token))

    def test_login_screen_and_forced_password_change(self):
        from streamlit.testing.v1 import AppTest
        auth.set_account(self.token, self.worker, 'campo', PASSWORD)
        app = AppTest.from_string('from services.web_auth_ui import require_login\nu=require_login()\n'
                                 'import streamlit as st\nst.write("DATOS PRIVADOS")').run()
        self.assertFalse(app.exception)
        self.assertFalse(any('DATOS PRIVADOS' in m.value for m in app.markdown))
        app.text_input[0].input('campo')
        app.text_input[1].input(PASSWORD)
        next(b for b in app.button if b.label == 'Iniciar sesión').click().run(timeout=10)
        self.assertFalse(app.exception)
        self.assertTrue(any('Define tu contraseña' in t.value for t in app.title))
        self.assertFalse(any('DATOS PRIVADOS' in m.value for m in app.markdown))

    def test_admin_screen_stops_anonymous_and_field_users(self):
        from streamlit.testing.v1 import AppTest
        token = self.create_field_login()
        source = 'from services.web_auth_ui import require_admin\nrequire_admin()\nimport streamlit as st\nst.write("SECRETO ADMIN")'
        for credential in ('', token):
            app = AppTest.from_string(source)
            app.session_state['_web_token'] = credential
            app.run()
            self.assertFalse(app.exception)
            self.assertTrue(app.error)
            self.assertFalse(any('SECRETO ADMIN' in m.value for m in app.markdown))


if __name__ == '__main__':
    unittest.main()
