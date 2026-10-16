"""Captura persistente de reportes de texto sobre el esquema existente."""
import time
import base64
from fastapi import HTTPException
from backend.tasks import identity, visible_query

INCIDENT_PREFIX = '[INCIDENCIA]\n'


def eligible(conn, uid, tid=None, after=0, limit=6, incident=False):
    # Primero validar permiso de envío, luego visibilidad territorial propia.
    permission='incidents.submit' if incident else 'reports.submit'
    _, scope = identity(conn, uid, permission)
    if scope not in ('own','all'):
        raise HTTPException(403, 'No tienes permiso para reportar tareas propias.')
    return visible_query(conn,uid,task_id=tid,after=after,limit=limit,permission=permission,received_only=True)


def menu(conn, uid, after=0, incident=False):
    route='incident' if incident else 'report'
    rows=eligible(conn,uid,after=after,incident=incident)
    if not rows:
        return {'status':'reports','reply':'No tienes tareas recibidas disponibles para reportar. Consulta /mis_tareas y confirma recepción primero.'}
    buttons=[[{'text':f"#{t['id']} · {t['activity_name'][:65]}",'callback_data':f"{route}select:{t['id']}:{t['generation']}"}] for t in rows[:5]]
    if len(rows)>5:
        buttons.append([{'text':'Más tareas','callback_data':f"{route}page:{rows[4]['id']}"}])
    if incident:
        return {'status':'reports','reply':'Selecciona la tarea donde ocurrió el problema. Describe la incidencia en texto o con una foto y descripción. /cancelar descarta la captura.','reply_markup':{'inline_keyboard':buttons}}
    return {'status':'reports','reply':'Selecciona una tarea para reportar tu avance en texto o con una foto y su descripción. /cancelar descarta la captura.', 'reply_markup':{'inline_keyboard':buttons}}


def select(conn, uid, tid, generation, callback_id, incident=False):
    wid,_=identity(conn,uid,'incidents.submit' if incident else 'reports.submit')
    tasks=eligible(conn,uid,tid,incident=incident)
    if not tasks or tasks[0]['generation']!=generation:
        raise HTTPException(409,'No puedes reportar esta asignación. Revisa /mis_tareas y su recepción.')
    now=int(time.time())
    if incident:
        callback_id='incident:'+callback_id
    previous=conn.execute('SELECT worker_id FROM public.field_report_selections WHERE callback_id=%s',(callback_id,)).fetchone()
    if previous:
        session=conn.execute('SELECT worker_id FROM public.field_report_sessions WHERE worker_id=%s AND selection_id=%s AND expires_at>%s',(wid,callback_id,now)).fetchone()
        if previous['worker_id']!=wid or not session:
            return 'Esta selección ya fue atendida. Usa /reportar para iniciar otro reporte.'
    else:
        conn.execute('INSERT INTO public.field_report_selections (callback_id,worker_id) VALUES (%s,%s)',(callback_id,wid))
        conn.execute('INSERT INTO public.field_report_sessions (worker_id,task_id,generation,selection_id,started_at,expires_at) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT(worker_id) DO UPDATE SET task_id=excluded.task_id,generation=excluded.generation,selection_id=excluded.selection_id,started_at=excluded.started_at,expires_at=excluded.expires_at',(wid,tid,generation,callback_id,now,now+1800))
        for table in ('supporter_sessions','field_need_sessions'):
            conn.execute(f'DELETE FROM public.{table} WHERE worker_id=%s',(wid,))
    if incident:
        return f'Describe la incidencia de la tarea #{tid} en texto (máximo {4000-len(INCIDENT_PREFIX)} caracteres) o con una foto y descripción. Se guardará como INCIDENCIA, por validar. Tienes 30 minutos; /cancelar descarta la captura.'
    return f'Escribe el avance de la tarea #{tid} en texto (máximo 4000 caracteres) o envía una foto con el avance en su descripción. Una foto por reporte, sin álbumes ni archivos. Tienes 30 minutos; /cancelar descarta la captura.'


