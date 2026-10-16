import time
import unittest
from unittest.mock import Mock
from backend.help import help_reply
from backend.telegram import process_message
from backend.main import Message


class HelpTests(unittest.TestCase):
    def connection(self,worker=True,active=1,expired=False):
        conn=Mock()
        def execute(sql,params=()):
            self.assertTrue(sql.startswith('SELECT'))
            result=Mock()
            if 'field_workers' in sql:
                result.fetchone.return_value={'id':1,'active':active,'role_key':'field'} if worker else None
            elif 'field_role_permissions' in sql:
                result.fetchall.return_value=[{'permission_key':'tasks.view'}]
            elif 'field_report_sessions' in sql:
                result.fetchone.return_value={'expires_at':int(time.time())+(-1 if expired else 900),'selection_id':'incident:1'}
            else:
                result.fetchone.return_value=None
            return result
        conn.execute.side_effect=execute
        return conn

    def test_help_filters_permissions_and_preserves_capture(self):
        reply=help_reply(self.connection(),123)['reply']
        self.assertIn('/mis_tareas',reply)
        self.assertNotIn('/simpatizante',reply)
        self.assertIn('Captura pendiente: incidencia',reply)
        self.assertIn('no renueva',reply)

    def test_unlinked_and_inactive(self):
        self.assertIn('/start CODIGO',help_reply(self.connection(worker=False),123)['reply'])
        self.assertIn('desactivado',help_reply(self.connection(active=0),123)['reply'])

    def test_expired_capture_not_shown(self):
        self.assertNotIn('Captura pendiente',help_reply(self.connection(expired=True),123)['reply'])

    def test_unknown_command_shows_help_without_mutation(self):
        message=Message.model_validate({'message_id':1,'from':{'id':123,'is_bot':False},'chat':{'id':123,'type':'private'},'text':'/desconocido'})
        reply=process_message(self.connection(),message)
        self.assertEqual(reply['status'],'help')
        self.assertIn('Comando desconocido',reply['reply'])
