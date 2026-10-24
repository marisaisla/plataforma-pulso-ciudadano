"""Migración aditiva explícita: python -m backend.migrate_history."""
from pathlib import Path
from backend.database import connect


def migrate():
    folder = Path(__file__).resolve().parents[1] / 'scripts'
    with connect() as conn:
        for name in ('agregar_base_historica_postgresql.sql', 'migrar_cargas_electorales_schema.sql'):
            conn.execute((folder/name).read_text(encoding='utf-8'))


if __name__ == '__main__':
    migrate()
    print('Base histórica electoral creada/verificada. No se cargaron resultados ni se alteraron tablas operativas.')
