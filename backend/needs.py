"""Necesidades territoriales: captura Telegram independiente."""
import re
import time
from backend.supporters import campaigns, can_access


def menu(conn, worker_id):
    conn.execute('DELETE FROM public.field_need_sessions WHERE worker_id=%s', (worker_id,))
    options = campaigns(conn, worker_id, 'needs.submit')
    if not options:
        return 'No tienes una campaña autorizada para registrar necesidades. Contacta a coordinación.'
    return {'text': 'Selecciona la campaña para registrar una necesidad territorial. '
                    'También puedes usar /necesidad FOLIO_CAMPAÑA. /cancelar descarta la captura.',
        'reply_markup': {'inline_keyboard': [[{'text': f'#{pid} · {name[:60]}',
            'callback_data': f'needcampaign:{pid}'}] for pid,name in options[:50]]}}


def select_campaign(conn, worker_id, profile_id):
    if profile_id not in dict(campaigns(conn, worker_id, 'needs.submit')):
        return 'No tienes permiso para registrar necesidades en esta campaña.'
    now = int(time.time())
    conn.execute('''INSERT INTO public.field_need_sessions VALUES (%s,%s,%s,%s) ON CONFLICT(worker_id)
        DO UPDATE SET profile_id=excluded.profile_id,started_at=excluded.started_at,expires_at=excluded.expires_at''',
        (worker_id,profile_id,now,now+1800))
    return ('Envía la necesidad en un solo mensaje con este formato:\n'
            'Estado: estado\nMunicipio: municipio\nSección: número\n'
            'Origen: detectada o comentada\nNecesidad: descripción de lo que hace falta\n\n'
            'Todos los campos son obligatorios. Descripción: máximo 3000 caracteres; puede ocupar '
            'varias líneas al final. No incluyas datos personales de quien te lo comentó. '
            'Tienes 30 minutos; /cancelar descarta la captura. No necesitas una tarea asignada.')


def reply(rid):
    return f'Necesidad N-{rid:06d} guardada en Go2Win para consulta de coordinación y dirección de campaña.'


def saved_message(conn, worker_id, message):
    row = conn.execute('SELECT id FROM public.field_needs WHERE worker_id=%s AND source_chat_id=%s AND source_message_id=%s',
        (worker_id,message['chat']['id'],message.get('message_id'))).fetchone()
    return reply(row['id']) if row else None


