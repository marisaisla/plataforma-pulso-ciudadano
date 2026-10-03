import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from services import database
from services.field_staff import initialize_staff, create_worker, list_workers
from services.field_permissions import list_scopes
from web_test_helpers import admin_session


class StaffUiTests(unittest.TestCase):
    def test_role_and_scope_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'ui.db'
            with closing(sqlite3.connect(path)) as conn, conn:
                conn.execute('CREATE TABLE profiles (id INTEGER PRIMARY KEY, name TEXT)')
                conn.execute("INSERT INTO profiles VALUES (1, 'Campaña de prueba')")
                conn.execute('CREATE TABLE territories (state TEXT, municipality TEXT)')
                conn.execute("INSERT INTO territories VALUES ('Sonora', 'Hermosillo')")
            with patch.dict(os.environ, {'DB_BACKEND': 'sqlite'}), patch.object(database, 'DB_PATH', path):
                initialize_staff()
                worker = create_worker('Persona de prueba', 'Equipo A')
                token = admin_session()
                app = AppTest.from_string('from services.field_staff_ui import render_field_staff\nrender_field_staff()')
                app.session_state['_web_token'] = token
                app.run()
                self.assertFalse(app.exception)
                next(s for s in app.selectbox if s.label == 'Rol').select('supervisor')
                next(b for b in app.button if b.label == 'Guardar rol y equipo').click().run()
                self.assertFalse(app.exception)
                self.assertEqual(list_workers()[0]['role_key'], 'supervisor')
                next(s for s in app.selectbox if s.label == 'Estado autorizado').select('Sonora').run()
                next(s for s in app.selectbox if s.label == 'Municipio autorizado').select('Hermosillo').run()
                next(b for b in app.button if b.label == 'Agregar alcance').click().run()
                self.assertFalse(app.exception)
                self.assertEqual(list_scopes(worker)[0]['municipality'], 'Hermosillo')
                next(b for b in app.button if b.label == 'Retirar este alcance').click().run()
                self.assertFalse(app.exception)
                self.assertFalse(list_scopes(worker))


if __name__ == '__main__':
    unittest.main()