def saved(row, incident=False):
    labels={'pending':'Por validar','accepted':'Aceptado','correction':'Corrección solicitada'}
    label='Incidencia' if incident else 'Reporte'
    return f"{label} R-{row['id']:06d} guardado en Go2Win. Estado: {labels[row['status']]}. Este reporte no concluye la tarea." + (' Validarlo no significa que el problema esté resuelto.' if incident else '')


def capture(conn, message, photo_loader=None):
    uid=message.sender.id
    worker=conn.execute('SELECT id FROM public.field_workers WHERE telegram_user_id=%s AND active=1',(uid,)).fetchone()
    if not worker:
        raise HTTPException(403,'Cuenta no vinculada o acceso desactivado.')
    wid=worker['id']
    previous=conn.execute('SELECT id,status,body FROM public.field_reports WHERE worker_id=%s AND source_chat_id=%s AND source_message_id=%s',(wid,message.chat.id,message.message_id)).fetchone()
    if previous:
        return saved(previous,previous['body'].startswith(INCIDENT_PREFIX))
    session=conn.execute('SELECT * FROM public.field_report_sessions WHERE worker_id=%s',(wid,)).fetchone()
    if not session:
        return None
    if session['expires_at']<=int(time.time()):
        conn.execute('DELETE FROM public.field_report_sessions WHERE worker_id=%s',(wid,))
        return 'La captura venció sin guardar. Usa /reportar para comenzar de nuevo.'
    incident=session['selection_id'].startswith('incident:')
    tasks=eligible(conn,uid,session['task_id'],incident=incident)
    if not tasks or tasks[0]['generation']!=session['generation']:
        conn.execute('DELETE FROM public.field_report_sessions WHERE worker_id=%s',(wid,))
        return 'La asignación o tus permisos cambiaron. No se guardó el reporte.'
    if message.date is None or message.date<session['started_at']:
        return 'Ese mensaje es anterior a la captura. Envía un texto nuevo.'
    text=((message.caption if message.photo else message.text) or '').strip()
    if message.media_group_id:
        return 'Envía una sola foto con descripción, no un álbum. Aún no se guardó.'
    if any(k in (message.model_extra or {}) for k in ('document','video','voice','audio')) or not text:
        return 'Envía texto o una foto con el avance en su descripción; usa /cancelar para salir.'
    limit=4000-len(INCIDENT_PREFIX) if incident else 4000
    if len(text)>limit:
        return f'El reporte supera {limit} caracteres. Acórtalo; aún no se guardó.'
    if incident:
        text=INCIDENT_PREFIX+text
    photo=None
    content=None
    if message.photo:
        from backend.photos import download_photo, validate_photo, MAX_BYTES
        photo=max(message.photo,key=lambda p:p.width*p.height)
        try:
            if (photo.file_size or 0)>MAX_BYTES or photo.width*photo.height>25_000_000:
                raise ValueError('Límites excedidos.')
            raw=(photo_loader or download_photo)(photo.file_id)
            validate_photo(raw)
            content=base64.b64encode(raw).decode('ascii')
        except ValueError:
            return 'La fotografía debe ser un JPEG válido de hasta 10 MB y 25 millones de píxeles. Envía otra; aún no se guardó.'
    row=conn.execute("INSERT INTO public.field_reports (task_id,worker_id,generation,body,source_chat_id,source_message_id) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id,status",(session['task_id'],wid,session['generation'],text,message.chat.id,message.message_id)).fetchone()
    if photo:
        conn.execute('INSERT INTO public.field_report_photos (report_id,file_id,file_unique_id,content_base64) VALUES (%s,%s,%s,%s)',(row['id'],photo.file_id,photo.file_unique_id,content))
    conn.execute('DELETE FROM public.field_report_sessions WHERE worker_id=%s',(wid,))
    return saved(row,incident)