def capture(conn, worker_id, message):
    session = conn.execute('SELECT * FROM public.field_need_sessions WHERE worker_id=%s',(worker_id,)).fetchone()
    if session is None:
        return None
    if session['expires_at'] <= int(time.time()):
        conn.execute('DELETE FROM public.field_need_sessions WHERE worker_id=%s',(worker_id,))
        return 'La captura de necesidad venció sin guardar. Usa /necesidad para reiniciar.'
    if not isinstance(message.get('date'),int) or message['date'] < session['started_at']:
        return 'Ese mensaje es anterior a la captura. Envía la necesidad en un mensaje nuevo.'
    text = message.get('text') or ''
    if len(text) > 3800 or any(k in message for k in ('photo','document','contact','video','audio','voice')):
        return 'Envía la necesidad en texto, máximo 3800 caracteres incluyendo los campos.'
    fields = {}
    for line in text.splitlines():
        if 'necesidad' in fields:
            fields['necesidad'] += '\n' + line
            continue
        if ':' not in line:
            return 'Usa el formato indicado, con un campo por línea. Coloca Necesidad al final.'
        key,value = line.split(':',1)
        key = key.strip().casefold()
        key = {'seccion':'sección','descripcion':'necesidad','descripción':'necesidad'}.get(key,key)
        if key not in {'estado','municipio','sección','origen','necesidad'} or key in fields:
            return 'Hay campos repetidos o desconocidos. Usa el formato indicado.'
        fields[key] = value.strip()
    if any(not fields.get(k) or len(fields[k]) > 120 for k in ('estado','municipio')):
        return 'Estado y municipio son obligatorios, máximo 120 caracteres cada uno.'
    section = fields.get('sección','')
    if not re.fullmatch(r'[0-9]{1,6}',section) or int(section) == 0:
        return 'La sección es obligatoria: escribe un número positivo de hasta 6 dígitos.'
    section = str(int(section))
    description = fields.get('necesidad','').strip()
    if not 1 <= len(description) <= 3000:
        return 'Describe la necesidad con entre 1 y 3000 caracteres.'
    origin = fields.get('origen','').casefold()
    if origin not in {'detectada','comentada'}:
        return 'Indica Origen: detectada o Origen: comentada.'
    if not can_access(worker_id,'needs.submit',conn=conn, profile_id=session['profile_id'],
                      state=fields['estado'],municipality=fields['municipio'],assigned_worker_id=worker_id):
        return 'No tienes permiso en esa campaña y territorio. No se guardó la necesidad.'
    if not isinstance(message.get('message_id'),int):
        return 'No se pudo identificar el mensaje. Envía los datos nuevamente.'
    rid = conn.execute('''INSERT INTO public.field_needs
        (profile_id,worker_id,state,municipality,electoral_section,description,origin,source_chat_id,source_message_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
        (session['profile_id'],worker_id,fields['estado'],fields['municipio'],section,description,origin,
         message['chat']['id'],message['message_id'])).fetchone()['id']
    conn.execute('DELETE FROM public.field_need_sessions WHERE worker_id=%s',(worker_id,))
    return reply(rid)


def process(conn,message,parts):
    from backend.tasks import identity
    from fastapi import HTTPException
    command=parts[0].split('@')[0].lower() if parts else ''
    worker=conn.execute('SELECT id FROM public.field_workers WHERE telegram_user_id=%s AND active=1',(message.sender.id,)).fetchone()
    if not worker:
        return {'status':'rejected','reply':'Cuenta no vinculada o acceso desactivado.'} if command=='/necesidad' else None
    wid=worker['id']
    data=message.model_dump(by_alias=True,exclude_none=True)
    previous=saved_message(conn,wid,data)
    if previous:
        return {'status':'needs','reply':previous}
    if command=='/necesidad':
        try: identity(conn,message.sender.id,'needs.submit')
        except HTTPException as exc: return {'status':'rejected','reply':exc.detail}
        for table in ('field_report_sessions','supporter_sessions','field_need_sessions'):
            conn.execute(f'DELETE FROM public.{table} WHERE worker_id=%s',(wid,))
        if len(parts)==2 and parts[1].isascii() and parts[1].isdigit() and len(parts[1])<=18:
            return {'status':'needs','reply':select_campaign(conn,wid,int(parts[1]))}
        if len(parts)!=1:
            return {'status':'needs','reply':'Uso: /necesidad o /necesidad FOLIO_CAMPAÑA'}
        result=menu(conn,wid)
        return {'status':'needs','reply':result['text'],'reply_markup':result['reply_markup']} if isinstance(result,dict) else {'status':'needs','reply':result}
    if not conn.execute('SELECT 1 FROM public.field_need_sessions WHERE worker_id=%s',(wid,)).fetchone():
        return None
    if command=='/cancelar':
        conn.execute('DELETE FROM public.field_need_sessions WHERE worker_id=%s',(wid,))
        return {'status':'needs','reply':'Captura de necesidad cancelada sin guardar.'}
    if command.startswith('/'):
        return None
    return {'status':'needs','reply':capture(conn,wid,data)}


def callback(conn,cb):
    from backend.tasks import identity
    from fastapi import HTTPException
    parts=cb.data.split(':')
    if len(parts)!=2 or not parts[1].isascii() or not parts[1].isdigit() or len(parts[1])>18:
        return {'status':'rejected','reply':'Selección inválida. Usa /necesidad.'}
    try: wid,_=identity(conn,cb.sender.id,'needs.submit')
    except HTTPException as exc: return {'status':'rejected','reply':exc.detail}
    for table in ('field_report_sessions','supporter_sessions'):
        conn.execute(f'DELETE FROM public.{table} WHERE worker_id=%s',(wid,))
    return {'status':'needs','reply':select_campaign(conn,wid,int(parts[1]))}


