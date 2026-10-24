"""Base histórica independiente del expediente y de las tablas operativas heredadas."""
import hashlib
import json
from collections import Counter
from typing import Annotated

from psycopg.types.json import Jsonb
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.admin import administrator, db
from backend.history_models import (ElectionCreate, GeographyImport, ResultImport,
                                    Level, code_for, parse_geography, parse_results,
                                    GeographyOut, GeographyDetail, GeographySaved, UnitPage,
                                    ElectionOut, PreviewOut, ImportSaved, ImportOut, ImportDetail, ResultPage)

router = APIRouter(prefix='/api/v1/history', tags=['Base histórica electoral'],
                   dependencies=[Depends(administrator)])


def fail(message, code=422):
    raise HTTPException(code, message)


def parse(parser, text):
    try:
        return parser(text)
    except ValueError as exc:
        fail(str(exc))


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def lock(conn):
    # Serializa cargas para evitar carreras entre duplicados y revisiones.
    conn.execute('SELECT pg_advisory_xact_lock(70262101)')


def get(conn, table, rid):
    # table siempre es una constante del módulo, nunca entrada del usuario.
    row = conn.execute(f'SELECT * FROM electoral_history.{table} WHERE id=%s', (rid,)).fetchone()
    if not row:
        fail('Registro histórico inexistente.', 404)
    return row


@router.get('/geographies', response_model=list[GeographyOut])
def geographies(conn=Depends(db)):
    return conn.execute('''SELECT g.id,g.version,g.valid_on,g.source,g.content_sha256,
        g.created_at,count(u.code) AS units FROM electoral_history.geographies g
        LEFT JOIN electoral_history.units u ON u.geography_id=g.id
        GROUP BY g.id ORDER BY g.id DESC''').fetchall()


@router.post('/geographies', status_code=201, response_model=GeographySaved)
def create_geography(body: GeographyImport, actor=Depends(administrator), conn=Depends(db)):
    rows = parse(parse_geography, body.csv_content)
    lock(conn)
    old = conn.execute('SELECT * FROM electoral_history.geographies WHERE version=%s', (body.version,)).fetchone()
    metadata = body.source.model_dump(mode='json')
    content_hash = sha(body.csv_content)
    if old:
        if old['content_sha256'] == content_hash and old['source'] == metadata and old['valid_on'] == body.valid_on:
            return {'id': old['id'], 'duplicate': True, 'units': len(rows)}
        fail('La versión geográfica ya existe con contenido distinto; usar una versión nueva.', 409)
    rid = conn.execute('''INSERT INTO electoral_history.geographies
        (version,valid_on,source,content_sha256,csv_content,created_by)
        VALUES (%s,%s,%s,%s,%s,%s) RETURNING id''',
        (body.version, body.valid_on, Jsonb(metadata), content_hash, body.csv_content, actor['id'])).fetchone()['id']
    with conn.cursor() as cursor:
        cursor.executemany('''INSERT INTO electoral_history.units
            (geography_id,level,code,name,entity_code,municipality_code,federal_district_code,local_district_code)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''',
            [(rid, r['level'], r['code'], r['name'], r['entity_code'], r['municipality_code'] or None,
              r['federal_district_code'] or None, r['local_district_code'] or None) for r in rows])
    return {'id': rid, 'duplicate': False, 'units': len(rows), 'levels': dict(Counter(r['level'] for r in rows))}


@router.get('/geographies/{geography_id}', response_model=GeographyDetail)
def geography_detail(geography_id: int, conn=Depends(db)):
    return get(conn, 'geographies', geography_id)


@router.get('/geographies/{geography_id}/units', response_model=UnitPage)
def units(geography_id: int, level: Level | None = None, entity_code: str | None = None,
          municipality_code: str | None = None, after: str = '',
          limit: Annotated[int, Query(ge=1, le=500)] = 100, conn=Depends(db)):
    get(conn, 'geographies', geography_id)
    rows = conn.execute('''SELECT * FROM electoral_history.units WHERE geography_id=%s
        AND (%s::text IS NULL OR level=%s) AND (%s::text IS NULL OR entity_code=%s)
        AND (%s::text IS NULL OR municipality_code=%s) AND (level||':'||code)>%s
        ORDER BY level,code LIMIT %s''',
        (geography_id, level, level, entity_code, entity_code, municipality_code, municipality_code, after, limit+1)).fetchall()
    items = rows[:limit]
    return {'items': items, 'next_after': items[-1]['level']+':'+items[-1]['code'] if len(rows)>limit else None}


@router.get('/elections', response_model=list[ElectionOut])
def elections(conn=Depends(db)):
    return conn.execute('SELECT * FROM electoral_history.elections ORDER BY election_date DESC,id DESC').fetchall()


