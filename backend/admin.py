"""Acceso web y administración sobre PostgreSQL; no modifica los servicios actuales."""
import hashlib
import hmac
import json
import re
import secrets
import time
from typing import Annotated, Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, SecretStr, StrictBool, field_validator

from backend.database import connect
from backend.telegram import serialize_changes, issue_code

router=APIRouter(prefix='/api/v1',tags=['Usuarios y acceso'])
bearer=HTTPBearer(auto_error=False)
Role=Literal['field','supervisor','coordinator','director','administrator']


def db():
    with connect() as conn:
        yield conn


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password):
    salt=secrets.token_bytes(16)
    value=hashlib.scrypt(password.encode(),salt=salt,n=131072,r=8,p=1,maxmem=256*1024*1024)
    return f'scrypt${salt.hex()}${value.hex()}'


def verify(password,encoded):
    try:
        scheme,salt,expected=encoded.split('$')
        if scheme!='scrypt': return False
        value=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=131072,r=8,p=1,maxmem=256*1024*1024)
        return hmac.compare_digest(value.hex(),expected)
    except (ValueError,TypeError):
        return False


class Login(BaseModel):
    username: str=Field(min_length=3,max_length=64)
    password: SecretStr=Field(min_length=1,max_length=128)


class PasswordChange(BaseModel):
    old_password: SecretStr=Field(min_length=1,max_length=128)
    new_password: SecretStr=Field(min_length=12,max_length=128)


class Account(BaseModel):
    username: str=Field(min_length=3,max_length=64)
    temporary_password: SecretStr=Field(min_length=12,max_length=128)

    @field_validator('username')
    @classmethod
    def username_format(cls,value):
        value=value.strip().lower()
        if not re.fullmatch(r'[a-z0-9._-]{3,64}',value):
            raise ValueError('Usuario inválido; usa letras sin acentos, números, puntos o guiones.')
        return value


class WorkerCreate(BaseModel):
    name: str=Field(min_length=1,max_length=120)
    team: str=Field(default='',max_length=120)

    @field_validator('name','team')
    @classmethod
    def trim(cls,value,info):
        value=value.strip()
        if info.field_name=='name' and not value: raise ValueError('El nombre es obligatorio.')
        return value


class Rename(BaseModel):
    name: str=Field(min_length=1,max_length=120)

    @field_validator('name')
    @classmethod
    def trim(cls,value):
        if not value.strip(): raise ValueError('El nombre es obligatorio.')
        return value.strip()


class Access(BaseModel):
    role_key: Role
    team: str=Field(default='',max_length=120)
    supervisor_id: int | None=Field(default=None,gt=0,le=2**63-1)


class Active(BaseModel):
    active: StrictBool


class Scope(BaseModel):
    profile_id: int=Field(gt=0,le=2**63-1)
    state: str=Field(default='',max_length=120)
    municipality: str=Field(default='',max_length=120)

    @field_validator('state','municipality')
    @classmethod
    def trim(cls,value): return value.strip()


class UserOut(BaseModel):
    id: int
    name: str
    team: str
    active: int
    role_key: str
    supervisor_id: int | None
    telegram_user_id: int | None
    telegram_chat_id: int | None
    linked_at: int | None
    created_at: int
    username: str | None
    must_change: int | None


class LoginOut(BaseModel):
    access_token: str
    token_type: str='bearer'
    expires_at: int
    must_change_password: bool


def current(credentials: Annotated[HTTPAuthorizationCredentials | None,Depends(bearer)],conn=Depends(db)):
    serialize_changes(conn)
    if not credentials:
        raise HTTPException(401,'Inicia sesión.',headers={'WWW-Authenticate':'Bearer'})
    user=conn.execute('''SELECT w.*,a.username,a.must_change,s.token_hash FROM public.web_sessions s
        JOIN public.web_accounts a ON a.worker_id=s.worker_id JOIN public.field_workers w ON w.id=a.worker_id
        WHERE s.token_hash=%s AND s.expires_at>%s AND s.development_instance IS NULL AND w.active=1''',
        (digest(credentials.credentials),int(time.time()))).fetchone()
    if not user:
        raise HTTPException(401,'Sesión inválida o vencida.',headers={'WWW-Authenticate':'Bearer'})
    return user


