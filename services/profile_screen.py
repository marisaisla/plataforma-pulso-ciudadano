"""Pantalla 01: toda consulta y guardado de perfiles/elección usa HTTP."""
from datetime import date
import pandas as pd
import streamlit as st
from services.profiles_api import request,ProfileAPIError
from services.web_auth_ui import session_token


def render_profiles():
    token=session_token()
    try:
        metadata=request('GET','/profiles/options',token)
        profiles=request('GET','/profiles',token)
        positions=request('GET','/profile-positions',token)
    except ProfileAPIError as exc:
        st.error(str(exc))
        if st.button('Reintentar conexión con API'): st.rerun()
        return
    notice=st.session_state.pop('_profile_api_notice',None)
    if notice: st.success(notice)
    st.subheader('Perfiles')
    with st.form('new_profile',clear_on_submit=True):
        name=st.text_input('Nombre de la persona, institución o tema',max_chars=300)
        actor_type=st.selectbox('Tipo de perfil',metadata['actor_types'])
        notes=st.text_area('Notas opcionales',max_chars=20000)
        if st.form_submit_button('Guardar perfil'):
            if not name.strip(): st.error('Escribe un nombre para el perfil.')
            else:
                try:
                    request('POST','/profiles',token,{'name':name,'actor_type':actor_type,'notes':notes})
                    st.session_state['_profile_api_notice']='Perfil guardado.'
                    st.rerun()
                except ProfileAPIError as exc: st.error(str(exc))
    if profiles: st.dataframe(pd.DataFrame(profiles),width='stretch',hide_index=True)
    active_profiles={f"{p['name']} (#{p['id']})":p['id'] for p in profiles if p['active']}
    if active_profiles:
        st.markdown('#### Desactivar perfil')
        st.caption('Conserva los datos y el historial; el perfil deja de estar disponible para nuevas trayectorias y en los selectores de perfiles activos.')
        selected=st.selectbox('Perfil a desactivar',list(active_profiles),index=None,
                              placeholder='Selecciona el perfil',key='profile_to_deactivate')
        if st.button('Desactivar perfil',disabled=selected is None):
            try:
                result=request('PUT',f'/profiles/{active_profiles[selected]}/active',token,{'active':False})
                st.session_state['_profile_api_notice']=f"Perfil {result['name']} desactivado. Sus datos se conservaron."
                st.session_state.pop('profile_to_deactivate',None)
                st.rerun()
            except ProfileAPIError as exc: st.error(str(exc))
    st.subheader('Cargo, candidatura o condición')
    options={f"{p['name']} (#{p['id']})":p['id'] for p in profiles if p['active']}
    if not options: st.info('Primero crea un perfil.')
    else:
        with st.form('new_position',clear_on_submit=True):
            chosen=st.selectbox('Perfil',list(options))
            office=st.text_input('Cargo o candidatura',placeholder='Presidencia municipal',max_chars=300)
            condition=st.selectbox('Condición',metadata['conditions'])
            col1,col2=st.columns(2)
            starts_at=col1.date_input('Inicio',value=date.today())
            ends_at=col2.date_input('Fin estimado o real',value=None)
            party=st.text_input('Partido o coalición (opcional)',max_chars=300)
            if st.form_submit_button('Guardar trayectoria'):
                if not office.strip(): st.error('Indica el cargo o candidatura.')
                elif ends_at and ends_at<starts_at: st.error('La fecha final no puede ser anterior al inicio.')
                else:
                    try:
                        request('POST',f'/profiles/{options[chosen]}/positions',token,{
                            'office':office,'condition':condition,'starts_at':starts_at.isoformat(),
                            'ends_at':ends_at.isoformat() if ends_at else None,'party_or_coalition':party})
                        st.session_state['_profile_api_notice']='Trayectoria guardada.'
                        st.rerun()
                    except ProfileAPIError as exc: st.error(str(exc))
    if positions:
        columns={'profile_name':'perfil','office':'cargo','condition':'condicion','starts_at':'inicio',
                 'ends_at':'fin','party_or_coalition':'partido_coalicion'}
        frame=pd.DataFrame(positions)[list(columns)].rename(columns=columns)
        st.dataframe(frame,width='stretch',hide_index=True)
