"""API de indicadores: cálculos de solo lectura sobre lotes explícitos."""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.admin import administrator, db
from backend.indicator_catalog import catalog, ENGINE_VERSION, CATALOG_VERSION
from backend.indicator_models import (Selection, Comparison, EvaluationOut, ComparisonOut,
                                      CatalogOut,DatasetOut,OptionOut)
from backend.indicator_engine import evaluate, compare

router=APIRouter(prefix='/api/v1/indicators',tags=['Indicadores electorales'],dependencies=[Depends(administrator)])


@router.get('/catalog',response_model=CatalogOut)
def definitions():
    return dict(engine_version=ENGINE_VERSION,catalog_version=CATALOG_VERSION,items=catalog())


@router.get('/datasets',response_model=list[DatasetOut])
def datasets(election_id: int | None=None,after: int=0,
             limit: Annotated[int,Query(ge=1,le=100)]=50,conn=Depends(db)):
    return conn.execute('''SELECT i.id,i.election_id,i.geography_id,i.level,i.vote_basis,
        i.source->>'stage' AS source_stage,i.coverage_note,e.name AS election_name,e.election_date,
        (to_jsonb(e)->>'legacy_election_year')::integer AS legacy_election_year,g.version AS geography_version,g.valid_on,
        (SELECT count(*) FROM electoral_history.results r WHERE r.import_id=i.id) AS units,
        (SELECT id FROM electoral_history.imports n WHERE n.supersedes_id=i.id) AS superseded_by
        FROM electoral_history.imports i JOIN electoral_history.elections e ON e.id=i.election_id
        JOIN electoral_history.geographies g ON g.id=i.geography_id
        WHERE i.id>%s AND (%s::bigint IS NULL OR i.election_id=%s) ORDER BY i.id LIMIT %s''',
        (after,election_id,election_id,limit)).fetchall()


@router.get('/datasets/{import_id}/options',response_model=list[OptionOut])
def options(import_id: int,conn=Depends(db)):
    if not conn.execute('SELECT id FROM electoral_history.imports WHERE id=%s',(import_id,)).fetchone():
        raise HTTPException(404,'Lote inexistente.')
    return conn.execute('''SELECT option_code,option_name,count(*) AS units_reported,
        count(votes) AS units_with_known_votes FROM electoral_history.votes
        WHERE import_id=%s GROUP BY option_code,option_name ORDER BY option_code''',(import_id,)).fetchall()


def load_dataset(conn,selection):
    metadata=conn.execute('''SELECT i.id,i.election_id,i.geography_id,i.level,i.vote_basis,i.source,
        i.content_sha256,i.fingerprint,i.coverage_note,
        (SELECT id FROM electoral_history.imports n WHERE n.supersedes_id=i.id) AS superseded_by
        FROM electoral_history.imports i WHERE i.id=%s''',(selection.import_id,)).fetchone()
    if not metadata:
        raise HTTPException(404,'Lote inexistente.')
    if metadata['superseded_by'] and not selection.allow_superseded:
        raise HTTPException(409,'El lote fue sustituido. Elegir su revisión o reconocer explícitamente la reproducción histórica.')
    legacy=metadata['source']['stage']=='legacy_snapshot' or metadata['vote_basis']=='legacy_reported'
    if legacy and selection.mode!='exploratory':
        raise HTTPException(409,'Carga heredada pendiente de acreditación. Solo se permite su exploración explícita; no se certifica al calcular.')
    if selection.mode=='validated' and metadata['source']['stage'] not in ('official_computation','final_judgment'):
        raise HTTPException(409,'La etapa declarada no corresponde a resultados oficiales estructurados.')
    election=conn.execute('SELECT * FROM electoral_history.elections WHERE id=%s',(metadata['election_id'],)).fetchone()
    geography=conn.execute('''SELECT id,version,valid_on,source,content_sha256
        FROM electoral_history.geographies WHERE id=%s''',(metadata['geography_id'],)).fetchone()
    if selection.mode=='validated' and (not election['election_date'] or not geography['valid_on']):
        raise HTTPException(409,'La elección o geografía carece de fechas acreditadas.')
    rows=conn.execute('''SELECT r.*,u.name,u.entity_code FROM electoral_history.results r
        JOIN electoral_history.units u ON u.geography_id=%s AND u.level=%s AND u.code=r.unit_code
        WHERE r.import_id=%s ORDER BY r.unit_code''',
        (metadata['geography_id'],metadata['level'],selection.import_id)).fetchall()
    lookup={r['unit_code']:r for r in rows}
    for row in rows: row['options']=[]
    votes=conn.execute('''SELECT unit_code,option_code,option_name,votes FROM electoral_history.votes
        WHERE import_id=%s ORDER BY unit_code,option_code''',(selection.import_id,)).fetchall()
    for vote in votes:
        lookup[vote['unit_code']]['options'].append(vote)
    return dict(metadata=metadata,election=election,geography=geography,rows=rows)


@router.post('/evaluate',response_model=EvaluationOut)
def evaluation(body: Selection,conn=Depends(db)):
    return evaluate(load_dataset(conn,body),body.model_dump(mode='json'))


@router.post('/compare',response_model=ComparisonOut)
def comparison(body: Comparison,conn=Depends(db)):
    return compare(load_dataset(conn,body.a),load_dataset(conn,body.b),body.model_dump(mode='json'))