def administrator(user=Depends(current)):
    if user['must_change']:
        raise HTTPException(403,'Primero cambia tu contraseña temporal.')
    if user['role_key']!='administrator':
        raise HTTPException(403,'Se requiere una sesión de administrador.')
    return user


def worker(conn,wid):
    row=conn.execute('SELECT * FROM public.field_workers WHERE id=%s',(wid,)).fetchone()
    if not row: raise HTTPException(404,'Trabajador no encontrado.')
    return row


def audit(conn,wid,action,details,actor):
    conn.execute('INSERT INTO public.field_access_audit (worker_id,action,details,actor,created_at) VALUES (%s,%s,%s,%s,%s)',
                 (wid,action,json.dumps(details,ensure_ascii=False),f"worker:{actor['id']}",int(time.time())))


def revoke(conn,wid):
    conn.execute('DELETE FROM public.web_sessions WHERE worker_id=%s',(wid,))


def protect_admin(conn,wid,role=None,active=None):
    row=worker(conn,wid)
    if row['active'] and row['role_key']=='administrator' and (active is False or role not in (None,'administrator')):
        account=conn.execute('SELECT 1 FROM public.web_accounts WHERE worker_id=%s',(wid,)).fetchone()
        other=conn.execute("SELECT 1 FROM public.field_workers w JOIN public.web_accounts a ON a.worker_id=w.id WHERE w.id<>%s AND w.active=1 AND w.role_key='administrator'",(wid,)).fetchone()
        if account and not other:
            raise HTTPException(409,'Crea otro administrador con acceso web antes de retirar al último.')


SELECT_USER='''SELECT w.*,a.username,a.must_change FROM public.field_workers w
               LEFT JOIN public.web_accounts a ON a.worker_id=w.id'''


@router.post('/auth/login',response_model=LoginOut)
def login(body:Login,conn=Depends(db)):
    """Acceso con credenciales existentes. Cinco fallos bloquean el usuario cinco minutos."""
    serialize_changes(conn)
    now=int(time.time())
    username=body.username.strip().lower()
    key=digest(username)
    attempt=conn.execute('SELECT * FROM public.web_login_attempts WHERE login_hash=%s',(key,)).fetchone()
    if attempt and attempt['locked_until']>now:
        return JSONResponse(status_code=429,content={'detail':'Espera unos minutos antes de intentar nuevamente.'})
    account=conn.execute('SELECT a.*,w.active FROM public.web_accounts a JOIN public.field_workers w ON w.id=a.worker_id WHERE a.username=%s',(username,)).fetchone()
    valid=verify(body.password.get_secret_value(),account['password_hash'] if account else 'scrypt$'+'00'*16+'$'+'00'*64)
    if not account or not account['active'] or not valid:
        failures=(attempt['failures'] if attempt and now-attempt['updated_at']<900 else 0)+1
        locked=now+300 if failures>=5 else 0
        conn.execute('INSERT INTO public.web_login_attempts (login_hash,failures,locked_until,updated_at) VALUES (%s,%s,%s,%s) ON CONFLICT(login_hash) DO UPDATE SET failures=excluded.failures,locked_until=excluded.locked_until,updated_at=excluded.updated_at',(key,0 if locked else failures,locked,now))
        # Retornar respuesta en lugar de lanzar excepción permite confirmar el contador.
        return JSONResponse(status_code=401,content={'detail':'Usuario o contraseña inválidos.'})
    conn.execute('DELETE FROM public.web_login_attempts WHERE login_hash=%s',(key,))
    token=secrets.token_urlsafe(32)
    conn.execute('INSERT INTO public.web_sessions (token_hash,worker_id,expires_at) VALUES (%s,%s,%s)',(digest(token),account['worker_id'],now+28800))
    return {'access_token':token,'expires_at':now+28800,'must_change_password':bool(account['must_change'])}


@router.get('/auth/me',response_model=UserOut)
def me(user=Depends(current)):
    return user


@router.post('/auth/logout',status_code=204)
def logout(user=Depends(current),conn=Depends(db)):
    conn.execute('DELETE FROM public.web_sessions WHERE token_hash=%s',(user['token_hash'],))
    return Response(status_code=204)


