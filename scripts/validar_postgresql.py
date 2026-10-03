"""Validate migrated PostgreSQL without retaining test data or changing public sequences.

Run with --flujos to additionally exercise services using session-local temporary
copies of the schema (including constraints), all discarded by ROLLBACK.
No Telegram/network messages are sent. Never imports the application's app.py.
"""
import argparse
import ast
from contextlib import ExitStack
import json
from pathlib import Path
import re
import secrets
import sys
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from psycopg import sql as pgsql
from services import database
from services.postgres_backend import TOKENS, translate, validate_schema

ROOT = Path(__file__).resolve().parents[1]


def check_queries(conn):
    checked = 0
    failures = []
    paths = [ROOT / 'app.py', *sorted((ROOT / 'services').glob('*.py')),
             *sorted((ROOT / 'scripts').glob('*.py'))]
    for path in paths:
        if path.name in {'database.py', 'postgres_backend.py', 'exportar_postgresql.py',
                         'merge_transferred_database.py', 'test_message_analysis.py', 'validar_postgresql.py'}:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, 'id', '')
            arg = node.args[0]
            if name not in {'execute', 'executemany', 'query'} or not isinstance(arg, ast.Constant) or not isinstance(arg.value, str):
                continue
            sql = arg.value
            if not re.match(r'\s*(SELECT|INSERT|UPDATE|DELETE)\b', sql, re.I):
                continue
            count = sum(m.group() == '?' for m in TOKENS.finditer(sql))
            try:
                with conn.raw.transaction():
                    # EXPLAIN (without ANALYZE) does not execute the statement.
                    conn.raw.execute('EXPLAIN ' + translate(sql), (None,) * count)
                checked += 1
            except Exception as exc:
                failures.append(f'{path.relative_to(ROOT)}:{node.lineno}: {exc}')
    if failures:
        raise AssertionError('\n'.join(failures))
    print(f'Consultas estaticas verificadas con EXPLAIN: {checked}.')


class Borrowed:
    """Each service context uses a savepoint; only the test owns the outer transaction."""
    def __init__(self, conn):
        self.conn = conn

    def execute(self, *args):
        return self.conn.execute(*args)

    def executemany(self, *args):
        return self.conn.executemany(*args)

    def __enter__(self):
        self.transaction = self.conn.raw.transaction()
        self.transaction.__enter__()
        return self

    def __exit__(self, *args):
        return self.transaction.__exit__(*args)

    def close(self):
        pass


