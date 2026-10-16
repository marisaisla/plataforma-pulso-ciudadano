import unittest
import httpx
from backend.telegram_polling import process_update, telegram_call, TransportError


class PollingTests(unittest.TestCase):
    def test_api_precedes_reply(self):
        calls = []
        def handler(request):
            calls.append(request.url.path)
            if request.url.host == 'localhost':
                self.assertEqual(request.headers['X-Telegram-Bot-Api-Secret-Token'], 'secret')
                return httpx.Response(200, json={'status':'linked', 'reply':'Vinculado'})
            return httpx.Response(200, json={'ok':True,'result':{}})
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            process_update(client, 'fake', 'http://localhost', 'secret', self.update())
        self.assertEqual(calls, ['/api/v1/integrations/telegram/updates', '/botfake/sendMessage'])

    def update(self):
        return {'update_id':1,'message':{'from':{'id':123,'is_bot':False},'chat':{'id':123,'type':'private'}}}

    def test_api_failure_never_sends_reply(self):
        with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503))) as client:
            with self.assertRaises(TransportError) as error:
                process_update(client, 'fake', 'http://localhost', 'secret', self.update())
        self.assertFalse(error.exception.fatal)

    def test_bad_credentials_stop_receiver(self):
        with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(401))) as client:
            with self.assertRaises(TransportError) as error:
                process_update(client, 'fake', 'http://localhost', 'secret', self.update())
        self.assertTrue(error.exception.fatal)

    def test_failed_reply_is_not_acknowledged(self):
        def handler(request):
            if request.url.host == 'localhost':
                return httpx.Response(200, json={'status':'already_linked','reply':'Vinculado'})
            raise httpx.ConnectError('token=fake', request=request)
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(TransportError) as error:
                process_update(client, 'fake', 'http://localhost', 'secret', self.update())
        self.assertNotIn('fake', str(error.exception))

    def test_telegram_conflict_stops_receiver(self):
        with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(409, json={'ok':False,'error_code':409}))) as client:
            with self.assertRaises(TransportError) as error:
                telegram_call(client, 'fake', 'getUpdates')
        self.assertTrue(error.exception.fatal)
