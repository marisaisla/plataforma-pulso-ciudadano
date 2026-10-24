"""Reglas de importación y pruebas HTTP/SQL aisladas de los datos del negocio."""
import os
from pathlib import Path
import unittest
import uuid

from pydantic import ValidationError
from backend.history_models import (GeographyImport, ResultImport, ElectionCreate,
                                    parse_geography, parse_results, GEO_COLUMNS, RESULT_COLUMNS)

GEO = ','.join(GEO_COLUMNS)+'\n'+'''entity,26,Entidad de prueba,26,,,
municipality,26001,Municipio de prueba,26,,,
federal_district,2601,Distrito federal de prueba,26,,,
local_district,2602,Distrito local de prueba,26,,,
section,260001,Sección de prueba,26,26001,2601,2602
'''
CSV = ','.join(RESULT_COLUMNS)+'\n'+'''260001,100,80,2,1,OPTION_A,Opción A de prueba,50
260001,100,80,2,1,OPTION_B,Opción B de prueba,27
'''
SOURCE = dict(authority='FUENTE SINTÉTICA DE PRUEBAS', url='https://example.org/test-only',
              title='Datos ficticios; no son resultados oficiales', published_on='2024-06-10',
              retrieved_on='2024-06-11', cutoff_on='2024-06-10', version='test-1',
              stage='official_computation', methodology='Fixture sintético aislado; no usar en producción.')
ELECTION = dict(code='TEST_2024', name='Elección sintética de prueba', election_date='2024-06-02',
                jurisdiction='local', office='Ayuntamiento', principle='MR', process='ordinary', entity_code='26')


class HistoryValidationTests(unittest.TestCase):
    def test_geography_preserves_codes_and_independent_districts(self):
        rows = parse_geography(GEO)
        self.assertEqual(rows[-1]['code'], '260001')
        self.assertEqual(rows[-1]['federal_district_code'], '2601')
        self.assertEqual(rows[-1]['local_district_code'], '2602')

    def test_missing_parent_wrong_entity_and_duplicate_rejected(self):
        for text in [GEO.replace('municipality,26001,Municipio de prueba,26,,,\n', ''),
                     GEO.replace('260001,Sección', '270001,Sección'),
                     GEO+'entity,26,Repetida,26,,,\n']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_geography(text)

    def test_missing_is_not_zero(self):
        rows = parse_results(CSV.replace(',27\n', ',\n'))
        self.assertIsNone(rows['260001']['votes']['OPTION_B']['votes'])
        rows = parse_results(CSV.replace(',27\n', ',0\n').replace(',80,', ',53,'))
        self.assertEqual(rows['260001']['votes']['OPTION_B']['votes'], 0)

    def test_duplicate_totals_and_fractional_or_negative_votes_rejected(self):
        for text in [CSV+CSV.splitlines()[1]+'\n', CSV.replace(',27\n', ',-1\n'),
                     CSV.replace(',27\n', ',27.5\n'), CSV.replace('260001,100,80,2,1,OPTION_B', '260001,99,80,2,1,OPTION_B')]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_results(text)

    def test_reconciliation_and_partial_overflow(self):
        for text in [CSV.replace(',80,', ',81,'), CSV.replace(',27\n', ',100\n')]:
            with self.assertRaises(ValueError):
                parse_results(text)
        parse_results(CSV.replace(',80,', ',,'))

    def test_csv_structure_and_row_limit(self):
        for text in [','.join(RESULT_COLUMNS)+'\n', CSV.replace('unit_code', 'unit'),
                     CSV.replace(',50\n', ',50,extra\n'), CSV.replace(',50\n', '\n')]:
            with self.assertRaises(ValueError):
                parse_results(text)
        with self.assertRaises(ValueError):
            parse_results(','.join(RESULT_COLUMNS)+'\n'+((CSV.splitlines()[1]+'\n')*20001))

    def test_source_rules_and_csv_hash_input_is_exact(self):
        content = GEO+'\n'
        model = GeographyImport(version='test', valid_on='2024-01-01',
            source={**SOURCE, 'stage':'geography'}, csv_content=content)
        self.assertEqual(model.csv_content, content)
        for source in [{**SOURCE, 'stage':'geography'}, {**SOURCE, 'url':'http://example.org'},
                       {**SOURCE, 'published_on':'2099-01-01'}]:
            with self.assertRaises(ValidationError):
                ResultImport(election_id=1, geography_id=1, level='section', vote_basis='party',
                    source=source, coverage_note='test', csv_content=CSV)
        with self.assertRaises(ValidationError):
            ElectionCreate(**{**ELECTION, 'entity_code':None})


