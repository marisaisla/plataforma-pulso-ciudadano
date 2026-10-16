"""Captura Telegram independiente sobre el esquema existente."""
import re
import time


def can_access(worker_id, permission, *, profile_id, state, municipality, assigned_worker_id, conn):
    worker=conn.execute('SELECT role_key FROM public.field_workers WHERE id=%s AND active=1',(worker_id,)).fetchone()
    if not worker or assigned_worker_id!=worker_id:
        return False
    grant=conn.execute('SELECT scope FROM public.field_role_permissions WHERE role_key=%s AND permission_key=%s',(worker['role_key'],permission)).fetchone()
    if not grant:
        return False
    if grant['scope']=='all':
        return True
    if grant['scope'] not in ('own','team','campaign'):
        return False
    return conn.execute("SELECT 1 FROM public.field_worker_scopes WHERE worker_id=%s AND profile_id=%s AND (state='' OR state=%s) AND (municipality='' OR municipality=%s)",(worker_id,profile_id,state,municipality)).fetchone() is not None


def campaigns(conn, worker_id, permission='supporters.submit'):
    worker = conn.execute('SELECT role_key FROM public.field_workers WHERE id=%s AND active=1', (worker_id,)).fetchone()
    if worker is None:
        return []
    rows = conn.execute('''SELECT DISTINCT p.id,p.name,s.state,s.municipality FROM public.profiles p
        JOIN public.field_worker_scopes s ON s.profile_id=p.id WHERE s.worker_id=%s ORDER BY p.id''', (worker_id,))
    result = {r['id']: r['name'] for r in rows if can_access(worker_id, permission,
        profile_id=r['id'], state=r['state'], municipality=r['municipality'], assigned_worker_id=worker_id, conn=conn)}
    if worker['role_key'] == 'administrator' and conn.execute("SELECT 1 FROM public.field_role_permissions WHERE role_key='administrator' AND permission_key=%s AND scope='all'",(permission,)).fetchone():
        result = {r['id']: r['name'] for r in conn.execute('SELECT id,name FROM public.profiles ORDER BY id')}
    return list(result.items())


def menu(conn, worker_id):
    conn.execute('DELETE FROM public.supporter_sessions WHERE worker_id=%s', (worker_id,))
    options = campaigns(conn, worker_id)
    if not options:
        return 'No tienes una campaña autorizada para registrar simpatizantes. Contacta a coordinación.'
    # Una opción por campaña; /simpatizante FOLIO permite elegir cuando hay muchas.
    return {'text': 'Selecciona la campaña para registrar al simpatizante. '
                    'También puedes usar /simpatizante FOLIO_CAMPAÑA. Usa /cancelar para salir.',
            'reply_markup': {'inline_keyboard': [[{'text': f'#{pid} · {name[:60]}',
                 'callback_data': f'supportcampaign:{pid}'}] for pid, name in options[:50]]}}


def select_campaign(conn, worker_id, profile_id):
    if profile_id not in dict(campaigns(conn, worker_id)):
        return 'No puedes registrar simpatizantes en esta campaña.'
    now = int(time.time())
    conn.execute('''INSERT INTO public.supporter_sessions VALUES (%s,%s,%s,%s) ON CONFLICT(worker_id)
        DO UPDATE SET profile_id=excluded.profile_id,started_at=excluded.started_at,expires_at=excluded.expires_at''',
        (worker_id, profile_id, now, now+1800))
    return ('Envía los datos en un solo mensaje con este formato (30 minutos; /cancelar para salir):\n'
            'Nombre: nombre completo\nTeléfono: +52 y número de 10 dígitos\nEstado: estado\n'
            'Municipio: municipio\nSección: número opcional\nClave de elector: clave\nRegistro: SI\nMensajes: SI o NO\n\n'
            'Escribe Registro: SI solo si la persona autorizó guardar sus datos como simpatizante '
            'en esta campaña. Mensajes: SI requiere además su autorización para recibir información. '
            'El registro conserva tu identidad y fecha como constancia de tu declaración.')


