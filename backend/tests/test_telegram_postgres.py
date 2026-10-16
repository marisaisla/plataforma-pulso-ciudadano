"""Pruebas optativas contra PostgreSQL con tablas temporales, sin datos reales."""
import hashlib
import os
import time
import unittest

from fastapi import HTTPException
from backend.database import connect
from backend.main import Message
from backend.telegram import issue_code, process_message


class TemporaryTables:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=()):
        return self.conn.execute(sql.replace('public.field_', 'pg_temp.field_'), params)


@unittest.skipUnless(os.environ.get('API_TEST_POSTGRES') == '1', 'Activar API_TEST_POSTGRES=1')
class TelegramPostgresTests(unittest.TestCase):
    def setUp(self):
        self.raw = connect()
        self.addCleanup(self.raw.close)
        self.addCleanup(self.raw.rollback)
        self.raw.execute('CREATE TEMP TABLE field_workers (LIKE public.field_workers INCLUDING ALL) ON COMMIT DROP')
        self.raw.execute('CREATE TEMP TABLE field_activation_codes (LIKE public.field_activation_codes INCLUDING ALL) ON COMMIT DROP')
        self.conn = TemporaryTables(self.raw)
        self.conn.execute('INSERT INTO public.field_workers (id,name,team,active,created_at) VALUES (1,%s,%s,1,%s)',
                          ('API TEST', '', int(time.time())))

    def message(self, code, sender=123):
        return Message.model_validate({'message_id':1, 'from':{'id':sender,'is_bot':False},
                                       'chat':{'id':sender,'type':'private'}, 'text':'/start ' + code})

    def test_activation_and_retry_preserve_link_timestamp(self):
        code = issue_code(self.conn, 1)['activation_code']
        stored = self.conn.execute('SELECT code_hash FROM public.field_activation_codes').fetchone()
        self.assertEqual(stored['code_hash'], hashlib.sha256(code.encode()).hexdigest())
        self.assertEqual(process_message(self.conn, self.message(code))['status'], 'linked')
        first = self.conn.execute('SELECT linked_at FROM public.field_workers WHERE id=1').fetchone()
        self.assertEqual(process_message(self.conn, self.message(code))['status'], 'already_linked')
        self.assertEqual(first, self.conn.execute('SELECT linked_at FROM public.field_workers WHERE id=1').fetchone())
        self.assertEqual(process_message(self.conn, self.message(code, 456))['status'], 'rejected')

    def test_new_code_invalidates_old_and_expiration_rejects(self):
        old = issue_code(self.conn, 1)['activation_code']
        new = issue_code(self.conn, 1)['activation_code']
        self.assertEqual(process_message(self.conn, self.message(old))['status'], 'rejected')
        self.conn.execute('UPDATE public.field_activation_codes SET expires_at=0')
        self.assertEqual(process_message(self.conn, self.message(new))['status'], 'rejected')
        self.assertIsNone(self.conn.execute('SELECT telegram_user_id FROM public.field_workers WHERE id=1').fetchone()['telegram_user_id'])

    def test_deactivation_blocks_code_and_activation(self):
        code = issue_code(self.conn, 1)['activation_code']
        self.conn.execute('UPDATE public.field_workers SET active=0 WHERE id=1')
        self.assertEqual(process_message(self.conn, self.message(code))['status'], 'rejected')
        with self.assertRaises(HTTPException) as raised:
            issue_code(self.conn, 1)
        self.assertEqual(raised.exception.status_code, 409)

    def test_group_and_mismatched_identity_are_ignored(self):
        code = issue_code(self.conn, 1)['activation_code']
        message = self.message(code)
        message.chat.type = 'group'
        self.assertEqual(process_message(self.conn, message)['status'], 'ignored')
        message.chat.type = 'private'
        message.chat.id = 456
        self.assertEqual(process_message(self.conn, message)['status'], 'ignored')
