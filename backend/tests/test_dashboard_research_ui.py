import unittest
from streamlit.testing.v1 import AppTest
from backend.tests.test_indicator_dashboard_ui import SCRIPT


RESEARCH_SCRIPT=SCRIPT.replace("if path.startswith('/profiles?'): return []",'''if path.startswith('/profiles?'): return [dict(id=1,name='Perfil Uno'),dict(id=2,name='Perfil Dos')]
    if path.startswith('/indicators/dashboard/research?'):
        from urllib.parse import parse_qs,urlparse
        from backend.dashboard_research import describe_survey,survey_fingerprint
        profile=int(parse_qs(urlparse(path).query)['profile_id'][0])
        raw=dict(id=1,profile_id=profile,name='Careo de prueba',pollster='Fuente ficticia',territory='A',
                 fieldwork_date='2026-06-01',sample_size=400,methodology='Metodología sintética',
                 profile_result_pct=42.0,source_url='https://example.org/test',notes='Indecisos 9%')
        review=dict(items={survey_fingerprint(raw):dict(kind='hypothetical_matchup',reference_only=False,note='Fuente sintética',indecision_pct=9)})
        survey=describe_survey(raw,review)
        raw2={**raw,'id':2,'name':'Aprobación sintética','profile_result_pct':65.0}
        review2=dict(items={survey_fingerprint(raw2):dict(kind='approval',reference_only=False,note='Aprobación, no preferencia')})
        surveys=[survey,describe_survey(raw2,review2)] if profile==1 else []
        positions=[dict(id=1,office='Cargo declarado',condition='En funciones',starts_at='2024-01-01',ends_at=None,party_or_coalition='Partido',is_current=1)] if profile==1 else []
        documents=[dict(id=1,title='Documento de prueba',document_type='Referencia',source_url=None,imported_at='2026-10-22')] if profile==1 else []
        evidence=[dict(id=1,variable_code='name_recognition',status='Documentada',evidence_note='Nota de conocimiento sin medición',source_label='Expediente',source_url=None,reference_date=None,related_cards=['IC01'])] if profile==1 else []
        return dict(profile=dict(id=profile,name='Perfil Uno' if profile==1 else 'Perfil Dos',active=1),reviewed_on='2026-10-22',
                    surveys=surveys,positions=positions,documents=documents,evidence=evidence,coalitions=[],
                    totals=dict(surveys=len(surveys),positions=len(positions),documents=len(documents),evidence=len(evidence),coalitions=0),
                    truncated=False,warnings=['Las referencias no son mediciones certificadas.'])''')


class ResearchUITests(unittest.TestCase):
    def screen(self):
        app=AppTest.from_string(RESEARCH_SCRIPT).run(timeout=30)
        self.assertEqual(len(app.exception),0,str(app.exception))
        app.selectbox(key='dash_research_profile').set_value(1).run(timeout=30)
        app.button(key='dash_research_query').click().run(timeout=30)
        self.assertEqual(len(app.exception),0,str(app.exception))
        return app

    def test_selected_measurement_and_dossier_references_are_displayed(self):
        app=self.screen()
        self.assertTrue(any('Documento de prueba' in str(d.value) for d in app.dataframe))
        self.assertTrue(any('Nota de conocimiento' in m.value for m in app.markdown))
        app.selectbox(key='dash_research_survey_1').set_value(1).run(timeout=30)
        self.assertEqual(len(app.exception),0,str(app.exception))
        self.assertEqual(len(app.metric),2)
        self.assertCountEqual([m.value for m in app.metric],['42.00','9.00'])
        self.assertTrue(all(m.label=='Porcentaje reportado' for m in app.metric))

    def test_approval_does_not_feed_preference_and_profile_change_clears_results(self):
        app=self.screen()
        app.selectbox(key='dash_research_survey_1').set_value(1).run(timeout=30)
        self.assertEqual(len(app.metric),2)
        app.selectbox(key='dash_research_survey_1').set_value(2).run(timeout=30)
        self.assertEqual(len(app.exception),0,str(app.exception))
        self.assertEqual(len(app.metric),0)
        app.selectbox(key='dash_research_profile').set_value(2).run(timeout=30)
        self.assertEqual(len(app.dataframe),0)
        self.assertFalse(any('Nota de conocimiento' in m.value for m in app.markdown))
        app.button(key='dash_research_query').click().run(timeout=30)
        self.assertEqual(len(app.exception),0,str(app.exception))
        self.assertEqual(len(app.metric),0)
        self.assertTrue(any('no tiene registros de encuestas' in i.value for i in app.info))
