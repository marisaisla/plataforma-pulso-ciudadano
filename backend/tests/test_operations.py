import os
import base64
import unittest
import test_admin


@unittest.skipUnless(os.environ.get('API_TEST_POSTGRES')=='1','Activar API_TEST_POSTGRES=1')
class OperationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_admin.AdminTests.setUpClass()
        cls.hashed=test_admin.AdminTests.hashed

    def setUp(self):
        test_admin.AdminTests.setUp(self)
        raw=self.conn.raw
        tables=['territorial_strategies','territorial_action_plans','field_task_assignments','field_task_events',
                'field_reports','field_report_reviews','field_report_photos','supporters','field_needs','territories','profile_territories','profile_positions']
        for table in tables:
            raw.execute(f'CREATE TEMP TABLE {table} (LIKE public.{table} INCLUDING ALL) ON COMMIT DROP')
        for table in ('territorial_action_plans','field_task_events','field_reports'):
            raw.execute(f'ALTER TABLE pg_temp.{table} ALTER COLUMN id DROP IDENTITY IF EXISTS')
            raw.execute(f'CREATE TEMP SEQUENCE test_op_{table}_id START 100')
            raw.execute(f"ALTER TABLE pg_temp.{table} ALTER COLUMN id SET DEFAULT nextval('pg_temp.test_op_{table}_id')")
        self.conn.execute("INSERT INTO public.profiles (id,name,actor_type) VALUES (10,'Prueba','Persona')")
        self.conn.execute("INSERT INTO public.field_worker_scopes (worker_id,profile_id,state,municipality) VALUES (2,10,'Sonora','Hermosillo')")
        for key in ('tasks.view','tasks.assign','tasks.confirm','reports.view','reports.review','supporters.view','needs.view'):
            self.conn.execute('INSERT INTO public.field_role_permissions (role_key,permission_key,scope) VALUES (%s,%s,%s)',('administrator',key,'all'))
        for key in ('tasks.view','tasks.confirm','reports.view','supporters.view','needs.view'):
            self.conn.execute('INSERT INTO public.field_role_permissions (role_key,permission_key,scope) VALUES (%s,%s,%s)',('field',key,'own'))
        self.conn.execute("INSERT INTO public.territorial_strategies (id,profile_id,state,municipality,strategic_focus,objective,tactics) VALUES (10,10,'Sonora','Hermosillo','Prueba','Objetivo','Táctica')")
        token=self.client.post('/api/v1/auth/login',json={'username':'field_test','password':'PasswordPrueba123!'}).json()['access_token']
        self.field={'Authorization':'Bearer '+token}

    def activity(self):
        response=self.client.post('/api/v1/activities',headers=self.headers,json={'strategy_id':10,'activity_name':'Actividad de prueba','due_date':'2026-10-15','priority_level':'Alta'})
        self.assertEqual(response.status_code,201,response.text)
        return response.json()['id']

    def report(self,tid):
        row=self.conn.execute("INSERT INTO public.field_reports (task_id,worker_id,generation,body,source_chat_id,source_message_id) VALUES (%s,2,'generation','Avance',123,1) RETURNING id",(tid,)).fetchone()
        return row['id']

    def test_activity_assignment_reception_preserved_and_unassignment_history(self):
        tid=self.activity()
        self.assertEqual(self.client.get('/api/v1/activities?strategy_id=10',headers=self.headers).json()[0]['id'],tid)
        candidates=self.client.get(f'/api/v1/activities/{tid}/candidates',headers=self.headers).json()
        self.assertIn(2,[w['id'] for w in candidates])
        path=f'/api/v1/activities/{tid}/assignment'
        self.assertEqual(self.client.put(path,headers=self.headers,json={'worker_id':2}).status_code,204)
        generation=self.client.get(path,headers=self.headers).json()['generation']
        self.conn.execute("UPDATE public.field_task_assignments SET received_at='2026-10-15 12:00:00' WHERE task_id=%s",(tid,))
        self.client.put(path,headers=self.headers,json={'worker_id':2})
        row=self.client.get(path,headers=self.headers).json()
        self.assertEqual(row['generation'],generation)
        self.assertIsNotNone(row['received_at'])
        self.assertEqual(self.client.put(path,headers=self.field,json={'worker_id':2}).status_code,403)
        self.assertEqual(self.client.put(path,headers=self.headers,json={'worker_id':None}).status_code,204)
        self.assertEqual(self.conn.execute('SELECT count(*) AS n FROM public.field_task_events').fetchone()['n'],2)
        response=self.client.patch(f'/api/v1/activities/{tid}',headers=self.headers,json={'status':'Concluida','evidence_note':'Prueba'})
        self.assertIsNotNone(response.json()['completed_at'])
        self.assertEqual(self.client.put(path,headers=self.headers,json={'worker_id':2}).status_code,409)

    def test_report_photo_review_and_scope_revocation(self):
        tid=self.activity()
        rid=self.report(tid)
        self.conn.execute('INSERT INTO public.field_report_photos (report_id,file_id,file_unique_id,content_base64) VALUES (%s,%s,%s,%s)',(rid,'file','unique',base64.b64encode(b'photo-test').decode()))
        response=self.client.get(f'/api/v1/reports/{rid}/photo',headers=self.field)
        self.assertEqual(response.content,b'photo-test')
        self.assertEqual(response.headers['cache-control'],'no-store')
        path=f'/api/v1/reports/{rid}/review'
        self.assertEqual(self.client.put(path,headers=self.field,json={'decision':'accepted'}).status_code,403)
        self.assertEqual(self.client.put(path,headers=self.headers,json={'decision':'correction'}).status_code,422)
        for _ in range(2): self.assertEqual(self.client.put(path,headers=self.headers,json={'decision':'accepted','note':'Verificado'}).status_code,204)
        self.assertEqual(self.client.put(path,headers=self.headers,json={'decision':'correction','note':'Cambiar'}).status_code,409)
        self.conn.execute('DELETE FROM public.field_worker_scopes WHERE worker_id=2')
        self.assertEqual(self.client.get(f'/api/v1/reports/{rid}/photo',headers=self.field).status_code,403)
        self.assertEqual(self.client.get(f'/api/v1/activities/{tid}/reports',headers=self.field).json(),[])

    def test_catalogs_filter_by_owner_and_scope(self):
        self.conn.execute("INSERT INTO public.supporters (id,profile_id,worker_id,name,phone,voter_key,state,municipality,electoral_section,registration_consent,messaging_consent,source_chat_id,source_message_id) VALUES (1,10,2,'Persona ficticia','+525512345678','ABCDEF123456789012','Sonora','Hermosillo','123',1,0,123,1)")
        self.conn.execute("INSERT INTO public.field_needs (id,profile_id,worker_id,state,municipality,electoral_section,description,origin,source_chat_id,source_message_id) VALUES (1,10,2,'Sonora','Hermosillo','123','Necesidad de prueba','comentada',123,2)")
        for path in ('/api/v1/needs','/api/v1/supporters'):
            self.assertEqual(len(self.client.get(path,headers=self.field).json()),1)
        self.conn.execute('DELETE FROM public.field_worker_scopes WHERE worker_id=2')
        for path in ('/api/v1/needs','/api/v1/supporters'):
            self.assertEqual(self.client.get(path,headers=self.field).json(),[])
            self.assertEqual(len(self.client.get(path,headers=self.headers).json()),1)

    def test_scope_and_closed_task_block_assignment(self):
        tid=self.activity()
        self.conn.execute('DELETE FROM public.field_worker_scopes WHERE worker_id=2')
        self.assertEqual(self.client.put(f'/api/v1/activities/{tid}/assignment',headers=self.headers,json={'worker_id':2}).status_code,409)
        self.assertEqual(self.client.get('/api/v1/activities?strategy_id=10').status_code,401)
        self.assertEqual(self.client.get('/api/v1/activities?strategy_id=10',headers=self.field).status_code,403)

    def test_portal_omits_hashes_and_filters_reports(self):
        tid=self.activity()
        rid=self.report(tid)
        self.client.put(f'/api/v1/activities/{tid}/assignment',headers=self.headers,json={'worker_id':2})
        response=self.client.get('/api/v1/field/portal',headers=self.field)
        self.assertEqual(response.status_code,200,response.text)
        data=response.json()
        self.assertEqual(data['tasks'][0]['id'],tid)
        self.assertEqual(data['reports'][0]['id'],rid)
        self.assertFalse(data['reports'][0]['can_review'])
        self.assertNotIn('token_hash',data['user'])

    def test_telegram_report_history_includes_review(self):
        from backend.reports import history
        tid=self.activity()
        rid=self.report(tid)
        self.conn.execute('UPDATE public.field_workers SET telegram_user_id=123 WHERE id=2')
        self.client.put(f'/api/v1/reports/{rid}/review',headers=self.headers,json={'decision':'correction','note':'Agrega información'})
        result=history(self.conn,123)
        self.assertIn('Corrección solicitada',result['reply'])
        self.assertIn('Agrega información',result['reply'])
        self.conn.execute('DELETE FROM public.field_worker_scopes WHERE worker_id=2')
        self.assertIn('No hay reportes',history(self.conn,123)['reply'])
