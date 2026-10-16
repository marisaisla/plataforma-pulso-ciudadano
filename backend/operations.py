"""Operación web de tareas y registros Telegram con sesión Bearer."""
import base64
import secrets
from datetime import date
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Response
from pydantic import BaseModel,Field,field_validator
from backend.admin import current,administrator,db
from backend.permissions import allowed

router=APIRouter(prefix='/api/v1',tags=['Operación de campo'])
UTC="to_char(CURRENT_TIMESTAMP AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS')"


def authenticated(user=Depends(current)):
    if user['must_change']: raise HTTPException(403,'Primero cambia tu contraseña temporal.')
    return user


def task(conn,tid):
    row=conn.execute('SELECT * FROM public.territorial_action_plans WHERE id=%s',(tid,)).fetchone()
    if not row: raise HTTPException(404,'Actividad no encontrada.')
    return row


def assignment_row(conn,tid):
    return conn.execute('SELECT a.*,w.name FROM public.field_task_assignments a JOIN public.field_workers w ON w.id=a.worker_id WHERE a.task_id=%s',(tid,)).fetchone()


def candidates(conn,t,user):
    return [dict(w) for w in conn.execute('SELECT id,name,telegram_user_id FROM public.field_workers WHERE active=1 ORDER BY name,id').fetchall()
            if allowed(conn,w['id'],'tasks.confirm',t,w['id']) and allowed(conn,user['id'],'tasks.assign',t,w['id'])]


@router.get('/territory-options')
def territory_options(state:str='',actor=Depends(administrator),conn=Depends(db)):
    states=[r['state'] for r in conn.execute("SELECT DISTINCT state FROM public.territories WHERE COALESCE(state,'')<>'' ORDER BY state").fetchall()]
    municipalities=[r['municipality'] for r in conn.execute("SELECT DISTINCT municipality FROM public.territories WHERE state=%s AND COALESCE(municipality,'')<>'' ORDER BY municipality",(state,)).fetchall()] if state else []
    return {'states':states,'municipalities':municipalities}


@router.get('/profiles/{pid}/states')
def profile_states(pid:int,actor=Depends(administrator),conn=Depends(db)):
    rows=conn.execute("SELECT DISTINCT t.state FROM public.profile_territories pt JOIN public.territories t ON t.id=pt.territory_id WHERE pt.profile_id=%s AND TRIM(COALESCE(t.state,''))<>'' ORDER BY t.state",(pid,)).fetchall()
    if rows: return [r['state'] for r in rows]
    context=conn.execute("SELECT COALESCE(p.notes,'')||' '||COALESCE(pp.office,'') AS contexto FROM public.profiles p LEFT JOIN public.profile_positions pp ON pp.profile_id=p.id WHERE p.id=%s",(pid,)).fetchall()
    text=' '.join(r['contexto'] for r in context).casefold()
    return [r['state'] for r in conn.execute("SELECT DISTINCT state FROM public.territories WHERE TRIM(COALESCE(state,''))<>'' ORDER BY state").fetchall() if r['state'].casefold() in text]


@router.get('/action-strategies')
def strategies(profile_id:int,state:str,actor=Depends(administrator),conn=Depends(db)):
    return conn.execute('SELECT id,municipality,party_or_coalition,strategic_focus,objective,status FROM public.territorial_strategies WHERE profile_id=%s AND state=%s ORDER BY municipality,id',(profile_id,state)).fetchall()


@router.get('/activities')
def activities(strategy_id:int,actor=Depends(administrator),conn=Depends(db)):
    return conn.execute('''SELECT t.*,w.name AS trabajador_telegram,a.received_at AS recepcion_telegram_utc
        FROM public.territorial_action_plans t LEFT JOIN public.field_task_assignments a ON a.task_id=t.id
        LEFT JOIN public.field_workers w ON w.id=a.worker_id WHERE t.strategy_id=%s
        ORDER BY CASE t.priority_level WHEN 'Alta' THEN 1 WHEN 'Media' THEN 2 ELSE 3 END,t.due_date,t.id''',(strategy_id,)).fetchall()


class ActivityCreate(BaseModel):
    strategy_id:int=Field(gt=0)
    activity_name:str=Field(min_length=1,max_length=300)
    activity_description:str | None=Field(default=None,max_length=20000)
    responsible:str | None=Field(default=None,max_length=300)
    due_date:date
    priority_level:Literal['Alta','Media','Baja']='Media'
    district:str | None=Field(default=None,max_length=120)
    electoral_section:str | None=Field(default=None,max_length=120)

    @field_validator('activity_name')
    @classmethod
    def name(cls,value):
        if not value.strip(): raise ValueError('Escribe un nombre para la actividad.')
        return value.strip()


