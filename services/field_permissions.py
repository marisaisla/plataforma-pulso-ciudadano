"""Permisos de operación de campo; el panel local sigue siendo una consola de confianza.

El backend debe obtener worker_id desde una identidad autenticada y el contexto de
la tarea desde la base. Nunca aceptar esos identificadores como prueba de identidad.
"""
import json
import time
from contextlib import closing, nullcontext

from services.database import connection


ROLE_LABELS = {
    'field': 'Personal de campo',
    'supervisor': 'Supervisor',
    'coordinator': 'Coordinador',
    'director': 'Director de campaña',
    'administrator': 'Administrador',
}
PERMISSION_LABELS = {
    'needs.submit': 'Registrar necesidades territoriales',
    'needs.view': 'Consultar necesidades territoriales',
    'supporters.submit': 'Registrar simpatizantes',
    'supporters.view': 'Consultar catálogo de simpatizantes',
    'tasks.view': 'Consultar tareas',
    'tasks.confirm': 'Confirmar recepción',
    'reports.submit': 'Enviar avances',
    'reports.view': 'Consultar reportes y resultados',
    'evidence.submit': 'Enviar evidencias',
    'incidents.submit': 'Reportar incidencias',
    'reports.review': 'Validar o solicitar correcciones',
    'tasks.assign': 'Asignar tareas',
    'incidents.manage': 'Atender incidencias',
    'priorities.manage': 'Definir prioridades',
    'users.manage': 'Administrar usuarios',
    'roles.manage': 'Administrar roles y alcances',
    'settings.manage': 'Administrar configuración',
}
OWN = {p: 'own' for p in ('tasks.view', 'tasks.confirm', 'reports.submit', 'reports.view', 'evidence.submit', 'incidents.submit', 'supporters.submit', 'supporters.view')}
ROLE_GRANTS = {
    'field': {**OWN, 'needs.submit': 'own', 'needs.view': 'own'},
    'supervisor': {**OWN, 'supporters.view': 'team', 'tasks.view': 'team', 'reports.view': 'team', 'reports.review': 'team', 'incidents.manage': 'team'},
    'coordinator': {**OWN, 'tasks.view': 'team', 'reports.view': 'team', 'reports.review': 'team',
                    'tasks.assign': 'team', 'incidents.manage': 'team', 'supporters.view': 'team', 'needs.view': 'campaign'},
    'director': {'tasks.view': 'campaign', 'reports.view': 'campaign', 'priorities.manage': 'campaign', 'supporters.view': 'campaign', 'needs.view': 'campaign'},
    'administrator': {p: 'all' for p in PERMISSION_LABELS},
}
SCOPE_LABELS = {'own': 'Propias', 'team': 'Equipo a cargo', 'campaign': 'Campaña autorizada', 'all': 'Toda la operación'}


def initialize_permissions(conn):
    """Migración aditiva y repetible dentro de la transacción de inicialización."""
    statements = [
        'CREATE TABLE IF NOT EXISTS field_roles (key TEXT PRIMARY KEY, label TEXT NOT NULL)',
        'CREATE TABLE IF NOT EXISTS field_permissions (key TEXT PRIMARY KEY, label TEXT NOT NULL)',
        '''CREATE TABLE IF NOT EXISTS field_role_permissions (
            role_key TEXT NOT NULL REFERENCES field_roles(key),
            permission_key TEXT NOT NULL REFERENCES field_permissions(key),
            scope TEXT NOT NULL CHECK(scope IN ('own','team','campaign','all')),
            PRIMARY KEY(role_key, permission_key))''',
        '''CREATE TABLE IF NOT EXISTS field_worker_scopes (
            worker_id INTEGER NOT NULL REFERENCES field_workers(id),
            profile_id INTEGER NOT NULL REFERENCES profiles(id),
            state TEXT NOT NULL DEFAULT '', municipality TEXT NOT NULL DEFAULT '',
            CHECK(municipality = '' OR state != ''),
            PRIMARY KEY(worker_id, profile_id, state, municipality))''',
        '''CREATE TABLE IF NOT EXISTS field_access_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL REFERENCES field_workers(id),
            action TEXT NOT NULL, details TEXT NOT NULL,
            actor TEXT NOT NULL DEFAULT 'local_console', created_at INTEGER NOT NULL)''',
    ]
    for sql in statements:
        conn.execute(sql)
    conn.executemany('INSERT OR IGNORE INTO field_roles VALUES (?, ?)', ROLE_LABELS.items())
    conn.executemany('INSERT OR IGNORE INTO field_permissions VALUES (?, ?)', PERMISSION_LABELS.items())
    for role, grants in ROLE_GRANTS.items():
        conn.executemany('INSERT OR IGNORE INTO field_role_permissions VALUES (?, ?, ?)',
                         [(role, p, scope) for p, scope in grants.items()])
    columns = {r[1] for r in conn.execute('PRAGMA table_info(field_workers)')}
    if 'role_key' not in columns:
        # SQLite no admite ADD COLUMN con FK y DEFAULT no nulo: validar rol mediante triggers.
        conn.execute("ALTER TABLE field_workers ADD COLUMN role_key TEXT NOT NULL DEFAULT 'field'")
    if 'supervisor_id' not in columns:
        conn.execute('ALTER TABLE field_workers ADD COLUMN supervisor_id INTEGER REFERENCES field_workers(id)')
    for operation in ('INSERT', 'UPDATE'):
        conn.execute(f'''CREATE TRIGGER IF NOT EXISTS field_workers_role_{operation.lower()}
            BEFORE {operation} ON field_workers
            WHEN NOT EXISTS (SELECT 1 FROM field_roles WHERE key = NEW.role_key)
            BEGIN SELECT RAISE(ABORT, 'Rol desconocido'); END''')


