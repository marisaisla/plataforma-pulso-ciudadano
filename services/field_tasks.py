"""Asignación local y recepción por Telegram sobre las actividades existentes."""
import secrets
from contextlib import closing

from services.database import connection
from services.field_permissions import can_access


def initialize_tasks(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS field_task_assignments (
        task_id INTEGER PRIMARY KEY REFERENCES territorial_action_plans(id),
        worker_id INTEGER NOT NULL REFERENCES field_workers(id),
        generation TEXT NOT NULL,
        assigned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        received_at TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS field_task_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL REFERENCES territorial_action_plans(id),
        worker_id INTEGER NOT NULL REFERENCES field_workers(id),
        generation TEXT NOT NULL, event TEXT NOT NULL,
        actor TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
    conn.execute('CREATE INDEX IF NOT EXISTS field_task_worker_idx ON field_task_assignments(worker_id, task_id)')


def context(task, worker_id):
    return {'profile_id': task['profile_id'], 'state': task['state'],
            'municipality': task['municipality'], 'assigned_worker_id': worker_id}


def task_is_open(task):
    return task['status'] in {'Pendiente', 'En curso'}


def eligible_workers(task_id):
    with closing(connection()) as conn:
        task = conn.execute('SELECT * FROM territorial_action_plans WHERE id = ?', (task_id,)).fetchone()
        if task is None:
            return []
        return [dict(w) for w in conn.execute('SELECT * FROM field_workers WHERE active = 1 ORDER BY name, id')
                if can_access(w['id'], 'tasks.confirm', conn=conn, **context(task, w['id']))]


def assign_task_locally(task_id, worker_id, *, session_token=None):
    """La consola local es administrativa. No exponer esta función como API anónima."""
    with closing(connection()) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        task = conn.execute('SELECT * FROM territorial_action_plans WHERE id = ?', (task_id,)).fetchone()
        if task is None or not task_is_open(task):
            raise ValueError('La actividad debe existir y estar pendiente o en curso.')
        previous = conn.execute('SELECT * FROM field_task_assignments WHERE task_id = ?', (task_id,)).fetchone()
        actor = 'local_console'
        if session_token is not None:
            from services.web_auth import require_user
            user = require_user(session_token, conn)
            targets = [worker_id] + ([previous['worker_id']] if previous else [])
            if not all(can_access(user['id'], 'tasks.assign', conn=conn, **context(task, wid)) for wid in targets):
                raise PermissionError('No tienes permiso para cambiar esta asignación.')
            actor = f"worker:{user['id']}"
        if worker_id is not None and not can_access(worker_id, 'tasks.confirm', conn=conn, **context(task, worker_id)):
            raise ValueError('El trabajador está inactivo o no tiene permiso y alcance para esta actividad.')
        if previous and previous['worker_id'] == worker_id:
            return  # Guardar de nuevo no borra la recepción ni cambia el botón vigente.
        if previous:
            conn.execute('INSERT INTO field_task_events (task_id, worker_id, generation, event, actor) '
                         "VALUES (?, ?, ?, 'unassigned', ?)",
                         (task_id, previous['worker_id'], previous['generation'], actor))
            conn.execute('DELETE FROM field_task_assignments WHERE task_id = ?', (task_id,))
        if worker_id is not None:
            generation = secrets.token_hex(8)
            conn.execute('INSERT INTO field_task_assignments (task_id, worker_id, generation) VALUES (?, ?, ?)',
                         (task_id, worker_id, generation))
            conn.execute('INSERT INTO field_task_events (task_id, worker_id, generation, event, actor) '
                         "VALUES (?, ?, ?, 'assigned', ?)", (task_id, worker_id, generation, actor))


def get_assignment(task_id):
    with closing(connection()) as conn:
        row = conn.execute('SELECT a.*, w.name FROM field_task_assignments a JOIN field_workers w '
                           'ON w.id = a.worker_id WHERE task_id = ?', (task_id,)).fetchone()
        return dict(row) if row else None


def task_page(conn, worker_id, after=0):
    """Solo tareas propias, incluso para administradores; consultas de equipo quedan aparte."""
    rows = conn.execute('''SELECT t.*, a.generation, a.received_at FROM territorial_action_plans t
        JOIN field_task_assignments a ON a.task_id = t.id
        WHERE a.worker_id = ? AND t.id > ? AND t.status IN ('Pendiente', 'En curso') ORDER BY t.id''',
                        (worker_id, after))
    visible = []
    for task in rows:
        if can_access(worker_id, 'tasks.view', conn=conn, **context(task, worker_id)):
            visible.append(dict(task))
            if len(visible) == 4:
                break
    if not visible:
        return {'text': 'No hay tareas activas asignadas a ti dentro de tu alcance en esta página. '
                        'Si esperabas una, pide a coordinación revisar la asignación y tu territorio. '
                        'Usa /mis_tareas para volver al inicio.'}
    lines = ['Mis tareas · actividades asignadas a ti']
    buttons = []
    for task in visible[:3]:
        tid = task['id']
        lines.append(f"\n#{tid} · {task['activity_name'][:100]}\n"
                     f"{task['state'][:50]} / {task['municipality'][:60]}\n"
                     f"Fecha: {(task['due_date'] or 'Sin fecha')[:30]} · {task['status']}\n"
                     f"Resumen: {(task['activity_description'] or 'Sin descripción')[:180]}\n"
                     f"Ver detalle: /tarea {tid}\n"
                     f"Recepción: {task['received_at'] + ' UTC' if task['received_at'] else 'Por confirmar'}")
        if not task['received_at'] and can_access(worker_id, 'tasks.confirm', conn=conn, **context(task, worker_id)):
            buttons.append([{'text': f'Confirmar recepción #{tid}',
                             'callback_data': f"taskconfirm:{tid}:{task['generation']}"}])
    if len(visible) > 3:
        buttons.append([{'text': 'Siguientes tareas', 'callback_data': f"taskpage:{visible[2]['id']}"}])
    if after:
        buttons.append([{'text': 'Volver al inicio', 'callback_data': 'taskpage:0'}])
    result = {'text': '\n'.join(lines)}
    if buttons:
        result['reply_markup'] = {'inline_keyboard': buttons}
    return result


def task_detail(conn, worker_id, task_id, offset=0):
    task = conn.execute('''SELECT t.*, a.generation, a.received_at FROM territorial_action_plans t
        JOIN field_task_assignments a ON a.task_id = t.id WHERE t.id = ? AND a.worker_id = ?''',
                        (task_id, worker_id)).fetchone()
    if task is None or not task_is_open(task) or not can_access(worker_id, 'tasks.view', conn=conn, **context(task, worker_id)):
        return {'text': 'Esta actividad no está disponible para tu usuario. Usa /mis_tareas.'}
    full = (f"Tarea #{task_id}: {task['activity_name']}\n{task['state']} / {task['municipality']}\n"
            f"Fecha: {task['due_date'] or 'Sin fecha'} · {task['status']}\n\n"
            f"{task['activity_description'] or 'Sin descripción'}")
    offset = offset if 0 <= offset < len(full) else 0
    buttons = []
    if offset + 1800 < len(full):
        buttons.append([{'text': 'Continuar detalle', 'callback_data': f'taskdetail:{task_id}:{offset+1800}'}])
    if not task['received_at'] and can_access(worker_id, 'tasks.confirm', conn=conn, **context(task, worker_id)):
        buttons.append([{'text': f'Confirmar recepción #{task_id}',
                         'callback_data': f"taskconfirm:{task_id}:{task['generation']}"}])
    result = {'text': full[offset:offset+1800]}
    if buttons:
        result['reply_markup'] = {'inline_keyboard': buttons}
    return result


def confirm_task(conn, worker_id, task_id, generation):
    """Debe llamarse dentro de BEGIN IMMEDIATE; permiso y cambio usan la misma transacción."""
    row = conn.execute('''SELECT t.*, a.worker_id, a.generation, a.received_at
        FROM territorial_action_plans t JOIN field_task_assignments a ON a.task_id = t.id WHERE t.id = ?''',
                       (task_id,)).fetchone()
    if (row is None or row['worker_id'] != worker_id or row['generation'] != generation
            or not task_is_open(row)
            or not can_access(worker_id, 'tasks.confirm', conn=conn, **context(row, worker_id))):
        return 'No puedes confirmar esta asignación. Puede haber cambiado o ya no estar activa. Usa /mis_tareas.'
    if row['received_at']:
        return f"La recepción de la tarea #{task_id} ya estaba registrada: {row['received_at']} UTC."
    conn.execute('UPDATE field_task_assignments SET received_at = CURRENT_TIMESTAMP WHERE task_id = ?', (task_id,))
    conn.execute('INSERT INTO field_task_events (task_id, worker_id, generation, event, actor) '
                 "VALUES (?, ?, ?, 'received', ?)", (task_id, worker_id, generation, f'telegram_worker:{worker_id}'))
    return f'Recepción de la tarea #{task_id} registrada en Go2Win. Esto no marca la actividad como concluida.'
