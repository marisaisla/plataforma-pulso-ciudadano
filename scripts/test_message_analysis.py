"""Pruebas aisladas: nunca consultan la API ni modifican la base del usuario."""
import gc
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from services import database as db
from services import message_analysis as ma
from services.territorial_pulse import rebuild_explicit_municipality_links, municipal_pulse_summary


class MessageAnalysisTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(db, "DB_PATH", Path(self.temp.name) / "test.db")
        self.db_patch.start()
        db.initialize_database()
        with db.connection() as conn:
            self.profile = conn.execute("INSERT INTO profiles(name,actor_type) VALUES ('Perfil de prueba','Persona')").lastrowid
            source = conn.execute("INSERT INTO sources(profile_id,source_type,name) VALUES (?,'X','Prueba')", (self.profile,)).lastrowid
            self.message = conn.execute("INSERT INTO publications(profile_id,source_id,external_id,title,text,url) VALUES (?,?,'test-1','Solicitud','Baches en Mérida','https://example.org/1')", (self.profile,source)).lastrowid
        self.setting = patch.object(ma, "get_setting", side_effect=lambda k: 'test-model' if k == 'OPENAI_MODEL' else 'test-key')
        self.setting.start()

    def tearDown(self):
        self.setting.stop()
        self.db_patch.stop()
        gc.collect()
        self.temp.cleanup()

    def response(self, **kwargs):
        keys = kwargs['json']['text']['format']['schema']['required']
        value = {k: {"sentiment":"Crítico", "content_type":"Denuncia", "topic":"Mérida" if k == 'territorio' else 'Baches',
                     "urgency":"Media", "relation_to_profile":"Directa", "explanation":"Se solicitan reparaciones."} for k in keys}
        return Mock(ok=True, json=lambda: {"output_text":json.dumps(value)})

    def test_single_request_five_results_and_no_rebilling(self):
        with patch.object(ma.requests,'post',side_effect=lambda *a,**kw:self.response(**kw)) as post:
            result = ma.analyze_messages(self.profile,[self.message])
            self.assertEqual(result['analyzed'],1)
            self.assertEqual(post.call_count,1)
            self.assertEqual(len(ma.message_results(self.profile)[0]['results']),5)
            ma.analyze_messages(self.profile,[self.message])
            self.assertEqual(post.call_count,1)
        rebuild_explicit_municipality_links(self.profile,'Yucatán',['Mérida'])
        self.assertEqual(municipal_pulse_summary(self.profile,'Yucatán')[0]['negative'],1)

    def test_partial_preserved_and_only_missing_requested(self):
        with db.connection() as conn:
            ap=conn.execute("SELECT id FROM analysis_approaches WHERE name='Perfil político'").fetchone()[0]
            conn.execute("""INSERT INTO analysis_results(publication_id,approach_id,sentiment,explanation,method,content_type,topic,urgency,relation_to_profile)
                            VALUES (?,?,'Favorable','Anterior','OpenAI contextual v1','Noticia','Tema','Normal','Directa')""",(self.message,ap))
        with patch.object(ma.requests,'post',side_effect=lambda *a,**kw:self.response(**kw)) as post:
            ma.analyze_messages(self.profile,[self.message])
            keys=post.call_args.kwargs['json']['text']['format']['schema']['required']
            self.assertEqual(len(keys),4)
            self.assertNotIn('perfil',keys)
        saved=ma.message_results(self.profile)[0]
        self.assertEqual(saved['sentiment'],'Positivo')
        self.assertEqual(saved['results']['Perfil político']['explanation'],'Anterior')

    def test_invalid_response_leaves_message_pending(self):
        with patch.object(ma.requests,'post',return_value=Mock(ok=True,json=lambda:{'output_text':'{}'})):
            result=ma.analyze_messages(self.profile,[self.message])
        self.assertTrue(result['errors'])
        self.assertEqual(ma.message_results(self.profile)[0]['status'],'Sin analizar')

    def test_basic_result_is_versioned_before_completion(self):
        with db.connection() as conn:
            ap=conn.execute("SELECT id FROM analysis_approaches WHERE name='Perfil político'").fetchone()[0]
            conn.execute("INSERT INTO analysis_results(publication_id,approach_id,sentiment,method) VALUES (?,?,'Neutral','Reglas locales v1')",(self.message,ap))
        with patch.object(ma.requests,'post',side_effect=lambda *a,**kw:self.response(**kw)):
            ma.analyze_messages(self.profile,[self.message])
        self.assertEqual(ma.message_results(self.profile)[0]['status'],'Completo')
        with db.connection() as conn:
            saved=json.loads(conn.execute('SELECT previous_result FROM analysis_result_versions').fetchone()[0])
            self.assertEqual(saved['sentiment'],'Neutral')

    def test_optional_query_includes_saved_results(self):
        from services import capture
        with patch.object(ma.requests,'post',side_effect=lambda *a,**kw:self.response(**kw)):
            ma.analyze_messages(self.profile,[self.message])
        with patch.object(capture,'get_setting',return_value='test'), patch.object(capture.requests,'post',return_value=Mock(ok=True,json=lambda:{'output_text':'Resumen de prueba'})) as post:
            result=capture.run_prompt_query(self.profile,'Resume los resultados',[self.message])
            self.assertFalse(result['errors'])
            self.assertIn('Análisis guardados',post.call_args.kwargs['json']['input'])
            self.assertIn('Se solicitan reparaciones',post.call_args.kwargs['json']['input'])

    def test_ui_filters_navigation_no_network(self):
        from streamlit.testing.v1 import AppTest
        with patch.object(ma.requests,'post',side_effect=lambda *a,**kw:self.response(**kw)):
            ma.analyze_messages(self.profile,[self.message])
        source=f"from services.analysis_view import render_analysis\nrender_analysis({{'Prueba':{self.profile}}})"
        with patch.object(ma.requests,'post') as post:
            app=AppTest.from_string(source, default_timeout=30).run()
            self.assertFalse(app.exception)
            self.assertEqual(app.button[0].label,'Analizar mensajes pendientes')
            self.assertTrue(app.button[0].disabled)
            self.assertTrue(any('Distribución del sentimiento' in m.value for m in app.markdown))
            self.assertTrue(any('Evolución del sentimiento' in m.value for m in app.markdown))
            self.assertTrue(any('Temas principales' in m.value for m in app.markdown))
            app.selectbox[3].select('Negativo').run()
            self.assertFalse(app.exception)
            self.assertTrue(any('Perfil político' in m.value for m in app.markdown))
            post.assert_not_called()


if __name__=='__main__':
    unittest.main()