def audit(conn, worker_id, action, details):
    conn.execute('INSERT INTO field_access_audit (worker_id, action, details, created_at) VALUES (?, ?, ?, ?)',
                 (worker_id, action, json.dumps(details, ensure_ascii=False), int(time.time())))


def save_access(worker_id, role_key, team='', supervisor_id=None):
    """Administración exclusiva de la consola local; no exponer como endpoint anónimo."""
    if role_key not in ROLE_LABELS or len(team.strip()) > 120:
        raise ValueError('Rol o equipo inválido.')
    with closing(connection()) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        current = conn.execute('SELECT * FROM field_workers WHERE id = ?', (worker_id,)).fetchone()
        if current is None:
            raise ValueError('No existe el trabajador.')
        from services.web_auth import protect_last_admin
        protect_last_admin(conn, worker_id, role=role_key)
        if supervisor_id is not None:
            manager = conn.execute('SELECT * FROM field_workers WHERE id = ?', (supervisor_id,)).fetchone()
            if (worker_id == supervisor_id or manager is None or not manager['active']
                    or manager['role_key'] not in {'supervisor', 'coordinator'}):
                raise ValueError('Selecciona un supervisor o coordinador activo distinto del trabajador.')
            if not team.strip() or team.strip().casefold() != manager['team'].strip().casefold():
                raise ValueError('El trabajador y su supervisor deben pertenecer al mismo equipo.')
            ancestor = supervisor_id
            seen = {worker_id}
            while ancestor is not None:
                if ancestor in seen:
                    raise ValueError('La asignación produciría un ciclo de supervisión.')
                seen.add(ancestor)
                row = conn.execute('SELECT supervisor_id FROM field_workers WHERE id = ?', (ancestor,)).fetchone()
                ancestor = row['supervisor_id'] if row else None
        new = {'role_key': role_key, 'team': team.strip(), 'supervisor_id': supervisor_id}
        old = {key: current[key] for key in new}
        if new != old:
            from services.web_auth import revoke_worker_sessions
            revoke_worker_sessions(conn, worker_id)
            conn.execute('UPDATE field_workers SET role_key = ?, team = ?, supervisor_id = ? WHERE id = ?',
                         (role_key, team.strip(), supervisor_id, worker_id))
            audit(conn, worker_id, 'access_changed', {'before': old, 'after': new})


def list_scopes(worker_id):
    with closing(connection()) as conn:
        return [dict(r) for r in conn.execute('SELECT * FROM field_worker_scopes WHERE worker_id = ? '
                                              'ORDER BY profile_id, state, municipality', (worker_id,))]


def add_scope(worker_id, profile_id, state='', municipality=''):
    state, municipality = state.strip(), municipality.strip()
    if (municipality and not state) or max(len(state), len(municipality)) > 120:
        raise ValueError('Selecciona estado antes de municipio.')
    with closing(connection()) as conn, conn:
        if conn.execute('SELECT 1 FROM profiles WHERE id = ?', (profile_id,)).fetchone() is None:
            raise ValueError('No existe el perfil/campaña.')
        if conn.execute('SELECT 1 FROM field_workers WHERE id = ?', (worker_id,)).fetchone() is None:
            raise ValueError('No existe el trabajador.')
        changed = conn.execute('INSERT OR IGNORE INTO field_worker_scopes VALUES (?, ?, ?, ?)',
                               (worker_id, profile_id, state, municipality)).rowcount
        if changed:
            audit(conn, worker_id, 'scope_added', {'profile_id': profile_id, 'state': state, 'municipality': municipality})