@router.post('/elections', status_code=201, response_model=ElectionOut)
def create_election(body: ElectionCreate, actor=Depends(administrator), conn=Depends(db)):
    lock(conn)
    data = body.model_dump()
    old = conn.execute('SELECT * FROM electoral_history.elections WHERE code=%s', (body.code,)).fetchone()
    if old:
        if any(old[key] != value for key, value in data.items()):
            fail('El código de elección ya identifica metadatos distintos.', 409)
        return old
    return conn.execute('''INSERT INTO electoral_history.elections
        (code,name,election_date,jurisdiction,office,principle,process,entity_code,created_by)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
        (*data.values(), actor['id'])).fetchone()


def prepare(conn, body):
    groups = parse(parse_results, body.csv_content)
    election = get(conn, 'elections', body.election_id)
    geography = get(conn, 'geographies', body.geography_id)
    if election['election_date'] is None or geography['valid_on'] is None:
        fail('Esta elección/geografía heredada requiere acreditar fechas antes de cargar resultados oficiales.', 409)
    if body.source.cutoff_on < election['election_date'] or body.source.published_on < election['election_date']:
        fail('El corte/publicación de resultados no puede preceder a la elección.')
    available = {r['code']: r for r in conn.execute('''SELECT code,entity_code FROM electoral_history.units
        WHERE geography_id=%s AND level=%s''', (body.geography_id, body.level)).fetchall()}
    for code in groups:
        unit = available.get(code)
        if not unit:
            fail('Unidad ausente del catálogo/nivel seleccionado: ' + code)
        try:
            code_for(body.level, code, unit['entity_code'])
        except ValueError as exc:
            fail(str(exc))
        if election['entity_code'] and election['entity_code'] != unit['entity_code']:
            fail('La unidad no pertenece a la entidad de la elección: ' + code)
    if body.supersedes_id:
        previous = get(conn, 'imports', body.supersedes_id)
        if any(previous[k] != getattr(body, k) for k in ('election_id', 'geography_id', 'level', 'vote_basis')):
            fail('La revisión debe conservar elección, geografía, nivel y base de votos.', 409)
        previous_codes = {r['unit_code'] for r in conn.execute(
            'SELECT unit_code FROM electoral_history.results WHERE import_id=%s', (body.supersedes_id,)).fetchall()}
        if previous_codes != set(groups):
            fail('Una revisión debe conservar la cobertura de unidades del lote anterior.', 409)
    fingerprint = sha(json.dumps(body.model_dump(mode='json'), sort_keys=True, ensure_ascii=False))
    duplicate = conn.execute('SELECT id FROM electoral_history.imports WHERE fingerprint=%s', (fingerprint,)).fetchone()
    if body.supersedes_id and not duplicate and conn.execute(
            'SELECT id FROM electoral_history.imports WHERE supersedes_id=%s', (body.supersedes_id,)).fetchone():
        fail('Ese lote ya tiene una revisión; revisar su sucesor para no crear ramas.', 409)
    warnings = []
    if any(any(v is None for v in g['totals'].values()) or
           any(v['votes'] is None for v in g['votes'].values()) for g in groups.values()):
        warnings.append('Hay datos faltantes: se conservarán como null, sin imputación de ceros.')
    if any(g['totals']['nominal_list'] is not None and g['totals']['total_votes'] is not None and
           g['totals']['total_votes'] > g['totals']['nominal_list'] for g in groups.values()):
        warnings.append('Votación mayor a lista nominal; revisar cobertura/casillas especiales.')
    return groups, fingerprint, {'units': len(groups), 'vote_rows': sum(len(g['votes']) for g in groups.values()),
                                 'content_sha256': sha(body.csv_content), 'warnings': warnings,
                                 'duplicate_id': duplicate['id'] if duplicate else None}


@router.post('/imports/preview', response_model=PreviewOut)
def preview(body: ResultImport, conn=Depends(db)):
    return prepare(conn, body)[2]


@router.post('/imports', status_code=201, response_model=ImportSaved)
def import_results(body: ResultImport, actor=Depends(administrator), conn=Depends(db)):
    lock(conn)
    groups, fingerprint, report = prepare(conn, body)
    if report['duplicate_id']:
        return {'id': report['duplicate_id'], 'duplicate': True, **report}
    rid = conn.execute('''INSERT INTO electoral_history.imports
        (election_id,geography_id,level,vote_basis,source,content_sha256,fingerprint,csv_content,
         supersedes_id,coverage_note,created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
        (body.election_id, body.geography_id, body.level, body.vote_basis, Jsonb(body.source.model_dump(mode='json')),
         report['content_sha256'], fingerprint, body.csv_content, body.supersedes_id, body.coverage_note, actor['id'])).fetchone()['id']
    with conn.cursor() as cursor:
        cursor.executemany('''INSERT INTO electoral_history.results
            (import_id,unit_code,nominal_list,total_votes,null_votes,unregistered_votes)
            VALUES (%s,%s,%s,%s,%s,%s)''', [(rid, code, *group['totals'].values()) for code, group in groups.items()])
        cursor.executemany('''INSERT INTO electoral_history.votes
            (import_id,unit_code,option_code,option_name,votes) VALUES (%s,%s,%s,%s,%s)''',
            [(rid, code, option, v['name'], v['votes']) for code, group in groups.items() for option, v in group['votes'].items()])
    return {'id': rid, 'duplicate': False, **report}


@router.get('/imports', response_model=list[ImportOut])
def imports(election_id: int | None = None, after: int = 0,
            limit: Annotated[int, Query(ge=1, le=100)] = 50, conn=Depends(db)):
    return conn.execute('''SELECT i.id,i.election_id,i.geography_id,i.level,i.vote_basis,i.source,
        i.content_sha256,i.coverage_note,i.supersedes_id,i.created_at,i.created_by,
        (SELECT id FROM electoral_history.imports n WHERE n.supersedes_id=i.id) AS superseded_by
        FROM electoral_history.imports i WHERE (%s::bigint IS NULL OR election_id=%s)
        AND id>%s ORDER BY id LIMIT %s''', (election_id, election_id, after, limit)).fetchall()


@router.get('/imports/{import_id}', response_model=ImportDetail)
def import_detail(import_id: int, conn=Depends(db)):
    # Incluye el CSV recibido y metadata para reproducir la carga.
    return get(conn, 'imports', import_id)


@router.get('/imports/{import_id}/results', response_model=ResultPage)
def results(import_id: int, entity_code: str | None = None, unit_code: str | None = None,
            after: str = '', limit: Annotated[int, Query(ge=1, le=500)] = 100, conn=Depends(db)):
    batch = get(conn, 'imports', import_id)
    rows = conn.execute('''SELECT r.*,u.name,u.entity_code,u.municipality_code,
        u.federal_district_code,u.local_district_code FROM electoral_history.results r
        JOIN electoral_history.units u ON u.geography_id=%s AND u.level=%s AND u.code=r.unit_code
        WHERE r.import_id=%s AND (%s::text IS NULL OR u.entity_code=%s)
        AND (%s::text IS NULL OR r.unit_code=%s) AND r.unit_code>%s
        ORDER BY r.unit_code LIMIT %s''',
        (batch['geography_id'], batch['level'], import_id, entity_code, entity_code, unit_code, unit_code, after, limit+1)).fetchall()
    items = rows[:limit]
    if items:
        votes = conn.execute('''SELECT unit_code,option_code,option_name,votes FROM electoral_history.votes
            WHERE import_id=%s AND unit_code=ANY(%s) ORDER BY unit_code,option_code''',
            (import_id, [r['unit_code'] for r in items])).fetchall()
        by_unit = {}
        for vote in votes:
            by_unit.setdefault(vote['unit_code'], []).append(vote)
        for row in items:
            row['options'] = by_unit.get(row['unit_code'], [])
    return {'import_id': import_id, 'level': batch['level'], 'vote_basis': batch['vote_basis'],
            'items': items, 'next_after': items[-1]['unit_code'] if len(rows)>limit else None}


@router.get('/legacy/runs')
def legacy_runs(after: int = 0, limit: Annotated[int, Query(ge=1, le=100)] = 50, conn=Depends(db)):
    return conn.execute('''SELECT id,snapshot_sha256,snapshot_path,created_by,created_at,report
        FROM electoral_history.legacy_runs WHERE id>%s ORDER BY id LIMIT %s''',(after,limit)).fetchall()


@router.get('/legacy/runs/{run_id}')
def legacy_run(run_id: int, conn=Depends(db)):
    return get(conn,'legacy_runs',run_id)


@router.get('/legacy/runs/{run_id}/records')
def legacy_records(run_id: int, status: str | None = None, state: str | None = None,
                   after: str = '', limit: Annotated[int, Query(ge=1,le=100)] = 50, conn=Depends(db)):
    from backend.legacy_history import TABLES
    get(conn,'legacy_runs',run_id)
    if status not in (None,'pending','normalized'):
        fail('Estado de migración inválido.')
    table,rid = '',0
    if after:
        try:
            table,raw_id = after.split(':',1)
            rid = int(raw_id)
            if table not in TABLES or rid<0:
                raise ValueError()
        except ValueError:
            fail('Cursor inválido; usar next_after de la respuesta anterior.')
    rows = conn.execute('''SELECT source_table,source_id,row_sha256,status,issues,import_id,unit_code,
        original_row->>'state' AS state,original_row->>'election_year' AS election_year,
        original_row->>'election_type' AS election_type,original_row->>'source' AS source
        FROM electoral_history.legacy_records WHERE run_id=%s
        AND (%s::text IS NULL OR status=%s) AND (%s::text IS NULL OR original_row->>'state'=%s)
        AND (source_table,source_id)>(%s,%s) ORDER BY source_table,source_id LIMIT %s''',
        (run_id,status,status,state,state,table,rid,limit+1)).fetchall()
    items=rows[:limit]
    return dict(items=items,next_after=items[-1]['source_table']+':'+str(items[-1]['source_id']) if len(rows)>limit else None)


@router.get('/legacy/runs/{run_id}/records/{source_table}/{source_id}')
def legacy_record(run_id: int,source_table: str,source_id: int,conn=Depends(db)):
    row=conn.execute('''SELECT * FROM electoral_history.legacy_records
        WHERE run_id=%s AND source_table=%s AND source_id=%s''',(run_id,source_table,source_id)).fetchone()
    if not row:
        fail('Registro original archivado inexistente.',404)
    return row
