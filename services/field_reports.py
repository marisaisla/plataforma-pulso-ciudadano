"""Reportes de texto con captura persistente, folios e historial de revisión."""
import time
from contextlib import closing

from services.database import connection
from services.field_permissions import can_access
from services.field_tasks import context, task_is_open

STATUS_LABELS = {'pending': 'Por validar', 'accepted': 'Aceptado', 'correction': 'Corrección solicitada'}


def initialize_reports(conn):
    statements = [
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


def assigned_task(conn, worker_id, task_id, generation):
    task = conn.execute('''SELECT t.*, a.worker_id, a.generation, a.received_at
        FROM territorial_action_plans t JOIN field_task_assignments a ON a.task_id=t.id
        WHERE t.id=?''', (task_id,)).fetchone()
    if (task is None or task['worker_id'] != worker_id or task['generation'] != generation
            or not task['received_at'] or not task_is_open(task)
            or not can_access(worker_id, 'reports.submit', conn=conn, **context(task, worker_id))):
        return None
    return task


def report_menu(conn, worker_id, after=0):
    rows = conn.execute('''SELECT t.*, a.generation, a.received_at FROM territorial_action_plans t
        JOIN field_task_assignments a ON a.task_id=t.id WHERE a.worker_id=? AND t.id>?
        AND a.received_at IS NOT NULL AND t.status IN ('Pendiente','En curso') ORDER BY t.id''',
                        (worker_id, after))
    visible = []
    for row in rows:
        if can_access(worker_id, 'reports.submit', conn=conn, **context(row, worker_id)):
            visible.append(row)
            if len(visible) == 6:
                break
    if not visible:
        return {'text': 'No tienes tareas recibidas disponibles para reportar en esta página. '
                        'Consulta /mis_tareas y confirma recepción primero. Usa /reportar para volver al inicio. No se guardó ningún reporte.'}
    buttons = [[{'text': f"#{r['id']} · {r['activity_name'][:65]}",
                 'callback_data': f"reportselect:{r['id']}:{r['generation']}"}] for r in visible[:5]]
    if len(visible) > 5:
        buttons.append([{'text': 'Más tareas', 'callback_data': f"reportpage:{visible[4]['id']}"}])
    return {'text': 'Selecciona la tarea para registrar tu avance. Después enviarás un mensaje de texto. '
                    'Usa /cancelar para salir sin guardar.', 'reply_markup': {'inline_keyboard': buttons}}


def select_report_task(conn, worker_id, task_id, generation, callback_id):
    if not callback_id or assigned_task(conn, worker_id, task_id, generation) is None:
        return 'No puedes reportar esta asignación. Revisa /mis_tareas y su recepción.'
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
    return (f'Escribe el avance de la tarea #{task_id} en un solo mensaje (máximo 4000 caracteres). '
            'Quedará por validar. Tienes 30 minutos; /cancelar descarta la captura.')


def saved_reply(report_id, status='pending'):
    return (f'Reporte {folio(report_id)} guardado en Go2Win. Estado: {STATUS_LABELS[status]}. '
            'Este reporte no concluye la tarea. Consulta /mis_reportes.')


def saved_message(conn, worker_id, message):
    row = conn.execute('SELECT id, status FROM field_reports WHERE worker_id=? AND source_chat_id=? AND source_message_id=?',
                       (worker_id, message['chat']['id'], message.get('message_id'))).fetchone()
    return saved_reply(row['id'], row['status']) if row else None


def capture_report(conn, worker_id, message):
    session = conn.execute('SELECT * FROM field_report_sessions WHERE worker_id=?', (worker_id,)).fetchone()
    if session is None:
        return None
    if session['expires_at'] <= int(time.time()):
        conn.execute('DELETE FROM field_report_sessions WHERE worker_id=?', (worker_id,))
        return 'La captura venció sin guardar. Usa /reportar para comenzar de nuevo.'
    if assigned_task(conn, worker_id, session['task_id'], session['generation']) is None:
        conn.execute('DELETE FROM field_report_sessions WHERE worker_id=?', (worker_id,))
        return 'La asignación o tus permisos cambiaron. No se guardó el reporte. Revisa /mis_tareas.'
    if not isinstance(message.get('date'), int) or message['date'] < session['started_at']:
        return 'Ese mensaje es anterior a la captura. Envía un texto nuevo para el reporte.'
    text = message.get('text', '').strip()
    if not text or any(k in message for k in ('photo', 'document', 'video', 'voice', 'audio')):
        return 'Espero un mensaje de texto. Las fotografías todavía no están habilitadas; usa /cancelar para salir.'
    if len(text) > 4000:
        return 'El reporte supera 4000 caracteres. Acórtalo y envíalo de nuevo; aún no se guardó.'
    if not isinstance(message.get('message_id'), int):
        return 'No se pudo identificar el mensaje. Envía el texto nuevamente.'
    rid = conn.execute('''INSERT INTO field_reports
        (task_id,worker_id,generation,body,source_chat_id,source_message_id) VALUES (?,?,?,?,?,?) RETURNING id''',
        (session['task_id'], worker_id, session['generation'], text, message['chat']['id'], message['message_id'])).fetchone()[0]
    conn.execute('DELETE FROM field_report_sessions WHERE worker_id=?', (worker_id,))
    return saved_reply(rid)


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
