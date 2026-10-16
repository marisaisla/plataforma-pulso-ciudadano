import unittest
from unittest.mock import patch,Mock
import requests
from services.profiles_api import request,ProfileAPIError
from streamlit.testing.v1 import AppTest


SCRIPT='''
import streamlit as st
from unittest.mock import patch
from services.profile_screen import render_profiles
if 'api_calls' not in st.session_state: st.session_state.api_calls=[]
if 'profiles' not in st.session_state: st.session_state.profiles=[{'id':1,'name':'Perfil prueba','actor_type':'Persona','active':1,'notes':''}]
def fake(method,path,token,payload=None):
    st.session_state.api_calls.append((method,path,payload))
    if path=='/profiles/options': return {'actor_types':['Persona'],'conditions':['Candidato/a','Otro']}
    if method=='GET' and path=='/profiles': return st.session_state.profiles
    if method=='GET': return []
    if method=='PUT':
        selected_id=int(path.split('/')[2])
        profile=next(p for p in st.session_state.profiles if p['id']==selected_id)
        profile['active']=0
        return profile
    if path=='/profiles':
        st.session_state.profiles.append(dict(payload,id=2,active=1))
    return {'id':2}
with patch('services.profile_screen.request',side_effect=fake),patch('services.profile_screen.session_token',return_value='normal-session'):
    render_profiles()
'''


class ProfileScreenTests(unittest.TestCase):
    def test_button_deactivates_selected_profile_through_api(self):
        app=AppTest.from_string(SCRIPT).run(timeout=20)
        self.assertTrue(next(b for b in app.button if b.label=='Desactivar perfil').disabled)
        app.selectbox(key='profile_to_deactivate').select('Perfil prueba (#1)').run(timeout=20)
        next(b for b in app.button if b.label=='Desactivar perfil').click().run(timeout=20)
        self.assertFalse(app.exception)
        self.assertTrue(any(c[0]=='PUT' and c[1]=='/profiles/1/active' and c[2]=={'active':False} for c in app.session_state['api_calls']))
        self.assertEqual(app.session_state['profiles'][0]['active'],0)
    def test_screen_saves_profile_and_position_through_http_client(self):
        app=AppTest.from_string(SCRIPT).run(timeout=20)
        self.assertFalse(app.exception)
        app.text_input[0].set_value('Nuevo perfil')
        next(b for b in app.button if b.label=='Guardar perfil').click().run(timeout=20)
        self.assertFalse(app.exception)
        self.assertTrue(any(c[0]=='POST' and c[1]=='/profiles' for c in app.session_state['api_calls']))
        next(t for t in app.text_input if t.label=='Cargo o candidatura').set_value('Cargo de prueba')
        next(b for b in app.button if b.label=='Guardar trayectoria').click().run(timeout=20)
        self.assertFalse(app.exception)
        self.assertTrue(any(c[0]=='POST' and c[1].endswith('/positions') for c in app.session_state['api_calls']))

    def test_client_sends_session_and_never_falls_back_on_network_failure(self):
        response=Mock(status_code=200,ok=True)
        response.json.return_value=[]
        with patch('services.profiles_api.get_setting',return_value='http://127.0.0.1:8000'),patch('services.profiles_api.requests.request',return_value=response) as http:
            request('GET','/profiles','token-test')
            self.assertEqual(http.call_args.kwargs['headers']['Authorization'],'Bearer token-test')
        with patch('services.profiles_api.requests.request',side_effect=requests.ConnectionError()):
            with self.assertRaises(ProfileAPIError): request('GET','/profiles','token-test')

    def test_screen_api_failure_shows_error_without_forms(self):
        script='''
from unittest.mock import patch
from services.profile_screen import render_profiles
from services.profiles_api import ProfileAPIError
with patch('services.profile_screen.request',side_effect=ProfileAPIError('API no disponible')),patch('services.profile_screen.session_token',return_value='session'):
    render_profiles()
'''
        app=AppTest.from_string(script).run(timeout=20)
        self.assertFalse(app.exception)
        self.assertIn('API no disponible',app.error[0].value)
        self.assertEqual(len(app.text_input),0)
