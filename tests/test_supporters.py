import time
import unittest
from unittest.mock import patch
import test_field_tasks as task_tests
from services import field_staff as staff, field_permissions as access, supporters
from scripts import integrador_telegram as bot


class SupporterTests(unittest.TestCase):
    setUp = task_tests.TaskTests.setUp
    message = task_tests.TaskTests.message
    sql = task_tests.TaskTests.sql

    def start(self):
        return staff.telegram_reply(self.message(101, '/simpatizante 1'))

    def data(self, mid=30):
        return {**self.message(101, 'Nombre: Persona ficticia\nTeléfono: 6621234567\nEstado: Sonora\n'
            'Municipio: Hermosillo\nSección: 123\nClave de elector: ABCDEF90010126H000\nRegistro: SI\nMensajes: NO'),
            'message_id': mid, 'date': int(time.time())}

    def test_register_retry_normalization_consent_and_catalog(self):
        from web_test_helpers import admin_session
        self.assertIn('Clave de elector', self.start())
        first = staff.telegram_reply(self.data())
        self.assertIn('S-000001', first)
        self.assertEqual(first, staff.telegram_reply(self.data()))
        row = supporters.catalog(admin_session())[0]
        self.assertEqual((row['phone'],row['voter_key'],row['messaging_consent']),
                         ('+526621234567','ABCDEF90010126H000',0))
        self.assertEqual(self.sql('SELECT COUNT(*) FROM supporters')[0][0], 1)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM supporter_sessions')[0][0], 0)
        with self.assertRaises(PermissionError):
            supporters.catalog('invalid')

    def test_duplicate_phone_or_key_never_overwrites(self):
        self.start()
        staff.telegram_reply(self.data())
        self.start()
        self.assertIn('ya están registrados', staff.telegram_reply(self.data(31)))
        msg = self.data(32)
        msg['text'] = msg['text'].replace('6621234567','6629876543')
        self.assertIn('ya están registrados', staff.telegram_reply(msg))
        self.assertEqual(self.sql('SELECT COUNT(*) FROM supporters')[0][0], 1)

    def test_invalid_fields_and_missing_consent_keep_capture(self):
        self.start()
        for old,new,expected in [('Registro: SI','Registro: NO','autorización'),
                                 ('Mensajes: NO','Mensajes: tal vez','Mensajes: SI o NO'),
                                 ('ABCDEF90010126H000','bad','18 letras'),
                                 ('6621234567','abc','Teléfono inválido')]:
            msg = self.data()
            msg['text'] = msg['text'].replace(old,new)
            self.assertIn(expected, staff.telegram_reply(msg))
        self.assertEqual(self.sql('SELECT COUNT(*) FROM supporters')[0][0], 0)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM supporter_sessions')[0][0], 1)

    def test_permissions_expiry_cancel_and_mutually_exclusive_capture(self):
        self.start()
        access.remove_scope(self.worker,1,'Sonora','Hermosillo')
        self.assertIn('No tienes permiso',staff.telegram_reply(self.data()))
        access.add_scope(self.worker,1,'Sonora','Hermosillo')
        self.sql('UPDATE supporter_sessions SET expires_at=0')
        self.assertIn('venció',staff.telegram_reply(self.data()))
        self.start()
        staff.telegram_reply(self.message(101,'/reportar'))
        self.assertEqual(self.sql('SELECT COUNT(*) FROM supporter_sessions')[0][0],0)
        self.start()
        staff.telegram_reply(self.message(101,'/cancelar'))
        self.assertEqual(self.sql('SELECT COUNT(*) FROM supporter_sessions')[0][0],0)
        self.assertIn('No puedes',staff.telegram_reply(self.message(101,'/simpatizante 999')))

    def test_send_failure_and_restart_do_not_duplicate(self):
        self.start()
        with patch.object(bot.transport,'api',side_effect=bot.transport.TelegramError('Network')):
            with self.assertRaises(bot.transport.TelegramError):
                bot.process_update({'message':self.data()})
        staff.initialize_staff()
        with patch.object(bot.transport,'api') as api:
            bot.process_update({'message':self.data()})
            self.assertIn('S-000001',api.call_args.kwargs['text'])
        self.assertEqual(self.sql('SELECT COUNT(*) FROM supporters')[0][0],1)

    def test_catalog_scope_revocation_and_other_worker_isolation(self):
        from test_web_portal import PortalTests
        from services import web_auth as auth
        self.start()
        staff.telegram_reply(self.data())
        admin, field = PortalTests.tokens(self)
        self.assertEqual(len(supporters.catalog(field)),1)
        auth.set_account(admin,self.other,'other','Contraseña ficticia inicial 123')
        temporary = auth.login('other','Contraseña ficticia inicial 123')
        auth.change_password(temporary,'Contraseña ficticia inicial 123','Contraseña ficticia personal 456')
        other = auth.login('other','Contraseña ficticia personal 456')
        self.assertFalse(supporters.catalog(other))
        access.remove_scope(self.worker,1,'Sonora','Hermosillo')
        self.assertFalse(supporters.catalog(field))

    def test_catalog_ui_search(self):
        from streamlit.testing.v1 import AppTest
        from web_test_helpers import admin_session
        self.start()
        staff.telegram_reply(self.data())
        app = AppTest.from_string('from services.supporters_ui import render_supporters\nrender_supporters()', default_timeout=10)
        app.session_state['_web_token'] = admin_session()
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.dataframe[0].value),1)
        app.checkbox[0].check().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.dataframe),0)


if __name__ == '__main__':
    unittest.main()
