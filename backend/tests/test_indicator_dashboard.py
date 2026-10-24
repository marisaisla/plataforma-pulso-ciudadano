import os
import unittest
from collections import Counter

from backend.indicator_dashboard import cards, CODE_BY_SERIES


class DashboardCatalogTests(unittest.TestCase):
    def test_every_indicator_has_explicit_readiness_and_missing_inputs(self):
        result=cards()
        self.assertEqual(len({c['code'] for c in result['items']}),45)
        self.assertEqual(Counter(c['availability'] for c in result['items']),
                         {'Exploratorio':4,'Parcial':17,'Bloqueado':12,'Pendiente':12})
        self.assertTrue(all(c['missing'] and c['evidence'] for c in result['items']))
        self.assertEqual(CODE_BY_SERIES['ITER_GRAPROES'],'IT11')
        self.assertEqual(CODE_BY_SERIES['ITER_VPH_INTER'],'IT13')


@unittest.skipUnless(os.environ.get('API_TEST_POSTGRES')=='1','Activar API_TEST_POSTGRES=1')
class DashboardPostgresTests(unittest.TestCase):
    def setUp(self):
        from backend.database import connect
        from backend.main import app
        from backend.admin import db,administrator
        from fastapi.testclient import TestClient
        self.context=connect()
        self.conn=self.context.__enter__()
        # Temporary table shadows public, without touching production rows or sequences.
        self.conn.execute('''CREATE TEMP TABLE territorial_indicators (
            id bigint,state text,municipality_code text,municipality text,indicator_id text,
            indicator_name text,unit text,value double precision,period text,source text,retrieved_at text
        ) ON COMMIT DROP''')
        rows=[(1,'A','001','Uno','ITER_GRAPROES','Escolaridad','años',8.5,'2020','Fuente A','2026-10-22'),
              (2,'A','002','Dos','ITER_GRAPROES','Escolaridad','años',None,'2020','Fuente A','2026-10-22'),
              (3,'A','003','Tres','ITER_GRAPROES','Escolaridad','años',float('nan'),'2020','Fuente A','2026-10-22'),
              (4,'B','001','Otro estado','ITER_GRAPROES','Escolaridad','años',9,'2020','Fuente A','2026-10-22'),
              (5,'A','001','Uno','ITER_GRAPROES','Escolaridad','años',10,'2025','Fuente B','2026-10-22'),
              (6,'A','001','Uno','ITER_VPH_INTER','Internet','viviendas',0,'2020','Fuente A','2026-10-22')]
        for row in rows:
            self.conn.execute('INSERT INTO territorial_indicators VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',row)
        self.app=app
        self.db=db
        self.admin=administrator
        app.dependency_overrides[db]=lambda:self.conn
        app.dependency_overrides[administrator]=lambda:{'id':2}
        self.client=TestClient(app)
        self.params=dict(state='A',period='2020',source='Fuente A',family='IT11',indicator_id='ITER_GRAPROES')

    def tearDown(self):
        self.app.dependency_overrides.clear()
        self.client.close()
        self.conn.rollback()
        self.context.__exit__(None,None,None)

    def test_filters_pagination_null_and_nonfinite_remain_distinct_from_zero(self):
        response=self.client.get('/api/v1/indicators/dashboard/inegi',params={**self.params,'limit':2})
        self.assertEqual(response.status_code,200,response.text)
        data=response.json()
        self.assertEqual(data['total'],3)
        self.assertEqual(data['next_after'],2)
        self.assertEqual(data['items'][0]['value'],8.5)
        self.assertIsNone(data['items'][1]['value'])
        page=self.client.get('/api/v1/indicators/dashboard/inegi',params={**self.params,'after':2}).json()
        self.assertEqual([r['id'] for r in page['items']],[3])
        self.assertIsNone(page['items'][0]['value'])
        self.assertEqual(page['items'][0]['value_status'],'missing_or_nonfinite')
        zero=self.client.get('/api/v1/indicators/dashboard/inegi',params={**self.params,'family':'IT13','indicator_id':'ITER_VPH_INTER'}).json()
        self.assertEqual(zero['items'][0]['value'],0)
        self.assertEqual(self.conn.execute('SELECT count(*) n FROM territorial_indicators').fetchone()['n'],6)

    def test_empty_mismatched_source_family_and_municipality(self):
        for extra in ({'source':'Otra'},{'municipality_code':'999'},{'family':'IT10'}):
            data=self.client.get('/api/v1/indicators/dashboard/inegi',params={**self.params,**extra}).json()
            self.assertEqual(data['total'],0)
            self.assertEqual(data['items'],[])

    def test_options_and_required_filters_and_authentication(self):
        response=self.client.get('/api/v1/indicators/dashboard/inegi/options?state=B')
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['states'],['A','B'])
        self.assertEqual(len(response.json()['municipalities']),1)
        self.assertEqual(len(self.client.get('/api/v1/indicators/dashboard/cards').json()['items']),45)
        for extra in ({'limit':501},{'family':'IC01'},{'after':-1}):
            self.assertEqual(self.client.get('/api/v1/indicators/dashboard/inegi',params={**self.params,**extra}).status_code,422)
        self.assertEqual(self.client.get('/api/v1/indicators/dashboard/inegi').status_code,422)
        del self.app.dependency_overrides[self.admin]
        for path in ('cards','inegi/options','inegi'):
            self.assertEqual(self.client.get('/api/v1/indicators/dashboard/'+path).status_code,401)
