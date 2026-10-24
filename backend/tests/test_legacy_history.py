import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import uuid

from backend.legacy_history import (TABLES, PROTECTED, analyze, canonical, digest,
    protected_checksums, read_sources, write_migration)


def row(rid=1, **changes):
    return dict(id=rid, state='Sonora', municipality_code='001', municipality='Municipio de prueba',
        election_type='Ayuntamientos', election_year=2024, source='https://example.org/synthetic',
        imported_at='2026-01-01 00:00:00', payload=json.dumps(dict(lista_nominal=100,votes_total=80,
            votes_nulos=2,votes_no_reg=1,votes_test_a=50,votes_test_b=27,participacion_pct=80,
            nota='Conservar esta información adicional')), **changes)


def sources(municipal=None, sections=None):
    return {TABLES[0]:municipal or [],TABLES[1]:[],TABLES[2]:sections or []}


class LegacyValidationTests(unittest.TestCase):
    def test_additional_fields_and_original_payload_remain_exact(self):
        original = row()
        records,report = analyze(sources([original]))
        self.assertEqual(report['normalized'],1)
        self.assertEqual(records[0]['original'],original)
        self.assertEqual(records[0]['votes']['votes_test_a'],50)
        self.assertEqual(records[0]['payload']['nota'],'Conservar esta información adicional')

    def test_missing_keys_and_fractional_counts_remain_pending_not_discarded(self):
        a = row(); a['municipality_code'] = None; a['municipality'] = ''
        b = row(2); payload=json.loads(b['payload']); payload['votes_test_a']=50.5; b['payload']=json.dumps(payload)
        records, report = analyze(sources([a,b]))
        self.assertEqual(report['source_rows'],2)
        self.assertEqual(report['pending'],2)
        self.assertEqual(records[1]['original']['payload'], b['payload'])

    def test_mixed_attribution_is_retained_with_warning(self):
        original = row(); p=json.loads(original['payload']); p['votes_cc_test']=77; original['payload']=json.dumps(p)
        records,report = analyze(sources([original]))
        self.assertEqual(report['normalized'],1)
        self.assertIn('opciones_no_concilian_posible_atribucion_mixta_no_se_corrigen', records[0]['issues'])
        self.assertEqual(records[0]['votes']['votes_cc_test'],77)

    def test_duplicate_sections_are_not_aggregated_or_overwritten(self):
        a=row(); a.update(section_code='0001',district_code='01')
        b={**a,'id':2,'district_code':'02'}
        records,report=analyze(sources(sections=[a,b]))
        self.assertEqual(report['pending'],2)
        self.assertEqual(len(records),2)

    def test_missing_is_distinct_from_zero_and_alias_code_evidence(self):
        a=row(); p=json.loads(a['payload']); p['votes_test_a']=None; p['votes_test_b']=0; a['payload']=json.dumps(p)
        records,_=analyze(sources([a]))
        self.assertIsNone(records[0]['votes']['votes_test_a'])
        self.assertEqual(records[0]['votes']['votes_test_b'],0)

    def test_snapshot_failure_does_not_fall_back_locally(self):
        from backend.migrate_legacy_history import verified_snapshot
        with patch('services.settings.get_setting',return_value=''):
            with self.assertRaisesRegex(RuntimeError,'GO2WIN_FILES_ROOT'):
                verified_snapshot('{}',digest('{}'))


class LegacyCursor:
    def __init__(self,raw,schema): self.raw,self.schema=raw,schema
    def copy(self,sql): return self.raw.copy(sql.replace('electoral_history.',self.schema+'.'))


