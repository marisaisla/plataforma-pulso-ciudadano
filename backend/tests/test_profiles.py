import os
import unittest
import test_admin


@unittest.skipUnless(os.environ.get('API_TEST_POSTGRES')=='1','Activar API_TEST_POSTGRES=1')
class ProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_admin.AdminTests.setUpClass()
        cls.hashed=test_admin.AdminTests.hashed

    def setUp(self):
        test_admin.AdminTests.setUp(self)
        raw=self.conn.raw
        for table in ('profile_positions','profile_keywords'):
            raw.execute(f'CREATE TEMP TABLE {table} (LIKE public.{table} INCLUDING ALL) ON COMMIT DROP')
        for table in ('profiles','profile_positions','profile_keywords'):
            raw.execute(f'ALTER TABLE pg_temp.{table} ALTER COLUMN id DROP IDENTITY IF EXISTS')
            raw.execute(f'CREATE TEMP SEQUENCE api_test_{table}_id START 1000')
            raw.execute(f"ALTER TABLE pg_temp.{table} ALTER COLUMN id SET DEFAULT nextval('pg_temp.api_test_{table}_id')")

    def create(self):
        return self.client.post('/api/v1/profiles',headers=self.headers,json={'name':' Candidato prueba ','actor_type':'Persona','notes':'Notas'})

    def test_create_profile_and_initial_keyword(self):
        response=self.create()
        self.assertEqual(response.status_code,201,response.text)
        self.assertEqual(response.json()['name'],'Candidato prueba')
        keyword=self.conn.execute('SELECT keyword FROM public.profile_keywords').fetchone()
        self.assertEqual(keyword['keyword'],'Candidato prueba')
        rows=self.client.get('/api/v1/profiles',headers=self.headers).json()
        self.assertEqual(rows[0]['id'],response.json()['id'])
        self.assertIn('notes',rows[0])

    def test_position_roundtrip_and_date_validation(self):
        pid=self.create().json()['id']
        body={'office':'Presidencia municipal','condition':'Candidato/a','starts_at':'2026-10-15','ends_at':None,'party_or_coalition':'Prueba'}
        response=self.client.post(f'/api/v1/profiles/{pid}/positions',headers=self.headers,json=body)
        self.assertEqual(response.status_code,201,response.text)
        rows=self.client.get('/api/v1/profile-positions',headers=self.headers).json()
        self.assertEqual(rows[0]['profile_id'],pid)
        self.assertIsNone(rows[0]['ends_at'])
        body['ends_at']='2026-01-01'
        self.assertEqual(self.client.post(f'/api/v1/profiles/{pid}/positions',headers=self.headers,json=body).status_code,422)

    def test_auth_and_invalid_profile(self):
        self.assertEqual(self.client.get('/api/v1/profiles').status_code,401)
        self.assertEqual(self.client.post('/api/v1/profiles',headers=self.headers,json={'name':'   ','actor_type':'Persona'}).status_code,422)
        token=self.client.post('/api/v1/auth/login',json={'username':'field_test','password':'PasswordPrueba123!'}).json()['access_token']
        self.assertEqual(self.client.get('/api/v1/profiles',headers={'Authorization':'Bearer '+token}).status_code,403)

    def test_active_filter_and_profile_missing(self):
        pid=self.create().json()['id']
        self.conn.execute('UPDATE public.profiles SET active=0 WHERE id=%s',(pid,))
        self.assertEqual(self.client.get('/api/v1/profiles?active_only=true',headers=self.headers).json(),[])
        body={'office':'Cargo','condition':'Otro','starts_at':'2026-10-15'}
        self.assertEqual(self.client.post(f'/api/v1/profiles/{pid}/positions',headers=self.headers,json=body).status_code,409)
        self.assertEqual(self.client.post('/api/v1/profiles/999/positions',headers=self.headers,json=body).status_code,404)

    def test_deactivate_is_idempotent_and_keeps_history(self):
        pid=self.create().json()['id']
        body={'office':'Cargo','condition':'Otro','starts_at':'2026-10-15'}
        self.assertEqual(self.client.post(f'/api/v1/profiles/{pid}/positions',headers=self.headers,json=body).status_code,201)
        for _ in range(2):
            r=self.client.put(f'/api/v1/profiles/{pid}/active',headers=self.headers,json={'active':False})
            self.assertEqual(r.status_code,200,r.text)
            self.assertEqual(r.json()['active'],0)
        self.assertEqual(self.client.get('/api/v1/profiles?active_only=true',headers=self.headers).json(),[])
        self.assertEqual(len(self.client.get('/api/v1/profile-positions',headers=self.headers).json()),1)
        self.assertTrue(self.conn.execute('SELECT 1 FROM public.profile_keywords WHERE profile_id=%s',(pid,)).fetchone())
        self.assertEqual(self.client.put(f'/api/v1/profiles/{pid}/active',json={'active':False}).status_code,401)
        self.assertEqual(self.client.put('/api/v1/profiles/999/active',headers=self.headers,json={'active':False}).status_code,404)
        self.assertEqual(self.client.put(f'/api/v1/profiles/{pid}/active',headers=self.headers,json={'active':'false'}).status_code,422)
