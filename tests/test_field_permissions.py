import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import closing

from services import database
from services import field_staff as staff
from services import field_permissions as access


class PermissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'test.db'
        self.patch = patch.object(database, 'DB_PATH', self.path)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute('CREATE TABLE profiles (id INTEGER PRIMARY KEY, name TEXT)')
            conn.execute('CREATE TABLE territorial_action_plans (id INTEGER PRIMARY KEY)')
            conn.executemany('INSERT INTO profiles VALUES (?, ?)', [(1, 'Campaña A'), (2, 'Campaña B')])
        staff.initialize_staff()
        self.people = {}
        for role in access.ROLE_LABELS:
            wid = staff.create_worker(role, 'Equipo A')
            self.people[role] = wid
            access.save_access(wid, role, 'Equipo A')
            access.add_scope(wid, 1, 'Sonora', 'Hermosillo')
        access.save_access(self.people['field'], 'field', 'Equipo A', self.people['supervisor'])
        self.context = dict(profile_id=1, state='Sonora', municipality='Hermosillo',
                            assigned_worker_id=self.people['field'])

    def test_all_role_grants_on_valid_resource(self):
        for role, wid in self.people.items():
            for permission in access.PERMISSION_LABELS:
                scope = access.ROLE_GRANTS[role].get(permission)
                expected = scope is not None and (scope != 'own' or role == 'field')
                with self.subTest(role=role, permission=permission):
                    self.assertEqual(access.can_access(wid, permission, **self.context), expected)

    def test_field_cannot_view_other_worker_or_administer(self):
        other = staff.create_worker('Otra persona', 'Equipo A')
        access.add_scope(other, 1, 'Sonora', 'Hermosillo')
        self.assertFalse(access.can_access(other, 'tasks.view', **self.context))
        self.assertFalse(access.can_access(self.people['field'], 'roles.manage'))
        with self.assertRaises(PermissionError):
            access.require_access(self.people['field'], 'tasks.assign', **self.context)

    def test_campaign_and_territory_boundaries(self):
        for role in ('field', 'supervisor', 'coordinator', 'director'):
            wid = self.people[role]
            for change in ({'profile_id': 2}, {'state': 'Chihuahua'}, {'municipality': 'Cajeme'}, {'profile_id': None}):
                self.assertFalse(access.can_access(wid, 'tasks.view', **{**self.context, **change}))
        self.assertTrue(access.can_access(self.people['administrator'], 'tasks.view', profile_id=2))

    def test_supervisor_requires_direct_assignment(self):
        access.save_access(self.people['field'], 'field', 'Equipo A')
        self.assertFalse(access.can_access(self.people['supervisor'], 'reports.review', **self.context))
        self.assertTrue(access.can_access(self.people['coordinator'], 'reports.review', **self.context))

    def test_team_and_owner_scope_required(self):
        access.save_access(self.people['field'], 'field', 'Equipo B')
        self.assertFalse(access.can_access(self.people['coordinator'], 'tasks.assign', **self.context))
        access.save_access(self.people['field'], 'field', 'Equipo A')
        access.remove_scope(self.people['field'], 1, 'Sonora', 'Hermosillo')
        self.assertFalse(access.can_access(self.people['coordinator'], 'tasks.assign', **self.context))

    def test_coordinator_cannot_manage_director_or_administrator_tasks(self):
        for role in ('director', 'administrator', 'coordinator'):
            other = staff.create_worker('Otra persona ' + role, 'Equipo A')
            access.save_access(other, role, 'Equipo A')
            access.add_scope(other, 1)
            self.assertFalse(access.can_access(self.people['coordinator'], 'tasks.assign',
                                               **{**self.context, 'assigned_worker_id': other}))

    def test_no_self_validation(self):
        for role in ('supervisor', 'coordinator'):
            self.assertFalse(access.can_access(self.people[role], 'reports.review',
                                               **{**self.context, 'assigned_worker_id': self.people[role]}))

    def test_inactive_and_unknown_permissions_deny(self):
        for role, wid in self.people.items():
            self.assertFalse(access.can_access(wid, 'unknown'))
            staff.set_worker_active(wid, False)
            self.assertFalse(access.can_access(wid, 'tasks.view', **self.context))
        self.assertFalse(access.can_access(999, 'tasks.view', **self.context))

    def test_role_change_revokes_immediately_and_is_audited(self):
        wid = self.people['administrator']
        self.assertTrue(access.can_access(wid, 'users.manage'))
        access.save_access(wid, 'field', 'Equipo A')
        self.assertFalse(access.can_access(wid, 'users.manage'))
        with closing(sqlite3.connect(self.path)) as conn, conn:
            self.assertGreater(conn.execute('SELECT COUNT(*) FROM field_access_audit WHERE worker_id = ?', (wid,)).fetchone()[0], 0)

    def test_invalid_roles_cycles_and_supervisors(self):
        with self.assertRaises(ValueError):
            access.save_access(self.people['field'], 'invented')
        with self.assertRaises(ValueError):
            access.save_access(self.people['field'], 'field', 'Equipo B', self.people['supervisor'])
        with self.assertRaises(ValueError):
            access.save_access(self.people['field'], 'field', 'Equipo A', self.people['field'])
        access.save_access(self.people['supervisor'], 'supervisor', 'Equipo A', self.people['coordinator'])
        with self.assertRaises(ValueError):
            access.save_access(self.people['coordinator'], 'coordinator', 'Equipo A', self.people['supervisor'])

    def test_no_scope_and_wildcards(self):
        worker = staff.create_worker('Nueva persona')
        context = {**self.context, 'assigned_worker_id': worker}
        self.assertFalse(access.can_access(worker, 'tasks.view', **context))
        access.add_scope(worker, 1, 'Sonora')
        self.assertTrue(access.can_access(worker, 'tasks.view', **context))
        self.assertFalse(access.can_access(worker, 'tasks.view', **{**context, 'state': 'Chihuahua'}))
        with self.assertRaises(ValueError):
            access.add_scope(worker, 1, '', 'Hermosillo')

    def test_telegram_profile_only_for_linked_user(self):
        code = staff.issue_code(self.people['field'])
        message = {'chat': {'id': 123, 'type': 'private'}, 'from': {'id': 123}, 'text': '/mi_perfil'}
        self.assertIn('Solicita tu código', staff.telegram_reply(message))
        staff.telegram_reply({**message, 'text': '/start ' + code})
        text = staff.telegram_reply(message)
        self.assertIn('Personal de campo', text)
        self.assertIn('Campaña A', text)
        self.assertNotIn('Campaña B', text)
        self.assertIsNone(staff.telegram_reply({**message, 'chat': {'id': 123, 'type': 'group'}}))

    def test_legacy_migration_preserves_link_and_is_repeatable(self):
        legacy = Path(self.temp.name) / 'legacy.db'
        with closing(sqlite3.connect(legacy)) as conn, conn:
            conn.execute('CREATE TABLE field_workers (id INTEGER PRIMARY KEY, name TEXT, team TEXT, active INTEGER, '
                         'telegram_user_id INTEGER UNIQUE, telegram_chat_id INTEGER UNIQUE, linked_at INTEGER, created_at INTEGER)')
            conn.execute("INSERT INTO field_workers VALUES (7, 'Persona existente', '', 1, 123, 123, 100, 90)")
        with patch.object(database, 'DB_PATH', legacy):
            staff.initialize_staff()
            staff.initialize_staff()
            person = staff.list_workers()[0]
            self.assertEqual((person['id'], person['telegram_user_id'], person['linked_at'], person['role_key']),
                             (7, 123, 100, 'field'))


if __name__ == '__main__':
    unittest.main()
