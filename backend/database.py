import psycopg
from psycopg.rows import dict_row

from backend.config import setting


def connect():
    keys = {'host': 'PGHOST', 'port': 'PGPORT', 'dbname': 'PGDATABASE',
            'user': 'PGUSER', 'password': 'PGPASSWORD'}
    config = {name: setting(key) for name, key in keys.items()}
    if not all(config.values()):
        raise RuntimeError('Falta configuración PostgreSQL.')
    return psycopg.connect(**config, row_factory=dict_row, connect_timeout=5,
                          application_name='Go2Win API', options='-c timezone=UTC')
