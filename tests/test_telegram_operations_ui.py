import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest


class TelegramOperationsTests(unittest.TestCase):
    def run_screen(self,linked=False):
        worker={'id':4,'name':'Trabajador prueba','team':'Equipo','role_key':'field','active':1,
                'telegram_user_id':123 if linked else None}
        with patch('services.telegram_operations_ui.require_admin'),\
             patch('services.telegram_operations_ui.list_workers',return_value=[worker]),\
             patch('services.supporters_ui.render_supporters'),patch('services.field_needs_ui.render_needs'),\
             patch('services.telegram_operations_ui.issue_code',return_value='code-test') as issue,\
             patch('services.telegram_operations_ui.unlink_worker') as unlink:
            app=AppTest.from_string('from services.telegram_operations_ui import render_telegram_operations\nrender_telegram_operations()').run(timeout=20)
            self.assertFalse(app.exception)
            self.assertEqual([t.label for t in app.tabs],['Vinculación de Telegram','Simpatizantes','Necesidades territoriales'])
            self.assertNotIn('Registrar trabajador',[b.label for b in app.button])
            self.assertNotIn('Rol',[s.label for s in app.selectbox])
            if linked:
                button=next(b for b in app.button if b.label=='Desvincular Telegram')
                self.assertTrue(button.disabled)
                app.checkbox[0].check().run(timeout=20)
                next(b for b in app.button if b.label=='Desvincular Telegram').click().run(timeout=20)
                unlink.assert_called_once_with(4)
            else:
                next(b for b in app.button if b.label=='Generar código de activación').click().run(timeout=20)
                issue.assert_called_once_with(4)
                self.assertEqual(app.code[0].value,'/start code-test')
            self.assertFalse(app.exception)

    def test_issue_code_is_in_telegram_screen(self): self.run_screen()
    def test_unlink_requires_explicit_selection(self): self.run_screen(linked=True)

    def test_both_screens_require_administrator(self):
        for module,function in [('services.field_staff_ui','render_user_administration'),('services.telegram_operations_ui','render_telegram_operations')]:
            script=f'from {module} import {function}\n{function}()'
            # st.stop evita que se consulte la base sin autorización.
            with patch(module+'.require_admin',side_effect=lambda:__import__('streamlit').stop()) as require:
                app=AppTest.from_string(script).run(timeout=20)
                require.assert_called_once()
                self.assertFalse(app.button)
