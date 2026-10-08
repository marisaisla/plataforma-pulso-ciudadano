"""Catálogo de simpatizantes capturados por personal autenticado."""
import re
import time
from contextlib import closing
from services.database import connection
from services.field_permissions import can_access


def initialize_supporters(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS supporters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER NOT NULL REFERENCES profiles(id),
        worker_id INTEGER NOT NULL REFERENCES field_workers(id),
        name TEXT NOT NULL, phone TEXT NOT NULL, voter_key TEXT NOT NULL, state TEXT NOT NULL,
        municipality TEXT NOT NULL, electoral_section TEXT NOT NULL DEFAULT '',
        registration_consent INTEGER NOT NULL CHECK(registration_consent=1),
        messaging_consent INTEGER NOT NULL CHECK(messaging_consent IN (0,1)),
        source_chat_id INTEGER NOT NULL, source_message_id INTEGER NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(profile_id,phone), UNIQUE(profile_id,voter_key), UNIQUE(source_chat_id,source_message_id))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS supporter_sessions (
        worker_id INTEGER PRIMARY KEY REFERENCES field_workers(id),
        profile_id INTEGER NOT NULL REFERENCES profiles(id),
        started_at INTEGER NOT NULL, expires_at INTEGER NOT NULL)''')


def campaigns(conn, worker_id, permission='supporters.submit'):
    worker = conn.execute('SELECT role_key FROM field_workers WHERE id=? AND active=1', (worker_id,)).fetchone()
    if worker is None:
        return []
    rows = conn.execute('''SELECT DISTINCT p.id,p.name,s.state,s.municipality FROM profiles p
        JOIN field_worker_scopes s ON s.profile_id=p.id WHERE s.worker_id=? ORDER BY p.id''', (worker_id,))
    result = {r['id']: r['name'] for r in rows if can_access(worker_id, permission,
        profile_id=r['id'], state=r['state'], municipality=r['municipality'], assigned_worker_id=worker_id, conn=conn)}
    if worker['role_key'] == 'administrator':
        result = {r['id']: r['name'] for r in conn.execute('SELECT id,name FROM profiles ORDER BY id')}
    return list(result.items())


def menu(conn, worker_id):
    conn.execute('DELETE FROM supporter_sessions WHERE worker_id=?', (worker_id,))
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
    conn.execute('''INSERT INTO supporter_sessions VALUES (?,?,?,?) ON CONFLICT(worker_id)
        DO UPDATE SET profile_id=excluded.profile_id,started_at=excluded.started_at,expires_at=excluded.expires_at''',
        (worker_id, profile_id, now, now+1800))
    return ('Envía los datos en un solo mensaje con este formato (30 minutos; /cancelar para salir):\n'
            'Nombre: nombre completo\nTeléfono: +52 y número de 10 dígitos\nEstado: estado\n'
            'Municipio: municipio\nSección: número opcional\nClave de elector: clave\nRegistro: SI\nMensajes: SI o NO\n\n'
            'Escribe Registro: SI solo si la persona autorizó guardar sus datos como simpatizante '
            'en esta campaña. Mensajes: SI requiere además su autorización para recibir información. '
            'El registro conserva tu identidad y fecha como constancia de tu declaración.')


def capture(conn, worker_id, message):
    session = conn.execute('SELECT * FROM supporter_sessions WHERE worker_id=?', (worker_id,)).fetchone()
    if session is None:
        return None
    if session['expires_at'] <= int(time.time()):
        conn.execute('DELETE FROM supporter_sessions WHERE worker_id=?', (worker_id,))
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
    duplicate = conn.execute('SELECT id FROM supporters WHERE profile_id=? AND (phone=? OR voter_key=?)',
                             (session['profile_id'],phone,voter_key)).fetchone()
    if duplicate:
        return 'El teléfono o la clave de elector ya están registrados en esta campaña. No se modificó el registro existente. Usa /cancelar para salir.'
    rid = conn.execute('''INSERT INTO supporters
        (profile_id,worker_id,name,phone,voter_key,state,municipality,electoral_section,registration_consent,
        messaging_consent,source_chat_id,source_message_id) VALUES (?,?,?,?,?,?,?,?,1,?,?,?) RETURNING id''',
        (session['profile_id'], worker_id, fields['nombre'],phone,voter_key,fields['estado'],fields['municipio'],section,
         int(fields['mensajes'].upper() in {'SI','SÍ'}),message['chat']['id'],message['message_id'])).fetchone()[0]
    conn.execute('DELETE FROM supporter_sessions WHERE worker_id=?', (worker_id,))
    return saved_reply(rid)


def saved_reply(rid):
    return f'Simpatizante S-{rid:06d} registrado en Go2Win. No se ha enviado ningún mensaje a esa persona.'


def saved_message(conn, worker_id, message):
    row = conn.execute('SELECT id FROM supporters WHERE worker_id=? AND source_chat_id=? AND source_message_id=?',
                       (worker_id,message['chat']['id'],message.get('message_id'))).fetchone()
    return saved_reply(row['id']) if row else None


def catalog(token):
    from services.web_auth import require_user
    with closing(connection()) as conn:
        user = require_user(token, conn)
        return [dict(r) for r in conn.execute('''SELECT s.*,p.name AS campaign,w.name AS registered_by
            FROM supporters s JOIN profiles p ON p.id=s.profile_id JOIN field_workers w ON w.id=s.worker_id
            ORDER BY s.id DESC''') if can_access(user['id'], 'supporters.view', conn=conn,
                profile_id=r['profile_id'],state=r['state'],municipality=r['municipality'],assigned_worker_id=r['worker_id'])]
