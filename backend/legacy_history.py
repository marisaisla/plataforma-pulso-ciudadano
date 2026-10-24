"""Migración aditiva de cargas anteriores. Nunca escribe en public.

Normalizar no equivale a acreditar una fuente: todas las cargas mantienen la marca
legacy_snapshot/legacy_reported y quedan fuera de la vista de hechos oficiales.
"""
import csv
import hashlib
import io
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation

from psycopg.types.json import Jsonb

from backend.history_models import GEO_COLUMNS, RESULT_COLUMNS

TABLES = ('territorial_election_results', 'territorial_district_results', 'territorial_section_results')
PROTECTED = ('profiles', 'profile_positions', 'profile_keywords', 'profile_territories',
             'territories', 'territorial_indicators')
ENTITY_CODES = {'campeche':'04', 'chihuahua':'08', 'estado de mexico':'15', 'guerrero':'12',
                'nayarit':'18', 'queretaro':'22', 'sonora':'26', 'yucatan':'31'}
LEVELS = dict(zip(TABLES, ('municipality', 'local_district', 'section')))
TOTALS = {'nominal_list':'lista_nominal', 'total_votes':'votes_total',
          'null_votes':'votes_nulos', 'unregistered_votes':'votes_no_reg'}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), default=str)


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def key(value):
    return ''.join(c for c in unicodedata.normalize('NFD', str(value).strip().casefold())
                   if unicodedata.category(c) != 'Mn')


def number(value):
    if value is None or value == '':
        return None
    if isinstance(value, bool):
        raise ValueError('Conteo booleano inválido')
    try:
        n = Decimal(str(value))
        if not n.is_finite() or n != n.to_integral_value() or not 0 <= n <= 2**63-1:
            raise ValueError('Conteo negativo, fraccionario o fuera de rango')
        return int(n)
    except InvalidOperation as exc:
        raise ValueError('Conteo no numérico') from exc


def component(value, width, entity=None):
    text = str(value or '').strip()
    if entity and len(text) == width+2 and text.startswith(entity):
        text = text[2:]
    if not re.fullmatch(r'[0-9]{1,'+str(width)+'}', text) or int(text) == 0:
        raise ValueError('Clave faltante, cero o incompatible')
    return text.zfill(width)


def read_sources(conn):
    return {table: conn.execute(f'SELECT * FROM public.{table} ORDER BY id').fetchall() for table in TABLES}


def protected_checksums(conn):
    result = {}
    for table in PROTECTED:
        result[table] = conn.execute(f'''SELECT count(*) AS rows,
            md5(COALESCE(string_agg(md5(to_jsonb(t)::text),'' ORDER BY md5(to_jsonb(t)::text)),'')) AS checksum
            FROM public.{table} t''').fetchone()
    return result


