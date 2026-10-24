import copy
import os
import unittest
from pydantic import ValidationError

from backend.indicator_catalog import catalog
from backend.indicator_models import Selection,Comparison
from backend.indicator_engine import evaluate,compare,unit_metrics


def dataset(basis='party',year=2024,rows=None):
    return dict(metadata=dict(id=1,election_id=1,geography_id=1,level='section',vote_basis=basis,
        source=dict(stage='official_computation',cutoff_on=f'{year}-06-10',url='https://example.org/test'),
        content_sha256='test',fingerprint='test',coverage_note='Dos unidades sintéticas, no datos oficiales',superseded_by=None),
        election=dict(election_date=f'{year}-06-02',jurisdiction='local',office='Cargo de prueba',principle='MR',process='ordinary',entity_code='26'),
        geography=dict(id=1,version='test',valid_on='2020-01-01'),
        rows=rows or [unit('260001',100,80,2,1,[50,27]),unit('260002',200,100,5,0,[45,50])])


def unit(code,nominal,total,nulls,unregistered,votes):
    return dict(unit_code=code,name='Unidad sintética '+code,entity_code='26',nominal_list=nominal,
        total_votes=total,null_votes=nulls,unregistered_votes=unregistered,
        options=[dict(option_code='P'+str(i+1),option_name='Opción '+str(i+1),votes=v) for i,v in enumerate(votes)])


def selection(**changes):
    return Selection(import_id=1,option_code='P1',participation_proxy=True,**changes).model_dump(mode='json')


def comparison(a=None,b=None,mapping=True,**changes):
    return Comparison(a=a or selection(),b=b or selection(),option_mapping=[dict(option_a=p,option_b=p,evidence_url='https://example.org/mapping',note='Equivalencia sintética para prueba') for p in ('P1','P2')] if mapping else [],**changes).model_dump(mode='json')


