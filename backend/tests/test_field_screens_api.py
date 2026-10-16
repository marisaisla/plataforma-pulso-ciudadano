import os
import unittest
from unittest.mock import patch
import requests
from streamlit.testing.v1 import AppTest
import test_operations


@unittest.skipUnless(os.environ.get('API_TEST_POSTGRES')=='1','Activar API_TEST_POSTGRES=1')
class FieldScreensTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_operations.OperationTests.setUpClass()
        cls.hashed=test_operations.OperationTests.hashed

    def setUp(self):
        test_operations.OperationTests.setUp(self)
        self.conn.execute("INSERT INTO public.territories (id,territory_type,state,municipality) VALUES (10,'Estado','Sonora','Hermosillo')")
        self.conn.execute('INSERT INTO public.profile_territories (profile_id,territory_id) VALUES (10,10)')
        self.calls=[]
        def send(method,url,**kwargs):
            path='/api/v1/'+url.split('/api/v1/',1)[1]
            self.calls.append((method,path,kwargs.get('json')))
            http=self.client.request(method,path,headers=kwargs.get('headers'),json=kwargs.get('json'))
            response=requests.Response()
            response.status_code=http.status_code
            response._content=http.content
            return response
        transport=patch('services.profiles_api.requests.request',side_effect=send)
        transport.start()
        self.addCleanup(transport.stop)
        legacy_sql=patch('services.database.connection',side_effect=AssertionError('La pantalla no debe abrir conexiones SQL'))
        legacy_sql.start()
        self.addCleanup(legacy_sql.stop)

    def run_view(self,module,function):
        app=AppTest.from_string(f'from {module} import {function}\n{function}()',default_timeout=30)
        app.session_state['_web_token']='admin-session'
        app.run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        return app

    def test_action_plan_form_assignment_and_progress_use_api(self):
        app=self.run_view('services.action_plans_ui','render_action_plans')
        next(t for t in app.text_input if t.label=='Nombre de la actividad').set_value('Actividad desde pantalla')
        next(b for b in app.button if b.label=='Agregar actividad').click().run(timeout=30)
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertTrue(any(m=='POST' and p=='/api/v1/activities' for m,p,_ in self.calls))
        next(s for s in app.selectbox if s.label=='Trabajador registrado').select(2)
        next(b for b in app.button if b.label=='Guardar asignación de Telegram').click().run(timeout=30)
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertTrue(any(m=='PUT' and p.endswith('/assignment') for m,p,_ in self.calls))
        next(s for s in app.selectbox if s.label=='Estatus').select('En curso').run(timeout=30)
        next(b for b in app.button if b.label=='Guardar avance de la actividad').click().run(timeout=30)
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertTrue(any(m=='PATCH' and p.startswith('/api/v1/activities/') for m,p,_ in self.calls))

    def test_admin_screen_and_telegram_catalogs_use_api(self):
        self.run_view('services.field_staff_ui','render_user_administration')
        paths=[p for _,p,_ in self.calls]
        self.assertTrue(any(p.startswith('/api/v1/users?') for p in paths))
        self.run_view('services.telegram_operations_ui','render_telegram_operations')
        paths=[p for _,p,_ in self.calls]
        self.assertIn('/api/v1/supporters',paths)
        self.assertIn('/api/v1/needs',paths)
