"""Comprueba la conexión y las columnas requeridas sin escribir datos."""
from backend.database import connect


def main():
    # Solo lectura de las tablas reales. Nunca modifica trabajadores existentes.
    with connect() as conn:
        columns = conn.execute("SELECT table_name,column_name FROM information_schema.columns WHERE table_schema='public' AND table_name IN ('field_workers','field_activation_codes')").fetchall()
        required = {'field_workers': {'id','name','active','telegram_user_id','telegram_chat_id','linked_at','created_at'},
                    'field_activation_codes': {'code_hash','worker_id','expires_at','consumed_at'}}
        for table, expected in required.items():
            actual = {r['column_name'] for r in columns if r['table_name'] == table}
            assert expected <= actual, 'Faltan columnas: ' + table
        conn.execute('SELECT id FROM public.field_workers LIMIT 0')
        conn.execute('SELECT code_hash FROM public.field_activation_codes LIMIT 0')
    print('PostgreSQL: conexión y esquema de vinculación verificados (solo lectura).')


if __name__ == '__main__':
    main()
