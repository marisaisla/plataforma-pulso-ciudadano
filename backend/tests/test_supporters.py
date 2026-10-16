import os
import time
import unittest
import test_tasks
from backend.main import Message
from backend import supporters


@unittest.skipUnless(os.environ.get('API_TEST_POSTGRES')=='1','Activar API_TEST_POSTGRES=1')
class SupporterTests(unittest.TestCase):
    def setUp(self):
        test_tasks.TaskTests.setUp(self)
        for sql in [
            'CREATE TEMP TABLE profiles (id bigint,name text)',
            'CREATE TEMP TABLE supporter_sessions (worker_id bigint PRIMARY KEY,profile_id bigint,started_at bigint,expires_at bigint)',
            'CREATE TEMP TABLE field_report_sessions (worker_id bigint)',
            'CREATE TEMP TABLE field_need_sessions (worker_id bigint)',
            "CREATE TEMP TABLE supporters (id bigserial PRIMARY KEY,profile_id bigint,worker_id bigint,name text,phone text,voter_key text,state text,municipality text,electoral_section text,registration_consent bigint,messaging_consent bigint,source_chat_id bigint,source_message_id bigint,UNIQUE(profile_id,phone),UNIQUE(profile_id,voter_key),UNIQUE(source_chat_id,source_message_id))",
        ]: self.conn.execute(sql)
        self.conn.execute("INSERT INTO public.profiles VALUES (10,'Campaña de prueba'),(11,'Otra')")
        self.conn.execute("INSERT INTO public.field_role_permissions VALUES ('field','supporters.submit','own')")

    def message(self,text=None,mid=100):
        return Message.model_validate({'message_id':mid,'date':int(time.time()),'from':{'id':123,'is_bot':False},'chat':{'id':123,'type':'private'},'text':text or 'Nombre: Persona de prueba\nTeléfono: 5512345678\nEstado: Sonora\nMunicipio: Hermosillo\nSección: 123\nClave de elector: ABCDEF123456789012\nRegistro: SI\nMensajes: NO'})

    def start(self):
        return supporters.process(self.conn,self.message('/simpatizante 10',mid=299),['/simpatizante','10'])

    def test_capture_and_retry_do_not_duplicate(self):
        self.start()
        msg=self.message()
        first=supporters.process(self.conn,msg,[])
        self.assertIn('S-000001',first['reply'])
        self.assertEqual(first,supporters.process(self.conn,msg,[]))
        row=self.conn.execute('SELECT * FROM public.supporters').fetchone()
        self.assertEqual(row['phone'],'+525512345678')
        self.assertEqual(row['messaging_consent'],0)

    def test_consent_and_territory_rejected_without_save(self):
        self.start()
        for old,new in [('Registro: SI','Registro: NO'),('Municipio: Hermosillo','Municipio: Otro'),('Mensajes: NO','Mensajes: TALVEZ')]:
            result=supporters.process(self.conn,self.message(self.message().text.replace(old,new)),[])
            self.assertNotIn('S-000',result['reply'])
        self.assertEqual(self.conn.execute('SELECT count(*) AS n FROM public.supporters').fetchone()['n'],0)

    def test_campaign_filter_and_cancel(self):
        self.assertEqual(supporters.campaigns(self.conn,1),[(10,'Campaña de prueba')])
        self.start()
        result=supporters.process(self.conn,self.message('/cancelar'),['/cancelar'])
        self.assertIn('cancelada',result['reply'])
        self.assertIsNone(supporters.process(self.conn,self.message(),[]))

    def test_expiration_and_duplicate_phone(self):
        self.start()
        self.conn.execute('UPDATE public.supporter_sessions SET expires_at=0')
        self.assertIn('venció',supporters.process(self.conn,self.message(),[])['reply'])
        self.start()
        supporters.process(self.conn,self.message(),[])
        self.start()
        self.assertIn('ya están registrados',supporters.process(self.conn,self.message(mid=101),[])['reply'])
