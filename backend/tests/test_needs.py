import os
import time
import unittest
import test_supporters
from backend.main import Message
from backend import needs


@unittest.skipUnless(os.environ.get('API_TEST_POSTGRES')=='1','Activar API_TEST_POSTGRES=1')
class NeedTests(unittest.TestCase):
    def setUp(self):
        test_supporters.SupporterTests.setUp(self)
        self.conn.execute('ALTER TABLE pg_temp.field_need_sessions ADD COLUMN profile_id bigint, ADD COLUMN started_at bigint, ADD COLUMN expires_at bigint')
        self.conn.execute('CREATE UNIQUE INDEX temp_need_worker ON pg_temp.field_need_sessions(worker_id)')
        self.conn.execute('CREATE TEMP TABLE field_needs (id bigserial PRIMARY KEY,profile_id bigint,worker_id bigint,state text,municipality text,electoral_section text,description text,origin text,source_chat_id bigint,source_message_id bigint,UNIQUE(source_chat_id,source_message_id))')
        self.conn.execute("INSERT INTO public.field_role_permissions VALUES ('field','needs.submit','own')")

    def message(self,text=None,mid=500):
        return Message.model_validate({'message_id':mid,'date':int(time.time()),'from':{'id':123,'is_bot':False},'chat':{'id':123,'type':'private'},'text':text or 'Estado: Sonora\nMunicipio: Hermosillo\nSección: 00123\nOrigen: comentada\nNecesidad: Falta alumbrado.\nEn dos calles.'})

    def start(self):
        return needs.process(self.conn,self.message('/necesidad 10',499),['/necesidad','10'])

    def test_saved_once_and_multiline_description(self):
        self.start()
        first=needs.process(self.conn,self.message(),[])
        self.assertIn('N-000001',first['reply'])
        self.assertEqual(first,needs.process(self.conn,self.message(),[]))
        row=self.conn.execute('SELECT * FROM public.field_needs').fetchone()
        self.assertEqual(row['electoral_section'],'123')
        self.assertEqual(row['description'],'Falta alumbrado.\nEn dos calles.')

    def test_invalid_origin_section_and_territory_rejected(self):
        self.start()
        for old,new in [('Origen: comentada','Origen: otro'),('Sección: 00123','Sección: 0'),('Municipio: Hermosillo','Municipio: Otro')]:
            result=needs.process(self.conn,self.message(self.message().text.replace(old,new)),[])
            self.assertNotIn('N-000',result['reply'])
        self.assertEqual(self.conn.execute('SELECT count(*) AS n FROM public.field_needs').fetchone()['n'],0)

    def test_cancel_expiration_and_removed_permission(self):
        self.start()
        self.conn.execute('UPDATE public.field_need_sessions SET expires_at=0')
        self.assertIn('venció',needs.process(self.conn,self.message(),[])['reply'])
        self.start()
        self.conn.execute("DELETE FROM public.field_role_permissions WHERE permission_key='needs.submit'")
        self.assertIn('No tienes permiso',needs.process(self.conn,self.message(),[])['reply'])
        self.assertIn('cancelada',needs.process(self.conn,self.message('/cancelar'),['/cancelar'])['reply'])

    def test_campaign_menu_and_new_flow_clears_other_sessions(self):
        self.conn.execute('INSERT INTO public.supporter_sessions VALUES (1,10,1,9999999999)')
        result=needs.process(self.conn,self.message('/necesidad'),['/necesidad'])
        self.assertEqual(result['reply_markup']['inline_keyboard'][0][0]['callback_data'],'needcampaign:10')
        self.assertEqual(self.conn.execute('SELECT count(*) AS n FROM public.supporter_sessions').fetchone()['n'],0)