@router.post('/activities',status_code=201)
def create_activity(body:ActivityCreate,actor=Depends(administrator),conn=Depends(db)):
    strategy=conn.execute('SELECT s.* FROM public.territorial_strategies s JOIN public.profiles p ON p.id=s.profile_id WHERE s.id=%s AND p.active=1',(body.strategy_id,)).fetchone()
    if not strategy: raise HTTPException(404,'Estrategia no encontrada o perfil inactivo.')
    return conn.execute('''INSERT INTO public.territorial_action_plans
        (strategy_id,profile_id,state,municipality,district,electoral_section,activity_name,activity_description,responsible,due_date,priority_level)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
        (body.strategy_id,strategy['profile_id'],strategy['state'],strategy['municipality'],body.district,body.electoral_section,body.activity_name,body.activity_description,body.responsible,body.due_date.isoformat(),body.priority_level)).fetchone()


class Progress(BaseModel):
    status:Literal['Pendiente','En curso','Concluida','Cancelada']
    evidence_note:str | None=Field(default=None,max_length=20000)


@router.patch('/activities/{tid}')
def progress(tid:int,body:Progress,actor=Depends(administrator),conn=Depends(db)):
    task(conn,tid)
    return conn.execute(f"UPDATE public.territorial_action_plans SET status=%s,evidence_note=%s,completed_at=CASE WHEN %s='Concluida' THEN {UTC} ELSE completed_at END,updated_at={UTC} WHERE id=%s RETURNING *",(body.status,body.evidence_note,body.status,tid)).fetchone()


@router.get('/activities/{tid}/assignment')
def assignment(tid:int,user=Depends(authenticated),conn=Depends(db)):
    t=task(conn,tid)
    row=assignment_row(conn,tid)
    if not allowed(conn,user['id'],'tasks.view',t,row['worker_id'] if row else None): raise HTTPException(403,'No tienes acceso a esta actividad.')
    return row


@router.get('/activities/{tid}/candidates')
def eligible_workers(tid:int,user=Depends(authenticated),conn=Depends(db)):
    t=task(conn,tid)
    previous=assignment_row(conn,tid)
    if previous and not allowed(conn,user['id'],'tasks.assign',t,previous['worker_id']): raise HTTPException(403,'No puedes cambiar esta asignación.')
    return candidates(conn,t,user) if t['status'] in ('Pendiente','En curso') else []


class Assignment(BaseModel):
    worker_id:int | None=Field(default=None,gt=0)


@router.put('/activities/{tid}/assignment',status_code=204)
def assign(tid:int,body:Assignment,user=Depends(authenticated),conn=Depends(db)):
    t=task(conn,tid)
    if t['status'] not in ('Pendiente','En curso'): raise HTTPException(409,'La actividad debe estar pendiente o en curso.')
    previous=assignment_row(conn,tid)
    targets=[body.worker_id]+([previous['worker_id']] if previous else [])
    if not all(allowed(conn,user['id'],'tasks.assign',t,wid) for wid in targets): raise HTTPException(403,'No puedes cambiar esta asignación.')
    if body.worker_id is not None and not allowed(conn,body.worker_id,'tasks.confirm',t,body.worker_id): raise HTTPException(409,'Trabajador inactivo o sin permiso/alcance para la tarea.')
    if previous and previous['worker_id']==body.worker_id: return Response(status_code=204)
    def event(wid,generation,kind):
        conn.execute('INSERT INTO public.field_task_events (task_id,worker_id,generation,event,actor) VALUES (%s,%s,%s,%s,%s)',(tid,wid,generation,kind,f"worker:{user['id']}"))
    if previous:
        event(previous['worker_id'],previous['generation'],'unassigned')
        conn.execute('DELETE FROM public.field_task_assignments WHERE task_id=%s',(tid,))
    if body.worker_id is not None:
        generation=secrets.token_hex(8)
        conn.execute('INSERT INTO public.field_task_assignments (task_id,worker_id,generation) VALUES (%s,%s,%s)',(tid,body.worker_id,generation))
        event(body.worker_id,generation,'assigned')
    return Response(status_code=204)


@router.get('/activities/{tid}/reports')
def reports(tid:int,user=Depends(authenticated),conn=Depends(db)):
    t=task(conn,tid)
    rows=conn.execute('''SELECT r.*,w.name,v.note,v.actor,v.created_at AS reviewed_at FROM public.field_reports r
        JOIN public.field_workers w ON w.id=r.worker_id LEFT JOIN public.field_report_reviews v ON v.report_id=r.id
        WHERE r.task_id=%s ORDER BY r.id DESC''',(tid,)).fetchall()
    return [dict(r) for r in rows if allowed(conn,user['id'],'reports.view',t,r['worker_id'])]


def report_context(conn,rid):
    row=conn.execute('SELECT r.*,t.profile_id,t.state,t.municipality FROM public.field_reports r JOIN public.territorial_action_plans t ON t.id=r.task_id WHERE r.id=%s',(rid,)).fetchone()
    if not row: raise HTTPException(404,'Reporte no encontrado.')
    return row


@router.get('/reports/{rid}/photo')
def photo(rid:int,user=Depends(authenticated),conn=Depends(db)):
    r=report_context(conn,rid)
    if not allowed(conn,user['id'],'reports.view',r,r['worker_id']): raise HTTPException(403,'No tienes permiso para consultar esta evidencia.')
    image=conn.execute('SELECT content_base64 FROM public.field_report_photos WHERE report_id=%s',(rid,)).fetchone()
    if not image: return Response(status_code=204)
    return Response(base64.b64decode(image['content_base64']),media_type='image/jpeg',headers={'Cache-Control':'no-store'})


class Review(BaseModel):
    decision:Literal['accepted','correction']
    note:str=Field(default='',max_length=500)


@router.put('/reports/{rid}/review',status_code=204)
def review(rid:int,body:Review,user=Depends(authenticated),conn=Depends(db)):
    r=report_context(conn,rid)
    if user['id']==r['worker_id'] or not allowed(conn,user['id'],'reports.review',r,r['worker_id']): raise HTTPException(403,'No puedes revisar este reporte.')
    note=body.note.strip()
    if body.decision=='correction' and not note: raise HTTPException(422,'La corrección requiere observaciones.')
    previous=conn.execute('SELECT decision,note FROM public.field_report_reviews WHERE report_id=%s',(rid,)).fetchone()
    if previous:
        if previous['decision']==body.decision and previous['note']==note: return Response(status_code=204)
        raise HTTPException(409,'La revisión anterior se conserva y no se puede sobrescribir.')
    conn.execute('INSERT INTO public.field_report_reviews (report_id,decision,note,actor) VALUES (%s,%s,%s,%s)',(rid,body.decision,note,f"worker:{user['id']}"))
    conn.execute('UPDATE public.field_reports SET status=%s WHERE id=%s',(body.decision,rid))
    return Response(status_code=204)


@router.get('/supporters')
def supporter_catalog(user=Depends(authenticated),conn=Depends(db)):
    rows=conn.execute('SELECT s.*,p.name AS campaign,w.name AS registered_by FROM public.supporters s JOIN public.profiles p ON p.id=s.profile_id JOIN public.field_workers w ON w.id=s.worker_id ORDER BY s.id DESC').fetchall()
    return [dict(r) for r in rows if allowed(conn,user['id'],'supporters.view',r,r['worker_id'])]


@router.get('/needs')
def needs_catalog(user=Depends(authenticated),conn=Depends(db)):
    rows=conn.execute('SELECT n.*,p.name AS campaign,w.name AS registered_by FROM public.field_needs n JOIN public.profiles p ON p.id=n.profile_id JOIN public.field_workers w ON w.id=n.worker_id ORDER BY n.id DESC').fetchall()
    return [dict(r) for r in rows if allowed(conn,user['id'],'needs.view',r,r['worker_id'])]


@router.get('/field/portal')
def portal(user=Depends(authenticated),conn=Depends(db)):
    tasks=conn.execute('''SELECT t.*,a.worker_id,a.received_at,w.name AS worker_name FROM public.territorial_action_plans t
        LEFT JOIN public.field_task_assignments a ON a.task_id=t.id LEFT JOIN public.field_workers w ON w.id=a.worker_id ORDER BY t.id DESC''').fetchall()
    rows=conn.execute('''SELECT r.*,t.profile_id,t.state,t.municipality,v.note FROM public.field_reports r JOIN public.territorial_action_plans t ON t.id=r.task_id LEFT JOIN public.field_report_reviews v ON v.report_id=r.id ORDER BY r.id DESC''').fetchall()
    reports=[]
    for r in rows:
        if allowed(conn,user['id'],'reports.view',r,r['worker_id']):
            reports.append(dict(r,can_review=user['id']!=r['worker_id'] and allowed(conn,user['id'],'reports.review',r,r['worker_id'])))
    return {'user':{'id':user['id'],'role_key':user['role_key'],'team':user['team']},
            'tasks':[dict(t) for t in tasks if allowed(conn,user['id'],'tasks.view',t,t['worker_id'])], 'reports':reports}
