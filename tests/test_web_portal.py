import unittest
from unittest.mock import patch
import test_field_tasks as task_tests
from services import web_auth as auth, field_staff as staff, field_permissions as access, field_tasks as tasks
from services.web_portal import portal_data, assignment_candidates
from services import field_reports as reports

PASSWORD = 'Contraseña ficticia inicial 123'
PERSONAL = 'Contraseña ficticia personal 456'


class PortalTests(unittest.TestCase):
    setUp = task_tests.TaskTests.setUp
    message = task_tests.TaskTests.message
    callback = task_tests.TaskTests.callback
    sql = task_tests.TaskTests.sql

    def tokens(self):
        auth.initialize_auth()
        auth.bootstrap_admin('Administrador', 'admin', PASSWORD)
        admin = auth.login('admin', PASSWORD)
        auth.set_account(admin, self.worker, 'campo', PASSWORD)
        temporary = auth.login('campo', PASSWORD)
        auth.change_password(temporary, PASSWORD, PERSONAL)
        return admin, auth.login('campo', PERSONAL)

    def test_scoped_read_and_backend_assignment_denial(self):
        admin, field = self.tokens()
        tasks.assign_task_locally(2, self.other)
        user, visible, _ = portal_data(field)
        self.assertEqual([t['id'] for t in visible], [1])
        with self.assertRaises(PermissionError):
            tasks.assign_task_locally(2, self.worker, session_token=field)
        self.assertEqual(tasks.get_assignment(2)['worker_id'], self.other)
        tasks.assign_task_locally(2, self.worker, session_token=admin)
        self.assertEqual(tasks.get_assignment(2)['worker_id'], self.worker)
        with self.assertRaises(PermissionError):
            portal_data('invented')

    def test_live_scope_revocation_and_expired_session_writes(self):
        admin, field = self.tokens()
        access.remove_scope(self.worker, 1, 'Sonora', 'Hermosillo')
        self.assertFalse(portal_data(field)[1])
        auth.logout(admin)
        with self.assertRaises(PermissionError):
            tasks.assign_task_locally(1, None, session_token=admin)

    def test_review_checks_session_not_supplied_actor(self):
        admin, field = self.tokens()
        self.sql("INSERT INTO field_reports (task_id,worker_id,generation,body,source_chat_id,source_message_id) "
                 "VALUES (1,?,'x','Reporte',101,99)", (self.worker,))
        with self.assertRaises(PermissionError):
            reports.review_report(1,'accepted','',actor_worker_id=999,session_token=field)
        reports.review_report(1,'accepted','Revisado',session_token=admin)
        self.assertEqual(reports.list_task_reports(1)[0]['status'], 'accepted')

    def test_coordinator_unassigned_queue_and_team_assignment(self):
        access.save_access(self.worker, 'coordinator')
        _, coordinator = self.tokens()
        self.assertIn(2, [t['id'] for t in portal_data(coordinator)[1]])
        self.assertNotIn(self.other, [w['id'] for w in assignment_candidates(coordinator, 2)])
        with self.assertRaises(PermissionError):
            tasks.assign_task_locally(2, self.other, session_token=coordinator)
        access.save_access(self.worker, 'coordinator', 'Equipo A')
        access.save_access(self.other, 'field', 'Equipo A', self.worker)
        coordinator = auth.login('campo', PERSONAL)
        self.assertIn(self.other, [w['id'] for w in assignment_candidates(coordinator, 2)])
        tasks.assign_task_locally(2, self.other, session_token=coordinator)
        self.assertEqual(tasks.get_assignment(2)['worker_id'], self.other)
        self.assertIn(2, [t['id'] for t in portal_data(coordinator)[1]])
        access.save_access(self.other, 'field', 'Equipo B')
        self.assertNotIn(2, [t['id'] for t in portal_data(coordinator)[1]])
        self.assertEqual(assignment_candidates(coordinator, 2), [])
        with self.assertRaises(PermissionError):
            tasks.assign_task_locally(2, self.worker, session_token=coordinator)

    def test_unassigned_queue_keeps_scope_and_role_boundaries(self):
        access.save_access(self.worker, 'coordinator', 'Equipo A')
        _, coordinator = self.tokens()
        self.sql("UPDATE territorial_action_plans SET municipality='Guaymas' WHERE id=2")
        self.sql("UPDATE territorial_action_plans SET profile_id=999 WHERE id=3")
        visible = [t['id'] for t in portal_data(coordinator)[1]]
        self.assertNotIn(2, visible)
        self.assertNotIn(3, visible)
        self.assertIn(4, visible)
        for permission in ('tasks.confirm', 'reports.submit', 'reports.view', 'reports.review'):
            self.assertFalse(access.can_access(self.worker, permission, profile_id=1,
                                               state='Sonora', municipality='Hermosillo'))
        for role in ('field', 'supervisor'):
            access.save_access(self.worker, role, 'Equipo A')
            token = auth.login('campo', PERSONAL)
            self.assertEqual([t['id'] for t in portal_data(token)[1]], [1])
        access.save_access(self.worker, 'coordinator', 'Equipo A')
        coordinator = auth.login('campo', PERSONAL)
        access.remove_scope(self.worker, 1, 'Sonora', 'Hermosillo')
        self.assertEqual(portal_data(coordinator)[1], [])

    def test_coordinator_screen_assigns_unassigned_task(self):
        from streamlit.testing.v1 import AppTest
        access.save_access(self.worker, 'coordinator', 'Equipo A')
        access.save_access(self.other, 'field', 'Equipo A')
        _, coordinator = self.tokens()
        app = AppTest.from_string('from services.web_portal import render_portal\nrender_portal()')
        app.session_state['_web_token'] = coordinator
        app.run()
        self.assertFalse(app.exception)
        expander = next(e for e in app.expander if e.label.startswith('#2 ·'))
        self.assertIn('Sin asignar', expander.label)
        expander.selectbox[0].select(self.other)
        expander.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(tasks.get_assignment(2)['worker_id'], self.other)


if __name__ == '__main__':
    unittest.main()