class IndicatorMathTests(unittest.TestCase):
    def test_catalog_has_45_unique_codes_and_support_is_explicit(self):
        items=catalog()
        self.assertEqual(len(items),45)
        self.assertEqual(len({i['code'] for i in items}),45)
        self.assertEqual(sum(i['engine_support']!='pending_inputs' for i in items),16)

    def test_single_denominators_hhi_and_coverage_distribution(self):
        response=evaluate(dataset(),selection())
        first=response['items'][0]['metrics']
        self.assertEqual(first['IT03']['value'],80)
        self.assertEqual(first['IT03']['status'],'proxy')
        self.assertEqual(first['IT04']['value'],20)
        self.assertEqual(first['IT05']['value'],2.5)
        self.assertAlmostEqual(first['IP02']['value'],100*50/77,places=5)
        self.assertAlmostEqual(first['IT09']['value'],(50/77)**2+(27/77)**2,places=5)
        self.assertEqual(response['summary']['IP05']['value'],2)
        self.assertAlmostEqual(first['IP11']['value'],100*50/95,places=5)
        self.assertEqual(response['summary']['IT03']['value'],60) # 180/300, nunca promedio 80% y 50%
        self.assertEqual(response['summary']['IT05']['numerator'],7)
        self.assertEqual(response['summary']['IT05']['denominator'],180)
        self.assertIsNone(first['IT06']['value'])

    def test_explicit_emitted_denominator_and_no_default_participation_proxy(self):
        s=selection(denominator='emitted_votes'); s['participation_proxy']=False
        metric=evaluate(dataset(),s)['items'][0]['metrics']
        self.assertEqual(metric['IP02']['value'],62.5)
        self.assertIsNone(metric['IT03']['value'])
        self.assertIsNone(metric['IT04']['value'])

    def test_missing_values_do_not_become_zero_and_summary_is_not_partial_sum(self):
        d=dataset();d['rows'][1]['nominal_list']=None;d['rows'][1]['options'][0]['votes']=None
        response=evaluate(d,selection())
        self.assertIsNone(response['summary']['IT01']['value'])
        self.assertIsNone(response['summary']['IP05']['value'])
        self.assertIsNone(response['summary']['IP11']['value'])
        self.assertEqual(response['coverage']['metric_coverage']['IT01']['available'],1)

    def test_zero_denominators_over_100_and_nonreconciled_composition(self):
        for row in [unit('260001',0,0,0,0,[0,0]), unit('260001',10,80,2,1,[50,27])]:
            metrics,_=unit_metrics(row,selection(),'party')
            self.assertIsNone(metrics['IT03']['value'])
        d=dataset();d['rows'][0]['options'][0]['votes']=100
        metric=evaluate(d,selection())['items'][0]['metrics']
        self.assertIsNone(metric['IP02']['value'])
        self.assertIsNone(metric['IT09']['value'])

    def test_margin_requires_candidacy_and_tie_has_no_arbitrary_winner(self):
        d=dataset('candidacy',rows=[unit('260001',100,80,0,0,[40,40])])
        m=evaluate(d,selection())['items'][0]['metrics']
        self.assertEqual(m['IT06']['value'],0)
        self.assertIsNone(m['IT06']['details']['winner'])
        d['rows'][0]['options'][0]['votes']=50;d['rows'][0]['options'][1]['votes']=30
        m=evaluate(d,selection())['items'][0]['metrics']['IT06']
        self.assertEqual(m['value'],20)
        self.assertEqual(m['details']['margin_pp'],25)

    def test_legacy_keeps_party_and_winner_metrics_unavailable(self):
        d=dataset('legacy_reported');d['metadata']['source']['stage']='legacy_snapshot'
        result=evaluate(d,selection(mode='exploratory'))
        for code in ('IP01','IP02','IP05','IT06','IT09'):
            self.assertIsNone(result['summary'][code]['value'])
        self.assertTrue(any('EXPLORATORIO' in w for w in result['warnings']))

    def test_pagination_does_not_change_summary_and_fingerprints_are_reproducible(self):
        original=dataset(); before=copy.deepcopy(original)
        full=evaluate(original,selection())
        page=evaluate(original,selection(limit=1))
        self.assertEqual(full['summary'],page['summary'])
        self.assertEqual(page['next_after'],'260001')
        again=evaluate(original,selection())
        self.assertEqual(full['provenance'],again['provenance'])
        self.assertEqual(original,before)

    def test_aggregation_does_not_hide_offsetting_errors_or_bad_participation_universes(self):
        d=dataset(rows=[unit('260001',100,10,0,0,[8,3]),unit('260002',100,10,0,0,[1,8])])
        result=evaluate(d,selection())
        self.assertIsNone(result['summary']['IT09']['value'])
        self.assertIsNone(result['summary']['IP02']['value'])
        d=dataset(rows=[unit('260001',10,20,0,0,[10,10]),unit('260002',100,10,0,0,[5,5])])
        self.assertIsNone(evaluate(d,selection())['summary']['IT03']['value'])

    def test_comparison_known_growth_delta_and_pedersen(self):
        a=dataset(year=2021,rows=[unit('260001',100,100,0,0,[60,40])])
        b=dataset(year=2024,rows=[unit('260001',120,100,0,0,[40,60])])
        result=compare(a,b,comparison())
        self.assertTrue(result['comparability']['comparable'])
        metrics=result['items'][0]['metrics']
        self.assertEqual(metrics['IP03']['value'],-20)
        self.assertAlmostEqual(metrics['IP04']['value'],-100/3,places=5)
        self.assertEqual(metrics['IT02']['value'],20)
        self.assertEqual(metrics['IT08']['value'],20)
        self.assertEqual(metrics['IP12']['value'],20)

    def test_incompatible_geography_metadata_chronology_and_legacy_are_blocked(self):
        a=dataset(year=2021)
        for field,value,kind in [('geography_id',2,'metadata'),('office','otro','election'),
                                 ('process','unknown','election'),('election_date','2020-01-01','election'),
                                 ('vote_basis','legacy_reported','metadata')]:
            b=dataset();b[kind][field]=value
            result=compare(a,b,comparison())
            self.assertFalse(result['comparability']['comparable'])
            self.assertFalse(result['items'])

    def test_missing_mapping_no_zero_imputation_and_explicit_intersection(self):
        a=dataset(year=2021);b=dataset()
        result=compare(a,b,comparison(mapping=False))
        self.assertIsNone(result['items'][0]['metrics']['IT08']['value'])
        b['rows']=b['rows'][:1]
        self.assertFalse(compare(a,b,comparison())['comparability']['comparable'])
        result=compare(a,b,comparison(coverage_mode='intersection'))
        self.assertTrue(result['comparability']['comparable'])
        self.assertEqual(result['comparability']['excluded_only_a'],1)

    def test_zero_baseline_has_absolute_change_but_no_relative_growth(self):
        a=dataset(year=2021,rows=[unit('260001',100,10,0,0,[0,10])])
        b=dataset(rows=[unit('260001',100,10,0,0,[5,5])])
        metrics=compare(a,b,comparison())['items'][0]['metrics']
        self.assertEqual(metrics['IP03']['value'],5)
        self.assertIsNone(metrics['IP04']['value'])

    def test_alternation_has_no_government_inference_and_tie_is_undefined(self):
        a=dataset('candidacy',2021,rows=[unit('260001',100,100,0,0,[60,40])])
        b=dataset('candidacy',2024,rows=[unit('260001',100,100,0,0,[40,60])])
        self.assertTrue(compare(a,b,comparison())['items'][0]['metrics']['IT07']['value'])
        b['rows'][0]['options'][0]['votes']=50;b['rows'][0]['options'][1]['votes']=50
        self.assertIsNone(compare(a,b,comparison())['items'][0]['metrics']['IT07']['value'])

    def test_mapping_must_be_bijective_and_have_https_evidence(self):
        request=comparison();request['option_mapping'].append(request['option_mapping'][0])
        with self.assertRaises(ValidationError): Comparison.model_validate(request)
        request=comparison();request['option_mapping'][0]['evidence_url']='http://example.org'
        with self.assertRaises(ValidationError): Comparison.model_validate(request)
        request=comparison();request['option_mapping'][0]['note']='   '
        with self.assertRaises(ValidationError): Comparison.model_validate(request)

    def test_scope_filters_empty_selection_and_missing_baseline_option(self):
        response=evaluate(dataset(),selection(entity_code='08'))
        self.assertEqual(response['coverage']['units_observed'],0)
        self.assertFalse(response['items'])
        a=dataset(year=2021);b=dataset()
        a['rows'][0]['options']=a['rows'][0]['options'][1:]
        self.assertIsNone(compare(a,b,comparison())['items'][0]['metrics']['IP03']['value'])

    def test_denominator_and_incomplete_mapping_block_volatility(self):
        a=dataset(year=2021);b=dataset()
        request=comparison();request['option_mapping']=request['option_mapping'][:1]
        self.assertIsNone(compare(a,b,request)['items'][0]['metrics']['IT08']['value'])
        request=comparison();request['a']['denominator']='emitted_votes'
        self.assertFalse(compare(a,b,request)['comparability']['comparable'])


