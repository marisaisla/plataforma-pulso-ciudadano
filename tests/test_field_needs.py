import time
import unittest
from unittest.mock import patch
import test_field_tasks as task_tests
from services import field_staff as staff, field_needs as needs, field_permissions as access
from scripts import integrador_telegram as bot


class NeedTests(unittest.TestCase):
    setUp = task_tests.TaskTests.setUp
    message = task_tests.TaskTests.message
    sql = task_tests.TaskTests.sql

    def start(self):
        return staff.telegram_reply(self.message(101,'/necesidad 1'))

    def data(self,mid=70):
        return {**self.message(101,'Estado: Sonora\nMunicipio: Hermosillo\nSección: 00123\n'
            'Origen: comentada\nNecesidad: Falta alumbrado\nEn dos calles.'),
            'date':int(time.time()),'message_id':mid}

    def test_capture_restart_retry_and_no_task_required(self):
        from web_test_helpers import admin_session
        self.sql('DELETE FROM field_task_assignments')
        self.assertIn('No necesitas una tarea',self.start())
        staff.initialize_staff()
        first = staff.telegram_reply(self.data())
        self.assertIn('N-000001',first)
        self.assertEqual(first,staff.telegram_reply(self.data()))
        row = needs.catalog(admin_session())[0]
        self.assertEqual((row['electoral_section'],row['origin'],row['description']),
                         ('123','comentada','Falta alumbrado\nEn dos calles.'))
        self.assertEqual(self.sql('SELECT count(*) FROM field_need_sessions')[0][0],0)
        self.assertEqual(self.sql('SELECT count(*) FROM field_needs')[0][0],1)

    def test_validation_scope_expiry_and_cancel(self):
        self.start()
        for old,new,expected in [('00123','0','sección es obligatoria'),('comentada','otra','Indica Origen'),
                                 ('Hermosillo','Otro municipio','No tienes permiso')]:
            msg = self.data()
            msg['text'] = msg['text'].replace(old,new)
            self.assertIn(expected,staff.telegram_reply(msg))
        self.assertEqual(self.sql('SELECT count(*) FROM field_needs')[0][0],0)
        self.sql('UPDATE field_need_sessions SET expires_at=0')
        self.assertIn('venció',staff.telegram_reply(self.data()))
        self.start()
        staff.telegram_reply(self.message(101,'/cancelar'))
        self.assertEqual(self.sql('SELECT count(*) FROM field_need_sessions')[0][0],0)
        self.start()
        access.remove_scope(self.worker,1,'Sonora','Hermosillo')
        self.assertIn('No tienes permiso',staff.telegram_reply(self.data()))

    def test_commands_and_callback_switch_capture(self):
        menu = staff.telegram_reply(self.message(101,'/necesidad'))
        cb = {'id':'need1','from':{'id':101},'message':{'chat':{'id':101,'type':'private'}},
              'data':menu['reply_markup']['inline_keyboard'][0][0]['callback_data']}
        self.assertIn('Necesidad:',staff.telegram_callback(cb))
        self.assertIn('Rol:',staff.telegram_reply(self.message(101,'/perfil')))
        staff.telegram_reply(self.message(101,'/simpatizante 1'))
        self.assertEqual(self.sql('SELECT count(*) FROM field_need_sessions')[0][0],0)
        staff.telegram_callback(cb)
        self.assertEqual(self.sql('SELECT count(*) FROM supporter_sessions')[0][0],0)
        staff.telegram_reply(self.message(101,'/incidencia'))
        self.assertEqual(self.sql('SELECT count(*) FROM field_need_sessions')[0][0],0)

    def test_send_failure_does_not_duplicate(self):
        self.start()
        with patch.object(bot.transport,'api',side_effect=bot.transport.TelegramError('Network')):
            with self.assertRaises(bot.transport.TelegramError):
                bot.process_update({'message':self.data()})
        with patch.object(bot.transport,'api') as api:
            bot.process_update({'message':self.data()})
            self.assertIn('N-000001',api.call_args.kwargs['text'])
        self.assertEqual(self.sql('SELECT count(*) FROM field_needs')[0][0],1)

    def test_needs_ui_filters_and_full_description(self):
        from streamlit.testing.v1 import AppTest
        from web_test_helpers import admin_session
        self.start()
        staff.telegram_reply(self.data())
        app = AppTest.from_string('from services.field_needs_ui import render_needs\nrender_needs()',default_timeout=10)
        app.session_state['_web_token'] = admin_session()
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.dataframe[0].value),1)
        next(s for s in app.selectbox if s.label=='Sección').select('123').run()
        self.assertFalse(app.exception)
        app.text_input[0].input('no existe').run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.dataframe),0)

    def test_coordinator_director_catalog_and_scope_revocation(self):
        from test_web_portal import PortalTests, PASSWORD, PERSONAL
        from services import web_auth as auth
        self.start()
        staff.telegram_reply(self.data())
        admin,field = PortalTests.tokens(self)
        self.assertEqual(len(needs.catalog(field)),1)
        for role in ('coordinator','director'):
            access.save_access(self.other,role,'Otro equipo')
            auth.set_account(admin,self.other,'manager',PASSWORD)
            temporary = auth.login('manager',PASSWORD)
            auth.change_password(temporary,PASSWORD,PERSONAL)
            token = auth.login('manager',PERSONAL)
            self.assertEqual(len(needs.catalog(token)),1)
            access.remove_scope(self.other,1,'Sonora','Hermosillo')
            self.assertFalse(needs.catalog(token))
            access.add_scope(self.other,1,'Sonora','Hermosillo')
        with self.assertRaises(PermissionError):
            needs.catalog('invalid')
