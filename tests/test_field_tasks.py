import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from services import database
from services import field_staff as staff
from services import field_tasks as tasks
from services import field_permissions as access
from scripts import integrador_telegram as bot


class TaskTests(unittest.TestCase):
    def setUp(self):
        backend_patch = patch.dict(os.environ, {"DB_BACKEND": "sqlite"})
        backend_patch.start()
        self.addCleanup(backend_patch.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'test.db'
        self.db_patch = patch.object(database, 'DB_PATH', self.path)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.executescript('''
                CREATE TABLE profiles (id INTEGER PRIMARY KEY, name TEXT);
                INSERT INTO profiles VALUES (1, 'Campaña A');
                CREATE TABLE territorial_action_plans (
                    id INTEGER PRIMARY KEY, profile_id INTEGER, state TEXT, municipality TEXT,
                    activity_name TEXT, activity_description TEXT, due_date TEXT, status TEXT);
            ''')
            conn.executemany('INSERT INTO territorial_action_plans VALUES (?, 1, ?, ?, ?, ?, ?, ?)',
                             [(i, 'Sonora', 'Hermosillo', f'Actividad {i}', 'Descripción', '2026-10-01', 'Pendiente')
                              for i in range(1, 8)])
        staff.initialize_staff()
        self.worker = staff.create_worker('Persona uno')
        self.other = staff.create_worker('Persona dos')
        for wid, uid in [(self.worker, 101), (self.other, 102)]:
            access.add_scope(wid, 1, 'Sonora', 'Hermosillo')
            code = staff.issue_code(wid)
            staff.telegram_reply(self.message(uid, '/start ' + code))
        tasks.assign_task_locally(1, self.worker)

    def message(self, uid, text):
        return {'chat': {'id': uid, 'type': 'private'}, 'from': {'id': uid}, 'text': text}

    def callback(self, uid=101, task_id=1, generation=None):
        if generation is None:
            generation = tasks.get_assignment(task_id)['generation']
        return {'id': 'callback1', 'from': {'id': uid}, 'message': {'chat': {'id': uid, 'type': 'private'}},
                'data': f'taskconfirm:{task_id}:{generation}'}

    def sql(self, sql, params=()):
        with closing(sqlite3.connect(self.path)) as conn, conn:
            return conn.execute(sql, params).fetchall()

    def test_only_own_tasks_and_receiver_buttons(self):
        tasks.assign_task_locally(2, self.other)
        response = staff.telegram_reply(self.message(101, '/mis_tareas'))
        self.assertIn('Actividad 1', response['text'])
        self.assertNotIn('Actividad 2', response['text'])
        button = response['reply_markup']['inline_keyboard'][0][0]
        self.assertLessEqual(len(button['callback_data'].encode()), 64)

    def test_receipt_is_persistent_idempotent_and_not_completion(self):
        cb = self.callback()
        self.assertIn('registrada en Go2Win', staff.telegram_callback(cb))
        first = tasks.get_assignment(1)['received_at']
        staff.initialize_staff()
        self.assertIn('ya estaba registrada', staff.telegram_callback(cb))
        self.assertEqual(tasks.get_assignment(1)['received_at'], first)
        self.assertEqual(self.sql("SELECT count(*) FROM field_task_events WHERE event='received'")[0][0], 1)
        self.assertEqual(self.sql('SELECT status FROM territorial_action_plans WHERE id=1')[0][0], 'Pendiente')

    def test_reassignment_invalidates_old_buttons_even_when_reassigned_back(self):
        old = self.callback()
        tasks.assign_task_locally(1, self.other)
        self.assertIn('No puedes', staff.telegram_callback(old))
        tasks.assign_task_locally(1, self.worker)
        self.assertIn('No puedes', staff.telegram_callback(old))
        self.assertIsNone(tasks.get_assignment(1)['received_at'])
        self.assertIn('registrada en Go2Win', staff.telegram_callback(self.callback()))

    def test_same_assignment_does_not_reset_receipt(self):
        staff.telegram_callback(self.callback())
        before = tasks.get_assignment(1)
        tasks.assign_task_locally(1, self.worker)
        self.assertEqual(tasks.get_assignment(1), before)

    def test_other_user_and_group_cannot_confirm(self):
        self.assertIn('No puedes', staff.telegram_callback(self.callback(uid=102)))
        cb = self.callback()
        cb['message']['chat']['type'] = 'group'
        self.assertIsNone(staff.telegram_callback(cb))
        self.assertIsNone(tasks.get_assignment(1)['received_at'])

    def test_scope_revocation_and_deactivation_take_effect(self):
        cb = self.callback()
        access.remove_scope(self.worker, 1, 'Sonora', 'Hermosillo')
        self.assertIn('No puedes', staff.telegram_callback(cb))
        self.assertNotIn('Actividad 1', staff.telegram_reply(self.message(101, '/mis_tareas'))['text'])
        staff.set_worker_active(self.worker, False)
        self.assertIn('no tiene acceso', staff.telegram_callback(cb))

    def test_closed_and_unassigned_tasks_not_confirmable(self):
        cb = self.callback()
        self.sql("UPDATE territorial_action_plans SET status='Concluida' WHERE id=1")
        self.assertIn('No puedes', staff.telegram_callback(cb))
        with self.assertRaises(ValueError):
            tasks.assign_task_locally(1, self.other)
        self.sql("UPDATE territorial_action_plans SET status='Pendiente' WHERE id=1")
        tasks.assign_task_locally(1, None)
        self.assertIn('No puedes', staff.telegram_callback(cb))

    def test_assign_rejects_ineligible_and_no_name_matching(self):
        unknown = staff.create_worker('Persona uno')
        with self.assertRaises(ValueError):
            tasks.assign_task_locally(2, unknown)
        self.assertNotIn(unknown, [w['id'] for w in tasks.eligible_workers(1)])
        self.assertIsNone(tasks.get_assignment(2))

    def test_pagination_and_long_text_limits(self):
        for tid in range(2, 8):
            tasks.assign_task_locally(tid, self.worker)
        self.sql('UPDATE territorial_action_plans SET activity_name=?, activity_description=?', ('😀'*1000, '😀'*5000))
        response = staff.telegram_reply(self.message(101, '/mis_tareas'))
        self.assertLessEqual(len(response['text'].encode('utf-16-le')) // 2, 4096)
        cb = self.callback()
        cb['data'] = 'taskpage:3'
        page = staff.telegram_callback(cb)
        self.assertIn('#4', page['text'])
        self.assertNotIn('#1', page['text'])

    def test_bad_callback_does_not_raise_or_modify(self):
        for data in ('taskconfirm:nope:x', 'taskconfirm:9999999999999999999999:x', 'taskpage:-1', 'taskpage:²', 'unknown'):
            cb = self.callback()
            cb['data'] = data
            self.assertIn('no es válido', staff.telegram_callback(cb))
        self.assertIsNone(tasks.get_assignment(1)['received_at'])

    def test_detail_includes_long_description_with_permission_checks(self):
        description = 'Inicio de instrucciones ' + 'x' * 4000 + ' FIN DEL DETALLE'
        self.sql('UPDATE territorial_action_plans SET activity_description=? WHERE id=1', (description,))
        response = staff.telegram_reply(self.message(101, '/tarea 1'))
        text = response['text']
        while True:
            next_button = next((b for row in response.get('reply_markup', {}).get('inline_keyboard', [])
                                for b in row if b['callback_data'].startswith('taskdetail:')), None)
            if not next_button:
                break
            cb = self.callback()
            cb['data'] = next_button['callback_data']
            response = staff.telegram_callback(cb)
            text += response['text']
        self.assertIn(description, text)
        self.assertNotIn('instrucciones', staff.telegram_reply(self.message(102, '/tarea 1'))['text'])
        self.assertIn('Envía /tarea', staff.telegram_reply(self.message(101, '/tarea nope')))

    def test_transport_retries_after_send_failure_without_duplicate_receipt(self):
        update = {'callback_query': self.callback()}
        def fail_send(method, **params):
            if method == 'sendMessage':
                raise bot.transport.TelegramError('Simulated network error')
        with patch.object(bot.transport, 'api', side_effect=fail_send):
            with self.assertRaises(bot.transport.TelegramError):
                bot.process_update(update)
        with patch.object(bot.transport, 'api') as api:
            bot.process_update(update)
            self.assertIn('ya estaba registrada', api.call_args.kwargs['text'])
        self.assertEqual(self.sql("SELECT count(*) FROM field_task_events WHERE event='received'")[0][0], 1)

    def test_assignment_widget(self):
        from streamlit.testing.v1 import AppTest
        from web_test_helpers import admin_session
        token = admin_session()
        with patch('services.field_tasks_ui.st.rerun', side_effect=lambda: None):
            app = AppTest.from_string("from services.field_tasks_ui import render_task_assignment\n"
                                     "render_task_assignment({'id': 2, 'status': 'Pendiente'})")
            app.session_state['_web_token'] = token
            app.run()
            self.assertFalse(app.exception)
            app.selectbox[0].select(self.worker)
            app.button[0].click().run()
            self.assertFalse(app.exception)
            self.assertEqual(tasks.get_assignment(2)['worker_id'], self.worker)


if __name__ == '__main__':
    unittest.main()
