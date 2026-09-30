import time
import unittest
from unittest.mock import patch

import test_field_tasks as task_tests
from services import field_staff as staff
from services import field_tasks as tasks
from services import field_reports as reports
from services import field_permissions as access
from scripts import integrador_telegram as bot


class ReportTests(unittest.TestCase):
    # Reutiliza solo la preparación de datos; no repite las pruebas de tareas.
    setUp = task_tests.TaskTests.setUp
    message = task_tests.TaskTests.message
    callback = task_tests.TaskTests.callback
    sql = task_tests.TaskTests.sql

    def select(self, selection='select1'):
        staff.telegram_callback(self.callback())
        cb = self.callback()
        cb['id'] = selection
        cb['data'] = cb['data'].replace('taskconfirm:', 'reportselect:')
        return cb, staff.telegram_callback(cb)

    def text(self, body='Avance de prueba', mid=10):
        return {**self.message(101, body), 'message_id': mid, 'date': int(time.time())}

    def submit(self, mid=10):
        self.select('select' + str(mid))
        return staff.telegram_reply(self.text(mid=mid))

    def test_requires_received_task_and_own_assignment(self):
        response = staff.telegram_reply(self.message(101, '/reportar'))
        self.assertIn('confirma recepción', response['text'])
        cb, prompt = self.select()
        self.assertIn('Escribe el avance', prompt)
        cb['from']['id'] = 102
        cb['message']['chat']['id'] = 102
        self.assertIn('No puedes', staff.telegram_callback(cb))

    def test_submit_creates_folio_pending_and_does_not_close_task(self):
        reply = self.submit()
        self.assertIn('R-000001', reply)
        self.assertIn('Por validar', reply)
        row = reports.list_task_reports(1)[0]
        self.assertEqual((row['body'], row['worker_id'], row['status']), ('Avance de prueba', self.worker, 'pending'))
        self.assertEqual(self.sql('SELECT status FROM territorial_action_plans WHERE id=1')[0][0], 'Pendiente')
        self.assertEqual(self.sql('SELECT COUNT(*) FROM field_report_sessions')[0][0], 0)

    def test_session_survives_restart_and_retry_does_not_duplicate(self):
        self.select()
        staff.initialize_staff()
        message = self.text()
        first = staff.telegram_reply(message)
        staff.initialize_staff()
        self.assertEqual(staff.telegram_reply(message), first)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM field_reports')[0][0], 1)

    def test_send_failure_preserves_saved_report_and_replays_folio(self):
        self.select()
        message = self.text()
        with patch.object(bot.transport, 'api', side_effect=bot.transport.TelegramError('Network')):
            with self.assertRaises(bot.transport.TelegramError):
                bot.process_update({'message': message})
        with patch.object(bot.transport, 'api') as api:
            bot.process_update({'message': message})
            self.assertIn('R-000001', api.call_args.kwargs['text'])
        self.assertEqual(len(reports.list_task_reports(1)), 1)

    def test_cancel_expiry_and_old_text(self):
        self.select()
        old = {**self.text(), 'date': 1}
        self.assertIn('anterior', staff.telegram_reply(old))
        self.assertIn('cancelada', staff.telegram_reply(self.message(101, '/cancelar')))
        staff.telegram_reply(self.text())
        self.assertFalse(reports.list_task_reports(1))
        self.select('select2')
        self.sql('UPDATE field_report_sessions SET expires_at=0')
        self.assertIn('venció', staff.telegram_reply(self.text()))
        self.assertFalse(reports.list_task_reports(1))

    def test_reassignment_and_scope_changes_prevent_save(self):
        self.select()
        tasks.assign_task_locally(1, self.other)
        self.assertIn('No se guardó', staff.telegram_reply(self.text()))
        tasks.assign_task_locally(1, self.worker)
        self.select('select2')
        access.remove_scope(self.worker, 1, 'Sonora', 'Hermosillo')
        self.assertIn('No se guardó', staff.telegram_reply(self.text()))
        self.assertFalse(reports.list_task_reports(1))

    def test_media_blank_and_oversize_keep_session(self):
        self.select()
        for msg in ({**self.text(''), 'photo': [{}]}, self.text('  ')):
            self.assertIn('Espero un mensaje', staff.telegram_reply(msg))
        self.assertIn('supera 4000', staff.telegram_reply(self.text('x' * 4001)))
        self.assertFalse(reports.list_task_reports(1))
        self.assertIn('guardado', staff.telegram_reply(self.text('x' * 4000)))

    def test_callback_replay_does_not_rearm_finished_capture(self):
        cb, _ = self.select()
        self.assertIn('Escribe el avance', staff.telegram_callback(cb))
        staff.telegram_reply(self.text())
        self.assertIn('ya fue atendida', staff.telegram_callback(cb))
        self.assertEqual(self.sql('SELECT COUNT(*) FROM field_report_sessions')[0][0], 0)
        staff.telegram_reply(self.text('Otro texto', 11))
        self.assertEqual(len(reports.list_task_reports(1)), 1)

    def test_correction_requires_reason_and_preserves_history(self):
        self.submit()
        with self.assertRaises(ValueError):
            reports.review_report(1, 'correction', '')
        reports.review_report(1, 'correction', 'Indica el resultado obtenido.')
        reports.review_report(1, 'correction', 'Indica el resultado obtenido.')
        with self.assertRaises(ValueError):
            reports.review_report(1, 'accepted', '')
        response = staff.telegram_reply(self.message(101, '/mis_reportes'))
        self.assertIn('Corrección solicitada', response['text'])
        self.assertIn('Indica el resultado', response['text'])
        self.submit(11)
        rows = reports.list_task_reports(1)
        self.assertEqual([r['status'] for r in rows], ['pending', 'correction'])

    def test_accept_does_not_complete_and_not_visible_to_other(self):
        self.submit()
        reports.review_report(1, 'accepted', 'Revisado')
        self.assertEqual(self.sql('SELECT status FROM territorial_action_plans WHERE id=1')[0][0], 'Pendiente')
        self.assertIn('Aceptado', staff.telegram_reply(self.text()))
        self.assertNotIn('R-000001', staff.telegram_reply(self.message(102, '/mis_reportes'))['text'])

    def test_review_permissions_no_self_review_and_wrong_scope(self):
        self.submit()
        with self.assertRaises(PermissionError):
            reports.review_report(1, 'accepted', '', actor_worker_id=self.worker)
        access.save_access(self.other, 'supervisor', 'Equipo A')
        access.save_access(self.worker, 'field', 'Equipo A', self.other)
        access.remove_scope(self.other, 1, 'Sonora', 'Hermosillo')
        with self.assertRaises(PermissionError):
            reports.review_report(1, 'accepted', '', actor_worker_id=self.other)
        access.add_scope(self.other, 1, 'Sonora', 'Hermosillo')
        reports.review_report(1, 'accepted', '', actor_worker_id=self.other)
        self.assertEqual(reports.list_task_reports(1)[0]['actor'], f'worker:{self.other}')

    def test_deactivation_and_unlink_clear_capture(self):
        self.select()
        staff.set_worker_active(self.worker, False)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM field_report_sessions')[0][0], 0)
        staff.set_worker_active(self.worker, True)
        self.select('select2')
        staff.unlink_worker(self.worker)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM field_report_sessions')[0][0], 0)

    def test_review_ui(self):
        from streamlit.testing.v1 import AppTest
        from web_test_helpers import admin_session
        self.submit()
        token = admin_session()
        app = AppTest.from_string('from services.field_reports_ui import render_task_reports\nrender_task_reports(1)')
        app.session_state['_web_token'] = token
        app.run()
        self.assertFalse(app.exception)
        app.selectbox[0].select('correction')
        app.text_area[0].input('Describe el resultado.')
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(reports.list_task_reports(1)[0]['status'], 'correction')


if __name__ == '__main__':
    unittest.main()
