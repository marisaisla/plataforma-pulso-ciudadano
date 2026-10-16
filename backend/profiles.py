"""Perfiles y trayectorias de la pantalla 01, con acceso administrativo."""
from datetime import date
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StrictBool, field_validator, model_validator
from backend.admin import administrator, db

router=APIRouter(prefix='/api/v1',tags=['Perfiles y elección'])
ACTOR_TYPES=['Persona','Partido político','Institución pública','Tema sin actor']
CONDITIONS=['Candidato/a','En funciones','Exfuncionario/a','Otro']


class ProfileCreate(BaseModel):
    name: str=Field(min_length=1,max_length=300)
    actor_type: Literal['Persona','Partido político','Institución pública','Tema sin actor']
    notes: str=Field(default='',max_length=20000)

    @field_validator('name','notes')
    @classmethod
    def trim(cls,value,info):
        value=value.strip()
        if info.field_name=='name' and not value:
            raise ValueError('Escribe un nombre para el perfil.')
        return value


class ProfileOut(BaseModel):
    id: int
    name: str
    actor_type: str
    active: int
    notes: str | None


class ProfileActive(BaseModel):
    active: StrictBool


class PositionCreate(BaseModel):
    office: str=Field(min_length=1,max_length=300)
    condition: Literal['Candidato/a','En funciones','Exfuncionario/a','Otro']
    starts_at: date
    ends_at: date | None=None
    party_or_coalition: str=Field(default='',max_length=300)

    @field_validator('office','party_or_coalition')
    @classmethod
    def trim(cls,value,info):
        value=value.strip()
        if info.field_name=='office' and not value:
            raise ValueError('Indica el cargo o candidatura.')
        return value

    @model_validator(mode='after')
    def ordered_dates(self):
        if self.ends_at and self.ends_at<self.starts_at:
            raise ValueError('La fecha final no puede ser anterior al inicio.')
        return self


class PositionOut(BaseModel):
    id: int
    profile_id: int
    profile_name: str
    office: str
    condition: str
    starts_at: str | None
    ends_at: str | None
    party_or_coalition: str | None
    is_current: int


@router.get('/profiles/options',summary='Tipos de perfil y condiciones')
def options(actor=Depends(administrator)):
    return {'actor_types':ACTOR_TYPES,'conditions':CONDITIONS}


@router.get('/profiles',summary='Consultar candidatos',response_model=list[ProfileOut])
def profiles(active_only:bool=False,actor=Depends(administrator),conn=Depends(db)):
    """Devuelve perfiles con sus campos completos; conserva id/name para clientes anteriores."""
    sql='SELECT id,name,actor_type,active,notes FROM public.profiles'
    if active_only: sql+=' WHERE active=1'
    return conn.execute(sql+' ORDER BY name,id').fetchall()


@router.post('/profiles',summary='Guardar perfil',response_model=ProfileOut,status_code=201)
def create_profile(body:ProfileCreate,actor=Depends(administrator),conn=Depends(db)):
    """Guarda perfil y palabra clave inicial juntos, conforme al comportamiento existente."""
    row=conn.execute('INSERT INTO public.profiles (name,actor_type,notes) VALUES (%s,%s,%s) RETURNING id,name,actor_type,active,notes',
                     (body.name,body.actor_type,body.notes)).fetchone()
    conn.execute('INSERT INTO public.profile_keywords (profile_id,keyword) VALUES (%s,%s)',(row['id'],body.name))
    return row


@router.put('/profiles/{profile_id}/active',summary='Activar o desactivar perfil',response_model=ProfileOut)
def set_profile_active(profile_id:int,body:ProfileActive,actor=Depends(administrator),conn=Depends(db)):
    """Cambia solo active; conserva trayectorias, palabras clave y demás registros relacionados."""
    row=conn.execute('UPDATE public.profiles SET active=%s WHERE id=%s RETURNING id,name,actor_type,active,notes',
                     (int(body.active),profile_id)).fetchone()
    if not row: raise HTTPException(404,'Perfil no encontrado.')
    return row


POSITION_QUERY='''SELECT pp.id,pp.profile_id,p.name AS profile_name,pp.office,pp.condition,
    pp.starts_at,pp.ends_at,pp.party_or_coalition,pp.is_current
    FROM public.profile_positions pp JOIN public.profiles p ON p.id=pp.profile_id'''


@router.get('/profile-positions',summary='Consultar cargos y candidaturas',response_model=list[PositionOut])
def positions(profile_id:int | None=None,actor=Depends(administrator),conn=Depends(db)):
    if profile_id is not None:
        return conn.execute(POSITION_QUERY+' WHERE pp.profile_id=%s ORDER BY pp.starts_at DESC,p.name,pp.id DESC',(profile_id,)).fetchall()
    return conn.execute(POSITION_QUERY+' ORDER BY pp.starts_at DESC,p.name,pp.id DESC').fetchall()


@router.post('/profiles/{profile_id}/positions',summary='Guardar cargo o candidatura',response_model=PositionOut,status_code=201)
def create_position(profile_id:int,body:PositionCreate,actor=Depends(administrator),conn=Depends(db)):
    profile=conn.execute('SELECT active FROM public.profiles WHERE id=%s',(profile_id,)).fetchone()
    if not profile: raise HTTPException(404,'Perfil no encontrado.')
    if not profile['active']: raise HTTPException(409,'El perfil está inactivo.')
    row=conn.execute('INSERT INTO public.profile_positions (profile_id,office,condition,starts_at,ends_at,party_or_coalition) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id',
                     (profile_id,body.office,body.condition,body.starts_at.isoformat(),body.ends_at.isoformat() if body.ends_at else None,body.party_or_coalition)).fetchone()
    return conn.execute(POSITION_QUERY+' WHERE pp.id=%s',(row['id'],)).fetchone()
