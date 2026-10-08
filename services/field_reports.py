"""Reportes de texto con captura persistente, folios e historial de revisión."""
import time
import base64
import io
from PIL import Image, UnidentifiedImageError
from contextlib import closing

from services.database import connection
from services.field_permissions import can_access
from services.field_tasks import context, task_is_open

STATUS_LABELS = {'pending': 'Por validar', 'accepted': 'Aceptado', 'correction': 'Corrección solicitada'}
MAX_PHOTO_BYTES = 10 * 1024 * 1024
INCIDENT_PREFIX = '[INCIDENCIA]\n'


def initialize_reports(conn):
    statements = [
        '''CREATE TABLE IF NOT EXISTS field_report_photos (
            report_id INTEGER PRIMARY KEY REFERENCES field_reports(id),
            file_id TEXT NOT NULL, file_unique_id TEXT NOT NULL,
            content_base64 TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS field_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL REFERENCES territorial_action_plans(id),
            worker_id INTEGER NOT NULL REFERENCES field_workers(id),
            generation TEXT NOT NULL, body TEXT NOT NULL CHECK(length(body) BETWEEN 1 AND 4000),
            source_chat_id INTEGER NOT NULL, source_message_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','correction')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_chat_id, source_message_id))''',
        '''CREATE TABLE IF NOT EXISTS field_report_sessions (
            worker_id INTEGER PRIMARY KEY REFERENCES field_workers(id),
            task_id INTEGER NOT NULL REFERENCES territorial_action_plans(id),
            generation TEXT NOT NULL, selection_id TEXT NOT NULL,
            started_at INTEGER NOT NULL, expires_at INTEGER NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS field_report_selections (
            callback_id TEXT PRIMARY KEY, worker_id INTEGER NOT NULL REFERENCES field_workers(id))''',
        '''CREATE TABLE IF NOT EXISTS field_report_reviews (
            report_id INTEGER PRIMARY KEY REFERENCES field_reports(id),
            decision TEXT NOT NULL CHECK(decision IN ('accepted','correction')),
            note TEXT NOT NULL, actor TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''',
        'CREATE INDEX IF NOT EXISTS field_reports_task_idx ON field_reports(task_id, id)',
    ]
    for sql in statements:
        conn.execute(sql)


def folio(report_id):
    return f'R-{report_id:06d}'


def assigned_task(conn, worker_id, task_id, generation, permission='reports.submit'):
    task = conn.execute('''SELECT t.*, a.worker_id, a.generation, a.received_at
        FROM territorial_action_plans t JOIN field_task_assignments a ON a.task_id=t.id
        WHERE t.id=?''', (task_id,)).fetchone()
    if (task is None or task['worker_id'] != worker_id or task['generation'] != generation
            or not task['received_at'] or not task_is_open(task)
            or not can_access(worker_id, permission, conn=conn, **context(task, worker_id))):
        return None
    return task


def report_menu(conn, worker_id, after=0, *, incident=False):
    route = 'incident' if incident else 'report'
    permission = 'incidents.submit' if incident else 'reports.submit'
    rows = conn.execute('''SELECT t.*, a.generation, a.received_at FROM territorial_action_plans t
        JOIN field_task_assignments a ON a.task_id=t.id WHERE a.worker_id=? AND t.id>?
        AND a.received_at IS NOT NULL AND t.status IN ('Pendiente','En curso') ORDER BY t.id''',
                        (worker_id, after))
    visible = []
    for row in rows:
        if can_access(worker_id, permission, conn=conn, **context(row, worker_id)):
            visible.append(row)
            if len(visible) == 6:
                break
    if not visible:
        return {'text': 'No tienes tareas recibidas disponibles para reportar en esta página. '
                        'Consulta /mis_tareas y confirma recepción primero. Usa /reportar o /incidencia para volver al inicio. No se guardó ningún reporte.'}
    buttons = [[{'text': f"#{r['id']} · {r['activity_name'][:65]}",
                 'callback_data': f"{route}select:{r['id']}:{r['generation']}"}] for r in visible[:5]]
    if len(visible) > 5:
        buttons.append([{'text': 'Más tareas', 'callback_data': f"{route}page:{visible[4]['id']}"}])
    if incident:
        return {'text': 'Selecciona la tarea donde ocurrió el problema. Después describe la incidencia '
                        'en texto o con una foto y descripción. Usa /cancelar para salir sin guardar.',
                'reply_markup': {'inline_keyboard': buttons}}
    return {'text': 'Selecciona la tarea para registrar tu avance. Después enviarás un mensaje de texto. '
                    'También puedes enviar una fotografía con el avance en su descripción. '
                    'Usa /cancelar para salir sin guardar.', 'reply_markup': {'inline_keyboard': buttons}}


