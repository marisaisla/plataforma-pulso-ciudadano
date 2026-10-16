"""Ayuda de Telegram según identidad, permisos y captura vigente."""
import time


COMMANDS = [
    ('tasks.view','/mis_tareas — Consultar tus tareas.\n/tarea FOLIO — Ver el detalle de una tarea.'),
    ('reports.submit','/reportar — Enviar un avance en texto o foto.'),
    ('reports.view','/mis_reportes — Consultar tus reportes y sus revisiones.'),
    ('incidents.submit','/incidencia — Registrar un problema de una tarea.'),
    ('supporters.submit','/simpatizante — Registrar una persona con su autorización.'),
    ('needs.submit','/necesidad — Capturar una necesidad territorial.'),
]


def help_reply(conn,uid,unknown=False):
    worker=conn.execute('SELECT id,active,role_key FROM public.field_workers WHERE telegram_user_id=%s',(uid,)).fetchone()
    prefix='Comando desconocido. Consulta /ayuda.\n\n' if unknown else ''
    if not worker:
        return {'status':'help','reply':prefix+'Ayuda Go2Win\nSolicita tu código a coordinación y envía /start CODIGO en este chat privado para vincular tu cuenta.'}
    if not worker['active']:
        return {'status':'help','reply':prefix+'Tu acceso está desactivado. Contacta a coordinación.'}
    grants=conn.execute('SELECT permission_key FROM public.field_role_permissions WHERE role_key=%s AND scope IN (%s,%s,%s,%s)',
                        (worker['role_key'],'own','team','campaign','all')).fetchall()
    permissions={g['permission_key'] for g in grants}
    lines=[prefix+'Ayuda Go2Win','/ayuda — Ver esta guía.','/perfil o /mi_perfil — Ver tu rol, equipo y territorios.']
    lines.extend(text for permission,text in COMMANDS if permission in permissions)
    lines.append('/cancelar — Descartar la captura pendiente.')
    if permissions & {'reports.submit','incidents.submit'}:
        lines.append('Para reportar o registrar una incidencia, primero confirma la recepción de la tarea.\nFotos: envía una sola foto con la descripción en el mismo mensaje, sin álbumes ni archivos.')
    lines.append('Las capturas duran 30 minutos. Los comandos respetan tus campañas y territorios autorizados.')
    now=int(time.time())
    pending=[]
    for table,label in [('field_report_sessions','reporte'),('supporter_sessions','simpatizante'),('field_need_sessions','necesidad')]:
        columns='expires_at,selection_id' if table=='field_report_sessions' else 'expires_at'
        session=conn.execute(f'SELECT {columns} FROM public.{table} WHERE worker_id=%s',(worker['id'],)).fetchone()
        if session and session['expires_at']>now:
            if table=='field_report_sessions' and session['selection_id'].startswith('incident:'):
                label='incidencia'
            pending.append(f"{label} (quedan {(session['expires_at']-now+59)//60} minutos)")
    if pending:
        lines.append('Captura pendiente: '+', '.join(pending)+'.\nContinúa enviando los datos solicitados o usa /cancelar. Consultar ayuda no renueva el plazo.')
    return {'status':'help','reply':'\n\n'.join(lines)}
