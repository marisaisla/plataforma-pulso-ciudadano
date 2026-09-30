"""Autenticación local: contraseñas scrypt y sesiones opacas revocables."""
import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from contextlib import closing

from services.database import connection
from services import development_access as development

SESSION_SECONDS = 8 * 60 * 60


def initialize_auth():
    with closing(connection()) as conn, conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS web_accounts (
                worker_id INTEGER PRIMARY KEY REFERENCES field_workers(id),
                username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
                must_change INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS web_sessions (
                token_hash TEXT PRIMARY KEY, worker_id INTEGER NOT NULL REFERENCES web_accounts(worker_id),
                expires_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS web_login_attempts (
                login_hash TEXT PRIMARY KEY, failures INTEGER NOT NULL, locked_until INTEGER NOT NULL,
                updated_at INTEGER NOT NULL);
        ''')
        columns = {r['name'] for r in conn.execute('PRAGMA table_info(web_sessions)')}
        if 'development_instance' not in columns:
            conn.execute('ALTER TABLE web_sessions ADD COLUMN development_instance TEXT')
        if not development.enabled():
            conn.execute('DELETE FROM web_sessions WHERE development_instance IS NOT NULL')
        else:
            conn.execute('DELETE FROM web_sessions WHERE development_instance IS NOT NULL '
                         'AND development_instance<>?', (development.INSTANCE,))


def username_key(username):
    value = username.strip().lower()
    if not re.fullmatch(r'[a-z0-9._-]{3,64}', value):
        raise ValueError('El usuario debe tener entre 3 y 64 letras sin acentos, números, puntos, guiones o guiones bajos.')
    return value


def hash_password(password):
    if not 12 <= len(password) <= 128:
        raise ValueError('La contraseña debe tener entre 12 y 128 caracteres.')
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=131072, r=8, p=1, maxmem=256*1024*1024)
    return f'scrypt${salt.hex()}${derived.hex()}'


def verify_password(password, encoded):
    if not isinstance(password, str) or len(password) > 128:
        return False
    try:
        scheme, salt, digest = encoded.split('$')
        if scheme != 'scrypt':
            return False
        derived = hashlib.scrypt(password.encode('utf-8'), salt=bytes.fromhex(salt), n=131072, r=8, p=1, maxmem=256*1024*1024)
        return hmac.compare_digest(derived.hex(), digest)
    except (ValueError, TypeError):
        return False


def token_hash(token):
    return hashlib.sha256((token or '').encode()).hexdigest()


def current_user(token, conn=None):
    if conn is None:
        with closing(connection()) as db:
            return current_user(token, db)
    row = conn.execute('''SELECT w.*, a.username, a.must_change, s.development_instance FROM web_sessions s
        JOIN web_accounts a ON a.worker_id=s.worker_id JOIN field_workers w ON w.id=a.worker_id
        WHERE s.token_hash=? AND s.expires_at>? AND w.active=1''', (token_hash(token), int(time.time()))).fetchone()
    if row is None:
        return None
    user = dict(row)
    if user['development_instance'] is not None:
        if user['development_instance'] != development.INSTANCE or not development.allowed():
            return None
        # Omitir el cambio temporal solo en esta sesión; conservar la cuenta original.
        user['must_change'] = 0
    return user


def development_accounts():
    if not development.allowed():
        return []
    with closing(connection()) as conn:
        return [dict(r) for r in conn.execute('SELECT w.id,w.name,w.role_key,a.username '
            'FROM field_workers w JOIN web_accounts a ON a.worker_id=w.id '
            'WHERE w.active=1 ORDER BY w.name,w.id')]


def login_development(worker_id):
    if not development.allowed():
        raise PermissionError('El acceso de desarrollo requiere configuración activa y acceso local.')
    with closing(connection()) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        if conn.execute('SELECT 1 FROM web_accounts a JOIN field_workers w ON w.id=a.worker_id '
                        'WHERE w.id=? AND w.active=1', (worker_id,)).fetchone() is None:
            raise ValueError('Selecciona una cuenta activa con acceso web.')
        token = secrets.token_urlsafe(32)
        conn.execute('INSERT INTO web_sessions (token_hash,worker_id,expires_at,development_instance) '
                     'VALUES (?,?,?,?)', (token_hash(token), worker_id, int(time.time())+SESSION_SECONDS,
                                         development.INSTANCE))
        return token


def require_user(token, conn, admin=False):
    user = current_user(token, conn)
    if user is None or user['must_change'] or (admin and user['role_key'] != 'administrator'):
        raise PermissionError('Tu sesión no tiene autorización. Inicia sesión nuevamente.')
    return user


def login(username, password):
    try:
        username = username_key(username)
    except ValueError:
        return None
    now = int(time.time())
    key = token_hash(username)
    with closing(connection()) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT a.*, w.active FROM web_accounts a JOIN field_workers w ON w.id=a.worker_id '
                           'WHERE a.username=?', (username,)).fetchone()
        dummy = 'scrypt$' + '00'*16 + '$' + '00'*64
        valid = verify_password(password, row['password_hash'] if row else dummy)
        attempt = conn.execute('SELECT * FROM web_login_attempts WHERE login_hash=?', (key,)).fetchone()
        if attempt and attempt['locked_until'] > now:
            return None
        if not row or not row['active'] or not valid:
            failures = (attempt['failures'] if attempt and now-attempt['updated_at'] < 900 else 0) + 1
            lock = now + 300 if failures >= 5 else 0
            conn.execute('INSERT OR REPLACE INTO web_login_attempts VALUES (?,?,?,?)',
                         (key, 0 if lock else failures, lock, now))
            return None
        conn.execute('DELETE FROM web_login_attempts WHERE login_hash=? OR updated_at<?', (key, now-86400))
        conn.execute('DELETE FROM web_sessions WHERE expires_at<=?', (now,))
        token = secrets.token_urlsafe(32)
        conn.execute('INSERT INTO web_sessions (token_hash,worker_id,expires_at) VALUES (?,?,?)',
                     (token_hash(token), row['worker_id'], now+SESSION_SECONDS))
        return token


def logout(token):
    with closing(connection()) as conn, conn:
        conn.execute('DELETE FROM web_sessions WHERE token_hash=?', (token_hash(token),))


def has_accounts():
    with closing(connection()) as conn:
        return conn.execute('SELECT 1 FROM web_accounts LIMIT 1').fetchone() is not None


def bootstrap_admin(name, username, password):
    """Solo desde la herramienta local de primer acceso; nunca desde el formulario público."""
    username = username_key(username)
    hashed = hash_password(password)
    if not name.strip() or len(name.strip()) > 120:
        raise ValueError('Escribe un nombre de hasta 120 caracteres.')
    with closing(connection()) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        if conn.execute('SELECT 1 FROM web_accounts LIMIT 1').fetchone():
            raise ValueError('El primer acceso ya fue configurado. Usa una cuenta administradora.')
        wid = conn.execute("INSERT INTO field_workers (name,team,active,created_at,role_key) VALUES (?,'',1,?,'administrator')",
                           (name.strip(), int(time.time()))).lastrowid
        conn.execute('INSERT INTO web_accounts VALUES (?,?,?,0)', (wid, username, hashed))
        return wid


def set_account(token, worker_id, username, password):
    username = username_key(username)
    hashed = hash_password(password)
    with closing(connection()) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        require_user(token, conn, admin=True)
        if conn.execute('SELECT 1 FROM field_workers WHERE id=? AND active=1', (worker_id,)).fetchone() is None:
            raise ValueError('El trabajador debe existir y estar activo.')
        try:
            conn.execute('''INSERT INTO web_accounts VALUES (?,?,?,1) ON CONFLICT(worker_id)
                DO UPDATE SET username=excluded.username,password_hash=excluded.password_hash,must_change=1''',
                         (worker_id, username, hashed))
        except sqlite3.IntegrityError:
            raise ValueError('Ese nombre de usuario ya está en uso.') from None
        conn.execute('DELETE FROM web_sessions WHERE worker_id=?', (worker_id,))
        conn.execute('DELETE FROM web_login_attempts WHERE login_hash=?', (token_hash(username),))


def change_password(token, old_password, new_password):
    hashed = hash_password(new_password)
    with closing(connection()) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        user = current_user(token, conn)
        if user is None:
            raise PermissionError('La sesión venció.')
        account = conn.execute('SELECT password_hash FROM web_accounts WHERE worker_id=?', (user['id'],)).fetchone()
        if not verify_password(old_password, account['password_hash']):
            raise ValueError('La contraseña actual no coincide.')
        if old_password == new_password:
            raise ValueError('Elige una contraseña diferente de la anterior.')
        conn.execute('UPDATE web_accounts SET password_hash=?,must_change=0 WHERE worker_id=?', (hashed, user['id']))
        conn.execute('DELETE FROM web_sessions WHERE worker_id=?', (user['id'],))


def protect_last_admin(conn, worker_id, *, role=None, active=None):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='web_accounts'").fetchone():
        return
    row = conn.execute('SELECT w.* FROM field_workers w JOIN web_accounts a ON a.worker_id=w.id WHERE w.id=?', (worker_id,)).fetchone()
    if row and row['active'] and row['role_key'] == 'administrator' and (role not in {None,'administrator'} or active is False):
        others = conn.execute("SELECT 1 FROM field_workers w JOIN web_accounts a ON a.worker_id=w.id "
                              "WHERE w.id<>? AND w.active=1 AND w.role_key='administrator'", (worker_id,)).fetchone()
        if not others:
            raise ValueError('Crea otro administrador con acceso web antes de desactivar o cambiar el rol del último administrador.')


def revoke_worker_sessions(conn, worker_id):
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='web_sessions'").fetchone():
        conn.execute('DELETE FROM web_sessions WHERE worker_id=?', (worker_id,))
