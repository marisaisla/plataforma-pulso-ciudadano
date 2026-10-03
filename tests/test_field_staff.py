import os
import tempfile
import unittest
import sqlite3
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from services import database, field_staff as staff


def message(user, text, chat_type='private'):
    return {'chat': {'id': user, 'type': chat_type}, 'from': {'id': user}, 'text': text}


class StaffTests(unittest.TestCase):
    def setUp(self):
        backend_patch = patch.dict(os.environ, {"DB_BACKEND": "sqlite"})
        backend_patch.start()
        self.addCleanup(backend_patch.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'test.db'
        self.patch = patch.object(database, 'DB_PATH', self.path)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        staff.initialize_staff()
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute('CREATE TABLE territorial_action_plans (id INTEGER PRIMARY KEY, status TEXT)')
        self.worker = staff.create_worker('Persona de prueba', 'Equipo A')

    def test_link_persists_and_code_cannot_be_reused(self):
        code = staff.issue_code(self.worker)
        self.assertNotIn(code.encode(), self.path.read_bytes())
        self.assertIn('Acceso activado', staff.telegram_reply(message(100, '/start ' + code)))
        staff.initialize_staff()
        self.assertEqual(staff.list_workers()[0]['telegram_user_id'], 100)
        self.assertIn('ya está vinculada', staff.telegram_reply(message(100, '/start ' + code)))
        self.assertIn('inválido', staff.telegram_reply(message(200, '/start ' + code)))

    def test_expired_and_replaced_codes(self):
        with patch.object(staff.time, 'time', return_value=1000):
            old = staff.issue_code(self.worker)
            new = staff.issue_code(self.worker)
            self.assertIn('inválido', staff.telegram_reply(message(100, '/start ' + old)))
        with patch.object(staff.time, 'time', return_value=2800):
            self.assertIn('inválido', staff.telegram_reply(message(100, '/start ' + new)))

    def test_disabled_and_unlinked(self):
        code = staff.issue_code(self.worker)
        staff.telegram_reply(message(100, '/start ' + code))
        staff.set_worker_active(self.worker, False)
        self.assertIn('desactivado', staff.telegram_reply(message(100, '/start')))
        staff.set_worker_active(self.worker, True)
        staff.unlink_worker(self.worker)
        self.assertIn('Solicita tu código', staff.telegram_reply(message(100, '/mis_tareas')))
        self.assertIn('inválido', staff.telegram_reply(message(100, '/start ' + code)))

    def test_groups_and_unknown_users_cannot_register_reports(self):
        code = staff.issue_code(self.worker)
        self.assertIsNone(staff.telegram_reply(message(100, '/start ' + code, 'group')))
        self.assertIsNone(staff.list_workers()[0]['telegram_user_id'])
        self.assertIn('Solicita tu código', staff.telegram_reply(message(100, '/reportar')))
        staff.telegram_reply(message(100, '/start ' + code))
        self.assertIn('No se guardó', staff.telegram_reply(message(100, '/reportar'))['text'])

    def test_one_account_cannot_claim_second_worker(self):
        code = staff.issue_code(self.worker)
        staff.telegram_reply(message(100, '/start ' + code))
        other = staff.create_worker('Segunda persona')
        other_code = staff.issue_code(other)
        staff.telegram_reply(message(100, '/start ' + other_code))
        workers = {w['id']: w for w in staff.list_workers()}
        self.assertIsNone(workers[other]['telegram_user_id'])
        self.assertIn('Acceso activado', staff.telegram_reply(message(200, '/start ' + other_code)))

    def test_deactivation_revokes_unused_code(self):
        code = staff.issue_code(self.worker)
        staff.set_worker_active(self.worker, False)
        staff.set_worker_active(self.worker, True)
        self.assertIn('inválido', staff.telegram_reply(message(100, '/start ' + code)))


if __name__ == '__main__':
    unittest.main()
