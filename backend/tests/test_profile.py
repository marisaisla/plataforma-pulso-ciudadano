import unittest
from unittest.mock import Mock
from backend.main import Message
from backend.telegram import process_message
from backend.profile import profile_reply


class ProfileTests(unittest.TestCase):
    def connection(self,active=1):
        conn=Mock()
        def execute(sql,params=()):
            self.assertTrue(sql.startswith('SELECT'), 'El perfil debe ser de solo lectura')
            result=Mock()
            result.fetchone.return_value={'id':1,'role_key':'field','team':'Equipo de prueba','active':active}
            result.fetchall.return_value=([{'label':'Consultar tareas','scope':'own'}] if 'field_role_permissions' in sql else [{'name':'Campaña','state':'Sonora','municipality':'Hermosillo'}])
            return result
        conn.execute.side_effect=execute
        return conn

    def test_aliases_show_profile_without_touching_sessions(self):
        conn=self.connection()
        def message(text):
            return Message.model_validate({'message_id':1,'from':{'id':123,'is_bot':False},'chat':{'id':123,'type':'private'},'text':text})
        first=process_message(conn,message('/perfil'))
        self.assertEqual(first,process_message(conn,message('/mi_perfil')))
        self.assertEqual(first['status'],'profile')
        self.assertIn('Personal de campo',first['reply'])
        self.assertIn('Hermosillo',first['reply'])
        self.assertIn('Consultar tareas: Propias',first['reply'])
        self.assertTrue(all('sessions' not in c.args[0] for c in conn.execute.call_args_list))

    def test_inactive_and_unlinked_are_rejected(self):
        self.assertEqual(profile_reply(self.connection(0),123)['status'],'rejected')
        conn=Mock()
        conn.execute.return_value.fetchone.return_value=None
        self.assertEqual(profile_reply(conn,123)['status'],'rejected')
