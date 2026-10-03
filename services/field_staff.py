"""Registro local de trabajadores y activación de Telegram para un solo bot."""
import hashlib
import secrets
import time
from contextlib import closing

from services.database import connection, is_postgresql
from services.field_permissions import initialize_permissions, describe_access, audit
from services.field_tasks import initialize_tasks, task_page, task_detail, confirm_task
from services.field_reports import (
    initialize_reports, report_menu, select_report_task, capture_report, saved_message, my_reports,
)


def initialize_staff():
    if is_postgresql():
        from services.postgres_backend import validate_schema
        validate_schema()
        return
    with closing(connection()) as conn, conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS field_workers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                team TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                telegram_user_id INTEGER UNIQUE,
                telegram_chat_id INTEGER UNIQUE,
                linked_at INTEGER,
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS field_activation_codes (
                code_hash TEXT PRIMARY KEY,
                worker_id INTEGER NOT NULL REFERENCES field_workers(id),
                expires_at INTEGER NOT NULL,
                consumed_at INTEGER
            );
        """)
        conn.execute('BEGIN IMMEDIATE')
        initialize_permissions(conn)
        initialize_tasks(conn)
        initialize_reports(conn)


def create_worker(name, team=''):
    name, team = name.strip(), team.strip()
    if not name or len(name) > 120 or len(team) > 120:
        raise ValueError('Escribe un nombre y usa como máximo 120 caracteres por campo.')
    with closing(connection()) as conn, conn:
        return conn.execute(
            'INSERT INTO field_workers (name, team, created_at) VALUES (?, ?, ?) RETURNING id',
            (name, team, int(time.time())),
        ).fetchone()[0]


def list_workers():
    with closing(connection()) as conn:
        return [dict(row) for row in conn.execute('SELECT * FROM field_workers ORDER BY name, id')]


def issue_code(worker_id):
    code = secrets.token_hex(16)
    with closing(connection()) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        worker = conn.execute('SELECT * FROM field_workers WHERE id = ?', (worker_id,)).fetchone()
        if not worker or not worker['active'] or worker['telegram_user_id'] is not None:
            raise ValueError('El trabajador debe estar activo y sin vínculo con Telegram.')
        conn.execute('DELETE FROM field_activation_codes WHERE worker_id = ?', (worker_id,))
        conn.execute('INSERT INTO field_activation_codes VALUES (?, ?, ?, NULL)',
                     (hashlib.sha256(code.encode()).hexdigest(), worker_id, int(time.time()) + 1800))
    return code


def set_worker_active(worker_id, active):
    with closing(connection()) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        from services.web_auth import protect_last_admin
        protect_last_admin(conn, worker_id, active=bool(active))
        if not active:
            from services.web_auth import revoke_worker_sessions
            revoke_worker_sessions(conn, worker_id)
        conn.execute('UPDATE field_workers SET active = ? WHERE id = ?', (int(active), worker_id))
        conn.execute('DELETE FROM field_activation_codes WHERE worker_id = ?', (worker_id,))
        conn.execute('DELETE FROM field_report_sessions WHERE worker_id = ?', (worker_id,))
        audit(conn, worker_id, 'active_changed', {'active': bool(active)})


def unlink_worker(worker_id):
    with closing(connection()) as conn, conn:
        conn.execute('UPDATE field_workers SET telegram_user_id = NULL, telegram_chat_id = NULL, '
                     'linked_at = NULL WHERE id = ?', (worker_id,))
        conn.execute('DELETE FROM field_activation_codes WHERE worker_id = ?', (worker_id,))
        conn.execute('DELETE FROM field_report_sessions WHERE worker_id = ?', (worker_id,))
        audit(conn, worker_id, 'telegram_unlinked', {})


def telegram_reply(message):
    """Activa identidades, consulta tareas y guarda reportes de texto."""
    chat, sender = message.get('chat', {}), message.get('from', {})
    if (chat.get('type') != 'private' or not isinstance(sender.get('id'), int)
            or chat.get('id') != sender['id'] or sender.get('is_bot')):
        return None
    parts = (message.get('text') or '').split()
    command = parts[0].split('@')[0].lower() if parts else ''
    with closing(connection()) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        worker = conn.execute('SELECT * FROM field_workers WHERE telegram_user_id = ?',
                              (sender['id'],)).fetchone()
        if worker and not worker['active']:
            return 'Tu acceso está desactivado. Contacta a coordinación.'
        if command == '/start' and len(parts) == 2 and not worker:
            code = parts[1]
            row = conn.execute(
                'SELECT c.worker_id FROM field_activation_codes c JOIN field_workers w '
                'ON w.id = c.worker_id WHERE c.code_hash = ? AND c.expires_at > ? '
                'AND c.consumed_at IS NULL AND w.active = 1 AND w.telegram_user_id IS NULL',
                (hashlib.sha256(code.encode()).hexdigest(), int(time.time())),
            ).fetchone()
            if row is None:
                return 'Código inválido, vencido o utilizado. Solicita uno nuevo a coordinación.'
            conn.execute('UPDATE field_workers SET telegram_user_id = ?, telegram_chat_id = ?, '
                         'linked_at = ? WHERE id = ?',
                         (sender['id'], chat['id'], int(time.time()), row['worker_id']))
            conn.execute('UPDATE field_activation_codes SET consumed_at = ? WHERE worker_id = ?',
                         (int(time.time()), row['worker_id']))
            return 'Acceso activado en Go2Win. Tu cuenta de Telegram quedó vinculada. '
        if not worker:
            return 'Solicita tu código a coordinación y envía /start CODIGO para activar tu acceso.'
        duplicate = saved_message(conn, worker['id'], message)
        if duplicate:
            return duplicate
        if command == '/reportar':
            conn.execute('DELETE FROM field_report_sessions WHERE worker_id=?', (worker['id'],))
            return report_menu(conn, worker['id'])
        if command == '/mis_reportes':
            return my_reports(conn, worker['id'])
        if command == '/mi_perfil':
            return describe_access(conn, worker)[:4000]
        if command == '/mis_tareas':
            return task_page(conn, worker['id'])
        if command == '/tarea':
            if len(parts) == 2 and parts[1].isascii() and parts[1].isdigit() and len(parts[1]) <= 18:
                return task_detail(conn, worker['id'], int(parts[1]))
            return 'Envía /tarea seguido del folio, por ejemplo /tarea 12.'
        if command in {'/start', '/ayuda'}:
            return ('Tu cuenta de Telegram ya está vinculada a Go2Win. '
                    'Usa /mi_perfil para consultar tu rol y alcance. '
                    'Usa /mis_tareas para consultar tus actividades y confirmar recepción. '
                    'Usa /reportar para registrar un avance y /mis_reportes para consultar su revisión. '
                    'Las fotografías siguen pendientes.')
        if command == '/cancelar':
            conn.execute('DELETE FROM field_report_sessions WHERE worker_id=?', (worker['id'],))
            return 'Captura cancelada. No se guardó ningún reporte nuevo.'
        if not command.startswith('/'):
            result = capture_report(conn, worker['id'], message)
            if result:
                return result
        return ('Usa /reportar para enviar un avance de texto, /mis_reportes para revisar su estado '
                'o /cancelar para salir de una captura. No se guardó ningún reporte ni archivo.')


def telegram_callback(callback):
    """Identidad desde Telegram; nunca confiar en usuario o territorio codificados en el botón."""
    sender = callback.get('from', {})
    chat = callback.get('message', {}).get('chat', {})
    if (chat.get('type') != 'private' or not isinstance(sender.get('id'), int)
            or chat.get('id') != sender['id'] or sender.get('is_bot')):
        return None
    with closing(connection()) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        worker = conn.execute('SELECT * FROM field_workers WHERE telegram_user_id = ? AND active = 1',
                              (sender['id'],)).fetchone()
        if worker is None:
            return 'Tu cuenta no tiene acceso activo. Contacta a coordinación.'
        parts = str(callback.get('data', '')).split(':')
        if len(parts) >= 2 and parts[1].isascii() and parts[1].isdigit() and len(parts[1]) <= 18:
            tid = int(parts[1])
            if len(parts) == 2 and parts[0] == 'taskpage':
                return task_page(conn, worker['id'], tid)
            if len(parts) == 2 and parts[0] == 'reportpage':
                return report_menu(conn, worker['id'], tid)
            if len(parts) == 2 and parts[0] == 'reporthistory':
                return my_reports(conn, worker['id'], tid)
            if len(parts) == 3 and parts[0] == 'reportselect':
                return select_report_task(conn, worker['id'], tid, parts[2], callback.get('id'))
            if len(parts) == 3 and parts[0] == 'taskconfirm':
                return confirm_task(conn, worker['id'], tid, parts[2])
            if (len(parts) == 3 and parts[0] == 'taskdetail' and parts[2].isascii()
                    and parts[2].isdigit() and len(parts[2]) <= 18):
                return task_detail(conn, worker['id'], tid, int(parts[2]))
        return 'Este botón no es válido. Usa /mis_tareas para consultar las opciones actuales.'
