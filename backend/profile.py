"""Perfil de la identidad Telegram, consultado en PostgreSQL."""
ROLE_LABELS = {'field':'Personal de campo','supervisor':'Supervisor','coordinator':'Coordinador',
               'director':'Director de campaña','administrator':'Administrador'}
SCOPE_LABELS = {'own':'Propias','team':'Equipo a cargo','campaign':'Campaña autorizada','all':'Toda la operación'}


def profile_reply(conn, telegram_user_id):
    worker=conn.execute('SELECT id,role_key,team,active FROM public.field_workers WHERE telegram_user_id=%s',
                        (telegram_user_id,)).fetchone()
    if not worker:
        return {'status':'rejected','reply':'Solicita tu código a coordinación y envía /start CODIGO para activar tu acceso.'}
    if not worker['active']:
        return {'status':'rejected','reply':'Tu acceso está desactivado. Contacta a coordinación.'}
    grants=conn.execute('SELECT p.label, g.scope FROM public.field_role_permissions g JOIN public.field_permissions p ON p.key=g.permission_key WHERE g.role_key=%s ORDER BY g.permission_key',
                        (worker['role_key'],)).fetchall()
    scopes=conn.execute('SELECT p.name,s.state,s.municipality FROM public.field_worker_scopes s JOIN public.profiles p ON p.id=s.profile_id WHERE s.worker_id=%s ORDER BY s.profile_id,s.state,s.municipality',
                        (worker['id'],)).fetchall()
    lines=[f"Rol: {ROLE_LABELS.get(worker['role_key'],'Sin rol válido')}",f"Equipo: {worker['team'] or 'Sin asignar'}"]
    if worker['role_key']=='administrator':
        lines.append('Alcance: toda la operación.')
    else:
        lines.append('Alcances: '+ ('; '.join(f"{s['name']} / {s['state'] or 'todos los estados'} / {s['municipality'] or 'todos los municipios'}" for s in scopes) if scopes else 'Sin asignar; solicita a coordinación tu campaña y territorio.'))
    lines.append('Permisos del rol:\n'+ ('\n'.join(f"• {g['label']}: {SCOPE_LABELS.get(g['scope'],'Sin alcance válido')}" for g in grants) or 'Sin permisos asignados.'))
    lines.append('Comandos: /mis_tareas, /tarea FOLIO, /reportar, /simpatizante, /necesidad y /cancelar.')
    return {'status':'profile','reply':'\n'.join(lines)}