def remove_scope(worker_id, profile_id, state='', municipality=''):
    with closing(connection()) as conn, conn:
        changed = conn.execute('DELETE FROM field_worker_scopes WHERE worker_id = ? AND profile_id = ? '
                               'AND state = ? AND municipality = ?', (worker_id, profile_id, state, municipality)).rowcount
        if changed:
            audit(conn, worker_id, 'scope_removed', {'profile_id': profile_id, 'state': state, 'municipality': municipality})


def _matches_scope(conn, worker_id, profile_id, state, municipality):
    if profile_id is None:
        return False
    return conn.execute('SELECT 1 FROM field_worker_scopes WHERE worker_id = ? AND profile_id = ? '
                        "AND (state = '' OR state = ?) AND (municipality = '' OR municipality = ?)",
                        (worker_id, profile_id, state, municipality)).fetchone() is not None


def can_access(worker_id, permission, *, profile_id=None, state='', municipality='', assigned_worker_id=None, conn=None):
    """Decisión por usuario activo, permiso, campaña, territorio y responsable real.

Preparada para el servicio de tareas; no sustituye autenticación ni filtra SQL por sí sola.
"""
    if permission not in PERMISSION_LABELS:
        return False
    with (closing(connection()) if conn is None else nullcontext(conn)) as conn:
        worker = conn.execute('SELECT * FROM field_workers WHERE id = ? AND active = 1', (worker_id,)).fetchone()
        if worker is None:
            return False
        grant = conn.execute('SELECT scope FROM field_role_permissions WHERE role_key = ? AND permission_key = ?',
                             (worker['role_key'], permission)).fetchone()
        if grant is None:
            return False
        scope = grant['scope']
        if scope == 'all':
            return True
        if not _matches_scope(conn, worker_id, profile_id, state, municipality):
            return False
        if scope == 'campaign':
            return True
        if scope == 'own':
            return assigned_worker_id == worker_id
        if assigned_worker_id is None:
            # Coordinación necesita ver la bolsa sin asignar de su ámbito.
            # Asignar sigue comprobando el equipo y alcance del destinatario.
            return worker['role_key'] == 'coordinator' and permission == 'tasks.view'
        if assigned_worker_id == worker_id:
            # Nadie valida su propio reporte, aunque pueda consultar su tarea.
            return permission in {'tasks.view', 'reports.view', 'tasks.assign', 'incidents.manage', 'supporters.view', 'supporters.submit'}
        owner = conn.execute('SELECT * FROM field_workers WHERE id = ? AND active = 1', (assigned_worker_id,)).fetchone()
        if (owner is None or not worker['team'].strip()
                or worker['team'].strip().casefold() != owner['team'].strip().casefold()
                or not _matches_scope(conn, owner['id'], profile_id, state, municipality)):
            return False
        if worker['role_key'] == 'supervisor':
            return owner['role_key'] == 'field' and owner['supervisor_id'] == worker_id
        return worker['role_key'] == 'coordinator' and owner['role_key'] in {'field', 'supervisor'}


def require_access(worker_id, permission, **context):
    if not can_access(worker_id, permission, **context):
        raise PermissionError('No tienes permiso para realizar esta acción en ese ámbito.')


def describe_access(conn, worker):
    grants = conn.execute('SELECT permission_key, scope FROM field_role_permissions WHERE role_key = ?',
                          (worker['role_key'],)).fetchall()
    lines = [f"Rol: {ROLE_LABELS.get(worker['role_key'], 'Sin rol válido')}", f"Equipo: {worker['team'] or 'Sin asignar'}"]
    if worker['role_key'] == 'administrator':
        lines.append('Alcance: toda la operación.')
    else:
        scopes = conn.execute('SELECT s.*, p.name FROM field_worker_scopes s JOIN profiles p ON p.id = s.profile_id '
                              'WHERE worker_id = ?', (worker['id'],)).fetchall()
        lines.append('Alcances: ' + ('; '.join(f"{r['name']} / {r['state'] or 'todos los estados'} / "
                                             f"{r['municipality'] or 'todos los municipios'}" for r in scopes)
                                    if scopes else 'Sin asignar; solicita a coordinación tu campaña y territorio.'))
    lines.append('Permisos del rol:\n' + '\n'.join(f"• {PERMISSION_LABELS[r['permission_key']]}: {SCOPE_LABELS[r['scope']]}" for r in grants))
    lines.append('Usa /mis_tareas para consultar actividades, /reportar para enviar avances y /mis_reportes para ver revisiones.')
    return '\n'.join(lines)
