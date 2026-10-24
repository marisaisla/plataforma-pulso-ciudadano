"""Read-only adapters for existing profile dossiers and survey records."""
import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.admin import administrator, db

router=APIRouter(prefix='/api/v1/indicators/dashboard',tags=['Dashboard de indicadores'],
                 dependencies=[Depends(administrator)])
REVIEW_FIELDS=('profile_id','name','pollster','territory','fieldwork_date','sample_size',
               'methodology','profile_result_pct','source_url','notes')
EVIDENCE_LINKS={
    'name_recognition':['IC01'], 'favorable_opinion':['IC02','IC04'],
    'undecided_voters':['IC07'], 'vote_intent':['IC05'],
    'electoral_experience':['IC08','IC09'], 'institutional_position':['IC08','IC11'],
    'nomination_probability':['IC11'], 'reputational_risk':['IC10','IC12'],
    'coalition_alliances':['IP06'],
}


def survey_fingerprint(row):
    value={key:row.get(key) for key in REVIEW_FIELDS}
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,
                                    separators=(',',':'),allow_nan=False).encode()).hexdigest()


@lru_cache(maxsize=1)
def survey_review():
    return json.loads(Path(__file__).with_name('dashboard_survey_review.json').read_text(encoding='utf-8'))


def percent(value):
    return type(value) in (float,int) and math.isfinite(value) and 0<=value<=100


def describe_survey(row,review=None):
    """Never classify by keywords or convert assessment scores into measurements."""
    row=dict(row)
    value=row.get('profile_result_pct')
    if value is not None and not math.isfinite(value):
        row['profile_result_pct']=None
    fingerprint=survey_fingerprint(row)
    reviewed=(review if review is not None else survey_review())['items'].get(fingerprint)
    kind=reviewed['kind'] if reviewed else 'unreviewed'
    missing=[name for name in ('pollster','territory','fieldwork_date','methodology','source_url')
             if not str(row.get(name) or '').strip()]
    if not row.get('sample_size') or row['sample_size']<=0:missing.append('sample_size')
    allowed=bool(reviewed and not reviewed.get('reference_only') and not missing
                 and kind in ('internal_preference','hypothetical_matchup','coalition_scenario'))
    reason=('Faltan metadatos: '+', '.join(missing)) if missing else 'Clasificación pendiente o reactivo distinto de preferencia electoral.'
    if reviewed and reviewed.get('reference_only'):reason=reviewed['note']
    if allowed and not percent(value):reason='Porcentaje ausente o fuera del intervalo 0–100.'
    preference=value if allowed and percent(value) else None
    indecision=reviewed.get('indecision_pct') if reviewed and allowed else None
    return dict(**row,kind=kind,classification_status='reviewed_snapshot' if reviewed else 'unreviewed_or_changed',
                fingerprint=fingerprint,metadata_missing=missing,
                review_note=reviewed['note'] if reviewed else 'Registro nuevo o modificado: requiere clasificación antes de alimentar tarjetas.',
                indicators={
                    'IC05':dict(value=preference,status='reported' if preference is not None else 'unavailable',
                                reason=None if preference is not None else reason,
                                source_field='profile_result_pct'),
                    'IC07':dict(value=indecision if percent(indecision) else None,
                                status='reported' if percent(indecision) else 'unavailable',
                                reason=None if percent(indecision) else 'No se ha identificado una categoría de indecisión revisada para este reactivo.',
                                source_field='notes (extracción revisada, sin sumar no sabe/ninguno)')})


class ReportedMetric(BaseModel):
    value: float | None
    status: str
    reason: str | None
    source_field: str


class SurveyOut(BaseModel):
    id: int
    profile_id: int
    name: str
    pollster: str | None=None
    territory: str | None=None
    fieldwork_date: str | None=None
    sample_size: int | None=None
    methodology: str | None=None
    profile_result_pct: float | None=None
    source_url: str | None=None
    notes: str | None=None
    kind: str
    classification_status: str
    fingerprint: str
    metadata_missing: list[str]
    review_note: str
    indicators: dict[str,ReportedMetric]


