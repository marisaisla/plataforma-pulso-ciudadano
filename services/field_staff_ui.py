"""Pantalla local de coordinación para el piloto de Telegram."""
import streamlit as st
from contextlib import closing
from services.field_staff import (
    initialize_staff, create_worker, list_workers, issue_code, set_worker_active, unlink_worker,
)
from services.database import connection
from services.web_auth_ui import require_admin, render_web_account
from services.field_permissions import (
    ROLE_LABELS, ROLE_GRANTS, PERMISSION_LABELS, SCOPE_LABELS,
    save_access, list_scopes, add_scope, remove_scope,
)


def query(sql, parameters=()):
    with closing(connection()) as conn:
        return [dict(row) for row in conn.execute(sql, parameters)]


def render_field_staff():
    require_admin()
    initialize_staff()
    st.caption('Registra al personal, configura su acceso y vincula Telegram. Asigna sus actividades desde Planes de acción.')
    st.info('Administración de usuarios. Los roles y alcances se aplican al panel operativo y a Telegram.')
    with st.expander('Consultar roles y permisos'):
        st.dataframe([{'Permiso': label, **{ROLE_LABELS[role]: SCOPE_LABELS.get(grants.get(key), 'Sin permiso')
                      for role, grants in ROLE_GRANTS.items()}} for key, label in PERMISSION_LABELS.items()],
                     hide_index=True, use_container_width=True)
        st.caption('Supervisor: personal de campo asignado directamente y del mismo equipo. '
                   'Coordinador: personal y supervisores de su equipo. Ambos necesitan alcance territorial. '
                   'Director: campañas y territorios autorizados. Administrador: toda la operación.')
    with st.form('new_field_worker', clear_on_submit=True):
        name = st.text_input('Nombre del trabajador', max_chars=120)
        team = st.text_input('Equipo (opcional)', max_chars=120)
        if st.form_submit_button('Registrar trabajador'):
            try:
                create_worker(name, team)
                st.success('Trabajador registrado. Selecciónalo abajo para generar su código.')
            except ValueError as exc:
                st.error(str(exc))
    workers = list_workers()
    if not workers:
        st.info('Registra al primer trabajador para iniciar la vinculación.')
        return
    st.button('Actualizar estado de vinculación')
    st.dataframe([{'Folio': w['id'], 'Nombre': w['name'], 'Equipo': w['team'],
                   'Rol': ROLE_LABELS.get(w['role_key'], 'Sin rol válido'),
                   'Acceso': 'Activo' if w['active'] else 'Desactivado',
                   'Telegram': 'Vinculado' if w['telegram_user_id'] is not None else 'Sin vincular'}
                  for w in workers], hide_index=True, use_container_width=True)
    selected = st.selectbox('Trabajador', [w['id'] for w in workers],
                            format_func=lambda wid: next(f"{w['name']} · #{wid}" for w in workers if w['id'] == wid))
    worker = next(w for w in workers if w['id'] == selected)
    with st.form(f'access_{selected}'):
        st.markdown('### Rol y equipo')
        role = st.selectbox('Rol', list(ROLE_LABELS), index=list(ROLE_LABELS).index(worker['role_key']),
                            format_func=ROLE_LABELS.get)
        team = st.text_input('Equipo asignado', value=worker['team'], max_chars=120)
        manager_options = [None] + [w['id'] for w in workers if w['id'] != selected and w['active']
                                    and w['role_key'] in {'supervisor', 'coordinator'}]
        # Mantener visible una referencia que dejó de ser válida, para corregirla explícitamente.
        if worker['supervisor_id'] is not None and worker['supervisor_id'] not in manager_options:
            manager_options.append(worker['supervisor_id'])
        manager = st.selectbox('Supervisor o coordinador responsable', manager_options,
                               index=manager_options.index(worker['supervisor_id']),
                               format_func=lambda wid: 'Sin asignar' if wid is None else
                               next((f"{w['name']} · #{wid}" for w in workers if w['id'] == wid), f'#{wid}'))
        if st.form_submit_button('Guardar rol y equipo'):
            try:
                save_access(selected, role, team, manager)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    st.markdown('### Campañas y territorios autorizados')
    profiles = query('SELECT id, name FROM profiles ORDER BY name')
    profile_names = {p['id']: p['name'] for p in profiles}
    scopes = list_scopes(selected)
    if worker['role_key'] == 'administrator':
        st.caption('Administrador tiene acceso a toda la operación. Los alcances guardados aplicarán si cambias su rol.')
    elif not scopes:
        st.warning('Sin alcance asignado: este usuario todavía no podrá operar tareas, aunque esté vinculado a Telegram.')
    for index, scope in enumerate(scopes):
        st.write(f"{profile_names.get(scope['profile_id'], scope['profile_id'])} · "
                 f"{scope['state'] or 'Todos los estados'} · {scope['municipality'] or 'Todos los municipios'}")
        if st.button('Retirar este alcance', key=f'remove_scope_{selected}_{index}'):
            remove_scope(selected, scope['profile_id'], scope['state'], scope['municipality'])
            st.rerun()
    if profiles:
        scope_profile = st.selectbox('Perfil / campaña', list(profile_names), format_func=profile_names.get,
                                     key=f'scope_profile_{selected}')
        states = [r['state'] for r in query("SELECT DISTINCT state FROM territories WHERE state IS NOT NULL AND state != '' ORDER BY state")]
        scope_state = st.selectbox('Estado autorizado', [''] + states,
                                   format_func=lambda s: s or 'Todos los estados', key=f'scope_state_{selected}')
        municipalities = [r['municipality'] for r in query("SELECT DISTINCT municipality FROM territories WHERE state = ? "
                                                           "AND municipality IS NOT NULL AND municipality != '' ORDER BY municipality", (scope_state,))]
        scope_municipality = st.selectbox('Municipio autorizado', [''] + municipalities,
                                          format_func=lambda m: m or 'Todos los municipios',
                                          key=f'scope_municipality_{selected}_{scope_state}', disabled=not scope_state)
        if st.button('Agregar alcance'):
            try:
                add_scope(selected, scope_profile, scope_state, scope_municipality)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    else:
        st.info('Registra un perfil en Go2Win para asignar un alcance.')
    st.caption('Un alcance para toda la campaña incluye los alcances más específicos. '
               'Retíralo si deseas restringir al usuario a un estado o municipio.')
    if worker['active'] and worker['telegram_user_id'] is None:
        if st.button('Generar código de activación'):
            try:
                code = issue_code(selected)
                st.code(f'/start {code}', language=None)
                st.info('Entrega este comando solo al trabajador seleccionado para que lo envíe al bot en privado. '
                        'Vence en 30 minutos y se usa una vez. Un código nuevo invalida el anterior. '
                        'Cópialo ahora: no se mostrará de nuevo al cambiar de pantalla.')
            except ValueError as exc:
                st.error(str(exc))
    if st.button('Desactivar acceso' if worker['active'] else 'Reactivar acceso'):
        try:
            set_worker_active(selected, not worker['active'])
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    if worker['telegram_user_id'] is not None:
        confirm = st.checkbox('Quiero retirar el vínculo con la cuenta actual', key=f'unlink_{selected}')
        if st.button('Desvincular Telegram', disabled=not confirm):
            unlink_worker(selected)
            st.rerun()
    render_web_account(worker)
