"""Vinculación PostgreSQL; no envía mensajes ni importa servicios existentes."""
import hashlib
import secrets
import time

from fastapi import HTTPException


def serialize_changes(conn):
    # El integrador y los servicios actuales utilizan este mismo bloqueo.
    conn.execute('SELECT pg_advisory_xact_lock(720260928)')


def issue_code(conn, worker_id):
    serialize_changes(conn)
    worker = conn.execute('SELECT * FROM public.field_workers WHERE id=%s FOR UPDATE',
                          (worker_id,)).fetchone()
    if not worker:
        raise HTTPException(404, 'Trabajador no encontrado.')
    if not worker['active'] or worker['telegram_user_id'] is not None:
        raise HTTPException(409, 'El trabajador debe estar activo y sin vínculo.')
    code = secrets.token_hex(16)
    expires_at = int(time.time()) + 1800
    conn.execute('DELETE FROM public.field_activation_codes WHERE worker_id=%s', (worker_id,))
    conn.execute('INSERT INTO public.field_activation_codes '
                 '(code_hash, worker_id, expires_at, consumed_at) VALUES (%s,%s,%s,NULL)',
                 (hashlib.sha256(code.encode()).hexdigest(), worker_id, expires_at))
    return {'worker_id': worker_id, 'activation_code': code,
            'command': '/start ' + code, 'expires_at': expires_at}


def process_message(conn, message):
    sender = message.sender
    if message.chat.type != 'private' or sender.is_bot or message.chat.id != sender.id:
        return {'status': 'ignored', 'reply': None}
    parts = (message.text or '').split()
    command=parts[0].split('@')[0].lower() if parts else ''
    if command=='/mis_reportes':
        from backend.reports import history
        serialize_changes(conn)
        return history(conn,sender.id)
    if command=='/evidencia':
        return {'status':'reports','reply':'Usa /reportar para enviar texto o una foto con descripción sobre una tarea recibida.'}
    known={'/start','/perfil','/mi_perfil','/mis_tareas','/tarea','/reportar','/incidencia','/simpatizante','/necesidad','/cancelar'}
    if command=='/ayuda' or (command.startswith('/') and command not in known):
        from backend.help import help_reply
        serialize_changes(conn)
        return help_reply(conn,sender.id,unknown=command!='/ayuda')
    if parts and parts[0].split('@')[0].lower() in ('/perfil','/mi_perfil'):
        from backend.profile import profile_reply
        serialize_changes(conn)
        return profile_reply(conn,sender.id)
    if not parts or parts[0].split('@')[0].lower() not in ('/start','/mis_tareas','/tarea','/reportar','/simpatizante'):
        from backend.needs import process as process_need
        serialize_changes(conn)
        result=process_need(conn,message,parts)
        if result:
            return result
    if not parts or parts[0].split('@')[0].lower() not in ('/start','/mis_tareas','/tarea','/reportar'):
        from backend.supporters import process as process_supporter
        serialize_changes(conn)
        result=process_supporter(conn,message,parts)
        if result:
            return result
    if not parts or parts[0].split('@')[0].lower() not in ('/start','/mis_tareas','/tarea'):
        from backend.reports import process
        serialize_changes(conn)
        result = process(conn, message, parts)
        if result:
            return result
    if parts and parts[0].split('@')[0].lower() in ('/mis_tareas', '/tarea'):
        from backend.tasks import command_reply, command_buttons
        serialize_changes(conn)
        return {'status': 'tasks', 'reply': command_reply(conn, sender.id, parts),
                'reply_markup': command_buttons(conn, sender.id, parts)}
    if len(parts) != 2 or parts[0].split('@')[0].lower() != '/start':
        return {'status': 'unsupported', 'reply': None}
    serialize_changes(conn)
    worker = conn.execute('SELECT * FROM public.field_workers WHERE telegram_user_id=%s',
                          (sender.id,)).fetchone()
    if worker:
        if not worker['active']:
            return {'status': 'rejected', 'reply': 'Tu acceso está desactivado. Contacta a coordinación.'}
        return {'status': 'already_linked', 'reply': 'Tu cuenta de Telegram ya está vinculada.'}
    now = int(time.time())
    row = conn.execute(
        'SELECT c.worker_id FROM public.field_activation_codes c '
        'JOIN public.field_workers w ON w.id=c.worker_id '
        'WHERE c.code_hash=%s AND c.expires_at>%s AND c.consumed_at IS NULL '
        'AND w.active=1 AND w.telegram_user_id IS NULL FOR UPDATE OF c,w',
        (hashlib.sha256(parts[1].encode()).hexdigest(), now),
    ).fetchone()
    if not row:
        return {'status': 'rejected', 'reply': 'Código inválido, vencido o utilizado. Solicita uno nuevo a coordinación.'}
    conn.execute('UPDATE public.field_workers SET telegram_user_id=%s, telegram_chat_id=%s, '
                 'linked_at=%s WHERE id=%s', (sender.id, message.chat.id, now, row['worker_id']))
    conn.execute('UPDATE public.field_activation_codes SET consumed_at=%s WHERE worker_id=%s',
                 (now, row['worker_id']))
    return {'status': 'linked', 'reply': 'Acceso activado en Go2Win. Tu cuenta de Telegram quedó vinculada.'}


def process_callback(conn, callback):
    from backend.tasks import confirm_receipt
    if not callback.message or callback.message.chat.type != 'private' or callback.sender.is_bot or callback.message.chat.id != callback.sender.id:
        return {'status': 'ignored', 'reply': None}
    parts = callback.data.split(':')
    if parts[0]=='reporthistory':
        from backend.reports import history
        if len(parts)!=2 or not parts[1].isascii() or not parts[1].isdigit() or len(parts[1])>18:
            return {'status':'rejected','reply':'Usa /mis_reportes para consultar tus reportes.'}
        serialize_changes(conn)
        return history(conn,callback.sender.id,int(parts[1]))
    if parts[0]=='needcampaign':
        from backend.needs import callback as need_callback
        serialize_changes(conn)
        return need_callback(conn,callback)
    if parts[0]=='supportcampaign':
        from backend.supporters import callback as supporter_callback
        serialize_changes(conn)
        return supporter_callback(conn,callback)
    if parts[0] in ('reportselect','reportpage','incidentselect','incidentpage'):
        from backend.reports import callback as report_callback
        serialize_changes(conn)
        return report_callback(conn, callback)
    if len(parts)!=3 or parts[0]!='taskconfirm' or not parts[1].isascii() or not parts[1].isdigit() or len(parts[1])>18 or int(parts[1])<=0:
        return {'status': 'unsupported', 'reply': None}
    serialize_changes(conn)
    try:
        return {'status':'received', 'reply':confirm_receipt(conn, callback.sender.id, int(parts[1]), parts[2])}
    except HTTPException as exc:
        return {'status':'rejected','reply':exc.detail}