def select_report_task(conn, worker_id, task_id, generation, callback_id, *, incident=False):
    permission = 'incidents.submit' if incident else 'reports.submit'
    if not callback_id or assigned_task(conn, worker_id, task_id, generation, permission) is None:
        return 'No puedes reportar esta asignación. Revisa /mis_tareas y su recepción.'
    if incident:
        callback_id = 'incident:' + callback_id
    previous = conn.execute('SELECT worker_id FROM field_report_selections WHERE callback_id=?', (callback_id,)).fetchone()
    now = int(time.time())
    if previous:
        session = conn.execute('SELECT * FROM field_report_sessions WHERE worker_id=? AND selection_id=? AND expires_at>?',
                               (worker_id, callback_id, now)).fetchone()
        if previous['worker_id'] != worker_id or session is None:
            return 'Esta selección ya fue atendida. Usa /reportar para iniciar otro reporte.'
    else:
        conn.execute('INSERT INTO field_report_selections VALUES (?, ?)', (callback_id, worker_id))
        conn.execute('INSERT INTO field_report_sessions VALUES (?, ?, ?, ?, ?, ?) '
                     'ON CONFLICT(worker_id) DO UPDATE SET task_id=excluded.task_id, '
                     'generation=excluded.generation, selection_id=excluded.selection_id, '
                     'started_at=excluded.started_at, expires_at=excluded.expires_at',
                     (worker_id, task_id, generation, callback_id, now, now + 1800))
    if incident:
        return (f'Describe la incidencia de la tarea #{task_id} en un mensaje '
                f'(máximo {4000-len(INCIDENT_PREFIX)} caracteres), o envía una foto con esa descripción. '
                'Se guardará como reporte marcado INCIDENCIA, por validar. Tienes 30 minutos; /cancelar descarta la captura.')
    return (f'Escribe el avance de la tarea #{task_id} en un solo mensaje (máximo 4000 caracteres). '
            'Puedes enviar una fotografía con el avance en su descripción, una por reporte. '
            'Quedará por validar. Tienes 30 minutos; /cancelar descarta la captura.')


def saved_reply(report_id, status='pending', *, incident=False):
    label = 'Incidencia' if incident else 'Reporte'
    return (f'{label} {folio(report_id)} guardado en Go2Win. Estado: {STATUS_LABELS[status]}. '
            'Este reporte no concluye la tarea. Consulta /mis_reportes.')


def saved_message(conn, worker_id, message):
    row = conn.execute('SELECT id, status, body FROM field_reports WHERE worker_id=? AND source_chat_id=? AND source_message_id=?',
                       (worker_id, message['chat']['id'], message.get('message_id'))).fetchone()
    return saved_reply(row['id'], row['status'], incident=row['body'].startswith(INCIDENT_PREFIX)) if row else None