def process(conn,message,parts):
    uid=message.sender.id
    try:
        worker=conn.execute('SELECT id FROM public.field_workers WHERE telegram_user_id=%s AND active=1',(uid,)).fetchone()
        if not worker:
            raise HTTPException(403,'Cuenta no vinculada o acceso desactivado.')
        wid=worker['id']
        cmd=parts[0].split('@')[0].lower() if parts else ''
        if cmd=='/cancelar':
            conn.execute('DELETE FROM public.field_report_sessions WHERE worker_id=%s',(wid,))
            return {'status':'reports','reply':'Captura de reporte cancelada. No se guardó un nuevo reporte.'}
        if cmd in ('/reportar','/incidencia'):
            for table in ('supporter_sessions','field_need_sessions'):
                conn.execute(f'DELETE FROM public.{table} WHERE worker_id=%s',(wid,))
            conn.execute('DELETE FROM public.field_report_sessions WHERE worker_id=%s',(wid,))
            return menu(conn,uid,incident=cmd=='/incidencia')
        if cmd.startswith('/'):
            return None
        reply=capture(conn,message)
        return {'status':'reports','reply':reply} if reply else None
    except HTTPException as exc:
        return {'status':'rejected','reply':exc.detail}


def callback(conn,cb):
    parts=cb.data.split(':')
    incident=parts[0].startswith('incident')
    try:
        if parts[0] in ('reportpage','incidentpage') and len(parts)==2 and parts[1].isascii() and parts[1].isdigit() and len(parts[1])<=18:
            return menu(conn,cb.sender.id,int(parts[1]),incident=incident)
        if len(parts)!=3 or parts[0] not in ('reportselect','incidentselect') or not parts[1].isascii() or not parts[1].isdigit() or len(parts[1])>18:
            return {'status':'rejected','reply':'Selección inválida. Usa /reportar.'}
        return {'status':'reports','reply':select(conn,cb.sender.id,int(parts[1]),parts[2],cb.id,incident=incident)}
    except HTTPException as exc:
        return {'status':'rejected','reply':exc.detail}


def history(conn,uid,before=9223372036854775807):
    from backend.permissions import allowed
    worker=conn.execute('SELECT id FROM public.field_workers WHERE telegram_user_id=%s AND active=1',(uid,)).fetchone()
    if not worker: return {'status':'rejected','reply':'Cuenta no vinculada o acceso desactivado.'}
    rows=conn.execute('''SELECT r.*,t.profile_id,t.state,t.municipality,v.note FROM public.field_reports r
        JOIN public.territorial_action_plans t ON t.id=r.task_id LEFT JOIN public.field_report_reviews v ON v.report_id=r.id
        WHERE r.worker_id=%s AND r.id<%s ORDER BY r.id DESC''',(worker['id'],before)).fetchall()
    visible=[]
    for row in rows:
        if allowed(conn,worker['id'],'reports.view',row,worker['id']):
            visible.append(row)
            if len(visible)==3: break
    if not visible: return {'status':'reports','reply':'No hay reportes visibles en esta página. Usa /mis_reportes para volver al inicio.'}
    labels={'pending':'Por validar','accepted':'Aceptado','correction':'Corrección solicitada'}
    reply='\n\n'.join(f"{'Incidencia · ' if r['body'].startswith(INCIDENT_PREFIX) else ''}R-{r['id']:06d} · tarea #{r['task_id']} · {labels[r['status']]}\n{r['created_at']} UTC\n{r['body'][:100]}\nRevisión: {r['note'] or 'Sin observaciones'}" for r in visible[:2])
    result={'status':'reports','reply':reply}
    if len(visible)>2:
        result['reply_markup']={'inline_keyboard':[[{'text':'Reportes anteriores','callback_data':f"reporthistory:{visible[1]['id']}"}]]}
    return result
