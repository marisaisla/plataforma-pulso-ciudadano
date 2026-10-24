import os
import unittest
from unittest.mock import patch

from backend.dashboard_research import describe_survey,survey_fingerprint


def survey(**changes):
    return dict(id=1,profile_id=1,name='Interna sintética',pollster='Fuente ficticia',territory='Territorio A',
                fieldwork_date='2026-06-01',sample_size=400,methodology='Fixture, no encuesta real',
                profile_result_pct=42.0,source_url='https://example.org/test',notes='Indecisos 9%',**changes)


def review(row,kind='internal_preference',**extra):
    return dict(reviewed_on='2026-10-22',items={survey_fingerprint(row):dict(
        kind=kind,reference_only=False,note='Clasificación sintética de prueba',**extra)})


class SurveyAdapterTests(unittest.TestCase):
    def test_reported_preference_and_reviewed_indecision_not_scores(self):
        row=survey()
        result=describe_survey(row,review(row,indecision_pct=9))
        self.assertEqual(result['indicators']['IC05']['value'],42)
        self.assertEqual(result['indicators']['IC07']['value'],9)
        self.assertEqual(result['indicators']['IC05']['status'],'reported')
        self.assertNotIn('IC01',result['indicators'])

    def test_changed_record_and_unknown_measurements_do_not_feed_cards(self):
        row=survey();metadata=review(row,indecision_pct=9)
        row['notes']='Cambió la pregunta'
        result=describe_survey(row,metadata)
        self.assertEqual(result['classification_status'],'unreviewed_or_changed')
        self.assertIsNone(result['indicators']['IC05']['value'])
        self.assertIsNone(result['indicators']['IC07']['value'])

    def test_approval_exclusions_and_missing_methodology_do_not_become_preference(self):
        row=survey()
        self.assertIsNone(describe_survey(row,review(row,'approval'))['indicators']['IC05']['value'])
        metadata=review(row);metadata['items'][survey_fingerprint(row)]['reference_only']=True
        self.assertIsNone(describe_survey(row,metadata)['indicators']['IC05']['value'])
        row['sample_size']=None
        result=describe_survey(row,review(row,indecision_pct=9))
        self.assertIn('sample_size',result['metadata_missing'])
        self.assertIsNone(result['indicators']['IC05']['value'])
        self.assertIsNone(result['indicators']['IC07']['value'])

    def test_zero_is_preserved_out_of_range_and_nonfinite_are_not_metrics(self):
        row=survey();row['profile_result_pct']=0.0
        self.assertEqual(describe_survey(row,review(row))['indicators']['IC05']['value'],0)
        row['profile_result_pct']=101.0
        self.assertIsNone(describe_survey(row,review(row))['indicators']['IC05']['value'])
        row['profile_result_pct']=float('nan')
        self.assertIsNone(describe_survey(row,dict(items={}))['profile_result_pct'])