def analyze(sources):
    """Plan determinista, sin DB ni cambios de valores. Retiene cada fila completa."""
    records, groups, code_candidates = [], defaultdict(list), defaultdict(set)
    for table in TABLES:
        for raw in sources[table]:
            row = dict(raw)
            try:
                payload = json.loads(row['payload'], parse_float=Decimal)
                if not isinstance(payload, dict):
                    raise ValueError('Payload no es objeto')
            except (ValueError, TypeError):
                payload = None
            entry = dict(source_table=table, source_id=row['id'], original=row,
                         row_sha256=digest(canonical(row)), payload=payload, issues=[], normalized=False)
            records.append(entry)
            identity = (row['state'], row['election_year'], row['election_type'], row.get('source') or '')
            entry['group'] = (table,)+identity
            groups[entry['group']].append(entry)
            if payload is not None and row.get('municipality'):
                try:
                    entity = ENTITY_CODES[key(row['state'])]
                    mun = component(payload.get('municipality_code_ine') or row.get('municipality_code'), 3, entity)
                    code_candidates[(row['state'], row['election_year'], key(row['municipality']))].add(mun)
                except (ValueError, KeyError):
                    pass
    for identity, entries in sorted(groups.items()):
        table, state, year, election_type, source = identity
        units = {}
        duplicate_codes = Counter()
        for entry in entries:
            try:
                payload, raw = entry['payload'], entry['original']
                if payload is None:
                    raise ValueError('payload_invalido')
                entity = ENTITY_CODES[key(state)]
                if election_type not in ('Ayuntamientos', 'Diputaciones locales', 'Gubernatura'):
                    raise ValueError('tipo_eleccion_no_acreditado')
                totals = {dest:number(payload.get(src)) for dest,src in TOTALS.items()}
                votes = {name:number(value) for name,value in payload.items()
                         if name.startswith('votes_') and name not in TOTALS.values()}
                if not votes:
                    raise ValueError('sin_opciones_de_voto')
                if any(not re.fullmatch(r'[A-Za-z0-9_+.-]{1,100}', option) for option in votes):
                    raise ValueError('codigo_opcion_incompatible')
                level = LEVELS[table]
                related = dict(municipality_code='', federal_district_code='', local_district_code='')
                if level in ('municipality', 'section'):
                    raw_mun = payload.get('municipality_code_ine') or raw.get('municipality_code')
                    if not raw_mun:
                        candidates = code_candidates.get((state, year, key(raw.get('municipality') or '')), set())
                        if len(candidates) != 1:
                            raise ValueError('municipio_sin_clave_inequivoca')
                        raw_mun = next(iter(candidates))
                        entry['issues'].append('clave_municipal_recuperada_de_otras_filas_del_mismo_estado_y_año')
                    mun = entity+component(raw_mun, 3, entity)
                    mun_name = raw.get('municipality') or f'Municipio {mun} (nombre pendiente)'
                    units[('municipality', mun)] = dict(level='municipality', code=mun, name=mun_name,
                                                       entity_code=entity, municipality_code='', federal_district_code='', local_district_code='')
                    if level == 'municipality':
                        code, name = mun, mun_name
                    else:
                        code = entity+component(raw.get('section_code'), 4, entity)
                        name = 'Sección '+component(raw.get('section_code'), 4, entity)
                        related['municipality_code'] = mun
                if level in ('local_district', 'section'):
                    try:
                        district = entity+component(raw.get('district_code'), 2, entity)
                    except ValueError:
                        if level != 'section':
                            raise
                        district = None
                        entry['issues'].append('distrito_desconocido_no_se_inventa')
                    if district:
                        units[('local_district', district)] = dict(level='local_district', code=district,
                            name=raw.get('district_name') or 'Distrito local '+district[2:], entity_code=entity,
                            municipality_code='', federal_district_code='', local_district_code='')
                        if level == 'local_district':
                            code, name = district, raw.get('district_name') or 'Distrito local '+district[2:]
                        else:
                            related['local_district_code'] = district
                units[('entity', entity)] = dict(level='entity', code=entity, name=state, entity_code=entity,
                                               municipality_code='', federal_district_code='', local_district_code='')
                entry.update(unit_code=code, unit=dict(level=level, code=code, name=name, entity_code=entity, **related),
                             totals=totals, votes=votes, normalized=True)
                duplicate_codes[code] += 1
                counts = list(votes.values()) + [totals['null_votes'], totals['unregistered_votes']]
                if any(v is None for v in counts) or totals['total_votes'] is None:
                    entry['issues'].append('componentes_o_total_faltantes')
                elif sum(counts) != totals['total_votes']:
                    entry['issues'].append('opciones_no_concilian_posible_atribucion_mixta_no_se_corrigen')
                if totals['nominal_list'] is None:
                    entry['issues'].append('lista_nominal_no_disponible')
            except (ValueError, KeyError) as exc:
                entry['issues'].append(str(exc))
                entry['normalized'] = False
        for entry in entries:
            if entry['normalized'] and duplicate_codes[entry['unit_code']] > 1:
                entry['normalized'] = False
                entry['issues'].append('varias_filas_para_misma_seccion_no_se_suman_ni_descartan')
        for entry in entries:
            if entry['normalized']:
                units[(entry['unit']['level'],entry['unit_code'])] = entry['unit']
        for entry in entries:
            entry['geography_units'] = units
    summary = dict(source_rows=len(records), normalized=sum(e['normalized'] for e in records),
                   pending=sum(not e['normalized'] for e in records),
                   tables={t:len(sources[t]) for t in TABLES},
                   issues=dict(Counter(issue for e in records for issue in e['issues'])),
                   groups=[dict(table=k[0], state=k[1], year=k[2], election_type=k[3], source=k[4],
                       rows=len(v), normalized=sum(e['normalized'] for e in v)) for k,v in sorted(groups.items())])
    return records, summary


def csv_text(columns, rows):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, lineterminator='\n')
    writer.writerow(columns)
    writer.writerows(rows)
    return stream.getvalue()


