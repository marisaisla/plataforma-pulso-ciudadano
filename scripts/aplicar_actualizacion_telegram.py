"""Aplica las migraciones Telegram juntas con validación previa al commit."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.settings import get_setting
from services.postgres_backend import Connection


def main():
    if get_setting('DB_BACKEND').strip().lower() != 'postgresql':
        raise RuntimeError('La actualización requiere DB_BACKEND=postgresql.')
    expected = json.loads((ROOT / 'services/postgres_schema.json').read_text(encoding='utf-8'))
    with Connection() as conn:
        target = conn.raw.execute('SELECT current_database()').fetchone()[0]
        if target != 'go2win_desarrollo':
            raise RuntimeError('La actualización solo admite go2win_desarrollo.')
        conn.raw.execute('SELECT pg_advisory_xact_lock(720260928)')
        conn.raw.execute('SET LOCAL search_path=public')
        conn.raw.execute("SET LOCAL lock_timeout = '10s'")
        for name in ('agregar_evidencias_postgresql.sql', 'agregar_simpatizantes_postgresql.sql', 'agregar_necesidades_postgresql.sql'):
            lines = (ROOT / 'scripts' / name).read_text(encoding='utf-8').splitlines()
            body = '\n'.join(line for line in lines if line.strip().upper() not in {'BEGIN;', 'COMMIT;'})
            conn.raw.execute(body)
            print(f'Preparado: {name}', flush=True)
        actual = {}
        for table, column in conn.raw.execute('SELECT table_name,column_name FROM information_schema.columns WHERE table_schema=%s', ('public',)):
            actual.setdefault(table, set()).add(column)
        missing = [f'{table}.{column}' for table, columns in expected.items()
                   for column in columns if column not in actual.get(table, set())]
        if missing:
            raise RuntimeError('Esquema incompleto; se revierte la transacción: ' + ', '.join(missing[:15]))
        grants = conn.raw.execute('SELECT count(*) FROM field_role_permissions WHERE permission_key = ANY(%s)',
                                 (['supporters.submit', 'supporters.view'],)).fetchone()[0]
        if grants != 9:
            raise RuntimeError('Permisos incompletos; se revierte la transacción.')
        needs_grants = conn.raw.execute('SELECT count(*) FROM field_role_permissions WHERE permission_key = ANY(%s)',
                                       (['needs.submit', 'needs.view'],)).fetchone()[0]
        if needs_grants != 6:
            raise RuntimeError('Permisos de necesidades incompletos; se revierte la transacción.')
    print('Actualización confirmada en go2win_desarrollo. Esquema, 9 permisos de simpatizantes y 6 de necesidades verificados.')


if __name__ == '__main__':
    main()
