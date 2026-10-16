import os
import unittest
from fastapi import HTTPException
from backend.database import connect
from backend.tasks import list_tasks, get_task, command_reply, command_buttons, confirm_receipt


class TempConnection:
    def __init__(self, conn):
        self.conn=conn

    def execute(self, sql, params=()):
        return self.conn.execute(sql.replace('public.', 'pg_temp.'), params)


@unittest.skipUnless(os.environ.get('API_TEST_POSTGRES')=='1', 'Activar API_TEST_POSTGRES=1')
class TaskTests(unittest.TestCase):
    def setUp(self):
        raw=connect()
        self.addCleanup(raw.close)
        self.addCleanup(raw.rollback)
        for sql in [
            'CREATE TEMP TABLE field_workers (id bigint, active bigint, role_key text, telegram_user_id bigint)',
            'CREATE TEMP TABLE field_role_permissions (role_key text, permission_key text, scope text)',
            'CREATE TEMP TABLE field_worker_scopes (worker_id bigint, profile_id bigint, state text, municipality text)',
            'CREATE TEMP TABLE field_task_assignments (task_id bigint, worker_id bigint, received_at text, generation text)',
            'CREATE TEMP TABLE field_task_events (task_id bigint, worker_id bigint, generation text, event text, actor text)',
            'CREATE TEMP TABLE territorial_action_plans (id bigint, profile_id bigint, activity_name text, activity_description text, state text, municipality text, due_date text, status text)',
        ]:
            raw.execute(sql)
        self.conn=TempConnection(raw)
        self.conn.execute("INSERT INTO public.field_workers VALUES (1,1,'field',123),(2,1,'administrator',456)")
        self.conn.execute("INSERT INTO public.field_role_permissions VALUES ('field','tasks.view','own'),('administrator','tasks.view','all')")
        self.conn.execute("INSERT INTO public.field_role_permissions VALUES ('field','tasks.confirm','own')")
        self.conn.execute("INSERT INTO public.field_worker_scopes VALUES (1,10,'Sonora','Hermosillo')")
        for tid, profile, municipality, status, owner in [(1,10,'Hermosillo','Pendiente',1),(2,10,'Hermosillo','En curso',1),(3,10,'Otro','Pendiente',1),(4,11,'Hermosillo','Pendiente',1),(5,10,'Hermosillo','Concluida',1),(6,10,'Hermosillo','Pendiente',2)]:
            self.conn.execute('INSERT INTO public.territorial_action_plans VALUES (%s,%s,%s,%s,%s,%s,NULL,%s)',
                              (tid,profile,'Actividad','x'*4000,'Sonora',municipality,status))
            self.conn.execute("INSERT INTO public.field_task_assignments VALUES (%s,%s,NULL,'abc123')",(tid,owner))

    def test_confirmation_button_and_duplicate_are_idempotent(self):
        buttons=command_buttons(self.conn,123,['/mis_tareas'])
        self.assertEqual(buttons['inline_keyboard'][0][0]['callback_data'],'taskconfirm:1:abc123')
        confirm_receipt(self.conn,123,1,'abc123')
        self.assertIn('ya estaba',confirm_receipt(self.conn,123,1,'abc123'))
        self.assertEqual(self.conn.execute('SELECT count(*) AS n FROM public.field_task_events').fetchone()['n'],1)
        self.assertIsNone(command_buttons(self.conn,123,['/tarea','1']))
        self.assertEqual(get_task(self.conn,123,1)['status'],'Pendiente')

    def test_stale_button_or_removed_permission_cannot_confirm(self):
        with self.assertRaises(HTTPException): confirm_receipt(self.conn,123,1,'old')
        self.conn.execute("DELETE FROM public.field_role_permissions WHERE permission_key='tasks.confirm'")
        with self.assertRaises(HTTPException): confirm_receipt(self.conn,123,1,'abc123')
        self.assertIsNone(command_buttons(self.conn,123,['/mis_tareas']))

    def test_confirmation_rejects_foreign_closed_and_out_of_scope(self):
        for task_id in (3,4,5,6):
            with self.assertRaises(HTTPException): confirm_receipt(self.conn,123,task_id,'abc123')

    def test_list_filters_scope_assignment_status_and_paginates(self):
        page=list_tasks(self.conn,123,limit=1)
        self.assertEqual([t['id'] for t in page['items']],[1])
        self.assertEqual(page['next_after'],1)
        page=list_tasks(self.conn,123,after=1,limit=1)
        self.assertEqual([t['id'] for t in page['items']],[2])
        self.assertIsNone(page['next_after'])

    def test_detail_hides_other_campaign_territory_closed_and_foreign_tasks(self):
        for tid in (3,4,5,6,999):
            with self.assertRaises(HTTPException) as error:
                get_task(self.conn,123,tid)
            self.assertEqual(error.exception.status_code,404)

    def test_inactive_and_missing_permission_forbidden(self):
        self.conn.execute('UPDATE public.field_workers SET active=0 WHERE id=1')
        with self.assertRaises(HTTPException): list_tasks(self.conn,123)
        self.conn.execute('UPDATE public.field_workers SET active=1 WHERE id=1')
        self.conn.execute("DELETE FROM public.field_role_permissions WHERE role_key='field'")
        with self.assertRaises(HTTPException): list_tasks(self.conn,123)
        with self.assertRaises(HTTPException): list_tasks(self.conn,999)

    def test_administrator_still_gets_only_own_tasks(self):
        self.assertEqual([t['id'] for t in list_tasks(self.conn,456)['items']],[6])

    def test_removed_scope_hides_previously_visible_task(self):
        self.conn.execute('DELETE FROM public.field_worker_scopes')
        self.assertEqual(list_tasks(self.conn,123)['items'],[])

    def test_bot_detail_pages_and_invalid_input(self):
        reply=command_reply(self.conn,123,['/tarea','1'])
        self.assertIn('/tarea 1 2',reply)
        self.assertLess(len(reply),4096)
        self.assertIn('Página 2/',command_reply(self.conn,123,['/tarea','1','2']))
        self.assertIn('Uso:',command_reply(self.conn,123,['/tarea','-1']))