def legacy_source(source, snapshot_hash, note):
    url_match = re.search(r'https://[^\s|]+', source)
    return dict(authority='Fuente heredada; acreditación pendiente', url=url_match.group(0) if url_match else None,
        title='Migración de carga electoral anterior', published_on=None, retrieved_on=date.today().isoformat(),
        cutoff_on=None, version='snapshot-'+snapshot_hash[:16], stage='legacy_snapshot', legacy_source_text=source,
        methodology='Copia aditiva desde PostgreSQL. No es una descarga ni revalidación oficial. '+note)


def write_migration(conn, sources, actor_id, snapshot_path, protected_before):
    """Una sola transacción de quien llama; el respaldo debe estar verificado antes."""
    conn.execute('SELECT pg_advisory_xact_lock(70262101)')
    snapshot_hash = digest(canonical(sources))
    old = conn.execute('SELECT id,report FROM electoral_history.legacy_runs WHERE snapshot_sha256=%s', (snapshot_hash,)).fetchone()
    if old:
        return {**old['report'], 'run_id':old['id'], 'duplicate':True}
    records, summary = analyze(sources)
    report = {**summary, 'snapshot_sha256':snapshot_hash, 'snapshot_path':str(snapshot_path),
              'protected_before':protected_before, 'verification':'pending_official_review', 'duplicate':False}
    run_id = conn.execute('''INSERT INTO electoral_history.legacy_runs
        (snapshot_sha256,snapshot_path,created_by,report) VALUES (%s,%s,%s,%s) RETURNING id''',
        (snapshot_hash,str(snapshot_path),actor_id,Jsonb(report))).fetchone()['id']
    report['run_id'] = run_id
    groups = defaultdict(list)
    for entry in records:
        groups[entry['group']].append(entry)
    batches = []
    for identity, entries in sorted(groups.items()):
        good = [e for e in entries if e['normalized']]
        if not good:
            continue
        table,state,year,election_type,source = identity
        group_hash = digest(canonical(identity))
        source_info = legacy_source(source,snapshot_hash,'Tabla '+table+'. Se conservan todas las columnas de voto como legacy_reported; no redistribuir coaliciones.')
        units = good[0]['geography_units']
        geo_csv = csv_text(GEO_COLUMNS, ([u[c] for c in GEO_COLUMNS] for _,u in sorted(units.items())))
        geo_id = conn.execute('''INSERT INTO electoral_history.geographies
            (version,valid_on,source,content_sha256,csv_content,created_by)
            VALUES (%s,NULL,%s,%s,%s,%s) RETURNING id''',
            ('legacy-'+snapshot_hash[:16]+'-'+group_hash[:16],Jsonb(source_info),digest(geo_csv),geo_csv,actor_id)).fetchone()['id']
        with conn.cursor().copy('''COPY electoral_history.units
                (geography_id,level,code,name,entity_code,municipality_code,federal_district_code,local_district_code) FROM STDIN''') as copy:
            for _,u in sorted(units.items()):
                copy.write_row((geo_id,*(u[c] or None for c in GEO_COLUMNS)))
        election_code = 'LEGACY_'+ENTITY_CODES[key(state)]+'_'+str(year)+'_'+digest(election_type)[:12]
        election = conn.execute('SELECT * FROM electoral_history.elections WHERE code=%s', (election_code,)).fetchone()
        if election:
            if (election.get('legacy_election_year') != year or election['entity_code'] != ENTITY_CODES[key(state)]
                    or election['office'] != election_type or election['election_date'] is not None):
                raise RuntimeError('El código de elección heredada colisiona con otro registro; no se sobrescribe.')
            election_id = election['id']
        else:
            election_id = conn.execute('''INSERT INTO electoral_history.elections
                (code,name,election_date,jurisdiction,office,principle,process,entity_code,created_by,legacy_election_year,legacy_note)
                VALUES (%s,%s,NULL,'local',%s,'unknown','unknown',%s,%s,%s,%s) RETURNING id''',
                (election_code,state+' · '+election_type+' '+str(year),election_type,ENTITY_CODES[key(state)],actor_id,year,
                 'Año y cargo de la carga anterior; jornada, principio y carácter ordinario/extraordinario pendientes de acreditar.')).fetchone()['id']
        chunks, chunk, n = [], [], 0
        for entry in good:
            if chunk and n+len(entry['votes']) > 18000:
                chunks.append(chunk)
                chunk,n = [],0
            chunk.append(entry)
            n += len(entry['votes'])
        if chunk:
            chunks.append(chunk)
        for index, chunk in enumerate(chunks):
            result_csv = csv_text(RESULT_COLUMNS, (
                [e['unit_code'],*e['totals'].values(),option,option,value]
                for e in chunk for option,value in sorted(e['votes'].items())))
            batch_id = conn.execute('''INSERT INTO electoral_history.imports
                (election_id,geography_id,level,vote_basis,source,content_sha256,fingerprint,csv_content,coverage_note,created_by)
                VALUES (%s,%s,%s,'legacy_reported',%s,%s,%s,%s,%s,%s) RETURNING id''',
                (election_id,geo_id,LEVELS[table],Jsonb(source_info),digest(result_csv),
                 digest(snapshot_hash+group_hash+str(index)),result_csv,
                 f'Carga heredada parcial, tabla {table}, lote {index+1}/{len(chunks)}: {len(chunk)} unidades. Acreditación pendiente; no sumar otras bases o niveles.',actor_id)).fetchone()['id']
            with conn.cursor().copy('''COPY electoral_history.results
                    (import_id,unit_code,nominal_list,total_votes,null_votes,unregistered_votes) FROM STDIN''') as copy:
                for e in chunk:
                    copy.write_row((batch_id,e['unit_code'],*e['totals'].values()))
            with conn.cursor().copy('''COPY electoral_history.votes
                    (import_id,unit_code,option_code,option_name,votes) FROM STDIN''') as copy:
                for e in chunk:
                    for option,value in sorted(e['votes'].items()):
                        copy.write_row((batch_id,e['unit_code'],option,option,value))
            for entry in chunk:
                entry['import_id'] = batch_id
            batches.append(batch_id)
    with conn.cursor().copy('''COPY electoral_history.legacy_records
            (run_id,source_table,source_id,row_sha256,original_row,status,issues,import_id,unit_code) FROM STDIN''') as copy:
        for e in records:
            copy.write_row((run_id,e['source_table'],e['source_id'],e['row_sha256'],Jsonb(json.loads(canonical(e['original']))),
                           'normalized' if e['normalized'] else 'pending',Jsonb(e['issues']),e.get('import_id'),e.get('unit_code')))
    # Conciliación exacta de totales/opciones, fila por fila; no comparar solo sumas.
    expected = {(e['import_id'],e['unit_code']):e for e in records if e['normalized']}
    totals = conn.execute('SELECT * FROM electoral_history.results WHERE import_id=ANY(%s)', (batches,)).fetchall()
    if len(totals) != len(expected):
        raise RuntimeError('Conciliación fallida: cantidad de unidades distinta.')
    for row in totals:
        if any(row[k] != expected[(row['import_id'],row['unit_code'])]['totals'][k] for k in TOTALS):
            raise RuntimeError('Conciliación fallida: cambió un total.')
    votes = conn.execute('SELECT * FROM electoral_history.votes WHERE import_id=ANY(%s)', (batches,)).fetchall()
    if len(votes) != sum(len(e['votes']) for e in expected.values()):
        raise RuntimeError('Conciliación fallida: cantidad de opciones distinta.')
    for row in votes:
        if expected[(row['import_id'],row['unit_code'])]['votes'][row['option_code']] != row['votes']:
            raise RuntimeError('Conciliación fallida: cambió una votación.')
    archive = conn.execute('SELECT source_table,source_id,row_sha256,original_row FROM electoral_history.legacy_records WHERE run_id=%s', (run_id,)).fetchall()
    originals = {(e['source_table'],e['source_id']):e for e in records}
    if len(archive) != len(records) or any(digest(canonical(r['original_row'])) != originals[(r['source_table'],r['source_id'])]['row_sha256'] for r in archive):
        raise RuntimeError('Conciliación fallida: archivo de originales incompleto o alterado.')
    after = protected_checksums(conn)
    if after != protected_before or digest(canonical(read_sources(conn))) != snapshot_hash:
        raise RuntimeError('Cambió información protegida o el origen; se revierte la migración.')
    report.update(protected_after=after, reconciled=True, imported_batches=len(batches), vote_rows=len(votes), archived_rows=len(archive))
    conn.execute('UPDATE electoral_history.legacy_runs SET report=%s WHERE id=%s', (Jsonb(report),run_id))
    return report
