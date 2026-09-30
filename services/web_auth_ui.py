"""Pantalla de acceso y controles de sesión compartidos."""
from pathlib import Path

import streamlit as st
from services import web_auth as auth
from services.field_permissions import ROLE_LABELS


def session_token():
    return st.session_state.get('_web_token', '')


def clear_session():
    st.session_state.clear()


def require_admin():
    user = auth.current_user(session_token())
    if user is None or user['must_change'] or user['role_key'] != 'administrator':
        st.error('Necesitas una sesión de administrador para abrir esta pantalla.')
        st.stop()
    return user


def password_form():
    with st.form('change_web_password', clear_on_submit=True):
        old = st.text_input('Contraseña actual', type='password')
        new = st.text_input('Nueva contraseña', type='password')
        confirmation = st.text_input('Repite la nueva contraseña', type='password')
        if st.form_submit_button('Cambiar contraseña'):
            try:
                if new != confirmation:
                    raise ValueError('Las contraseñas no coinciden.')
                auth.change_password(session_token(), old, new)
                clear_session()
                st.session_state['_login_notice'] = 'Contraseña actualizada. Inicia sesión con la nueva contraseña.'
                st.rerun()
            except (ValueError, PermissionError) as exc:
                st.error(str(exc))


def require_login():
    if auth.development.enabled():
        if auth.development.allowed():
            st.warning('Modo de desarrollo: acceso sin contraseña. Los roles y permisos siguen activos. '
                       'Los cambios se guardan en la base de datos actual.')
        else:
            st.info('Modo de desarrollo bloqueado: requiere ejecutar Go2Win con '
                    '--server.address 127.0.0.1 y abrirlo desde localhost, sin proxy. '
                    'Puedes iniciar sesión normalmente.')
    user = auth.current_user(session_token())
    if user is None:
        # Elimina resultados y selección de páginas de la sesión anterior.
        notice = st.session_state.get('_login_notice')
        if session_token():
            clear_session()
        _, center, _ = st.columns([1, 1.4, 1])
        with center:
            logo = Path(__file__).resolve().parent.parent / 'assets' / 'go2win_logo_official.webp'
            st.image(str(logo), width='stretch')
            st.markdown('## Iniciar sesión')
            st.caption('Tablero de mando · Acceso a tu espacio de trabajo')
            if notice:
                st.success(notice)
            if not auth.has_accounts():
                st.info('Configura el primer administrador desde PowerShell en esta computadora. '
                        'El registro de personal y Telegram se conserva.')
                st.code('.\\.venv\\Scripts\\python.exe scripts\\crear_admin.py', language='powershell')
                st.button('Ya configuré el administrador')
                st.stop()
            accounts = auth.development_accounts()
            if accounts:
                labels = {a['id']: f"{a['name']} · {ROLE_LABELS.get(a['role_key'], a['role_key'])} "
                          f"({a['username']})" for a in accounts}
                with st.form('development_login'):
                    worker_id = st.selectbox('Usuario de prueba', list(labels), format_func=labels.get)
                    if st.form_submit_button('Entrar sin contraseña'):
                        try:
                            token = auth.login_development(worker_id)
                            clear_session()
                            st.session_state['_web_token'] = token
                            st.rerun()
                        except (ValueError, PermissionError) as exc:
                            st.error(str(exc))
                st.caption('Para probar otro rol, cierra sesión y selecciona otra cuenta.')
            with st.form('web_login', clear_on_submit=True):
                username = st.text_input('Usuario', max_chars=64)
                password = st.text_input('Contraseña', type='password', max_chars=128)
                if st.form_submit_button('Iniciar sesión', type='primary'):
                    token = auth.login(username, password)
                    if token:
                        clear_session()
                        st.session_state['_web_token'] = token
                        st.rerun()
                    st.error('No se pudo iniciar sesión. Revisa tus datos o espera unos minutos si hubo varios intentos.')
            st.caption('Si necesitas acceso o restablecer tu contraseña, contacta al administrador.')
        st.stop()
    with st.sidebar:
        st.write(user['name'])
        st.caption(ROLE_LABELS.get(user['role_key'], 'Sin rol'))
        if st.button('Cerrar sesión'):
            auth.logout(session_token())
            clear_session()
            st.rerun()
        if not user['must_change']:
            with st.expander('Cambiar mi contraseña'):
                password_form()
    if user['must_change']:
        st.title('Define tu contraseña personal')
        st.info('Cambia la contraseña temporal antes de entrar a Go2Win. Usa entre 12 y 128 caracteres.')
        password_form()
        st.stop()
    return user


def render_web_account(worker):
    st.markdown('### Acceso a Go2Win')
    st.caption('Crear o restablecer una contraseña cierra las sesiones de esa persona. '
               'Deberá cambiar la contraseña temporal al ingresar. Su vínculo con Telegram se conserva.')
    with st.form(f"web_account_{worker['id']}", clear_on_submit=True):
        username = st.text_input('Usuario de acceso', max_chars=64)
        password = st.text_input('Contraseña temporal', type='password', max_chars=128)
        confirmation = st.text_input('Repite la contraseña temporal', type='password', max_chars=128)
        if st.form_submit_button('Crear o restablecer acceso web'):
            try:
                if password != confirmation:
                    raise ValueError('Las contraseñas no coinciden.')
                auth.set_account(session_token(), worker['id'], username, password)
                st.success('Acceso guardado. Entrega las credenciales a esa persona por un canal privado.')
            except (ValueError, PermissionError) as exc:
                st.error(str(exc))