@unittest.skipUnless(os.environ.get('API_TEST_POSTGRES')=='1','Activar API_TEST_POSTGRES=1')
class IndicatorPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_history import HistoryPostgresTests
        HistoryPostgresTests.setUpClass()
        cls.hashed=HistoryPostgresTests.hashed

    def setUp(self):
        from test_history import HistoryPostgresTests
        HistoryPostgresTests.setUp(self)
        self.bid=HistoryPostgresTests.post(self,HistoryPostgresTests.payload(self)).json()['id']

    def test_evaluate_http_defaults_and_no_source_writes(self):
        response=self.client.post('/api/v1/indicators/evaluate',headers=self.headers,
            json=dict(import_id=self.bid,participation_proxy=True))
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['summary']['IT03']['value'],80)
        self.assertIsNone(response.json()['summary']['IP01']['value']) # fixture candidacy, no party attribution
        self.assertEqual(self.conn.execute('SELECT count(*) AS n FROM electoral_history.imports').fetchone()['n'],1)
        catalog_response=self.client.get('/api/v1/indicators/catalog',headers=self.headers)
        self.assertEqual(len(catalog_response.json()['items']),45)
        self.assertEqual(len(self.client.get(f'/api/v1/indicators/datasets/{self.bid}/options',headers=self.headers).json()),2)
        datasets=self.client.get('/api/v1/indicators/datasets',headers=self.headers)
        self.assertEqual(datasets.status_code,200,datasets.text)
        self.assertEqual(datasets.json()[0]['units'],1)

    def test_legacy_is_rejected_unless_explicit_exploration(self):
        from psycopg.types.json import Jsonb
        self.conn.execute('UPDATE electoral_history.imports SET source=%s WHERE id=%s',
            (Jsonb(dict(stage='legacy_snapshot',cutoff_on=None)),self.bid))
        response=self.client.post('/api/v1/indicators/evaluate',headers=self.headers,json=dict(import_id=self.bid))
        self.assertEqual(response.status_code,409)
        response=self.client.post('/api/v1/indicators/evaluate',headers=self.headers,json=dict(import_id=self.bid,mode='exploratory'))
        self.assertEqual(response.status_code,200,response.text)
        self.assertIsNone(response.json()['summary']['IP01']['value'])

    def test_authentication_role_missing_id_and_validation(self):
        self.assertEqual(self.client.get('/api/v1/indicators/catalog').status_code,401)
        from backend.admin import digest
        import time
        self.conn.execute('INSERT INTO public.web_sessions(token_hash,worker_id,expires_at) VALUES (%s,2,%s)',(digest('field-indicator'),int(time.time())+3600))
        self.assertEqual(self.client.get('/api/v1/indicators/catalog',headers={'Authorization':'Bearer field-indicator'}).status_code,403)
        self.assertEqual(self.client.post('/api/v1/indicators/evaluate',headers=self.headers,json=dict(import_id=999999)).status_code,404)
        self.assertEqual(self.client.post('/api/v1/indicators/evaluate',headers=self.headers,json=dict(import_id=self.bid,limit=501)).status_code,422)

    def test_comparison_same_election_is_blocked_without_writing(self):
        response=self.client.post('/api/v1/indicators/compare',headers=self.headers,
            json=dict(a=dict(import_id=self.bid),b=dict(import_id=self.bid)))
        self.assertEqual(response.status_code,200,response.text)
        self.assertFalse(response.json()['comparability']['comparable'])

    def test_http_valid_comparison_and_superseded_guard(self):
        from test_history import ELECTION,SOURCE,CSV
        old=self.client.post('/api/v1/history/elections',headers=self.headers,
            json={**ELECTION,'code':'TEST_2021','election_date':'2021-06-06'}).json()['id']
        payload=dict(election_id=old,geography_id=self.gid,level='section',vote_basis='party',
            source={**SOURCE,'cutoff_on':'2021-06-10','published_on':'2021-06-10','retrieved_on':'2021-06-11'},
            coverage_note='Sintético',csv_content=CSV)
        ra=self.client.post('/api/v1/history/imports',headers=self.headers,json=payload)
        self.assertEqual(ra.status_code,201,ra.text)
        payload.update(election_id=self.eid,source=SOURCE)
        rb=self.client.post('/api/v1/history/imports',headers=self.headers,json=payload)
        self.assertEqual(rb.status_code,201,rb.text)
        a,b=ra.json()['id'],rb.json()['id']
        body=dict(a=dict(import_id=a,option_code='OPTION_A'),b=dict(import_id=b,option_code='OPTION_A'),
            option_mapping=[dict(option_a=c,option_b=c,evidence_url='https://example.org/mapping',note='Fixture') for c in ('OPTION_A','OPTION_B')])
        response=self.client.post('/api/v1/indicators/compare',headers=self.headers,json=body)
        self.assertEqual(response.status_code,200,response.text)
        self.assertTrue(response.json()['comparability']['comparable'])
        self.assertEqual(response.json()['summary']['IT08']['value'],0)
        payload['supersedes_id']=b;payload['source']={**SOURCE,'version':'correction'}
        revision=self.client.post('/api/v1/history/imports',headers=self.headers,json=payload)
        self.assertEqual(revision.status_code,201,revision.text)
        response=self.client.post('/api/v1/indicators/evaluate',headers=self.headers,json=dict(import_id=b))
        self.assertEqual(response.status_code,409)
        response=self.client.post('/api/v1/indicators/evaluate',headers=self.headers,json=dict(import_id=b,allow_superseded=True))
        self.assertEqual(response.status_code,200,response.text)
