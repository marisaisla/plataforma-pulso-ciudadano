"""Importación conservadora: solo completa tablas vacías y verifica catálogos.

Se detiene ante datos locales de negocio o diferencias de catálogo no previstas.
Conserva intactas las tablas locales de Telegram. No reemplaza archivos SQLite activos.
"""
import argparse
import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path


def quote(value):
    return '"' + value.replace('"', '""') + '"'


def readonly(path):
    return sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=20)


def tables(conn):
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}


def columns(conn, table):
    return [r[1] for r in conn.execute('PRAGMA table_info(' + quote(table) + ')')]


def validate(conn):
    if conn.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
        raise RuntimeError('Falló la comprobación de integridad.')
    if conn.execute('PRAGMA foreign_key_check').fetchall():
        raise RuntimeError('Existen referencias inválidas entre tablas.')


def merge(source, target):
    source_tables, target_tables = tables(source), tables(target)
    if not source_tables <= target_tables:
        raise RuntimeError('La base recibida contiene tablas no previstas.')
    report = {}
    target.execute('PRAGMA defer_foreign_keys = ON')
    for table in sorted(source_tables):
        if table.startswith('field_'):
            raise RuntimeError('La base recibida contiene personal: requiere comparación específica.')
        cols = columns(source, table)
        if set(cols) != set(columns(target, table)):
            raise RuntimeError('Columnas incompatibles: ' + table)
        names = ','.join(map(quote, cols))
        incoming = source.execute('SELECT ' + names + ' FROM ' + quote(table)).fetchall()
        current = target.execute('SELECT ' + names + ' FROM ' + quote(table)).fetchall()
        if table in {'prompt_catalog', 'analysis_approaches'}:
            # Los catálogos son idénticos salvo sus claves; conservamos las claves locales.
            content = lambda rows: {tuple(v for i, v in enumerate(row) if cols[i] != 'id') for row in rows}
            if content(incoming) != content(current):
                raise RuntimeError('Catálogo distinto: ' + table)
            if table == 'analysis_approaches' and set(incoming) != set(current):
                raise RuntimeError('Los enfoques necesitan reasignación de claves.')
            report[table] = {'imported': 0, 'existing': len(current)}
            continue
        if current:
            raise RuntimeError('La tabla local ya contiene registros: ' + table)
        if table == 'prompt_runs' and incoming:
            raise RuntimeError('Las consultas requieren reasignar claves de catálogo.')
        if incoming:
            target.executemany('INSERT INTO ' + quote(table) + ' (' + names + ') VALUES ('
                               + ','.join('?' for _ in cols) + ')', incoming)
        actual = target.execute('SELECT ' + names + ' FROM ' + quote(table)).fetchall()
        if set(actual) != set(incoming) or len(actual) != len(incoming):
            raise RuntimeError('Diferencia después de importar: ' + table)
        report[table] = {'imported': len(incoming), 'existing': 0}
    validate(target)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--target', type=Path, required=True)
    args = parser.parse_args()
    if not args.target.is_file() or args.source.resolve() == args.target.resolve():
        raise RuntimeError('Selecciona dos bases existentes y diferentes.')
    folder = args.target.parent / 'backups' / datetime.now().strftime('merge_%Y%m%d_%H%M%S_%f')
    folder.mkdir(parents=True)
    source_snapshot = folder / 'received.db'
    backup_path = folder / 'before_merge.db'
    trial_path = folder / 'verified_merge.db'
    with closing(readonly(args.source)) as src, closing(sqlite3.connect(source_snapshot)) as dst:
        src.backup(dst)
    with closing(readonly(source_snapshot)) as source, closing(sqlite3.connect(args.target, timeout=20)) as target:
        validate(source)
        target.execute('PRAGMA foreign_keys = ON')
        # Reserva la escritura; otras conexiones pueden leer durante respaldo y ensayo.
        target.execute('BEGIN IMMEDIATE')
        try:
            with closing(readonly(args.target)) as live, closing(sqlite3.connect(backup_path)) as backup:
                live.backup(backup)
            with closing(readonly(backup_path)) as backup, closing(sqlite3.connect(trial_path)) as trial:
                backup.backup(trial)
                trial.execute('PRAGMA foreign_keys = ON')
                trial.execute('BEGIN IMMEDIATE')
                report = merge(source, trial)
                trial.commit()
            preserved = {t: target.execute('SELECT * FROM ' + quote(t)).fetchall()
                         for t in tables(target) - tables(source)}
            merge(source, target)
            for table, rows in preserved.items():
                if target.execute('SELECT * FROM ' + quote(table)).fetchall() != rows:
                    raise RuntimeError('Se alteró una tabla local: ' + table)
            target.commit()
        except BaseException:
            target.rollback()
            raise
        validate(target)
        missing = [r[0] for r in target.execute('SELECT file_path FROM reference_documents')
                   if not Path(r[0]).exists()]
    result = {'backup': str(backup_path.resolve()), 'tables': report,
              'preserved_local_tables': {t: len(rows) for t, rows in preserved.items()},
              'missing_external_files': missing}
    (folder / 'report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'backup': result['backup'], 'imported_rows': sum(v['imported'] for v in report.values()),
                      'preserved': result['preserved_local_tables'], 'missing_external_files': len(missing)}, indent=2))


if __name__ == '__main__':
    main()