def capture_report(conn, worker_id, message, photo_loader=None):
    session = conn.execute('SELECT * FROM field_report_sessions WHERE worker_id=?', (worker_id,)).fetchone()
    if session is None:
        return None
    if session['expires_at'] <= int(time.time()):
        conn.execute('DELETE FROM field_report_sessions WHERE worker_id=?', (worker_id,))
        return 'La captura venció sin guardar. Usa /reportar para comenzar de nuevo.'
    incident = session['selection_id'].startswith('incident:')
    permission = 'incidents.submit' if incident else 'reports.submit'
    if assigned_task(conn, worker_id, session['task_id'], session['generation'], permission) is None:
        conn.execute('DELETE FROM field_report_sessions WHERE worker_id=?', (worker_id,))
        return 'La asignación o tus permisos cambiaron. No se guardó el reporte. Revisa /mis_tareas.'
    if not isinstance(message.get('date'), int) or message['date'] < session['started_at']:
        return 'Ese mensaje es anterior a la captura. Envía un texto nuevo para el reporte.'
    photos = message.get('photo')
    text = (message.get('caption' if photos else 'text') or '').strip()
    if not text or any(k in message for k in ('document', 'video', 'voice', 'audio')):
        return 'Espero un mensaje de texto o una fotografía con el avance en su descripción; usa /cancelar para salir.'
    if message.get('media_group_id'):
        return 'Envía una sola fotografía por reporte, con su descripción; no un álbum. Aún no se guardó.'
    limit = 4000 - len(INCIDENT_PREFIX) if incident else 4000
    if len(text) > limit:
        return f'El reporte supera {limit} caracteres. Acórtalo y envíalo de nuevo; aún no se guardó.'
    if incident:
        text = INCIDENT_PREFIX + text
    if not isinstance(message.get('message_id'), int):
        return 'No se pudo identificar el mensaje. Envía el texto nuevamente.'
    photo = None
    content = None
    if photos:
        valid = [p for p in photos if isinstance(p, dict) and p.get('file_id') and p.get('file_unique_id')]
        if not valid or photo_loader is None:
            return 'No se pudo procesar la fotografía. Envía una fotografía nueva con su descripción.'
        photo = max(valid, key=lambda p: p.get('width', 0) * p.get('height', 0))
        if photo.get('file_size', 0) > MAX_PHOTO_BYTES:
            return 'La fotografía supera 10 MB. Envía una más pequeña; aún no se guardó.'
        try:
            raw = photo_loader(photo['file_id'])
            if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_PHOTO_BYTES:
                raise ValueError('Tamaño inválido')
            with Image.open(io.BytesIO(raw)) as image:
                if image.format != 'JPEG' or image.width * image.height > 25_000_000:
                    raise ValueError('Imagen inválida')
                image.verify()
            content = base64.b64encode(raw).decode('ascii')
        except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError):
            return 'La fotografía no es un JPEG válido de hasta 10 MB. Envía otra; aún no se guardó.'
    rid = conn.execute('''INSERT INTO field_reports
        (task_id,worker_id,generation,body,source_chat_id,source_message_id) VALUES (?,?,?,?,?,?) RETURNING id''',
        (session['task_id'], worker_id, session['generation'], text, message['chat']['id'], message['message_id'])).fetchone()[0]
    if photo:
        conn.execute('INSERT INTO field_report_photos VALUES (?,?,?,?)',
                     (rid, photo['file_id'], photo['file_unique_id'], content))
    conn.execute('DELETE FROM field_report_sessions WHERE worker_id=?', (worker_id,))
    return saved_reply(rid, incident=incident)


def report_photo(report_id, token):
    """Solo entrega bytes tras comprobar sesión y alcance actuales."""
    from services.web_auth import require_user
    with closing(connection()) as conn:
        user = require_user(token, conn)
        report = conn.execute('''SELECT r.*, t.profile_id,t.state,t.municipality FROM field_reports r
            JOIN territorial_action_plans t ON t.id=r.task_id WHERE r.id=?''', (report_id,)).fetchone()
        if report is None or not can_access(user['id'], 'reports.view', conn=conn,
                                           **context(report, report['worker_id'])):
            raise PermissionError('No tienes permiso para consultar esta evidencia.')
        row = conn.execute('SELECT content_base64 FROM field_report_photos WHERE report_id=?', (report_id,)).fetchone()
        return base64.b64decode(row['content_base64']) if row else None