@router.post('/auth/password',status_code=204)
def change_password(body:PasswordChange,user=Depends(current),conn=Depends(db)):
    old,new=body.old_password.get_secret_value(),body.new_password.get_secret_value()
    row=conn.execute('SELECT password_hash FROM public.web_accounts WHERE worker_id=%s',(user['id'],)).fetchone()
    if old==new or not verify(old,row['password_hash']):
        raise HTTPException(400,'Contraseña actual inválida o nueva contraseña igual a la anterior.')
    conn.execute('UPDATE public.web_accounts SET password_hash=%s,must_change=0 WHERE worker_id=%s',(password_hash(new),user['id']))
    revoke(conn,user['id'])
    return Response(status_code=204)


@router.get('/users',response_model=list[UserOut])
def users(after:Annotated[int,Query(ge=0)]=0,limit:Annotated[int,Query(ge=1,le=100)]=50,actor=Depends(administrator),conn=Depends(db)):
    return conn.execute(SELECT_USER+' WHERE w.id>%s ORDER BY w.id LIMIT %s',(after,limit)).fetchall()


@router.post('/users',response_model=UserOut,status_code=201)
def create_user(body:WorkerCreate,actor=Depends(administrator),conn=Depends(db)):
    row=conn.execute('INSERT INTO public.field_workers (name,team,created_at) VALUES (%s,%s,%s) RETURNING id',(body.name,body.team,int(time.time()))).fetchone()
    audit(conn,row['id'],'worker_created',{},actor)
    return conn.execute(SELECT_USER+' WHERE w.id=%s',(row['id'],)).fetchone()


@router.get('/users/{wid}',response_model=UserOut)
def get_user(wid:int,actor=Depends(administrator),conn=Depends(db)):
    worker(conn,wid)
    return conn.execute(SELECT_USER+' WHERE w.id=%s',(wid,)).fetchone()


@router.patch('/users/{wid}',response_model=UserOut)
def edit_user(wid:int,body:Rename,actor=Depends(administrator),conn=Depends(db)):
    worker(conn,wid)
    conn.execute('UPDATE public.field_workers SET name=%s WHERE id=%s',(body.name,wid))
    audit(conn,wid,'name_changed',{},actor)
    return conn.execute(SELECT_USER+' WHERE w.id=%s',(wid,)).fetchone()


@router.put('/users/{wid}/access',status_code=204)
def access(wid:int,body:Access,actor=Depends(administrator),conn=Depends(db)):
    previous=worker(conn,wid)
    protect_admin(conn,wid,role=body.role_key)
    team=body.team.strip()
    if not conn.execute('SELECT 1 FROM public.field_roles WHERE key=%s',(body.role_key,)).fetchone():
        raise HTTPException(400,'Rol no configurado.')
    if body.supervisor_id is not None:
        manager=worker(conn,body.supervisor_id)
        if manager['id']==wid or not manager['active'] or manager['role_key'] not in ('supervisor','coordinator') or not team or team.casefold()!=manager['team'].strip().casefold():
            raise HTTPException(409,'Supervisor inválido o equipo diferente.')
        ancestor=body.supervisor_id
        seen={wid}
        while ancestor is not None:
            if ancestor in seen: raise HTTPException(409,'La supervisión produciría un ciclo.')
            seen.add(ancestor)
            ancestor=worker(conn,ancestor)['supervisor_id']
    children=conn.execute('SELECT team FROM public.field_workers WHERE supervisor_id=%s AND active=1',(wid,)).fetchall()
    if children and (not previous['active'] or body.role_key not in ('supervisor','coordinator') or any(c['team'].strip().casefold()!=team.casefold() for c in children)):
        raise HTTPException(409,'Reasigna primero al personal supervisado.')
    conn.execute('UPDATE public.field_workers SET role_key=%s,team=%s,supervisor_id=%s WHERE id=%s',(body.role_key,team,body.supervisor_id,wid))
    revoke(conn,wid)
    audit(conn,wid,'access_changed',{'role_key':body.role_key,'team':team,'supervisor_id':body.supervisor_id},actor)
    return Response(status_code=204)