def capture(conn, worker_id, message):
    session = conn.execute('SELECT * FROM public.supporter_sessions WHERE worker_id=%s', (worker_id,)).fetchone()
    if session is None:
        return None
    if session['expires_at'] <= int(time.time()):
        conn.execute('DELETE FROM public.supporter_sessions WHERE worker_id=%s', (worker_id,))
        return 'La captura de simpatizante venció. Usa /simpatizante para reiniciar.'
    if not isinstance(message.get('date'), int) or message['date'] < session['started_at']:
        return 'Envía un mensaje nuevo para registrar al simpatizante.'
    text = message.get('text') or ''
    if len(text) > 2000 or any(k in message for k in ('photo','document','contact','video','voice','audio')):
        return 'Envía los datos del simpatizante como texto, máximo 2000 caracteres.'
    fields = {}
    for line in text.splitlines():
        if ':' not in line:
            return 'Usa el formato indicado, un campo por línea y separado por dos puntos.'
        key, value = line.split(':', 1)
        key = key.strip().casefold()
        key = {'telefono': 'teléfono', 'seccion': 'sección'}.get(key, key)
        if key in fields or key not in {'nombre','teléfono','estado','municipio','sección','clave de elector','registro','mensajes'}:
            return 'Hay campos repetidos o desconocidos. Usa el formato indicado.'
        fields[key] = value.strip()
    if any(not fields.get(k) or len(fields[k]) > 120 for k in ('nombre','estado','municipio')):
        return 'Nombre, estado y municipio son obligatorios, máximo 120 caracteres cada uno.'
    if fields.get('registro', '').upper() not in {'SI','SÍ'}:
        return 'No se guardó: se requiere autorización de la persona para registrar sus datos.'
    if fields.get('mensajes','').upper() not in {'SI','SÍ','NO'}:
        return 'Indica Mensajes: SI o NO según la autorización de la persona.'
    phone = re.sub(r'[\s()\-]', '', fields.get('teléfono',''))
    if re.fullmatch(r'[0-9]{10}', phone):
        phone = '+52' + phone
    if not re.fullmatch(r'\+[1-9][0-9]{7,14}', phone):
        return 'Teléfono inválido. Usa 10 dígitos para México o +código de país y número.'
    section = fields.get('sección','')
    voter_key = fields.get('clave de elector','').upper()
    if not re.fullmatch(r'[A-Z0-9]{18}', voter_key):
        return 'La clave de elector debe contener 18 letras o números, sin espacios. No se guardó.'
    if section and not re.fullmatch(r'[0-9]{1,6}', section):
        return 'La sección debe contener de 1 a 6 dígitos o quedar vacía.'
    if not can_access(worker_id, 'supporters.submit', profile_id=session['profile_id'], state=fields['estado'],
                      municipality=fields['municipio'], assigned_worker_id=worker_id, conn=conn):
        return 'No tienes permiso para registrar en esa campaña y territorio. No se guardó.'
    if not isinstance(message.get('message_id'), int):
        return 'No se pudo identificar el mensaje; envíalo nuevamente.'
    duplicate = conn.execute('SELECT id FROM public.supporters WHERE profile_id=%s AND (phone=%s OR voter_key=%s)',
                             (session['profile_id'],phone,voter_key)).fetchone()
    if duplicate:
        return 'El teléfono o la clave de elector ya están registrados en esta campaña. No se modificó el registro existente. Usa /cancelar para salir.'
    rid = conn.execute('''INSERT INTO public.supporters
        (profile_id,worker_id,name,phone,voter_key,state,municipality,electoral_section,registration_consent,
        messaging_consent,source_chat_id,source_message_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,1,%s,%s,%s) RETURNING id''',
        (session['profile_id'], worker_id, fields['nombre'],phone,voter_key,fields['estado'],fields['municipio'],section,
         int(fields['mensajes'].upper() in {'SI','SÍ'}),message['chat']['id'],message['message_id'])).fetchone()['id']
    conn.execute('DELETE FROM public.supporter_sessions WHERE worker_id=%s', (worker_id,))
    return saved_reply(rid)


def saved_reply(rid):
    return f'Simpatizante S-{rid:06d} registrado en Go2Win. No se ha enviado ningún mensaje a esa persona.'


def saved_message(conn, worker_id, message):
    row = conn.execute('SELECT id FROM public.supporters WHERE worker_id=%s AND source_chat_id=%s AND source_message_id=%s',
                       (worker_id,message['chat']['id'],message.get('message_id'))).fetchone()
    return saved_reply(row['id']) if row else None


def process(conn,message,parts):
    from backend.tasks import identity
    from fastapi import HTTPException
    command=parts[0].split('@')[0].lower() if parts else ''
    worker=conn.execute('SELECT id FROM public.field_workers WHERE telegram_user_id=%s AND active=1',(message.sender.id,)).fetchone()
    if not worker:
        return {'status':'rejected','reply':'Cuenta no vinculada o acceso desactivado.'} if command=='/simpatizante' else None
    wid=worker['id']
    data=message.model_dump(by_alias=True,exclude_none=True)
    duplicate=saved_message(conn,wid,data)
    if duplicate:
        return {'status':'supporters','reply':duplicate}
    if command=='/simpatizante':
        try: identity(conn,message.sender.id,'supporters.submit')
        except HTTPException as exc: return {'status':'rejected','reply':exc.detail}
        for table in ('field_report_sessions','field_need_sessions','supporter_sessions'):
            conn.execute(f'DELETE FROM public.{table} WHERE worker_id=%s',(wid,))
        if len(parts)==2 and parts[1].isascii() and parts[1].isdigit() and len(parts[1])<=18:
            return {'status':'supporters','reply':select_campaign(conn,wid,int(parts[1]))}
        if len(parts)!=1:
            return {'status':'supporters','reply':'Uso: /simpatizante o /simpatizante FOLIO_CAMPAÑA'}
        result=menu(conn,wid)
        return {'status':'supporters','reply':result['text'],'reply_markup':result['reply_markup']} if isinstance(result,dict) else {'status':'supporters','reply':result}
    session=conn.execute('SELECT 1 FROM public.supporter_sessions WHERE worker_id=%s',(wid,)).fetchone()
    if not session:
        return None
    if command=='/cancelar':
        conn.execute('DELETE FROM public.supporter_sessions WHERE worker_id=%s',(wid,))
        return {'status':'supporters','reply':'Captura de simpatizante cancelada sin guardar.'}
    if command.startswith('/'):
        return None
    return {'status':'supporters','reply':capture(conn,wid,data)}


def callback(conn,cb):
    from backend.tasks import identity
    from fastapi import HTTPException
    parts=cb.data.split(':')
    if len(parts)!=2 or not parts[1].isascii() or not parts[1].isdigit() or len(parts[1])>18:
        return {'status':'rejected','reply':'Selección inválida. Usa /simpatizante.'}
    try: wid,_=identity(conn,cb.sender.id,'supporters.submit')
    except HTTPException as exc: return {'status':'rejected','reply':exc.detail}
    for table in ('field_report_sessions','field_need_sessions'):
        conn.execute(f'DELETE FROM public.{table} WHERE worker_id=%s',(wid,))
    return {'status':'supporters','reply':select_campaign(conn,wid,int(parts[1]))}


