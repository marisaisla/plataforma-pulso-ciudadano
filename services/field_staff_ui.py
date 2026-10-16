"""Administración de usuarios, roles, territorios y acceso al sistema."""
import streamlit as st
from services.field_api import (
    create_worker, list_workers, set_worker_active,
    require_admin,save_access,list_scopes,add_scope,remove_scope,profile_list,territories,roles,
)
from services.web_auth_ui import render_web_account
from services.field_permissions import (
    ROLE_LABELS, PERMISSION_LABELS, SCOPE_LABELS,
)


def _render_user_administration():
    require_admin()
    st.caption('Registra al personal y configura roles, equipos, territorios y acceso al sistema. La vinculación y las capturas del bot se encuentran en Operación de Telegram.')
    st.info('Administración de usuarios. Los roles y alcances se aplican al panel operativo y a Telegram.')
    with st.expander('Consultar roles y permisos'):
        role_grants={role:{} for role in ROLE_LABELS}
        for grant in roles():
            if grant['permission_key']:
                role_grants.setdefault(grant['key'],{})[grant['permission_key']]=grant['scope']
        st.dataframe([{'Permiso': label, **{ROLE_LABELS[role]: SCOPE_LABELS.get(grants.get(key), 'Sin permiso')
                      for role, grants in role_grants.items()}} for key, label in PERMISSION_LABELS.items()],
                     hide_index=True, width='stretch')
        st.caption('Supervisor: personal de campo asignado directamente y del mismo equipo. '
                   'Coordinador: personal y supervisores de su equipo. Ambos necesitan alcance territorial. '
                   'Director: campañas y territorios autorizados. Administrador: toda la operación.')
    with st.form('new_field_worker', clear_on_submit=True):
        name = st.text_input('Nombre del trabajador', max_chars=120)
        team = st.text_input('Equipo (opcional)', max_chars=120)
        if st.form_submit_button('Registrar trabajador'):
            try:
                create_worker(name, team)
                st.success('Trabajador registrado. Selecciónalo abajo para configurar su acceso.')
            except ValueError as exc:
                st.error(str(exc))
    workers = list_workers()
    if not workers:
        st.info('Registra al primer trabajador para configurar su acceso.')
        return
    st.button('Actualizar usuarios')
    st.dataframe([{'Folio': w['id'], 'Nombre': w['name'], 'Equipo': w['team'],
                   'Rol': ROLE_LABELS.get(w['role_key'], 'Sin rol válido'),
                   'Acceso': 'Activo' if w['active'] else 'Desactivado'}
                  for w in workers], hide_index=True, width='stretch')
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
    profiles = profile_list()
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
        states = territories()['states']
        scope_state = st.selectbox('Estado autorizado', [''] + states,
                                   format_func=lambda s: s or 'Todos los estados', key=f'scope_state_{selected}')
        municipalities = territories(scope_state)['municipalities']
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
    if st.button('Desactivar acceso' if worker['active'] else 'Reactivar acceso'):
        try:
            set_worker_active(selected, not worker['active'])
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    render_web_account(worker)


# Compatibilidad con herramientas que importan el render anterior.
def render_user_administration():
    from services.field_api import APIError
    try: _render_user_administration()
    except APIError as exc: st.error(str(exc))


render_field_staff = render_user_administration
