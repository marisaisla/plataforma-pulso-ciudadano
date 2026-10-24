import unittest
from streamlit.testing.v1 import AppTest


SCRIPT='''
from unittest.mock import patch
from backend.indicator_dashboard import cards
from services.indicator_dashboard_ui import render_indicator_dashboard
from services.profiles_api import ProfileAPIError

def respond(method,path,token,payload=None):
    if path.startswith('/profiles?'): return []
    if path=='/indicators/dashboard/cards': return cards()
    if path.startswith('/indicators/datasets?'):
        return [dict(id=1,election_name='Prueba 2024',level='section',units=1,
                     coverage_note='Una sección, fuente sintética',superseded_by=None)]
    if path.startswith('/indicators/dashboard/inegi/options'):
        return dict(states=['A'],municipalities=[dict(municipality_code='001',municipality='Uno')],
                    series=[dict(indicator_id='1002000001',indicator_name='Población total',family='IT10')],
                    periods=['2020'],sources=['Fuente sintética'])
    if path.startswith('/indicators/dashboard/inegi?'):
        return dict(total=1,next_after=None,scope='Datos sintéticos sin agregación',items=[dict(
            id=1,family='IT10',state='A',municipality_code='001',municipality='Uno',
            indicator_id='1002000001',indicator_name='Población total',unit='habitantes',
            value=150,period='2020',source='Fuente sintética',retrieved_at='2026-10-22',value_status='reported')])
    if path=='/indicators/evaluate':
        metric=lambda value,status='computed':dict(value=value,status=status,reason='Requiere proxy' if value is None else None)
        metrics=dict(IT01=metric(100),IT03=metric(80,'proxy') if payload['participation_proxy'] else metric(None),
                     IT04=metric(20,'proxy') if payload['participation_proxy'] else metric(None),IT05=metric(2.5))
        return dict(summary=metrics,warnings=['EXPLORATORIO: fuente sintética'],
                    coverage=dict(units_observed=1),items=[dict(unit_code='010001',name='Sección',metrics=metrics)],
                    provenance=dict(source='fixture'),request=payload,next_after=None)
    raise AssertionError((method,path))

with patch('services.indicator_dashboard_ui.session_token',return_value='test'),patch('services.indicator_dashboard_ui.request',side_effect=respond),patch('services.dashboard_research_ui.request',side_effect=respond):
    render_indicator_dashboard()
'''


class DashboardUITests(unittest.TestCase):
    def screen(self):
        app=AppTest.from_string(SCRIPT).run(timeout=30)
        self.assertEqual(len(app.exception),0,str(app.exception))
        return app

    def select(self,app,label,value):
        next(s for s in app.selectbox if s.label==label).set_value(value).run(timeout=30)
        self.assertEqual(len(app.exception),0,str(app.exception))

    def test_45_cards_render_without_fabricated_values(self):
        app=self.screen()
        self.assertEqual(len(app.expander),45)
        self.assertEqual(len(app.metric),0)
        headings=[m.value for m in app.markdown]
        self.assertTrue(any('IC01 ·' in v for v in headings))
        self.assertTrue(any('IT15 ·' in v for v in headings))

    def test_electoral_values_proxy_opt_in_and_stale_result_hidden(self):
        app=self.screen()
        self.select(app,'Lote electoral',1)
        app.button(key='dash_calculate').click().run(timeout=30)
        self.assertEqual(len(app.exception),0,str(app.exception))
        self.assertEqual(len(app.metric),2)
        app.checkbox(key='dash_proxy').check().run(timeout=30)
        self.assertEqual(len(app.metric),0)
        app.button(key='dash_calculate').click().run(timeout=30)
        self.assertEqual(len(app.exception),0,str(app.exception))
        self.assertEqual(len(app.metric),4)
        self.assertEqual(sum(m.label=='Aproximación explícita' for m in app.metric),2)
        app.text_input(key='dash_unit').set_value('010001').run(timeout=30)
        self.assertEqual(len(app.metric),0)

    def test_inegi_observations_display_and_source_filter_invalidation(self):
        app=self.screen()
        self.select(app,'Entidad INEGI','A')
        self.select(app,'Serie INEGI','1002000001')
        self.select(app,'Periodo INEGI','2020')
        self.select(app,'Fuente INEGI','Fuente sintética')
        app.button(key='dash_inegi_query').click().run(timeout=30)
        self.assertEqual(len(app.exception),0,str(app.exception))
        self.assertEqual(len(app.dataframe),1)
        self.assertEqual(app.dataframe[0].value.iloc[0]['value'],150)
        self.assertEqual(len(app.metric),0) # observation count is not a manufactured indicator score
        self.select(app,'Periodo INEGI',None)
        self.assertEqual(len(app.dataframe),0)

    def test_api_unavailable_has_visible_error(self):
        script=SCRIPT.replace("if path=='/indicators/dashboard/cards': return cards()",
                              "if path=='/indicators/dashboard/cards': raise ProfileAPIError('API no disponible',503)")
        app=AppTest.from_string(script).run(timeout=30)
        self.assertEqual(len(app.exception),0,str(app.exception))
        self.assertTrue(any('API no disponible' in e.value for e in app.error))
