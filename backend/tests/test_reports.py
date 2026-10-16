import time
import os
import unittest
import io
import base64
from PIL import Image
from backend.main import Message
from backend.reports import menu, select, capture, process
import test_tasks


@unittest.skipUnless(os.environ.get('API_TEST_POSTGRES')=='1', 'Activar API_TEST_POSTGRES=1')
class ReportTests(unittest.TestCase):
    def setUp(self):
        test_tasks.TaskTests.setUp(self)
        for sql in [
            'CREATE TEMP TABLE field_report_sessions (worker_id bigint PRIMARY KEY,task_id bigint,generation text,selection_id text,started_at bigint,expires_at bigint)',
            'CREATE TEMP TABLE field_report_selections (callback_id text PRIMARY KEY,worker_id bigint)',
            "CREATE TEMP TABLE field_reports (id bigserial PRIMARY KEY,task_id bigint,worker_id bigint,generation text,body text,source_chat_id bigint,source_message_id bigint,status text DEFAULT 'pending',UNIQUE(source_chat_id,source_message_id))",
            'CREATE TEMP TABLE supporter_sessions (worker_id bigint)',
            'CREATE TEMP TABLE field_need_sessions (worker_id bigint)',
            'CREATE TEMP TABLE field_report_photos (report_id bigint PRIMARY KEY,file_id text,file_unique_id text,content_base64 text)',
        ]:
            self.conn.execute(sql)
        self.conn.execute("INSERT INTO public.field_role_permissions VALUES ('field','reports.submit','own')")
        self.conn.execute("UPDATE public.field_task_assignments SET received_at='2026-10-12 10:00:00' WHERE task_id=1")

    def message(self,**changes):
        body={'message_id':50,'date':int(time.time()),'from':{'id':123,'is_bot':False},'chat':{'id':123,'type':'private'},'text':'Avance de prueba'}
        body.update(changes)
        return Message.model_validate(body)

    def test_report_saved_once_and_selection_cannot_reopen(self):
        self.assertEqual(len(menu(self.conn,123)['reply_markup']['inline_keyboard']),1)
        select(self.conn,123,1,'abc123','selection1')
        first=capture(self.conn,self.message())
        self.assertIn('R-000001',first)
        self.assertEqual(first,capture(self.conn,self.message()))
        self.assertEqual(self.conn.execute('SELECT count(*) AS n FROM public.field_reports').fetchone()['n'],1)
        self.assertIn('ya fue atendida',select(self.conn,123,1,'abc123','selection1'))

    def test_cancel_and_expiration_do_not_save(self):
        select(self.conn,123,1,'abc123','s1')
        self.conn.execute('UPDATE public.field_report_sessions SET expires_at=0')
        self.assertIn('venció',capture(self.conn,self.message()))
        select(self.conn,123,1,'abc123','s2')
        process(self.conn,self.message(text='/cancelar'),['/cancelar'])
        self.assertIsNone(capture(self.conn,self.message()))

    def test_stale_assignment_rejects_capture(self):
        select(self.conn,123,1,'abc123','s1')
        self.conn.execute("UPDATE public.field_task_assignments SET generation='changed' WHERE task_id=1")
        self.assertIn('cambiaron',capture(self.conn,self.message()))

    def test_photo_and_old_message_keep_session_without_saving(self):
        select(self.conn,123,1,'abc123','s1')
        self.assertIn('anterior',capture(self.conn,self.message(date=1)))
        self.assertIn('texto',capture(self.conn,self.message(photo=[{'file_id':'x','file_unique_id':'u','width':10,'height':10}])))
        self.assertEqual(self.conn.execute('SELECT count(*) AS n FROM public.field_reports').fetchone()['n'],0)

    def test_unreceived_or_foreign_task_cannot_be_selected(self):
        from fastapi import HTTPException
        for tid in (2,3,4,5,6):
            with self.assertRaises(HTTPException): select(self.conn,123,tid,'abc123','s'+str(tid))

    def photo_message(self,**changes):
        return self.message(photo=[{'file_id':'small','file_unique_id':'s','width':1,'height':1},
                                   {'file_id':'large','file_unique_id':'l','width':10,'height':10}],
                            caption='Avance con fotografía',**changes)

    def jpeg(self):
        buffer=io.BytesIO()
        Image.new('RGB',(10,10)).save(buffer,format='JPEG')
        return buffer.getvalue()

    def test_photo_and_report_saved_once(self):
        select(self.conn,123,1,'abc123','s1')
        raw=self.jpeg()
        def loader(file_id):
            self.assertEqual(file_id,'large')
            return raw
        first=capture(self.conn,self.photo_message(),loader)
        row=self.conn.execute('SELECT * FROM public.field_report_photos').fetchone()
        self.assertEqual(base64.b64decode(row['content_base64']),raw)
        self.assertEqual(first,capture(self.conn,self.photo_message(),lambda _:self.fail('No descargar duplicado')))

    def test_invalid_photo_and_album_keep_capture(self):
        select(self.conn,123,1,'abc123','s1')
        self.assertIn('JPEG',capture(self.conn,self.photo_message(),lambda _:b'not an image'))
        self.assertIn('álbum',capture(self.conn,self.photo_message(media_group_id='album'),lambda _:self.fail('No descargar álbum')))
        self.assertEqual(self.conn.execute('SELECT count(*) AS n FROM public.field_reports').fetchone()['n'],0)
        self.assertEqual(self.conn.execute('SELECT count(*) AS n FROM public.field_report_sessions').fetchone()['n'],1)

    def test_download_failure_does_not_save(self):
        select(self.conn,123,1,'abc123','s1')
        def loader(_): raise RuntimeError('Descarga fallida')
        with self.assertRaises(RuntimeError): capture(self.conn,self.photo_message(),loader)
        self.assertEqual(self.conn.execute('SELECT count(*) AS n FROM public.field_reports').fetchone()['n'],0)

    def test_incident_has_separate_permission_and_idempotent_folio(self):
        self.conn.execute("INSERT INTO public.field_role_permissions VALUES ('field','incidents.submit','own')")
        self.conn.execute("DELETE FROM public.field_role_permissions WHERE permission_key='reports.submit'")
        self.assertIn('incidentselect:',menu(self.conn,123,incident=True)['reply_markup']['inline_keyboard'][0][0]['callback_data'])
        select(self.conn,123,1,'abc123','incident1',incident=True)
        result=capture(self.conn,self.message(text='Se bloqueó el acceso.'))
        self.assertIn('Incidencia R-',result)
        self.assertEqual(result,capture(self.conn,self.message(text='Se bloqueó el acceso.')))
        self.assertEqual(self.conn.execute('SELECT body FROM public.field_reports').fetchone()['body'],'[INCIDENCIA]\nSe bloqueó el acceso.')

    def test_incident_photo_and_length_limit(self):
        self.conn.execute("INSERT INTO public.field_role_permissions VALUES ('field','incidents.submit','own')")
        select(self.conn,123,1,'abc123','incident1',incident=True)
        self.assertIn('supera',capture(self.conn,self.message(text='x'*4000)))
        self.assertIn('Incidencia',capture(self.conn,self.photo_message(),lambda _:self.jpeg()))
        self.assertIsNotNone(self.conn.execute('SELECT report_id FROM public.field_report_photos').fetchone())

    def test_incident_requires_permission_and_receipt(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException): select(self.conn,123,1,'abc123','s',incident=True)
        self.conn.execute("INSERT INTO public.field_role_permissions VALUES ('field','incidents.submit','own')")
        with self.assertRaises(HTTPException): select(self.conn,123,2,'abc123','s',incident=True)