@router.put('/users/{wid}/active',status_code=204)
def active(wid:int,body:Active,actor=Depends(administrator),conn=Depends(db)):
    worker(conn,wid)
    protect_admin(conn,wid,active=body.active)
    if not body.active and conn.execute('SELECT 1 FROM public.field_workers WHERE supervisor_id=%s AND active=1',(wid,)).fetchone():
        raise HTTPException(409,'Reasigna primero al personal supervisado.')
    conn.execute('UPDATE public.field_workers SET active=%s WHERE id=%s',(int(body.active),wid))
    revoke(conn,wid)
    for table in ('field_activation_codes','field_report_sessions','supporter_sessions','field_need_sessions'):
        conn.execute(f'DELETE FROM public.{table} WHERE worker_id=%s',(wid,))
    audit(conn,wid,'active_changed',{'active':body.active},actor)
    return Response(status_code=204)


@router.get('/users/{wid}/scopes')
def scopes(wid:int,actor=Depends(administrator),conn=Depends(db)):
    worker(conn,wid)
    return conn.execute('SELECT profile_id,state,municipality FROM public.field_worker_scopes WHERE worker_id=%s ORDER BY profile_id,state,municipality',(wid,)).fetchall()


def scope_change(conn,wid,body,actor,remove=False):
    worker(conn,wid)
    if body.municipality and not body.state: raise HTTPException(400,'Selecciona estado antes de municipio.')
    if not conn.execute('SELECT 1 FROM public.profiles WHERE id=%s',(body.profile_id,)).fetchone():
        raise HTTPException(404,'Campaña no encontrada.')
    values=(wid,body.profile_id,body.state,body.municipality)
    if remove:
        conn.execute('DELETE FROM public.field_worker_scopes WHERE worker_id=%s AND profile_id=%s AND state=%s AND municipality=%s',values)
    else:
        conn.execute('INSERT INTO public.field_worker_scopes (worker_id,profile_id,state,municipality) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING',values)
    revoke(conn,wid)
    audit(conn,wid,'scope_removed' if remove else 'scope_added',body.model_dump(),actor)


@router.post('/users/{wid}/scopes',status_code=204)
def add_scope(wid:int,body:Scope,actor=Depends(administrator),conn=Depends(db)):
    scope_change(conn,wid,body,actor)
    return Response(status_code=204)


@router.delete('/users/{wid}/scopes',status_code=204)
def remove_scope(wid:int,body:Scope,actor=Depends(administrator),conn=Depends(db)):
    scope_change(conn,wid,body,actor,True)
    return Response(status_code=204)


@router.put('/users/{wid}/account',status_code=204)
def account(wid:int,body:Account,actor=Depends(administrator),conn=Depends(db)):
    if not worker(conn,wid)['active']: raise HTTPException(409,'El trabajador está inactivo.')
    try:
        conn.execute('INSERT INTO public.web_accounts (worker_id,username,password_hash,must_change) VALUES (%s,%s,%s,1) ON CONFLICT(worker_id) DO UPDATE SET username=excluded.username,password_hash=excluded.password_hash,must_change=1',
                     (wid,body.username,password_hash(body.temporary_password.get_secret_value())))
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409,'Nombre de usuario ya utilizado.') from None
    revoke(conn,wid)
    conn.execute('DELETE FROM public.web_login_attempts WHERE login_hash=%s',(digest(body.username),))
    audit(conn,wid,'account_reset',{'username':body.username},actor)
    return Response(status_code=204)


@router.delete('/users/{wid}/telegram',status_code=204)
def unlink(wid:int,actor=Depends(administrator),conn=Depends(db)):
    worker(conn,wid)
    conn.execute('UPDATE public.field_workers SET telegram_user_id=NULL,telegram_chat_id=NULL,linked_at=NULL WHERE id=%s',(wid,))
    for table in ('field_activation_codes','field_report_sessions','supporter_sessions','field_need_sessions'):
        conn.execute(f'DELETE FROM public.{table} WHERE worker_id=%s',(wid,))
    audit(conn,wid,'telegram_unlinked',{},actor)
    return Response(status_code=204)


@router.post('/users/{wid}/telegram/activation-codes',status_code=201)
def activation(wid:int,actor=Depends(administrator),conn=Depends(db)):
    return issue_code(conn,wid)


@router.get('/roles')
def roles(actor=Depends(administrator),conn=Depends(db)):
    return conn.execute('SELECT r.key,r.label,g.permission_key,g.scope FROM public.field_roles r LEFT JOIN public.field_role_permissions g ON g.role_key=r.key ORDER BY r.key,g.permission_key').fetchall()


