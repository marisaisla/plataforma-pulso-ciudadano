"""Consultas de tareas propias con permisos obtenidos de PostgreSQL."""
from fastapi import HTTPException


def identity(conn, telegram_user_id, permission='tasks.view'):
    worker = conn.execute('SELECT id, active, role_key FROM public.field_workers WHERE telegram_user_id=%s',
                          (telegram_user_id,)).fetchone()
    if not worker or not worker['active']:
        raise HTTPException(403, 'Cuenta no vinculada o acceso desactivado.')
    grant = conn.execute('SELECT scope FROM public.field_role_permissions WHERE role_key=%s AND permission_key=%s',
                         (worker['role_key'], permission)).fetchone()
    if not grant or grant['scope'] not in ('own', 'team', 'campaign', 'all'):
        raise HTTPException(403, 'No tienes permiso para consultar tareas.')
    return worker['id'], grant['scope']


def visible_query(conn, telegram_user_id, task_id=None, after=0, limit=3, permission='tasks.view', received_only=False):
    worker_id, scope = identity(conn, telegram_user_id, permission)
    sql = '''SELECT t.id, t.profile_id, t.activity_name, t.activity_description,
        t.state, t.municipality, t.due_date, t.status, a.received_at, a.generation
        FROM public.territorial_action_plans t
        JOIN public.field_task_assignments a ON a.task_id=t.id
        WHERE a.worker_id=%s AND t.status IN ('Pendiente','En curso')'''
    params = [worker_id]
    if received_only:
        sql += ' AND a.received_at IS NOT NULL'
    if scope != 'all':
        sql += ''' AND EXISTS (SELECT 1 FROM public.field_worker_scopes s
            WHERE s.worker_id=a.worker_id AND s.profile_id=t.profile_id
            AND (s.state='' OR s.state=t.state)
            AND (s.municipality='' OR s.municipality=t.municipality))'''
    if task_id is not None:
        sql += ' AND t.id=%s'
        params.append(task_id)
    else:
        sql += ' AND t.id>%s'
        params.append(after)
    sql += ' ORDER BY t.id LIMIT %s'
    params.append(limit)
    return conn.execute(sql, params).fetchall()


def list_tasks(conn, telegram_user_id, after=0, limit=3):
    rows = visible_query(conn, telegram_user_id, after=after, limit=limit+1)
    return {'items': rows[:limit], 'next_after': rows[limit-1]['id'] if len(rows)>limit else None}


def get_task(conn, telegram_user_id, task_id):
    rows = visible_query(conn, telegram_user_id, task_id=task_id, limit=1)
    if not rows:
        raise HTTPException(404, 'Tarea no disponible para tu usuario.')
    return rows[0]


def can_confirm(conn, telegram_user_id, task):
    try:
        _, scope = identity(conn, telegram_user_id, 'tasks.confirm')
        return scope in ('own', 'all')
    except HTTPException:
        return False


def command_buttons(conn, telegram_user_id, parts):
    try:
        if parts[0].split('@')[0].lower() == '/mis_tareas':
            if len(parts)>2 or (len(parts)==2 and (not parts[1].isascii() or not parts[1].isdigit() or len(parts[1])>18)):
                return None
            tasks = list_tasks(conn, telegram_user_id, int(parts[1]) if len(parts)==2 else 0)['items']
        else:
            if len(parts) not in (2,3) or any(not p.isascii() or not p.isdigit() or len(p)>18 for p in parts[1:]) or int(parts[1])<=0:
                return None
            tasks = [get_task(conn, telegram_user_id, int(parts[1]))]
        buttons = [[{'text': f"Confirmar recepción #{t['id']}",
                     'callback_data': f"taskconfirm:{t['id']}:{t['generation']}"}]
                   for t in tasks if not t['received_at'] and can_confirm(conn, telegram_user_id, t)]
        from backend.surveys import questionnaire_button
        for task in tasks:
            button = questionnaire_button(conn, telegram_user_id, task)
            if button:
                buttons.append([button])
        return {'inline_keyboard': buttons} if buttons else None
    except HTTPException:
        return None


def confirm_receipt(conn, telegram_user_id, task_id, generation):
    # El caller adquiere serialize_changes en la misma transacción.
    task = get_task(conn, telegram_user_id, task_id)
    worker_id, _ = identity(conn, telegram_user_id)
    if task['generation'] != generation or not can_confirm(conn, telegram_user_id, task):
        raise HTTPException(409, 'No puedes confirmar esta asignación. Puede haber cambiado o tus permisos fueron retirados.')
    if task['received_at']:
        return f"La recepción de la tarea #{task_id} ya estaba registrada: {task['received_at']} UTC."
    received = conn.execute("UPDATE public.field_task_assignments SET received_at=to_char(CURRENT_TIMESTAMP AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS') WHERE task_id=%s AND worker_id=%s AND generation=%s RETURNING received_at",
                            (task_id, worker_id, generation)).fetchone()
    if not received:
        raise HTTPException(409, 'La asignación cambió. Usa /mis_tareas.')
    conn.execute("INSERT INTO public.field_task_events (task_id,worker_id,generation,event,actor) VALUES (%s,%s,%s,'received',%s)",
                 (task_id,worker_id,generation,f'telegram_worker:{worker_id}'))
    return f'Recepción de la tarea #{task_id} registrada en Go2Win. Esto no marca la actividad como concluida.'


def command_reply(conn, telegram_user_id, parts):
    command = parts[0].split('@')[0].lower()
    try:
        if command == '/mis_tareas':
            if len(parts)>2 or (len(parts)==2 and (not parts[1].isascii() or not parts[1].isdigit() or len(parts[1])>18)):
                return 'Uso: /mis_tareas o /mis_tareas ULTIMO_FOLIO'
            page = list_tasks(conn, telegram_user_id, int(parts[1]) if len(parts)==2 else 0)
            if not page['items']:
                return 'No hay tareas activas asignadas a ti dentro de tu alcance.'
            lines = ['Mis tareas · actividades asignadas a ti']
            for t in page['items']:
                lines.append(f"\n#{t['id']} · {t['activity_name'][:100]}\n{(t['state'] or '')[:50]} / {(t['municipality'] or '')[:60]}\nFecha: {t['due_date'] or 'Sin fecha'} · {t['status']}\nResumen: {(t['activity_description'] or 'Sin descripción')[:180]}\nVer detalle: /tarea {t['id']}\nRecepción: {t['received_at'] or 'Por confirmar'}")
            if page['next_after'] is not None:
                lines.append(f"\nSiguientes: /mis_tareas {page['next_after']}")
            return '\n'.join(lines)
        if len(parts) not in (2,3) or any(not p.isascii() or not p.isdigit() or len(p)>18 for p in parts[1:]) or int(parts[1])<=0:
            return 'Uso: /tarea FOLIO o /tarea FOLIO PAGINA'
        task = get_task(conn, telegram_user_id, int(parts[1]))
        full = f"Tarea #{task['id']}: {task['activity_name']}\n{task['state'] or ''} / {task['municipality'] or ''}\nFecha: {task['due_date'] or 'Sin fecha'} · {task['status']}\n\n{task['activity_description'] or 'Sin descripción'}"
        page = int(parts[2]) if len(parts)==3 else 1
        count = max(1, (len(full)+1799)//1800)
        if page<1 or page>count:
            return f'Página inválida. Esta tarea tiene {count} páginas.'
        reply = f'Página {page}/{count}\n' + full[(page-1)*1800:page*1800]
        if page<count:
            reply += f"\nContinuar: /tarea {task['id']} {page+1}"
        return reply
    except HTTPException as exc:
        return exc.detail
