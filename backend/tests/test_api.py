import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend.main import app, database


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.config = patch('backend.main.setting', side_effect=lambda k: {'API_ADMIN_KEY':'admin', 'TELEGRAM_WEBHOOK_SECRET':'telegram'}.get(k, ''))
        self.config.start()
        app.dependency_overrides[database] = lambda: object()

    def tearDown(self):
        app.dependency_overrides.clear()
        self.config.stop()

    def event(self, **changes):
        body = {'update_id': 1, 'message': {'message_id': 1, 'from': {'id':123, 'is_bot':False},
                'chat': {'id':123, 'type':'private'}, 'text':'/start example'}}
        body.update(changes)
        return body

    def test_authentication_prevents_database_access(self):
        app.dependency_overrides[database] = lambda: self.fail('Acceso a BD sin autenticación')
        self.assertEqual(self.client.post('/api/v1/integrations/telegram/updates', json=self.event()).status_code, 401)
        self.assertEqual(self.client.post('/api/v1/workers/1/telegram/activation-codes', headers={'X-API-Key':'wrong'}).status_code, 401)

    def test_strict_identity_validation(self):
        body = self.event()
        body['message']['from']['id'] = True
        response = self.client.post('/api/v1/integrations/telegram/updates', json=body,
                                    headers={'X-Telegram-Bot-Api-Secret-Token':'telegram'})
        self.assertEqual(response.status_code, 422)

    def test_unsupported_update_is_ignored(self):
        response = self.client.post('/api/v1/integrations/telegram/updates', json={'update_id':1,'edited_message':{}},
                                    headers={'X-Telegram-Bot-Api-Secret-Token':'telegram'})
        self.assertEqual(response.json()['status'], 'ignored')

    def test_success_response(self):
        with patch('backend.main.process_message', return_value={'status':'linked','reply':'ok'}):
            response = self.client.post('/api/v1/integrations/telegram/updates', json=self.event(),
                                        headers={'X-Telegram-Bot-Api-Secret-Token':'telegram'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'update_id':1,'status':'linked','reply':'ok'})

    def test_database_failure_does_not_expose_credentials(self):
        app.dependency_overrides[database] = lambda: (_ for _ in ()).throw(RuntimeError('password=secret'))
        response = self.client.get('/api/v1/health/database', headers={'X-API-Key':'admin'})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('secret', response.text)
