"""Necesidades territoriales detectadas o comunicadas al personal de campo."""
import re
import time
from contextlib import closing
from services.database import connection
from services.field_permissions import can_access
from services.supporters import campaigns


def initialize_needs(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS field_needs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER NOT NULL REFERENCES profiles(id),
        worker_id INTEGER NOT NULL REFERENCES field_workers(id),
        state TEXT NOT NULL, municipality TEXT NOT NULL, electoral_section TEXT NOT NULL,
        description TEXT NOT NULL CHECK(length(description) BETWEEN 1 AND 3000),
        origin TEXT NOT NULL CHECK(origin IN ('detectada','comentada')),
        source_chat_id INTEGER NOT NULL, source_message_id INTEGER NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(source_chat_id,source_message_id))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS field_need_sessions (
        worker_id INTEGER PRIMARY KEY REFERENCES field_workers(id),
        profile_id INTEGER NOT NULL REFERENCES profiles(id),
        started_at INTEGER NOT NULL, expires_at INTEGER NOT NULL)''')
    conn.execute('CREATE INDEX IF NOT EXISTS field_needs_territory_idx ON field_needs(profile_id,state,municipality,electoral_section)')


def menu(conn, worker_id):
    conn.execute('DELETE FROM field_need_sessions WHERE worker_id=?', (worker_id,))
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
    conn.execute('''INSERT INTO field_need_sessions VALUES (?,?,?,?) ON CONFLICT(worker_id)
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
    row = conn.execute('SELECT id FROM field_needs WHERE worker_id=? AND source_chat_id=? AND source_message_id=?',
        (worker_id,message['chat']['id'],message.get('message_id'))).fetchone()
    return reply(row['id']) if row else None


def capture(conn, worker_id, message):
    session = conn.execute('SELECT * FROM field_need_sessions WHERE worker_id=?',(worker_id,)).fetchone()
    if session is None:
        return None
    if session['expires_at'] <= int(time.time()):
        conn.execute('DELETE FROM field_need_sessions WHERE worker_id=?',(worker_id,))
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
    rid = conn.execute('''INSERT INTO field_needs
        (profile_id,worker_id,state,municipality,electoral_section,description,origin,source_chat_id,source_message_id)
        VALUES (?,?,?,?,?,?,?,?,?) RETURNING id''',
        (session['profile_id'],worker_id,fields['estado'],fields['municipio'],section,description,origin,
         message['chat']['id'],message['message_id'])).fetchone()[0]
    conn.execute('DELETE FROM field_need_sessions WHERE worker_id=?',(worker_id,))
    return reply(rid)


def catalog(token):
    from services.web_auth import require_user
    with closing(connection()) as conn:
        user = require_user(token,conn)
        return [dict(r) for r in conn.execute('''SELECT n.*,p.name AS campaign,w.name AS registered_by
            FROM field_needs n JOIN profiles p ON p.id=n.profile_id JOIN field_workers w ON w.id=n.worker_id
            ORDER BY n.id DESC''') if can_access(user['id'],'needs.view',conn=conn,
                profile_id=r['profile_id'],state=r['state'],municipality=r['municipality'],assigned_worker_id=r['worker_id'])]
