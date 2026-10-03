"""Exporta Go2Win SQLite a SQL PostgreSQL; no conecta ni modifica la fuente.

El destino debe ser go2win_desarrollo y su esquema public debe estar vacío.
El SQL contiene datos privados: guardarlo solo en data/backups (ignorado por Git).
"""
import argparse
from collections import defaultdict
import math
from pathlib import Path
import re
import sqlite3


def qi(value):
    return '"' + value.replace('"', '""') + '"'


def literal(value):
    if value is None:
        return 'NULL'
    if isinstance(value, str):
        if '\x00' in value:
            raise ValueError('Texto con NUL no representable en PostgreSQL.')
        return "'" + value.replace("'", "''") + "'"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and math.isfinite(value):
        return repr(value)
    raise ValueError(f'Tipo no soportado: {type(value).__name__}')


CHECKS = {
    'viability_electoral_scores': ['score >= 0 AND score <= 100'],
    'field_role_permissions': ["scope IN ('own','team','campaign','all')"],
    'field_worker_scopes': ["municipality = '' OR state != ''"],
    'field_reports': ['length(body) BETWEEN 1 AND 4000', "status IN ('pending','accepted','correction')"],
    'field_report_reviews': ["decision IN ('accepted','correction')"],
}


def export(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination.exists():
        raise ValueError('El archivo de salida ya existe; no se sobrescribe.')
    conn = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute('BEGIN')
        if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or conn.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('La fuente presenta errores de integridad.')
        tables = conn.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
        triggers = conn.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger'").fetchall()
        expected_triggers = {'field_workers_role_insert', 'field_workers_role_update'}
        if {r['name'] for r in triggers} != expected_triggers:
            raise ValueError('Triggers no reconocidos; revisar manualmente antes de exportar.')
        for row in triggers:
            operation = 'INSERT' if row['name'].endswith('_insert') else 'UPDATE'
            expected = f"CREATE TRIGGER {row['name']} BEFORE {operation} ON field_workers WHEN NOT EXISTS (SELECT 1 FROM field_roles WHERE key = NEW.role_key) BEGIN SELECT RAISE(ABORT, 'Rol desconocido'); END"
            if ' '.join(row['sql'].split()) != expected:
                raise ValueError('La definición del trigger cambió; revisar manualmente.')
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type='view'").fetchone():
            raise ValueError('Hay vistas que requieren conversión manual.')
        destination.parent.mkdir(parents=True, exist_ok=True)
        deferred, sequences, counts = [], [], {}
        with destination.open('x', encoding='utf-8', newline='\n') as out:
            def emit(sql):
                out.write(sql + '\n')
            emit("-- DATOS PRIVADOS. No subir a GitHub. Fuente: " + source.name)
            # Debe preceder todo dato UTF-8: psql en Windows puede iniciar en WIN1252.
            emit("BEGIN;\nSET LOCAL client_encoding='UTF8';\nSET LOCAL standard_conforming_strings=on;\nSET LOCAL search_path=public,pg_catalog;\nSET LOCAL timezone='UTC';")
            emit("DO $$ BEGIN IF current_database()<>'go2win_desarrollo' THEN RAISE EXCEPTION 'Base de destino incorrecta'; END IF; IF EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','S','f')) THEN RAISE EXCEPTION 'El esquema public debe estar vacío'; END IF; END $$;")
            for table in tables:
                name, ddl = table['name'], table['sql']
                cols = conn.execute('PRAGMA table_info(' + qi(name) + ')').fetchall()
                pk = [c['name'] for c in sorted(cols, key=lambda c: c['pk']) if c['pk']]
                checks = CHECKS.get(name, [])
                if len(re.findall(r'\bCHECK\s*\(', ddl, re.I)) != len(checks) or any(not re.search(r'CHECK\s*\(\s*'+re.escape(check)+r'\s*\)', ddl, re.I) for check in checks):
                    raise ValueError('Restricción CHECK no reconocida: ' + name)
                if re.search(r'\b(COLLATE|GENERATED|WITHOUT)\b', ddl, re.I):
                    raise ValueError('Definición especial no soportada: ' + name)
                fields = []
                for col in cols:
                    kind = {'INTEGER': 'BIGINT', 'REAL': 'DOUBLE PRECISION', 'TEXT': 'TEXT'}[col['type']]
                    field = qi(col['name']) + ' ' + kind
                    identity = len(pk) == 1 and col['pk'] and col['type'] == 'INTEGER'
                    if identity:
                        field += ' GENERATED BY DEFAULT AS IDENTITY'
                        maximum = conn.execute('SELECT max('+qi(col['name'])+') FROM '+qi(name)).fetchone()[0] or 0
                        seq = conn.execute('SELECT seq FROM sqlite_sequence WHERE name=?', (name,)).fetchone()
                        sequences.append((name, col['name'], max(maximum, seq[0] if seq else 0, 0)))
                    if col['notnull'] or col['pk']:
                        field += ' NOT NULL'
                    if col['dflt_value'] is not None and not identity:
                        default = col['dflt_value']
                        if default.upper() == 'CURRENT_TIMESTAMP' and kind == 'TEXT':
                            default = "to_char(CURRENT_TIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS')"
                        field += ' DEFAULT ' + default
                    fields.append(field)
                if pk:
                    fields.append('PRIMARY KEY (' + ','.join(map(qi, pk)) + ')')
                fields.extend('CHECK ('+check+')' for check in checks)
                for idx in conn.execute('PRAGMA index_list('+qi(name)+')'):
                    if idx['origin'] == 'pk':
                        continue
                    details = conn.execute('PRAGMA index_info('+qi(idx['name'])+')').fetchall()
                    if idx['partial'] or any(r['name'] is None for r in details):
                        raise ValueError('Índice especial no soportado: '+idx['name'])
                    column_list = ','.join(qi(r['name']) for r in details)
                    if idx['origin'] == 'u':
                        fields.append('UNIQUE ('+column_list+')')
                    else:
                        deferred.append('CREATE '+('UNIQUE ' if idx['unique'] else '')+'INDEX '+qi(idx['name'])+' ON '+qi(name)+' ('+column_list+');')
                emit('CREATE TABLE '+qi(name)+' (\n  '+',\n  '.join(fields)+'\n);')
                groups = defaultdict(list)
                for fk in conn.execute('PRAGMA foreign_key_list('+qi(name)+')'):
                    groups[fk['id']].append(fk)
                for group in groups.values():
                    group.sort(key=lambda r: r['seq'])
                    first = group[0]
                    target = ','.join(qi(r['to']) for r in group) if all(r['to'] for r in group) else ''
                    deferred.append('ALTER TABLE '+qi(name)+' ADD FOREIGN KEY ('+','.join(qi(r['from']) for r in group)+') REFERENCES '+qi(first['table'])+(' ('+target+')' if target else '')+' ON UPDATE '+first['on_update']+' ON DELETE '+first['on_delete']+';')
                count = 0
                cursor = conn.execute('SELECT '+','.join(qi(c['name']) for c in cols)+' FROM '+qi(name))
                while batch := cursor.fetchmany(100):
                    emit('INSERT INTO '+qi(name)+' ('+','.join(qi(c['name']) for c in cols)+') VALUES\n'+',\n'.join('('+','.join(literal(v) for v in row)+')' for row in batch)+';')
                    count += len(batch)
                counts[name] = count
            # Equivalente relacional de los dos triggers SQLite que validan el rol.
            deferred.append('ALTER TABLE field_workers ADD CONSTRAINT field_workers_role_valid FOREIGN KEY (role_key) REFERENCES field_roles(key);')
            for sql in deferred:
                emit(sql)
            for table, column, maximum in sequences:
                emit('SELECT setval(pg_get_serial_sequence('+literal(qi(table))+','+literal(column)+'),'+str(max(1, maximum))+','+('true' if maximum else 'false')+');')
            for table, count in counts.items():
                emit('DO $$ BEGIN IF (SELECT count(*) FROM '+qi(table)+') <> '+str(count)+" THEN RAISE EXCEPTION 'Conteo incorrecto: "+table+"'; END IF; END $$;")
            emit("COMMIT;\nSELECT 'Migracion completada y conteos validados' AS resultado;")
        return counts
    finally:
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('destination')
    args = parser.parse_args()
    counts = export(args.source, args.destination)
    print(f'Exportadas {len(counts)} tablas y {sum(counts.values())} registros a {args.destination}')
