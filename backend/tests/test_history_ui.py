"""Prueba de render de la pantalla sin SQL ni archivos electorales reales."""
import unittest


class HistoryUITests(unittest.TestCase):
    def test_empty_history_renders_and_does_not_write(self):
        from streamlit.testing.v1 import AppTest
        script = '''
from unittest.mock import patch
from services.history_ui import render_history
def respond(method,path,token,payload=None):
    assert method == 'GET', 'Renderizar la pantalla no debe escribir'
    assert path.startswith('/history/')
    return []
with patch('services.history_ui.session_token', return_value='test-token'), patch('services.history_ui.request', side_effect=respond):
    render_history()
'''
        app = AppTest.from_string(script).run(timeout=20)
        self.assertEqual(len(app.exception), 0, str(app.exception))
        self.assertEqual(len(app.tabs), 5)
        self.assertTrue(any('Primero registra' in item.value for item in app.info))

    def test_api_error_is_visible_without_sql_fallback(self):
        from streamlit.testing.v1 import AppTest
        script = '''
from unittest.mock import patch
from services.history_ui import render_history
from services.profiles_api import ProfileAPIError
with patch('services.history_ui.session_token', return_value='test-token'), patch('services.history_ui.request', side_effect=ProfileAPIError('API no disponible',503)):
    render_history()
'''
        app = AppTest.from_string(script).run(timeout=20)
        self.assertEqual(len(app.exception), 0, str(app.exception))
        self.assertEqual(app.error[0].value, 'API no disponible')
