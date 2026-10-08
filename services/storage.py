"""Portable file locations; credentials and SQLite remain machine-local."""
from pathlib import Path, PureWindowsPath
from services.settings import get_setting

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANAGED = ('data', 'output', 'assets/go2win_video')


def files_root() -> Path:
    value = get_setting('GO2WIN_FILES_ROOT').strip()
    if not value:
        return PROJECT_ROOT
    root = Path(value)
    if not root.is_absolute():
        raise ValueError('GO2WIN_FILES_ROOT debe ser una ruta absoluta o UNC.')
    return root


def storage_path(relative: str) -> Path:
    """Resolve a managed path without silently falling back to local copies."""
    value = relative.replace('\\', '/').strip('/')
    if '..' in value.split('/') or PureWindowsPath(relative).drive:
        raise ValueError('La ruta debe ser relativa y no contener ..')
    if not any(value == p or value.startswith(p + '/') for p in MANAGED):
        raise ValueError('Solo data, output y assets/go2win_video son compartidos.')
    return files_root() / value


def resolve_document_path(value: str) -> Path:
    """Read legacy project paths across machines without changing DB records.

    Unknown external absolute paths remain unchanged and must be migrated explicitly.
    """
    normalized = str(value).replace('\\', '/')
    if '..' in normalized.split('/'):
        raise ValueError('La ruta del documento no puede contener ..')
    # Current project and managed relative paths.
    prefix = PROJECT_ROOT.as_posix().rstrip('/') + '/'
    relative = normalized[len(prefix):] if normalized.casefold().startswith(prefix.casefold()) else normalized
    for base in MANAGED:
        if relative == base or relative.startswith(base + '/'):
            return storage_path(relative)
    # Previously registered absolute paths from another checkout/machine.
    if PureWindowsPath(normalized).is_absolute() or Path(normalized).is_absolute():
        for base in MANAGED:
            marker = '/' + base + '/'
            at = normalized.casefold().rfind(marker.casefold())
            if at >= 0:
                return storage_path(normalized[at + 1:])
        return Path(value)
    return PROJECT_ROOT / normalized