def my_reports(conn, worker_id, before=9223372036854775807):
    rows = conn.execute('''SELECT r.*, t.profile_id, t.state, t.municipality, v.note FROM field_reports r
        JOIN territorial_action_plans t ON t.id=r.task_id LEFT JOIN field_report_reviews v ON v.report_id=r.id
        WHERE r.worker_id=? AND r.id<? ORDER BY r.id DESC''', (worker_id, before))
    visible = []
    for row in rows:
        if can_access(worker_id, 'reports.view', conn=conn, **context(row, worker_id)):
            visible.append(row)
            if len(visible) == 3:
                break
    if not visible:
        return {'text': 'No hay reportes visibles en esta página. Usa /mis_reportes para volver al inicio.'}
    text = '\n\n'.join(f"{folio(r['id'])} · tarea #{r['task_id']} · {STATUS_LABELS[r['status']]}\n"
                       f"{r['created_at']} UTC\n{r['body'][:100]}\n"
                       f"Revisión: {r['note'] or 'Sin observaciones'}" for r in visible[:2])
    result = {'text': text}
    if len(visible) > 2:
        result['reply_markup'] = {'inline_keyboard': [[{'text': 'Reportes anteriores',
                                    'callback_data': f"reporthistory:{visible[1]['id']}"}]]}
    return result


def list_task_reports(task_id):
    """Lectura para la consola local de confianza, no un endpoint público."""
    with closing(connection()) as conn:
        return [dict(r) for r in conn.execute('''SELECT r.*, w.name, v.note, v.actor, v.created_at AS reviewed_at
            FROM field_reports r JOIN field_workers w ON w.id=r.worker_id
            LEFT JOIN field_report_reviews v ON v.report_id=r.id WHERE task_id=? ORDER BY r.id DESC''', (task_id,))]


def review_report(report_id, decision, note, *, actor_worker_id=None, session_token=None):
    """Sin actor_worker_id: consola local administrativa. Con actor: identidad autenticada por backend."""
    note = note.strip()
    if decision not in {'accepted', 'correction'} or len(note) > 500 or (decision == 'correction' and not note):
        raise ValueError('Selecciona una decisión válida. Para solicitar corrección escribe el motivo (máximo 500 caracteres).')
    with closing(connection()) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        if session_token is not None:
            from services.web_auth import require_user
            actor_worker_id = require_user(session_token, conn)['id']
        report = conn.execute('''SELECT r.*, t.profile_id, t.state, t.municipality FROM field_reports r
            JOIN territorial_action_plans t ON t.id=r.task_id WHERE r.id=?''', (report_id,)).fetchone()
        if report is None:
            raise ValueError('No existe el reporte.')
        if actor_worker_id is not None and (actor_worker_id == report['worker_id'] or not can_access(
                actor_worker_id, 'reports.review', conn=conn, **context(report, report['worker_id']))):
            raise PermissionError('No tienes permiso para revisar este reporte.')
        previous = conn.execute('SELECT * FROM field_report_reviews WHERE report_id=?', (report_id,)).fetchone()
        if previous:
            if previous['decision'] == decision and previous['note'] == note:
                return
            raise ValueError('El reporte ya fue revisado. Actualiza la pantalla; su revisión se conserva en el historial.')
        actor = 'local_console' if actor_worker_id is None else f'worker:{actor_worker_id}'
        conn.execute('INSERT INTO field_report_reviews (report_id, decision, note, actor) VALUES (?,?,?,?)',
                     (report_id, decision, note, actor))
        conn.execute('UPDATE field_reports SET status=? WHERE id=?', (decision, report_id))