class CursorProxy:
    def __init__(self, cursor, schema):
        self.cursor, self.schema = cursor, schema

    def __enter__(self):
        self.cursor.__enter__()
        return self

    def __exit__(self, *args):
        return self.cursor.__exit__(*args)

    def executemany(self, sql, params):
        return self.cursor.executemany(sql.replace('electoral_history.', self.schema+'.'), params)


class HistoryConnection:
    def __init__(self, raw, schema):
        self.raw, self.schema = raw, schema

    def execute(self, sql, params=()):
        return self.raw.execute(sql.replace('public.', 'pg_temp.').replace('electoral_history.', self.schema+'.'), params)

    def cursor(self):
        return CursorProxy(self.raw.cursor(), self.schema)


@unittest.skipUnless(os.environ.get('API_TEST_POSTGRES') == '1', 'Activar API_TEST_POSTGRES=1')
class HistoryPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import test_admin
        test_admin.AdminTests.setUpClass()
        cls.hashed = test_admin.AdminTests.hashed

    def setUp(self):
        import test_admin
        from backend.admin import db
        from backend.main import app
        test_admin.AdminTests.setUp(self)
        self.raw = self.conn.raw
        schema = 'history_test_'+uuid.uuid4().hex
        ddl = (Path(__file__).resolve().parents[2]/'scripts/agregar_base_historica_postgresql.sql').read_text(encoding='utf-8')
        ddl = ddl.replace('BEGIN;', '').replace('COMMIT;', '').replace('electoral_history', schema)
        self.raw.execute(ddl)
        self.conn = HistoryConnection(self.raw, schema)

        def transaction():
            with self.raw.transaction():
                yield self.conn
        app.dependency_overrides[db] = transaction
        geo = self.client.post('/api/v1/history/geographies', headers=self.headers,
            json=dict(version='TEST_GEO', valid_on='2024-01-01', source={**SOURCE,'stage':'geography'}, csv_content=GEO))
        self.assertEqual(geo.status_code, 201, geo.text)
        self.gid = geo.json()['id']
        election = self.client.post('/api/v1/history/elections', headers=self.headers, json=ELECTION)
        self.assertEqual(election.status_code, 201, election.text)
        self.eid = election.json()['id']

    def payload(self, **changes):
        return dict(election_id=self.eid, geography_id=self.gid, level='section', vote_basis='candidacy',
                    source=SOURCE, coverage_note='Una sección sintética, no es cobertura nacional.', csv_content=CSV, **changes)

    def post(self, payload=None, route='/imports'):
        return self.client.post('/api/v1/history'+route, headers=self.headers, json=payload or self.payload())

    def test_preview_does_not_write_and_roundtrip_pagination(self):
        r = self.post(route='/imports/preview')
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.conn.execute('SELECT count(*) AS n FROM electoral_history.imports').fetchone()['n'], 0)
        r = self.post()
        self.assertEqual(r.status_code, 201, r.text)
        rid = r.json()['id']
        page = self.client.get(f'/api/v1/history/imports/{rid}/results', headers=self.headers).json()
        self.assertEqual(page['items'][0]['options'][0]['votes'], 50)
        detail = self.client.get(f'/api/v1/history/imports/{rid}', headers=self.headers).json()
        self.assertEqual(detail['csv_content'], CSV)
        self.assertEqual(detail['created_by'], 1)
        self.assertEqual(self.post().json()['id'], rid)
        self.assertTrue(self.post().json()['duplicate'])
        self.assertEqual(self.conn.execute('SELECT count(*) AS n FROM electoral_history.imports').fetchone()['n'], 1)
        page = self.client.get(f'/api/v1/history/geographies/{self.gid}/units?limit=2', headers=self.headers).json()
        self.assertEqual(len(page['items']), 2)
        self.assertIsNotNone(page['next_after'])
        next_page = self.client.get(f"/api/v1/history/geographies/{self.gid}/units?limit=2&after={page['next_after']}", headers=self.headers).json()
        self.assertFalse({r['code'] for r in page['items']} & {r['code'] for r in next_page['items']})

    def test_versions_and_local_scope(self):
        bad = self.payload()
        bad['csv_content'] = CSV.replace('260001', '270001')
        self.assertEqual(self.post(bad).status_code, 422)
        self.assertEqual(self.post({**self.payload(), 'level':'municipality'}).status_code, 422)
        self.assertEqual(self.conn.execute('SELECT count(*) AS n FROM electoral_history.imports').fetchone()['n'], 0)
        election = {**ELECTION, 'name':'otro nombre'}
        self.assertEqual(self.post(election, '/elections').status_code, 409)
        geo = dict(version='TEST_GEO', valid_on='2024-01-01', source={**SOURCE,'stage':'geography'}, csv_content=GEO.replace('Entidad de prueba', 'Otro nombre'))
        self.assertEqual(self.post(geo, '/geographies').status_code, 409)

    def test_revision_preserves_original_and_rejects_branch(self):
        original = self.post().json()['id']
        payload = self.payload(supersedes_id=original)
        payload['source'] = {**SOURCE, 'version':'test-2', 'stage':'final_judgment'}
        payload['csv_content'] = CSV.replace(',50\n', ',49\n').replace(',27\n', ',28\n')
        revision = self.post(payload)
        self.assertEqual(revision.status_code, 201, revision.text)
        self.assertNotEqual(revision.json()['id'], original)
        self.assertTrue(self.post(payload).json()['duplicate'])
        payload['source']['version'] = 'branch'
        self.assertEqual(self.post(payload).status_code, 409)
        detail = self.client.get(f'/api/v1/history/imports/{original}', headers=self.headers).json()
        self.assertEqual(detail['csv_content'], CSV)

    def test_unknown_not_zero_and_no_mixed_geographies(self):
        payload = self.payload()
        payload['csv_content'] = CSV.replace(',27\n', ',\n')
        result = self.post(payload)
        self.assertEqual(result.status_code, 201, result.text)
        self.assertTrue(result.json()['warnings'])
        rid = result.json()['id']
        row = self.client.get(f'/api/v1/history/imports/{rid}/results', headers=self.headers).json()['items'][0]
        self.assertIsNone(row['options'][1]['votes'])

    def test_storage_error_rolls_back_entire_batch(self):
        from unittest.mock import patch
        original = CursorProxy.executemany

        def fail_votes(cursor, sql, params):
            if 'electoral_history.votes' in sql:
                raise RuntimeError('Fallo simulado después de guardar los totales')
            return original(cursor, sql, params)

        with patch.object(CursorProxy, 'executemany', fail_votes):
            self.assertEqual(self.post().status_code, 503)
        for table in ('imports', 'results', 'votes'):
            self.assertEqual(self.conn.execute(f'SELECT count(*) AS n FROM electoral_history.{table}').fetchone()['n'], 0)
        self.assertEqual(self.post().status_code, 201)

    def test_registered_foreign_entity_is_not_accepted_in_local_election(self):
        geo = dict(version='TEST_TWO_ENTITIES', valid_on='2024-01-01', source={**SOURCE,'stage':'geography'},
                   csv_content=GEO+'entity,27,Otra entidad,27,,,\nmunicipality,27001,Otro municipio,27,,,\nsection,270001,Otra sección,27,27001,,\n')
        response = self.post(geo, '/geographies')
        self.assertEqual(response.status_code, 201, response.text)
        payload = {**self.payload(), 'geography_id':response.json()['id'], 'csv_content':CSV.replace('260001','270001')}
        response = self.post(payload)
        self.assertEqual(response.status_code, 422)
        self.assertIn('entidad de la elección', response.json()['detail'])

    def test_revision_cannot_change_coverage(self):
        original = self.post().json()['id']
        payload = self.payload(supersedes_id=original)
        payload['geography_id'] = self.gid + 1000
        self.assertEqual(self.post(payload).status_code, 404)
        payload['geography_id'] = self.gid
        payload['vote_basis'] = 'party'
        self.assertEqual(self.post(payload).status_code, 409)

    def test_authentication_and_field_role_forbidden(self):
        self.assertEqual(self.client.get('/api/v1/history/elections').status_code, 401)
        from backend.admin import digest
        import time
        self.conn.execute('INSERT INTO public.web_sessions(token_hash,worker_id,expires_at) VALUES (%s,2,%s)',
                          (digest('field-session'), int(time.time())+3600))
        r = self.client.get('/api/v1/history/elections', headers={'Authorization':'Bearer field-session'})
        self.assertEqual(r.status_code, 403)