def check_flows(conn):
    from services import field_staff as staff, field_tasks as tasks, field_reports as reports
    from services import field_permissions as permissions, web_auth as auth, web_portal as portal

    # Verify privileges on the actual public table, using an explicit negative
    # key so its identity sequence is untouched. Always undo this probe.
    probe_id = -secrets.randbelow(2**60) - 1
    assert conn.execute('SELECT 1 FROM public.profiles WHERE id=?', (probe_id,)).fetchone() is None
    with conn.raw.transaction(force_rollback=True):
        row = conn.execute('INSERT INTO public.profiles (id,name,actor_type) VALUES (?,?,?) RETURNING id',
                           (probe_id, 'Prueba reversible PostgreSQL', 'Persona')).fetchone()
        assert row[0] == probe_id
        assert conn.execute('UPDATE public.profiles SET notes=? WHERE id=?', ('Temporal', probe_id)).rowcount == 1
        assert conn.execute('DELETE FROM public.profiles WHERE id=?', (probe_id,)).rowcount == 1
    assert conn.execute('SELECT 1 FROM public.profiles WHERE id=?', (probe_id,)).fetchone() is None

    tables = json.loads((ROOT / 'services/postgres_schema.json').read_text(encoding='utf-8'))
    # LIKE INCLUDING ALL copies identity definitions into separate temporary
    # sequences, but not foreign keys; restore those explicitly below.
    foreign_keys = conn.raw.execute("""SELECT t.relname,c.conname,pg_get_constraintdef(c.oid)
        FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid
        JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='public' AND c.contype='f'""").fetchall()
    for name in tables:
        conn.raw.execute(pgsql.SQL('CREATE TEMP TABLE {} (LIKE public.{} INCLUDING ALL) ON COMMIT DROP').format(
            pgsql.Identifier(name), pgsql.Identifier(name)))
    conn.raw.execute('SET LOCAL search_path=pg_temp,public')
    for table, name, definition in foreign_keys:
        conn.raw.execute(pgsql.SQL('ALTER TABLE pg_temp.{} ADD CONSTRAINT {} ').format(
            pgsql.Identifier(table), pgsql.Identifier(name)) + pgsql.SQL(definition.replace('REFERENCES public.', 'REFERENCES pg_temp.')))
    for name in ('field_roles', 'field_permissions', 'field_role_permissions'):
        conn.raw.execute(pgsql.SQL('INSERT INTO pg_temp.{} SELECT * FROM public.{}').format(
            pgsql.Identifier(name), pgsql.Identifier(name)))

    with ExitStack() as stack:
        for module in (database, staff, tasks, reports, permissions, auth, portal):
            stack.enter_context(patch.object(module, 'connection', lambda: Borrowed(conn)))
        profile = database.create_profile('Prueba temporal PostgreSQL', 'Persona', '')
        strategy = conn.execute('INSERT INTO territorial_strategies '
            '(profile_id,state,municipality,strategic_focus,objective,tactics) VALUES (?,?,?,?,?,?) RETURNING id',
            (profile, 'Sonora', 'Hermosillo', 'Prueba', 'Prueba', 'Prueba')).fetchone()[0]
        task = conn.execute('INSERT INTO territorial_action_plans '
            '(strategy_id,profile_id,state,municipality,activity_name) VALUES (?,?,?,?,?) RETURNING id',
            (strategy, profile, 'Sonora', 'Hermosillo', 'Actividad temporal')).fetchone()[0]
        password = 'Password temporal prueba 123!'
        admin_id = auth.bootstrap_admin('Administrador temporal', 'prueba_admin', password)
        admin = auth.login('prueba_admin', password)
        assert admin and auth.current_user(admin)['id'] == admin_id
        assert auth.login('prueba_admin', 'incorrecta') is None
        assert auth.login('prueba_admin', 'incorrecta') is None  # upsert attempts
        coordinator = staff.create_worker('Coordinador temporal', 'Pruebas')
        worker = staff.create_worker('Campo temporal', 'Pruebas')
        permissions.save_access(coordinator, 'coordinator', 'Pruebas')
        permissions.save_access(worker, 'field', 'Pruebas', coordinator)
        for wid, username in ((coordinator, 'prueba_coord'), (worker, 'prueba_campo')):
            permissions.add_scope(wid, profile, 'Sonora', 'Hermosillo')
            permissions.add_scope(wid, profile, 'Sonora', 'Hermosillo')  # ignore duplicates
            auth.set_account(admin, wid, username, password)
            token = auth.login(username, password)
            auth.change_password(token, password, password + ' nueva')
        coord_token = auth.login('prueba_coord', password + ' nueva')
        field_token = auth.login('prueba_campo', password + ' nueva')
        assert worker in [r['id'] for r in portal.assignment_candidates(coord_token, task)]
        tasks.assign_task_locally(task, worker, session_token=coord_token)
        assert portal.portal_data(field_token)[1][0]['id'] == task
        try:
            tasks.assign_task_locally(task, coordinator, session_token=field_token)
        except PermissionError:
            pass
        else:
            raise AssertionError('Campo no debe poder asignar tareas')
        user_id = 987654321
        message = {'from': {'id': user_id}, 'chat': {'id': user_id, 'type': 'private'}}
        code = staff.issue_code(worker)
        staff.telegram_reply({**message, 'text': '/start ' + code})
        generation = tasks.get_assignment(task)['generation']
        callback = {'id': 'temporal-confirm', 'from': message['from'], 'message': {'chat': message['chat']},
                    'data': f'taskconfirm:{task}:{generation}'}
        staff.telegram_callback(callback)
        assert tasks.get_assignment(task)['received_at']
        staff.telegram_callback({**callback, 'id': 'temporal-select', 'data': f'reportselect:{task}:{generation}'})
        report_message = {**message, 'text': 'Avance temporal con acentos: comunicación y 100%.',
                          'message_id': 1, 'date': int(time.time())}
        reply = staff.telegram_reply(report_message)
        assert reply == staff.telegram_reply(report_message)
        saved = reports.list_task_reports(task)
        assert len(saved) == 1 and saved[0]['status'] == 'pending'
        reports.review_report(saved[0]['id'], 'accepted', 'Validado temporalmente', session_token=coord_token)
        assert reports.list_task_reports(task)[0]['status'] == 'accepted'
        # Remote development sessions must survive initialization in this process.
        conn.execute('INSERT INTO web_sessions VALUES (?,?,?,?)', ('otra_instancia', worker, int(time.time()) + 600, 'remote'))
        auth.initialize_auth()
        assert conn.execute("SELECT 1 FROM web_sessions WHERE token_hash='otra_instancia'").fetchone()
        permissions.save_access(worker, 'field', 'Otro equipo')
        assert auth.current_user(field_token) is None
        try:
            permissions.save_access(admin_id, 'field')
        except ValueError:
            pass
        else:
            raise AssertionError('Debe proteger al ultimo administrador')
    print('Flujos comprobados: usuarios, sesiones, permisos, asignacion, Telegram simulado, reporte y revision.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--flujos', action='store_true')
    args = parser.parse_args()
    if not database.is_postgresql():
        raise SystemExit('Configura DB_BACKEND=postgresql; no se utilizara SQLite.')
    validate_schema()
    conn = database.connection()
    try:
        print('Conexion:', tuple(conn.execute('SELECT current_database(),current_user').fetchone()))
        check_queries(conn)
        if args.flujos:
            check_flows(conn)
    finally:
        conn.rollback()
        conn.close()
        print('ROLLBACK completado; las pruebas no conservan datos ni modifican secuencias publicas.')


if __name__ == '__main__':
    main()
