"""Primer administrador web. Las contraseñas se capturan ocultas y no se guardan en texto."""
import sys
from pathlib import Path
from getpass import getpass
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.database import initialize_database
from services.field_staff import initialize_staff
from services.web_auth import initialize_auth, has_accounts, bootstrap_admin


def main():
    initialize_database()
    initialize_staff()
    initialize_auth()
    if has_accounts():
        print('El primer acceso ya existe. Inicia sesión con la cuenta administradora.')
        return 1
    print('Crear administrador de Go2Win. Tu usuario de campo no se modifica.')
    name = input('Nombre del administrador: ').strip()
    username = input('Usuario de acceso: ').strip()
    password = getpass('Contraseña (12 a 128 caracteres): ')
    if password != getpass('Repite la contraseña: '):
        print('Las contraseñas no coinciden. No se creó la cuenta.')
        return 1
    try:
        bootstrap_admin(name, username, password)
    except ValueError as exc:
        print(exc)
        return 1
    print('Administrador creado. Regresa a Go2Win e inicia sesión.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        print('\nConfiguración cancelada.')
