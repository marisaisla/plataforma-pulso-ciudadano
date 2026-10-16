import secrets
from unittest.mock import patch
import unittest

import test_field_tasks as task_tests
import test_web_portal as portal_tests
from services import field_surveys as surveys, field_tasks as tasks, field_staff as staff
from services import field_permissions as access, web_auth as auth


class SurveyTests(unittest.TestCase):
    setUp = task_tests.TaskTests.setUp
    message = task_tests.TaskTests.message
    callback = task_tests.TaskTests.callback
    sql = task_tests.TaskTests.sql
    tokens = portal_tests.PortalTests.tokens

    def fixture(self, mode='multiple'):
        self.admin, self.field = self.tokens()
        self.questions = [dict(label='Calificación', type='number', required=True, min=0, max=10,
                               metric='average', metric_label='Calificación promedio'),
                          dict(label='Personas atendidas', type='number', required=False, min=0,
                               metric='sum', metric_label='Total atendido'),
                          dict(label='Servicio', type='choice', required=True, options=['Agua', 'Luz'],
                               metric='count', metric_label='Respuestas de servicio'),
                          dict(label='Comentario', type='text', required=False)]
        self.qid = surveys.save_questionnaire(self.admin, 1, 'Servicios', 'Instrucciones', mode, self.questions, publish=True)
        surveys.assign_questionnaire(self.admin, 1, self.qid, 1 if mode == 'single' else 10)
        self.task, self.survey, _, _ = surveys.task_data(self.field, 1)
        self.answers = dict(q1=8, q2=2, q3='Agua', q4='')

    def submit(self, answers=None, key=None, token=None):
        return surveys.submit_response(token or self.field, 1, self.task['assignment_generation'],
                                       self.survey['generation'], key or secrets.token_hex(24),
                                       self.answers if answers is None else answers)

    def test_submission_idempotency_and_metrics(self):
        self.fixture()
        key = secrets.token_hex(24)
        first = self.submit(key=key)
        self.assertEqual(first, self.submit(key=key))
        self.submit(dict(q1=4, q2=None, q3='Luz'))
        values = {m['Indicador']: m['Valor'] for m in surveys.results(self.admin, 1)[0]['metrics']}
        self.assertEqual(values['Cuestionarios enviados'], 2)
        self.assertEqual(values['Avance de la meta (%)'], 20)
        self.assertEqual(values['Calificación promedio'], 6)
        self.assertEqual(values['Total atendido'], 2)
        self.assertEqual(values['Respuestas de servicio'], 2)
        self.assertEqual(self.sql('SELECT count(*) FROM field_survey_responses')[0][0], 2)

    def test_validation_is_atomic(self):
        self.fixture()
        for answers in [dict(q1=None, q3='Agua'), dict(q1=11, q3='Agua'), dict(q1=float('nan'), q3='Agua'),
                        dict(q1=True, q3='Agua'), dict(q1=1, q3='Inventada'), dict(q1=1, q3='Agua', q9='extra'),
                        dict(q1=1, q3='Agua', q4='a'*3001)]:
            with self.subTest(answers=answers), self.assertRaises(ValueError):
                self.submit(answers)
        self.assertEqual(self.sql('SELECT count(*) FROM field_survey_responses')[0][0], 0)

    def test_single_mode_and_immutable_published_version(self):
        self.fixture('single')
        self.submit()
        with self.assertRaises(ValueError):
            self.submit()
        with self.assertRaises(ValueError):
            surveys.save_questionnaire(self.admin, 1, 'Modificado', '', 'single', self.questions, self.qid)
        with self.assertRaises(ValueError):
            surveys.assign_questionnaire(self.admin, 1, self.qid, 2)
        newer = surveys.save_questionnaire(self.admin, 1, 'Nueva versión', '', 'single', self.questions, publish=True)
        surveys.assign_questionnaire(self.admin, 1, newer)
        with self.assertRaises(surveys.APIError):
            self.submit()
        self.assertEqual(len(surveys.results(self.admin, 1)), 2)

    def test_permissions_and_reassignment_invalidate_links(self):
        self.fixture()
        with self.assertRaises(surveys.APIError):
            surveys.save_questionnaire(self.field, 1, 'Sin permiso', '', 'single', self.questions)
        with self.assertRaises(surveys.APIError):
            surveys.assign_questionnaire(self.field, 1, self.qid)
        with self.assertRaises(surveys.APIError):
            self.submit(token=self.admin)
        tasks.assign_task_locally(1, self.other)
        tasks.assign_task_locally(1, self.worker)
        with self.assertRaises(surveys.APIError):
            self.submit()

    def test_revoked_scope_closed_task_and_expired_session(self):
        self.fixture()
        access.remove_scope(self.worker, 1, 'Sonora', 'Hermosillo')
        with self.assertRaises(surveys.APIError):
            self.submit()
        access.add_scope(self.worker, 1, 'Sonora', 'Hermosillo')
        self.sql("UPDATE territorial_action_plans SET status='Concluida' WHERE id=1")
        with self.assertRaises(surveys.APIError):
            self.submit()
        self.sql("UPDATE territorial_action_plans SET status='Pendiente' WHERE id=1")
        auth.logout(self.field)
        with self.assertRaises(surveys.APIError):
            self.submit()

    def test_draft_edit_and_same_assignment_preserve_generation(self):
        self.fixture()
        draft = surveys.save_questionnaire(self.admin, 1, 'Borrador', '', 'multiple', self.questions)
        with self.assertRaises(ValueError):
            surveys.assign_questionnaire(self.admin, 1, draft)
        surveys.save_questionnaire(self.admin, 1, 'Publicado', '', 'multiple', self.questions, draft, publish=True)
        surveys.assign_questionnaire(self.admin, 1, self.qid, 20)
        self.assertEqual(surveys.task_data(self.admin, 1)[1]['generation'], self.survey['generation'])
        self.submit()

    def test_telegram_buttons_require_https_and_contain_no_session(self):
        self.fixture()
        from contextlib import closing
        from services.database import connection
        from http_api_helpers import SQLiteAPI
        from backend.tasks import command_buttons
        with closing(connection()) as conn:
            api = SQLiteAPI(conn)
            with patch('backend.surveys.setting', return_value='https://campo.example/go2win'):
                result = command_buttons(api, 101, ['/mis_tareas'])
                buttons = [b for row in result['inline_keyboard'] for b in row if 'url' in b]
                self.assertEqual(len(buttons), 1)
                self.assertIn('field_survey=1', buttons[0]['url'])
                self.assertNotIn(self.field, buttons[0]['url'])
                detail = command_buttons(api, 101, ['/tarea', '1'])
                self.assertTrue(any('url' in b for row in detail['inline_keyboard'] for b in row))
            with patch('backend.surveys.setting', return_value='http://localhost:8501'):
                result = command_buttons(api, 101, ['/mis_tareas'])
                self.assertFalse(any('url' in b for row in result['inline_keyboard'] for b in row))

    def test_api_outage_has_no_direct_database_fallback(self):
        import requests
        with patch('services.profiles_api.requests.request', side_effect=requests.ConnectionError), \
             patch('services.database.connection', side_effect=AssertionError('No SQL in client')):
            with self.assertRaises(surveys.APIError):
                surveys.task_data('token', 1)

    def test_results_use_historical_scope_and_no_other_task_leak(self):
        self.fixture()
        self.submit()
        with self.assertRaises(surveys.APIError):
            surveys.results(self.field, 2)
        self.sql("UPDATE field_survey_responses SET municipality='Guaymas'")
        self.assertEqual(surveys.results(self.field, 1)[0]['responses'], [])
        self.assertEqual(len(surveys.results(self.admin, 1)[0]['responses']), 1)

    def test_coordinator_can_configure_only_team_tasks(self):
        self.fixture()
        access.save_access(self.worker, 'coordinator', 'Equipo A')
        access.save_access(self.other, 'field', 'Equipo A', self.worker)
        coordinator = auth.login('campo', 'Contraseña ficticia personal 456')
        tasks.assign_task_locally(1, self.other)
        qid = surveys.save_questionnaire(coordinator, 1, 'Equipo', '', 'multiple', self.questions, publish=True)
        surveys.assign_questionnaire(coordinator, 1, qid, 5)
        access.save_access(self.other, 'field', 'Equipo B')
        with self.assertRaises(surveys.APIError):
            surveys.save_questionnaire(coordinator, 1, 'No permitido', '', 'multiple', self.questions)

    def test_capture_ui_saves_and_starts_next_interview(self):
        self.fixture()
        from streamlit.testing.v1 import AppTest
        source = f'''import streamlit as st
from services.field_surveys_ui import render_capture
st.session_state['_web_token'] = {self.field!r}
render_capture(1, {self.task['assignment_generation']!r}, {self.survey['generation']!r})
'''
        at = AppTest.from_string(source).run()
        self.assertFalse(at.exception)
        at.number_input[0].set_value(7)
        at.selectbox[0].select('Agua')
        at.button[0].click().run()
        self.assertFalse(at.exception)
        self.assertTrue(at.success)
        self.assertEqual(self.sql('SELECT count(*) FROM field_survey_responses')[0][0], 1)
        at.button[0].click().run()
        self.assertFalse(at.exception)
        self.assertIsNone(at.number_input[0].value)
        self.assertIsNone(at.selectbox[0].value)

    def test_configurator_ui_publishes_assigns_and_previews(self):
        self.admin, self.field = self.tokens()
        from streamlit.testing.v1 import AppTest
        source = f'''import streamlit as st
from services.field_surveys_ui import render_task_surveys
st.session_state['_web_token'] = {self.admin!r}
render_task_surveys(1)
'''
        at = AppTest.from_string(source).run()
        self.assertFalse(at.exception)
        at.text_input(key='survey_builder_1_0_title').set_value('Visita a colonia')
        at.text_input(key='survey_builder_1_0_0_label').set_value('Personas atendidas')
        at.selectbox(key='survey_builder_1_0_0_type').select('number').run()
        self.assertFalse(at.exception)
        at.selectbox(key='survey_builder_1_0_0_metric_number').select('sum').run()
        at.text_input(key='survey_builder_1_0_0_metric_label').set_value('Personas atendidas')
        at.checkbox(key='survey_builder_1_0_preview').check().run()
        self.assertFalse(at.exception)
        at.button(key='survey_builder_1_0_publish').click().run()
        self.assertFalse(at.exception)
        self.assertEqual(self.sql("SELECT status FROM field_questionnaires")[0][0], 'published')
        next(b for b in at.button if b.label == 'Asignar cuestionario a la actividad').click().run()
        self.assertFalse(at.exception)
        self.assertEqual(self.sql('SELECT count(*) FROM field_task_surveys')[0][0], 1)


if __name__ == '__main__':
    unittest.main()
