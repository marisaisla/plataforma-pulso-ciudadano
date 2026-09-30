import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import closing

import test_field_tasks as task_tests
from services import development_access as dev, web_auth as auth, field_tasks as tasks
from services.database import connection


class ConfigurationTests(unittest.TestCase):
    def test_default_explicit_flag_and_environment_priority(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(dev.os.environ, {}, clear=True):
            with patch.object(dev, 'ENV_PATH', Path(directory) / '.env'):
                self.assertFalse(dev.enabled())
                dev.ENV_PATH.write_text('GO2WIN_MODO_DESARROLLO=true\n', encoding='utf-8')
                self.assertTrue(dev.enabled())
                with patch.dict(dev.os.environ, {dev.KEY: 'false'}):
                    self.assertFalse(dev.enabled())
                dev.ENV_PATH.write_text('GO2WIN_MODO_DESARROLLO=anything\n', encoding='utf-8')
                self.assertFalse(dev.enabled())

    def test_local_binding_and_proxy_restrictions(self):
        import streamlit as st
        with patch('streamlit.runtime.scriptrunner.get_script_run_ctx', return_value=object()):
            with patch.object(st, 'get_option', return_value='127.0.0.1'):
                with patch.object(st, 'context', SimpleNamespace(headers={'Host': 'localhost:8501'})):
                    self.assertTrue(dev.local_request())
                with patch.object(st, 'context', SimpleNamespace(headers={'Host': 'example.com'})):
                    self.assertFalse(dev.local_request())
                with patch.object(st, 'context', SimpleNamespace(headers={'Host': 'localhost:8501', 'X-Forwarded-For': '1.2.3.4'})):
                    self.assertFalse(dev.local_request())
            for bind in ('0.0.0.0', '', None, '192.168.1.5'):
                with patch.object(st, 'get_option', return_value=bind):
                    self.assertFalse(dev.local_request())


class DevelopmentLoginTests(unittest.TestCase):
    setUp = task_tests.TaskTests.setUp
    message = task_tests.TaskTests.message
    sql = task_tests.TaskTests.sql

    def prepare(self):
        auth.initialize_auth()
        # La contraseña temporal sigue intacta; no se usa un password de producción.
        with closing(connection()) as conn, conn:
            conn.execute('INSERT INTO web_accounts VALUES (?,?,?,1)', (self.worker, 'campo', 'unchanged'))

    def test_permissions_account_and_session_revocation(self):
        self.prepare()
        with patch.object(dev, 'enabled', return_value=True), patch.object(dev, 'local_request', return_value=True):
            token = auth.login_development(self.worker)
            user = auth.current_user(token)
            self.assertEqual(user['role_key'], 'field')
            self.assertEqual(user['must_change'], 0)
            with self.assertRaises(PermissionError):
                tasks.assign_task_locally(2, self.other, session_token=token)
            self.assertEqual(self.sql('SELECT password_hash,must_change FROM web_accounts'), [('unchanged', 1)])
            with patch.object(dev, 'local_request', return_value=False):
                self.assertIsNone(auth.current_user(token))
                with self.assertRaises(PermissionError):
                    auth.login_development(self.worker)
            with patch.object(dev, 'INSTANCE', 'new-process'):
                self.assertIsNone(auth.current_user(token))
            with patch.object(dev, 'enabled', return_value=False):
                self.assertIsNone(auth.current_user(token))
                self.assertEqual(auth.development_accounts(), [])
                auth.initialize_auth()
            self.assertIsNone(auth.current_user(token))

    def test_inactive_unknown_and_logout(self):
        self.prepare()
        with patch.object(dev, 'allowed', return_value=True):
            with self.assertRaises(ValueError):
                auth.login_development(self.other)
            token = auth.login_development(self.worker)
            auth.logout(token)
            self.assertIsNone(auth.current_user(token))
            self.sql('UPDATE field_workers SET active=0 WHERE id=?', (self.worker,))
            with self.assertRaises(ValueError):
                auth.login_development(self.worker)

    def test_existing_password_session_survives_migration(self):
        import time
        with closing(connection()) as conn, conn:
            conn.execute('CREATE TABLE web_sessions(token_hash TEXT PRIMARY KEY,worker_id INTEGER,expires_at INTEGER)')
            conn.execute('INSERT INTO web_sessions VALUES (?,?,?)',
                         (auth.token_hash('existing-session'), self.worker, int(time.time())+1000))
        self.prepare()
        with patch.object(dev, 'enabled', return_value=False):
            user = auth.current_user('existing-session')
            self.assertEqual(user['id'], self.worker)
            self.assertEqual(user['must_change'], 1)
            self.assertIsNone(user['development_instance'])

    def test_screen_selects_test_account(self):
        from streamlit.testing.v1 import AppTest
        self.prepare()
        with patch.object(dev, 'enabled', return_value=True), patch.object(dev, 'local_request', return_value=True):
            app = AppTest.from_string('from services.web_auth_ui import require_login\nu=require_login()\nimport streamlit as st\nst.text(u["role_key"])').run()
            self.assertFalse(app.exception)
            next(b for b in app.button if b.label == 'Entrar sin contraseña').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.text[0].value, 'field')
            self.assertTrue(app.warning)
