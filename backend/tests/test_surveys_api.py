"""Recorrido HTTP real sobre tablas PostgreSQL temporales, sin modificar datos operativos."""
import os
import unittest
from unittest.mock import patch

import test_operations


@unittest.skipUnless(os.environ.get('API_TEST_POSTGRES') == '1', 'Activar API_TEST_POSTGRES=1')
class SurveyAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_operations.OperationTests.setUpClass()
        cls.hashed = test_operations.OperationTests.hashed

    def setUp(self):
        test_operations.OperationTests.setUp(self)
        for role, scope in [('administrator', 'all'), ('field', 'own')]:
            self.conn.execute('INSERT INTO public.field_role_permissions VALUES (%s,%s,%s)', (role, 'reports.submit', scope))
        self.tid = self.activity()
        self.path = f'/api/v1/activities/{self.tid}'
        self.assertEqual(self.client.put(self.path+'/assignment', headers=self.headers, json={'worker_id': 2}).status_code, 204)
        self.payload = dict(title='Visitas', description='Prueba', mode='multiple', publish=False,
                            questions=[dict(label='Calificación', type='number', required=True, min=0, max=10,
                                            metric='average', metric_label='Promedio')])

    activity = test_operations.OperationTests.activity

    def prepare(self, mode='multiple'):
        self.payload.update(mode=mode, publish=True)
        result = self.client.post(self.path+'/questionnaires', headers=self.headers, json=self.payload)
        self.assertEqual(result.status_code, 201, result.text)
        self.qid = result.json()['id']
        result = self.client.put(self.path+'/questionnaire', headers=self.headers,
                                 json=dict(questionnaire_id=self.qid, target=1 if mode == 'single' else 10))
        self.assertEqual(result.status_code, 204, result.text)
        data = self.client.get(self.path+'/questionnaires', headers=self.field).json()
        self.body = dict(assignment_generation=data['task']['assignment_generation'],
                         survey_generation=data['assignment']['generation'], submission_key='unique-request-key-0001',
                         answers={'q1': 8})
        return data

    def test_publish_capture_results_and_idempotency(self):
        data = self.prepare()
        self.assertTrue(data['task']['can_capture'])
        self.assertFalse(data['can_manage'])
        self.assertEqual(data['questionnaires'], [])
        result = self.client.get(self.path+'/questionnaire/capture', headers=self.field,
                                 params=dict(assignment=self.body['assignment_generation'], survey=self.body['survey_generation']))
        self.assertEqual(result.status_code, 200, result.text)
        first = self.client.post(self.path+'/questionnaire/responses', headers=self.field, json=self.body)
        self.assertEqual(first.status_code, 200, first.text)
        duplicate = self.client.post(self.path+'/questionnaire/responses', headers=self.field, json=self.body)
        self.assertEqual(first.json(), duplicate.json())
        self.body.update(submission_key='unique-request-key-0002', answers={'q1': 4})
        self.assertEqual(self.client.post(self.path+'/questionnaire/responses', headers=self.field, json=self.body).status_code, 200)
        values = self.client.get(self.path+'/questionnaire/results', headers=self.headers).json()[0]
        metrics = {m['Indicador']: m['Valor'] for m in values['metrics']}
        self.assertEqual(metrics, {'Cuestionarios enviados': 2, 'Avance de la meta (%)': 20, 'Promedio': 6})
        self.assertEqual(len(values['responses']), 2)

    def test_draft_edit_and_published_definition_is_immutable(self):
        result = self.client.post(self.path+'/questionnaires', headers=self.headers, json=self.payload)
        self.assertEqual(result.status_code, 201, result.text)
        qid = result.json()['id']
        self.assertEqual(self.client.put(self.path+'/questionnaire', headers=self.headers,
                                         json=dict(questionnaire_id=qid)).status_code, 422)
        self.payload.update(title='Publicado', publish=True)
        self.assertEqual(self.client.put(self.path+f'/questionnaires/{qid}', headers=self.headers, json=self.payload).status_code, 200)
        self.payload['title'] = 'Intento de cambio'
        self.assertEqual(self.client.put(self.path+f'/questionnaires/{qid}', headers=self.headers, json=self.payload).status_code, 422)
        self.assertEqual(self.conn.execute('SELECT title FROM public.field_questionnaires WHERE id=%s', (qid,)).fetchone()['title'], 'Publicado')

    def test_authorization_validation_and_assignment_generation(self):
        self.prepare()
        self.assertEqual(self.client.get(self.path+'/questionnaires').status_code, 401)
        self.assertEqual(self.client.post(self.path+'/questionnaires', headers=self.field, json=self.payload).status_code, 403)
        self.assertEqual(self.client.post(self.path+'/questionnaire/responses', headers=self.headers, json=self.body).status_code, 403)
        invalid = dict(self.body, answers={'q1': 11})
        self.assertEqual(self.client.post(self.path+'/questionnaire/responses', headers=self.field, json=invalid).status_code, 422)
        self.assertEqual(self.client.post(self.path+'/questionnaire/responses', headers=self.field, json=dict(self.body, worker_id=1)).status_code, 422)
        self.assertEqual(self.conn.execute('SELECT count(*) AS n FROM public.field_survey_responses').fetchone()['n'], 0)
        self.client.put(self.path+'/assignment', headers=self.headers, json={'worker_id': None})
        self.client.put(self.path+'/assignment', headers=self.headers, json={'worker_id': 2})
        self.assertEqual(self.client.post(self.path+'/questionnaire/responses', headers=self.field, json=self.body).status_code, 403)

    def test_single_response_version_change_and_historical_results(self):
        self.prepare('single')
        self.assertEqual(self.client.post(self.path+'/questionnaire/responses', headers=self.field, json=self.body).status_code, 200)
        self.body['submission_key'] = 'second-interview-key-0002'
        self.assertEqual(self.client.post(self.path+'/questionnaire/responses', headers=self.field, json=self.body).status_code, 422)
        new = self.client.post(self.path+'/questionnaires', headers=self.headers, json=self.payload).json()['id']
        self.client.put(self.path+'/questionnaire', headers=self.headers, json=dict(questionnaire_id=new))
        self.assertEqual(self.client.post(self.path+'/questionnaire/responses', headers=self.field, json=self.body).status_code, 403)
        self.assertEqual(len(self.client.get(self.path+'/questionnaire/results', headers=self.headers).json()), 2)

    def test_telegram_api_returns_authenticated_form_link(self):
        self.prepare()
        self.conn.execute('UPDATE public.field_workers SET telegram_user_id=123,telegram_chat_id=123 WHERE id=2')
        from backend.main import app, database
        app.dependency_overrides[database] = lambda: self.conn
        update = dict(update_id=1, message={'message_id': 1, 'from': {'id': 123, 'is_bot': False},
                                           'chat': {'id': 123, 'type': 'private'}, 'text': '/mis_tareas'})
        with patch('backend.main.setting', return_value='integration-test-secret'), \
             patch('backend.surveys.setting', return_value='https://campo.example/go2win'):
            result = self.client.post('/api/v1/integrations/telegram/updates',
                                      headers={'X-Telegram-Bot-Api-Secret-Token': 'integration-test-secret'}, json=update)
            self.assertEqual(result.status_code, 200, result.text)
            buttons = [b for row in result.json()['reply_markup']['inline_keyboard'] for b in row if 'url' in b]
            self.assertEqual(len(buttons), 1)
            self.assertIn(f'field_survey={self.tid}', buttons[0]['url'])
            self.assertNotIn('admin-session', buttons[0]['url'])
            self.assertNotIn('integration-test-secret', buttons[0]['url'])
            self.assertEqual(self.client.get(self.path+'/questionnaire/capture',
                            params=dict(assignment=self.body['assignment_generation'], survey=self.body['survey_generation'])).status_code, 401)

    def test_scope_revocation_blocks_capture_and_results(self):
        self.prepare()
        self.client.post(self.path+'/questionnaire/responses', headers=self.field, json=self.body)
        self.conn.execute('DELETE FROM public.field_worker_scopes WHERE worker_id=2')
        self.assertEqual(self.client.post(self.path+'/questionnaire/responses', headers=self.field, json=self.body).status_code, 403)
        self.assertEqual(self.client.get(self.path+'/questionnaire/results', headers=self.field).status_code, 403)
        self.assertEqual(len(self.client.get(self.path+'/questionnaire/results', headers=self.headers).json()[0]['responses']), 1)
