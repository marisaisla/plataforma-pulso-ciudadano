import os
import time
import unittest
from fastapi.testclient import TestClient
from backend.main import app
from backend.admin import db,password_hash,digest
from backend.database import connect


class TempConnection:
    def __init__(self,raw): self.raw=raw
    def execute(self,sql,params=()): return self.raw.execute(sql.replace('public.','pg_temp.'),params)


@unittest.skipUnless(os.environ.get('API_TEST_POSTGRES')=='1','Activar API_TEST_POSTGRES=1')
class AdminTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hashed=password_hash('PasswordPrueba123!')

    def setUp(self):
        raw=connect()
        self.addCleanup(raw.close)
        self.addCleanup(raw.rollback)
        tables=['field_workers','field_roles','field_role_permissions','field_worker_scopes','field_access_audit','web_accounts','web_sessions','web_login_attempts','profiles','field_activation_codes','field_report_sessions','supporter_sessions','field_need_sessions']
        for table in tables:
            raw.execute(f'CREATE TEMP TABLE {table} (LIKE public.{table} INCLUDING ALL) ON COMMIT DROP')
        for table in ('field_workers','field_access_audit'):
            raw.execute(f'ALTER TABLE pg_temp.{table} ALTER COLUMN id DROP IDENTITY IF EXISTS')
            raw.execute(f'CREATE TEMP SEQUENCE api_test_{table}_id START 1000')
            raw.execute(f"ALTER TABLE pg_temp.{table} ALTER COLUMN id SET DEFAULT nextval('pg_temp.api_test_{table}_id')")
        self.conn=TempConnection(raw)
        for wid,role in [(1,'administrator'),(2,'field')]:
            self.conn.execute('INSERT INTO public.field_workers (id,name,team,active,created_at,role_key) VALUES (%s,%s,%s,1,%s,%s)',(wid,'API TEST','',int(time.time()),role))
            self.conn.execute('INSERT INTO public.web_accounts (worker_id,username,password_hash,must_change) VALUES (%s,%s,%s,0)',(wid,'admin_test' if wid==1 else 'field_test',self.hashed))
        self.conn.execute("INSERT INTO public.field_roles VALUES ('administrator','Administrador'),('field','Campo'),('supervisor','Supervisor')")
        self.conn.execute('INSERT INTO public.web_sessions (token_hash,worker_id,expires_at) VALUES (%s,1,%s)',(digest('admin-session'),int(time.time())+3600))
        app.dependency_overrides[db]=lambda:self.conn
        self.addCleanup(app.dependency_overrides.clear)
        self.client=TestClient(app)
        self.headers={'Authorization':'Bearer admin-session'}

    def test_auth_required_and_field_forbidden(self):
        self.assertEqual(self.client.get('/api/v1/users').status_code,401)
        response=self.client.post('/api/v1/auth/login',json={'username':'field_test','password':'PasswordPrueba123!'})
        token=response.json()['access_token']
        self.assertEqual(self.client.get('/api/v1/users',headers={'Authorization':'Bearer '+token}).status_code,403)

    def test_login_me_logout_and_no_hash_exposure(self):
        response=self.client.post('/api/v1/auth/login',json={'username':'admin_test','password':'PasswordPrueba123!'})
        self.assertEqual(response.status_code,200)
        headers={'Authorization':'Bearer '+response.json()['access_token']}
        response=self.client.get('/api/v1/auth/me',headers=headers)
        self.assertEqual(response.status_code,200)
        self.assertNotIn('password_hash',response.json())
        self.assertNotIn('token_hash',response.json())
        self.assertEqual(self.client.post('/api/v1/auth/logout',headers=headers).status_code,204)
        self.assertEqual(self.client.get('/api/v1/auth/me',headers=headers).status_code,401)

    def test_create_reset_password_and_force_change(self):
        r=self.client.post('/api/v1/users',headers=self.headers,json={'name':'Persona de prueba'})
        self.assertEqual(r.status_code,201,r.text)
        wid=r.json()['id']
        r=self.client.put(f'/api/v1/users/{wid}/account',headers=self.headers,json={'username':'new_test','temporary_password':'TemporalPrueba123!'})
        self.assertEqual(r.status_code,204,r.text)
        token=self.client.post('/api/v1/auth/login',json={'username':'new_test','password':'TemporalPrueba123!'}).json()['access_token']
        headers={'Authorization':'Bearer '+token}
        self.assertEqual(self.client.get('/api/v1/users',headers=headers).status_code,403)
        r=self.client.post('/api/v1/auth/password',headers=headers,json={'old_password':'TemporalPrueba123!','new_password':'NuevaPrueba123!'})
        self.assertEqual(r.status_code,204,r.text)
        self.assertEqual(self.client.get('/api/v1/auth/me',headers=headers).status_code,401)

    def test_last_admin_cannot_be_disabled_or_demoted(self):
        self.assertEqual(self.client.put('/api/v1/users/1/active',headers=self.headers,json={'active':False}).status_code,409)
        self.assertEqual(self.client.put('/api/v1/users/1/access',headers=self.headers,json={'role_key':'field'}).status_code,409)

    def test_failed_login_is_counted_and_locks(self):
        for _ in range(5):
            self.assertEqual(self.client.post('/api/v1/auth/login',json={'username':'admin_test','password':'incorrecta'}).status_code,401)
        self.assertEqual(self.client.post('/api/v1/auth/login',json={'username':'admin_test','password':'PasswordPrueba123!'}).status_code,429)

    def test_disable_revokes_sessions_and_keeps_telegram_link(self):
        self.conn.execute('UPDATE public.field_workers SET telegram_user_id=123,telegram_chat_id=123 WHERE id=2')
        response=self.client.post('/api/v1/auth/login',json={'username':'field_test','password':'PasswordPrueba123!'})
        token=response.json()['access_token']
        self.assertEqual(self.client.put('/api/v1/users/2/active',headers=self.headers,json={'active':False}).status_code,204)
        self.assertEqual(self.client.get('/api/v1/auth/me',headers={'Authorization':'Bearer '+token}).status_code,401)
        self.assertEqual(self.conn.execute('SELECT telegram_user_id FROM public.field_workers WHERE id=2').fetchone()['telegram_user_id'],123)

    def test_access_scope_and_audit(self):
        response=self.client.put('/api/v1/users/2/access',headers=self.headers,json={'role_key':'supervisor','team':'Equipo API'})
        self.assertEqual(response.status_code,204,response.text)
        self.conn.execute("INSERT INTO public.profiles (id,name,actor_type) VALUES (10,'Campaña prueba','Otro')")
        scope={'profile_id':10,'state':'Sonora','municipality':'Hermosillo'}
        self.assertEqual(self.client.post('/api/v1/users/2/scopes',headers=self.headers,json=scope).status_code,204)
        self.assertEqual(len(self.client.get('/api/v1/users/2/scopes',headers=self.headers).json()),1)
        self.assertEqual(self.client.request('DELETE','/api/v1/users/2/scopes',headers=self.headers,json=scope).status_code,204)
        self.assertTrue(self.conn.execute('SELECT 1 FROM public.field_access_audit WHERE worker_id=2').fetchone())

    def test_supervision_cycle_is_rejected(self):
        self.conn.execute("UPDATE public.field_workers SET role_key='supervisor',team='API' WHERE id IN (1,2)")
        # Dependencia administrativa valida el rol actual, por eso usar un tercero supervisor.
        self.conn.execute("UPDATE public.field_workers SET role_key='administrator' WHERE id=1")
        self.conn.execute("INSERT INTO public.field_workers (id,name,team,active,created_at,role_key,supervisor_id) VALUES (3,'Supervisor','API',1,1,'supervisor',2)")
        response=self.client.put('/api/v1/users/2/access',headers=self.headers,json={'role_key':'supervisor','team':'API','supervisor_id':3})
        self.assertEqual(response.status_code,409)

    def test_validation_never_echoes_password(self):
        response=self.client.put('/api/v1/users/2/account',headers=self.headers,json={'username':'field_test','temporary_password':'shortsecret'})
        self.assertEqual(response.status_code,422)
        self.assertNotIn('shortsecret',response.text)
