"""PostgreSQL transport for the application's parameterized SQL interface.

Schema creation/migration is explicit; startup only validates the migrated schema.
"""
import json
import re
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import psycopg

from services.settings import get_setting


class Row(tuple):
    """Named and positional access, matching sqlite3.Row used by existing services."""
    def __new__(cls, values, names):
        row = super().__new__(cls, values)
        row.names = names
        return row

    def keys(self):
        return self.names

    def __getitem__(self, key):
        return super().__getitem__(self.names.index(key) if isinstance(key, str) else key)


def row_factory(cursor):
    names = tuple(c.name for c in cursor.description) if cursor.description else ()
    def make_row(values):
        # SUM(bigint) and AVG(bigint) return Decimal in PostgreSQL. Preserve the
        # JSON/pandas-friendly numbers returned by the original SQLite queries.
        return Row(tuple((int(v) if v == v.to_integral_value() else float(v))
                         if isinstance(v, Decimal) else v for v in values), names)
    return make_row


# Quoted literals/identifiers and comments must not have their question marks or
# SQL keywords rewritten. Percent signs are escaped for Psycopg's parameter API.
TOKENS = re.compile(r"' (?: '' | [^'] )* ' | \" (?: \"\" | [^\"] )* \" | --[^\n]* | /\*.*?\*/ | [A-Za-z_][A-Za-z_0-9]* | .", re.X | re.S)


@lru_cache(maxsize=1024)
def translate(sql):
    ignore = bool(re.match(r'\s*INSERT\s+OR\s+IGNORE\b', sql, re.I))
    if ignore:
        sql = re.sub(r'\bINSERT\s+OR\s+IGNORE\b', 'INSERT', sql, count=1, flags=re.I)
    if re.match(r'\s*(PRAGMA|INSERT\s+OR\s+REPLACE)\b', sql, re.I):
        raise ValueError('Esta operación SQLite necesita una conversión explícita para PostgreSQL.')
    parts = []
    for match in TOKENS.finditer(sql):
        token = match.group()
        if token == '?':
            parts.append('%s')
        elif token.upper() == 'GROUP_CONCAT':
            parts.append('STRING_AGG')
        elif token.upper() == 'CURRENT_TIMESTAMP':
            # v3 preserves timestamp columns as TEXT, in the original UTC format.
            parts.append("to_char(CURRENT_TIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS')")
        else:
            parts.append(token.replace('%', '%%'))
    result = ''.join(parts).strip().rstrip(';')
    if ignore:
        result += ' ON CONFLICT DO NOTHING'
    return result


class Connection:
    def __init__(self):
        config = {key[2:].lower(): get_setting(key) for key in
                  ('PGHOST', 'PGPORT', 'PGDATABASE', 'PGUSER', 'PGPASSWORD')}
        config['dbname'] = config.pop('database')
        if not all(config.values()):
            raise ValueError('Completa PGHOST, PGPORT, PGDATABASE, PGUSER y PGPASSWORD en .env.')
        self.raw = psycopg.connect(**config, connect_timeout=10, row_factory=row_factory,
                                  application_name='Go2Win', options='-c timezone=UTC')

    def execute(self, sql, parameters=()):
        if sql.strip().rstrip(';').upper() == 'BEGIN IMMEDIATE':
            # Preserve SQLite's serialization of authorization/assignment changes
            # across all Go2Win processes sharing this database. Released on exit.
            return self.raw.execute('SELECT pg_advisory_xact_lock(720260928)')
        return self.raw.execute(translate(sql), parameters)

    def executemany(self, sql, parameters):
        cursor = self.raw.cursor()
        cursor.executemany(translate(sql), parameters)
        return cursor

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        self.raw.close()

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        try:
            self.rollback() if kind else self.commit()
        finally:
            self.close()


def validate_schema():
    _validate_schema(tuple(get_setting(k) for k in ('PGHOST', 'PGPORT', 'PGDATABASE', 'PGUSER')))


@lru_cache(maxsize=8)
def _validate_schema(target):
    expected = json.loads(Path(__file__).with_name('postgres_schema.json').read_text(encoding='utf-8'))
    with Connection() as conn:
        actual = {}
        for row in conn.execute("SELECT table_name,column_name FROM information_schema.columns WHERE table_schema='public'"):
            actual.setdefault(row[0], set()).add(row[1])
        missing = [f'{table}.{column}' for table, columns in expected.items()
                   for column in columns if column not in actual.get(table, set())]
        if missing:
            raise RuntimeError('El esquema PostgreSQL requiere actualización. Ejecuta scripts/aplicar_actualizacion_telegram.py. Faltan: ' + ', '.join(missing[:15]))
