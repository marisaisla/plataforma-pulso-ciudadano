"""Política de equipo y territorio para consultas y acciones operativas web."""
def matches(conn,wid,pid,state,municipality):
    return conn.execute("SELECT 1 FROM public.field_worker_scopes WHERE worker_id=%s AND profile_id=%s AND (state='' OR state=%s) AND (municipality='' OR municipality=%s)",(wid,pid,state,municipality)).fetchone() is not None


def allowed(conn,wid,permission,task,owner):
    user=conn.execute('SELECT * FROM public.field_workers WHERE id=%s AND active=1',(wid,)).fetchone()
    if not user: return False
    grant=conn.execute('SELECT scope FROM public.field_role_permissions WHERE role_key=%s AND permission_key=%s',(user['role_key'],permission)).fetchone()
    if not grant: return False
    scope=grant['scope']
    if scope=='all': return True
    if not matches(conn,wid,task['profile_id'],task['state'],task['municipality']): return False
    if scope=='campaign': return True
    if scope=='own': return owner==wid
    if scope!='team': return False
    if owner is None: return user['role_key']=='coordinator' and permission=='tasks.view'
    if owner==wid:
        return permission in {'tasks.view','reports.view','tasks.assign','incidents.manage','supporters.view','supporters.submit'}
    target=conn.execute('SELECT * FROM public.field_workers WHERE id=%s AND active=1',(owner,)).fetchone()
    if not target or not user['team'].strip() or user['team'].strip().casefold()!=target['team'].strip().casefold(): return False
    if not matches(conn,owner,task['profile_id'],task['state'],task['municipality']): return False
    if user['role_key']=='supervisor': return target['role_key']=='field' and target['supervisor_id']==wid
    return user['role_key']=='coordinator' and target['role_key'] in {'field','supervisor'}
