"""Acceso de pruebas optativo, limitado a un servidor enlazado a loopback."""
import os
import secrets
from pathlib import Path
from urllib.parse import urlsplit

ENV_PATH = Path(__file__).resolve().parent.parent / '.env'
INSTANCE = secrets.token_hex(32)
KEY = 'GO2WIN_MODO_DESARROLLO'


def enabled():
    value = os.environ.get(KEY)
    if value is None:
        value = 'false'
        if ENV_PATH.is_file():
            for line in ENV_PATH.read_text(encoding='utf-8-sig').splitlines():
                key, separator, entry = line.strip().partition('=')
                if separator and key.strip() == KEY:
                    value = entry.split('#', 1)[0].strip().strip('\"\'')
    return value.strip().lower() == 'true'


def local_request():
    import streamlit as st
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    # No basta con un encabezado Host: el servidor debe escuchar solo en loopback.
    if st.get_option('server.address') not in {'127.0.0.1', '::1'}:
        return False
    if get_script_run_ctx(suppress_warning=True) is None:
        return False
    headers = st.context.headers
    if any(key.lower() == 'forwarded' or key.lower().startswith('x-forwarded-') for key in headers):
        return False
    try:
        return urlsplit('http://' + headers.get('Host', '')).hostname in {'localhost', '127.0.0.1', '::1'}
    except ValueError:
        return False


def allowed():
    return enabled() and local_request()