class Profile(BaseModel):
    id: int
    name: str
    active: int


class Position(BaseModel):
    id: int
    office: str
    condition: str
    starts_at: str | None=None
    ends_at: str | None=None
    party_or_coalition: str | None=None
    is_current: int


class Document(BaseModel):
    id: int
    title: str
    document_type: str
    source_url: str | None=None
    imported_at: str | None=None


class Evidence(BaseModel):
    id: int
    variable_code: str
    status: str
    evidence_note: str | None=None
    source_label: str | None=None
    source_url: str | None=None
    reference_date: str | None=None
    related_cards: list[str]


class Coalition(BaseModel):
    id: int
    scenario_name: str
    parties: str | None=None
    scope: str | None=None
    status: str
    notes: str | None=None
    source_url: str | None=None


class ResearchOut(BaseModel):
    profile: Profile
    reviewed_on: str
    surveys: list[SurveyOut]
    positions: list[Position]
    documents: list[Document]
    evidence: list[Evidence]
    coalitions: list[Coalition]
    totals: dict[str,int]
    truncated: bool
    warnings: list[str]


@router.get('/research',response_model=ResearchOut)
def research(profile_id: Annotated[int,Query(gt=0,le=2**63-1)],conn=Depends(db)):
    profile=conn.execute('SELECT id,name,active FROM profiles WHERE id=%s',(profile_id,)).fetchone()
    if not profile:raise HTTPException(404,'Perfil no encontrado.')
    specs={
        'surveys':('viability_surveys','id,profile_id,name,pollster,territory,fieldwork_date,sample_size,methodology,profile_result_pct,source_url,notes'),
        'positions':('profile_positions','id,office,condition,starts_at,ends_at,party_or_coalition,is_current'),
        'documents':('reference_documents','id,title,document_type,source_url,imported_at'),
        'evidence':('viability_electoral_evidence','id,variable_code,status,evidence_note,source_label,source_url,reference_date'),
        'coalitions':('viability_coalition_scenarios','id,scenario_name,parties,scope,status,notes,source_url'),
    }
    data={};totals={}
    for key,(table,columns) in specs.items():
        # Identifiers are constants above, never user input; values remain parameters.
        totals[key]=conn.execute(f'SELECT count(*) AS n FROM {table} WHERE profile_id=%s',(profile_id,)).fetchone()['n']
        rows=conn.execute(f'SELECT {columns} FROM {table} WHERE profile_id=%s ORDER BY id LIMIT 500',(profile_id,)).fetchall()
        data[key]=[dict(r) for r in rows]
    data['surveys']=[describe_survey(r) for r in data['surveys']]
    data['evidence']=[dict(r,related_cards=EVIDENCE_LINKS.get(r['variable_code'],[])) for r in data['evidence']]
    for r in data['documents']:
        if r['imported_at'] is not None:r['imported_at']=str(r['imported_at'])
    return dict(profile=profile,reviewed_on=survey_review()['reviewed_on'],**data,totals=totals,
                truncated=any(n>500 for n in totals.values()),warnings=[
                    'Porcentajes reportados por cada fuente; no son auditoría independiente ni pronóstico. No se promedian estudios o escenarios distintos.',
                    'Aprobación de gestión, preferencias internas y careos son reactivos diferentes. No se convierten puntuaciones 0–100 del expediente en porcentajes.',
                    'Las relaciones de evidencia son referencias temáticas; una nota de riesgo no acredita un procedimiento jurídico y una hipótesis no acredita nominación.',
                    'La evolución IC06 requiere revisión de comparabilidad. No se calculan diferencias automáticas entre estos registros.',
                    'Los documentos se consultan como metadatos del expediente existente; no se revalida aquí su contenido ni disponibilidad del archivo.'
                ])
