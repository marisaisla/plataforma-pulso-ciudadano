"""Read-only dashboard metadata and existing territorial observations."""
import json
import math
from pathlib import Path
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.admin import administrator, db
from backend.indicator_catalog import catalog

router = APIRouter(prefix='/api/v1/indicators/dashboard', tags=['Dashboard de indicadores'],
                   dependencies=[Depends(administrator)])

# Explicit correspondence to loaded series; no inference from similar labels.
INEGI = {
    'IT10': ['1002000001','1002000002','1002000003','1002000004','6207140357',
             'ITER_P_18A24','ITER_P_18YMAS','ITER_P_60YMAS',
             'chih_poblacion_total','chih_poblacion_18a24','chih_poblacion_18ymas'],
    'IT11': ['1005000038','ITER_GRAPROES','ITER_P15YM_AN','chih_escolaridad_promedio'],
    'IT12': ['6207019030','ITER_PEA','ITER_POCUPADA','ITER_PDESOCUP','chih_pea_pct','chih_ocupacion_pct'],
    'IT13': ['6207019042','6207019018','1003000001','1003000017','1003000018','1003000019',
             '1003000020','1003000023','1003000024','ITER_VIVPAR_HAB','ITER_VPH_AGUADV',
             'ITER_VPH_DRENAJ','ITER_VPH_C_ELEC','ITER_VPH_EXCSA','ITER_VPH_INTER',
             'ITER_VPH_PC','ITER_VPH_LAVAD','ITER_VPH_CEL','ITER_PDER_SS','ITER_PSINDER',
             'chih_internet_pct','chih_afiliacion_salud_pct','chih_agua_entubada_pct','chih_drenaje_pct'],
}
CODE_BY_SERIES = {series: code for code, series_list in INEGI.items() for series in series_list}
Family = Literal['IT10','IT11','IT12','IT13']


class Card(BaseModel):
    code: str
    family: str
    name: str
    unit: str
    formula: str
    availability: str
    evidence: str
    display: str
    missing: str
    engine_support: str


class CardsOut(BaseModel):
    reviewed_on: str
    note: str
    items: list[Card]


@lru_cache(maxsize=1)
def availability():
    return json.loads(Path(__file__).with_name('indicator_availability.json').read_text(encoding='utf-8'))


@router.get('/cards', response_model=CardsOut)
def cards():
    reviewed = availability()
    return dict(reviewed_on=reviewed['reviewed_on'],
                note='Estado del inventario revisado; no certifica fuentes ni garantiza datos para todos los filtros.',
                items=[dict(code=d['code'],family=d['family'],name=d['name'],unit=d['unit'],
                            formula=d['formula'],engine_support=d['engine_support'],**reviewed['items'][d['code']])
                       for d in catalog()])


class Municipality(BaseModel):
    municipality_code: str
    municipality: str


class Series(BaseModel):
    indicator_id: str
    indicator_name: str
    family: str


class OptionsOut(BaseModel):
    states: list[str]
    municipalities: list[Municipality]
    series: list[Series]
    periods: list[str]
    sources: list[str]


@router.get('/inegi/options', response_model=OptionsOut)
def options(state: Annotated[str | None,Query(max_length=120)]=None,conn=Depends(db)):
    ids=list(CODE_BY_SERIES)
    states=conn.execute('SELECT DISTINCT state FROM territorial_indicators WHERE indicator_id=ANY(%s) ORDER BY state',(ids,)).fetchall()
    rows=conn.execute('''SELECT DISTINCT municipality_code,municipality,indicator_id,indicator_name,period,source
        FROM territorial_indicators WHERE indicator_id=ANY(%s) AND (%s::text IS NULL OR state=%s)
        ORDER BY municipality_code,indicator_id''',(ids,state,state)).fetchall()
    municipalities=sorted({(r['municipality_code'],r['municipality']) for r in rows}) if state else []
    series=sorted({(r['indicator_id'],r['indicator_name']) for r in rows})
    return dict(states=[r['state'] for r in states],
                municipalities=[dict(municipality_code=c,municipality=n) for c,n in municipalities],
                series=[dict(indicator_id=i,indicator_name=n,family=CODE_BY_SERIES[i]) for i,n in series],
                periods=sorted({r['period'] for r in rows if r['period']}),
                sources=sorted({r['source'] for r in rows if r['source']}))


class Observation(BaseModel):
    id: int
    family: str
    state: str
    municipality_code: str
    municipality: str
    indicator_id: str
    indicator_name: str
    unit: str | None
    value: float | None
    period: str | None
    source: str
    retrieved_at: str
    value_status: str


class ObservationsOut(BaseModel):
    total: int
    items: list[Observation]
    next_after: int | None
    scope: str


@router.get('/inegi', response_model=ObservationsOut)
def observations(state: Annotated[str,Query(min_length=1,max_length=120)],
                 period: Annotated[str,Query(min_length=1,max_length=100)],
                 source: Annotated[str,Query(min_length=1,max_length=2000)],
                 family: Family,
                 municipality_code: Annotated[str | None,Query(max_length=20)]=None,
                 indicator_id: Annotated[str | None,Query(max_length=120)]=None,
                 after: Annotated[int,Query(ge=0)]=0,
                 limit: Annotated[int,Query(ge=1,le=500)]=100,conn=Depends(db)):
    where='''FROM territorial_indicators WHERE indicator_id=ANY(%s) AND state=%s AND period=%s AND source=%s
        AND (%s::text IS NULL OR municipality_code=%s) AND (%s::text IS NULL OR indicator_id=%s)'''
    params=(INEGI[family],state,period,source,municipality_code,municipality_code,indicator_id,indicator_id)
    total=conn.execute('SELECT count(*) AS n '+where,params).fetchone()['n']
    rows=conn.execute('SELECT * '+where+' AND id>%s ORDER BY id LIMIT %s',(*params,after,limit+1)).fetchall()
    items=[]
    for row in rows[:limit]:
        value=row['value']
        valid=value is not None and math.isfinite(value)
        items.append(dict(row,family=family,value=value if valid else None,
                          retrieved_at=str(row['retrieved_at']),value_status='reported' if valid else 'missing_or_nonfinite'))
    return dict(total=total,items=items,next_after=items[-1]['id'] if len(rows)>limit else None,
                scope='Observaciones registradas para estos filtros. Sin agregación, imputación ni certificación externa; la cobertura es municipal.')
