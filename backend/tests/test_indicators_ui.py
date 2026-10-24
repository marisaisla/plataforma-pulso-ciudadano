import unittest


class IndicatorUITests(unittest.TestCase):
    def run_screen(self,empty=True):
        from streamlit.testing.v1 import AppTest
        script='''
from unittest.mock import patch
from backend.indicator_catalog import catalog
from services.indicators_ui import render_indicators
def respond(method,path,token,payload=None):
    assert method=='GET', 'Renderizar no debe disparar cálculos'
    if path=='/indicators/catalog': return dict(items=catalog(),engine_version='1.0.0',catalog_version='2026-10-22')
    if path=='/history/elections': return []
    if path.startswith('/indicators/datasets'): return []
    raise AssertionError(path)
with patch('services.indicators_ui.session_token',return_value='test'),patch('services.indicators_ui.request',side_effect=respond):
    render_indicators()
'''
        return AppTest.from_string(script).run(timeout=20)

    def test_catalog_and_empty_selection_render_without_calculating(self):
        app=self.run_screen()
        self.assertEqual(len(app.exception),0,str(app.exception))
        self.assertEqual(len(app.tabs),3)
        self.assertEqual(len(app.dataframe),1)
        self.assertTrue(any('Selecciona' in info.value for info in app.info))

    def test_failure_is_visible_without_sql_fallback(self):
        from streamlit.testing.v1 import AppTest
        script='''
from unittest.mock import patch
from services.indicators_ui import render_indicators
from services.profiles_api import ProfileAPIError
with patch('services.indicators_ui.session_token',return_value='test'),patch('services.indicators_ui.request',side_effect=ProfileAPIError('API no disponible',503)):
    render_indicators()
'''
        app=AppTest.from_string(script).run(timeout=20)
        self.assertEqual(len(app.exception),0,str(app.exception))
        self.assertEqual(app.error[0].value,'API no disponible')

    def test_selected_dataset_calculates_and_renders_table_and_chart(self):
        from streamlit.testing.v1 import AppTest
        script='''
from unittest.mock import patch
from backend.indicator_catalog import catalog
from backend.indicator_engine import evaluate
from test_indicators import dataset
from services.indicators_ui import render_indicators
data=dataset()
def respond(method,path,token,payload=None):
    if path=='/indicators/catalog': return dict(items=catalog(),engine_version='1.0.0',catalog_version='2026-10-22')
    if path=='/history/elections': return [dict(id=1,name='Elección sintética')]
    if path.startswith('/indicators/datasets?'): return [dict(id=1,election_name='Elección sintética',level='section',units=2,vote_basis='party',coverage_note='Prueba aislada',superseded_by=None)]
    if path=='/indicators/datasets/1/options': return [dict(option_code='P1',option_name='Partido sintético 1'),dict(option_code='P2',option_name='Partido sintético 2')]
    if method=='POST' and path=='/indicators/evaluate': return evaluate(data,payload)
    raise AssertionError(path)
with patch('services.indicators_ui.session_token',return_value='test'),patch('services.indicators_ui.request',side_effect=respond):
    render_indicators()
'''
        app=AppTest.from_string(script).run(timeout=20)
        app.selectbox(key='indicator_single_dataset').select(1).run()
        app.selectbox(key='single_option').select('P1').run()
        next(b for b in app.button if b.label=='Calcular indicadores').click().run()
        self.assertEqual(len(app.exception),0,str(app.exception))
        self.assertEqual(len(app.dataframe),3)
        app.selectbox(key='single_result_chart').select('IT05').run()
        self.assertEqual(len(app.exception),0,str(app.exception))

    def test_comparison_displays_canonicalized_evidence_notes(self):
        from streamlit.testing.v1 import AppTest
        import json
        script='''
from unittest.mock import patch
from backend.indicator_catalog import catalog
from backend.indicator_models import Comparison
from backend.indicator_engine import compare
from test_indicators import dataset
from services.indicators_ui import render_indicators
def respond(method,path,token,payload=None):
    if path=='/indicators/catalog': return dict(items=catalog(),engine_version='1.0.0',catalog_version='2026-10-22')
    if path=='/history/elections': return [dict(id=1,name='A sintética'),dict(id=2,name='B sintética')]
    if path.startswith('/indicators/datasets?'): return [dict(id=i,election_name=f'Elección sintética {i}',level='section',units=2,vote_basis='party',coverage_note='Prueba aislada',superseded_by=None) for i in (1,2)]
    if path.endswith('/options'): return [dict(option_code=p,option_name=p) for p in ('P1','P2')]
    if method=='POST' and path=='/indicators/compare':
        body=Comparison.model_validate(payload).model_dump(mode='json')
        return compare(dataset(year=2021),dataset(year=2024),body)
    raise AssertionError(path)
with patch('services.indicators_ui.session_token',return_value='test'),patch('services.indicators_ui.request',side_effect=respond):
    render_indicators()
'''
        app=AppTest.from_string(script).run(timeout=20)
        app.selectbox(key='indicator_a_dataset').select(1).run()
        app.selectbox(key='indicator_b_dataset').select(2).run()
        mapping=[dict(option_a=p,option_b=p,evidence_url='https://example.org/test',note=' Evidencia sintética ') for p in ('P1','P2')]
        app.text_area[0].input(json.dumps(mapping)).run()
        next(b for b in app.button if b.label=='Comprobar comparabilidad y calcular').click().run()
        self.assertEqual(len(app.exception),0,str(app.exception))
        self.assertEqual(len(app.error),0)
        app.selectbox(key='comparison_result_chart').select('IT08').run()
        self.assertEqual(len(app.exception),0,str(app.exception))