@unittest.skipUnless(os.environ.get('API_TEST_POSTGRES')=='1','Activar API_TEST_POSTGRES=1')
class LegacyPostgresTests(unittest.TestCase):
    def setUp(self):
        from backend.database import connect
        from test_history import HistoryConnection
        raw=connect()
        self.addCleanup(raw.close)
        self.addCleanup(raw.rollback)
        schema='legacy_test_'+uuid.uuid4().hex
        root=Path(__file__).resolve().parents[2]/'scripts'
        for name in ('agregar_base_historica_postgresql.sql','migrar_cargas_electorales_schema.sql'):
            sql=(root/name).read_text(encoding='utf-8').replace('BEGIN;','').replace('COMMIT;','').replace('electoral_history',schema)
            raw.execute(sql)
        for table in (*TABLES,*PROTECTED):
            raw.execute(f'CREATE TEMP TABLE {table} (LIKE public.{table} INCLUDING ALL) ON COMMIT DROP')
            # Insertar IDs explícitos no debe consumir secuencias del negocio.
            if table in TABLES:
                raw.execute(f'ALTER TABLE pg_temp.{table} ALTER COLUMN id DROP IDENTITY IF EXISTS')
        class Connection(HistoryConnection):
            def cursor(self): return LegacyCursor(self.raw.cursor(),self.schema)
        self.conn=Connection(raw,schema)
        for source in [row(), row(2)]:
            if source['id']==2:
                source['municipality_code']=None
                source['municipality']='Sin clave de prueba'
            cols=list(source)
            self.conn.execute('INSERT INTO public.territorial_election_results ('+','.join(cols)+') VALUES ('+','.join(['%s']*len(cols))+')',tuple(source.values()))

    def test_roundtrip_reconciliation_idempotency_and_originals_untouched(self):
        initial=read_sources(self.conn)
        protected=protected_checksums(self.conn)
        report=write_migration(self.conn,initial,2,'test-only-snapshot',protected)
        self.assertTrue(report['reconciled'])
        self.assertEqual(report['archived_rows'],2)
        self.assertEqual(report['normalized'],1)
        self.assertEqual(report['pending'],1)
        self.assertEqual(read_sources(self.conn),initial)
        self.assertEqual(protected_checksums(self.conn),protected)
        repeat=write_migration(self.conn,initial,2,'test-only-snapshot',protected)
        self.assertTrue(repeat['duplicate'])
        self.assertEqual(repeat['run_id'],report['run_id'])
        self.assertEqual(self.conn.execute('SELECT count(*) AS n FROM electoral_history.imports').fetchone()['n'],1)
        self.assertEqual(self.conn.execute('SELECT count(*) AS n FROM electoral_history.fact_votes').fetchone()['n'],0)
        election=self.conn.execute('SELECT * FROM electoral_history.elections').fetchone()
        self.assertIsNone(election['election_date'])
        self.assertEqual(election['legacy_election_year'],2024)
        self.assertEqual(election['process'],'unknown')
        batch=self.conn.execute('SELECT * FROM electoral_history.imports').fetchone()
        self.assertEqual(batch['source']['stage'],'legacy_snapshot')
        self.assertIsNone(batch['source']['published_on'])
        self.assertEqual(batch['vote_basis'],'legacy_reported')

    def test_reconciliation_error_rolls_back_every_target_row(self):
        initial=read_sources(self.conn)
        protected=protected_checksums(self.conn)
        with self.assertRaises(RuntimeError):
            with self.conn.raw.transaction():
                write_migration(self.conn,initial,2,'test-only',{})
        self.assertEqual(self.conn.execute('SELECT count(*) AS n FROM electoral_history.legacy_runs').fetchone()['n'],0)
        self.assertEqual(self.conn.execute('SELECT count(*) AS n FROM electoral_history.imports').fetchone()['n'],0)
        self.assertEqual(read_sources(self.conn),initial)

    def test_migrated_sources_and_originals_are_readable_through_api(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        from backend.admin import administrator, db
        report=write_migration(self.conn,read_sources(self.conn),2,'test-only',protected_checksums(self.conn))
        app.dependency_overrides[db]=lambda:self.conn
        app.dependency_overrides[administrator]=lambda:{'id':2}
        self.addCleanup(app.dependency_overrides.clear)
        client=TestClient(app)
        self.assertEqual(client.get('/api/v1/history/elections').status_code,200)
        self.assertIsNone(client.get('/api/v1/history/geographies').json()[0]['valid_on'])
        runs=client.get('/api/v1/history/legacy/runs').json()
        self.assertEqual(runs[0]['report']['archived_rows'],2)
        path=f'/api/v1/history/legacy/runs/{report["run_id"]}/records'
        page=client.get(path+'?limit=1').json()
        self.assertEqual(len(page['items']),1)
        self.assertTrue(page['next_after'])
        next_page=client.get(path+'?after='+page['next_after']).json()
        self.assertNotEqual(page['items'][0]['source_id'],next_page['items'][0]['source_id'])
        pending=client.get(path+'?status=pending').json()
        self.assertEqual(len(pending['items']),1)
        row=pending['items'][0]
        original=client.get(path+'/'+row['source_table']+'/'+str(row['source_id'])).json()
        self.assertIn('nota',json.loads(original['original_row']['payload']))
        self.assertEqual(client.get(path+'?after=malformed').status_code,422)
        batches=client.get('/api/v1/history/imports').json()
        self.assertEqual(batches[0]['vote_basis'],'legacy_reported')
        result=client.get(f'/api/v1/history/imports/{batches[0]["id"]}/results')
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['items'][0]['total_votes'],80)