@unittest.skipUnless(os.environ.get('API_TEST_POSTGRES')=='1','Activar API_TEST_POSTGRES=1')
class ResearchPostgresTests(unittest.TestCase):
    def setUp(self):
        from backend.database import connect
        from backend.main import app
        from backend.admin import db,administrator
        from fastapi.testclient import TestClient
        self.ctx=connect();self.conn=self.ctx.__enter__()
        definitions={
            'profiles':'id bigint,name text,active bigint',
            'viability_surveys':'''id bigint,profile_id bigint,name text,pollster text,territory text,fieldwork_date text,
                sample_size bigint,methodology text,profile_result_pct double precision,source_url text,notes text''',
            'profile_positions':'''id bigint,profile_id bigint,office text,condition text,starts_at text,ends_at text,
                party_or_coalition text,is_current bigint''',
            'reference_documents':'id bigint,profile_id bigint,title text,document_type text,source_url text,imported_at text',
            'viability_electoral_evidence':'''id bigint,profile_id bigint,variable_code text,status text,evidence_note text,
                source_label text,source_url text,reference_date text''',
            'viability_coalition_scenarios':'id bigint,profile_id bigint,scenario_name text,parties text,scope text,status text,notes text,source_url text',
        }
        for table,columns in definitions.items():self.conn.execute(f'CREATE TEMP TABLE {table} ({columns}) ON COMMIT DROP')
        self.conn.execute("INSERT INTO profiles VALUES (1,'Uno',1),(2,'Dos',0),(3,'Vacío',1)")
        row=survey()
        self.conn.execute('INSERT INTO viability_surveys VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',tuple(row.values()))
        self.conn.execute("INSERT INTO profile_positions VALUES (1,1,'Cargo declarado','En funciones','2024-01-01',NULL,'Partido',1),(2,2,'Otro cargo','Otro',NULL,NULL,NULL,0)")
        self.conn.execute("INSERT INTO reference_documents VALUES (1,1,'Documento','Referencia',NULL,'2026-10-22')")
        self.conn.execute("INSERT INTO viability_electoral_evidence VALUES (1,1,'reputational_risk','Documentada','Nota de riesgo',NULL,NULL,NULL),(2,2,'name_recognition','Documentada','Otra persona',NULL,NULL,NULL)")
        self.conn.execute("INSERT INTO viability_coalition_scenarios VALUES (1,1,'Hipótesis','A-B','Local','Hipótesis',NULL,NULL)")
        self.patch=patch('backend.dashboard_research.survey_review',return_value=review(row,indecision_pct=9));self.patch.start()
        self.app=app;self.admin=administrator
        app.dependency_overrides[db]=lambda:self.conn
        app.dependency_overrides[administrator]=lambda:{'id':9}
        self.client=TestClient(app)

    def tearDown(self):
        self.patch.stop();self.app.dependency_overrides.clear();self.client.close()
        self.conn.rollback();self.ctx.__exit__(None,None,None)

    def test_profile_scoping_provenance_and_dossier_is_not_certified(self):
        response=self.client.get('/api/v1/indicators/dashboard/research?profile_id=1')
        self.assertEqual(response.status_code,200,response.text)
        data=response.json()
        self.assertEqual(data['totals'],dict(surveys=1,positions=1,documents=1,evidence=1,coalitions=1))
        self.assertEqual(data['surveys'][0]['indicators']['IC05']['value'],42)
        self.assertEqual(data['surveys'][0]['indicators']['IC07']['value'],9)
        self.assertEqual(data['evidence'][0]['related_cards'],['IC10','IC12'])
        self.assertEqual(data['positions'][0]['office'],'Cargo declarado')
        self.assertNotIn('file_path',data['documents'][0])
        self.assertNotIn('scores',data)
        self.assertEqual(self.conn.execute('SELECT count(*) n FROM profiles').fetchone()['n'],3)

    def test_missing_empty_and_inactive_profiles(self):
        self.assertEqual(self.client.get('/api/v1/indicators/dashboard/research?profile_id=999').status_code,404)
        data=self.client.get('/api/v1/indicators/dashboard/research?profile_id=3').json()
        self.assertEqual(data['surveys'],[])
        self.assertEqual(data['positions'],[])
        inactive=self.client.get('/api/v1/indicators/dashboard/research?profile_id=2').json()
        self.assertEqual(inactive['profile']['active'],0)
        self.assertEqual(inactive['totals']['positions'],1)

    def test_authentication_and_input_validation(self):
        self.assertEqual(self.client.get('/api/v1/indicators/dashboard/research?profile_id=0').status_code,422)
        self.assertEqual(self.client.get('/api/v1/indicators/dashboard/research').status_code,422)
        self.assertEqual(self.client.get('/api/v1/indicators/dashboard/research?profile_id=999999999999999999999999').status_code,422)
        del self.app.dependency_overrides[self.admin]
        self.assertEqual(self.client.get('/api/v1/indicators/dashboard/research?profile_id=1').status_code,401)

    def test_large_dossier_is_explicitly_truncated_without_hiding_total(self):
        self.conn.execute("INSERT INTO reference_documents SELECT n,3,'Documento ficticio','Referencia',NULL,NULL FROM generate_series(1,501) n")
        response=self.client.get('/api/v1/indicators/dashboard/research?profile_id=3')
        self.assertEqual(response.status_code,200,response.text)
        data=response.json()
        self.assertTrue(data['truncated'])
        self.assertEqual(data['totals']['documents'],501)
        self.assertEqual(len(data['documents']),500)
