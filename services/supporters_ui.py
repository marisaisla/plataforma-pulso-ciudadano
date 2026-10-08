"""Catálogo filtrado por sesión, rol y territorio."""
import streamlit as st
from services.supporters import catalog
from services.web_auth_ui import session_token


def render_supporters():
    st.subheader('Catálogo de simpatizantes')
    st.caption('Registrados desde /simpatizante. La autorización para recibir información se conserva por separado.')
    try:
        rows = catalog(session_token())
    except PermissionError as exc:
        st.error(str(exc))
        return
    search = st.text_input('Buscar por nombre, teléfono o clave de elector', key='supporter_search').strip().casefold()
    contact_only = st.checkbox('Solo quienes autorizaron recibir información', key='supporter_contact_only')
    rows = [r for r in rows if (not contact_only or r['messaging_consent']) and
            (not search or any(search in r[k].casefold() for k in ('name','phone','voter_key')))]
    st.caption(f'{len(rows)} registros visibles')
    if not rows:
        st.info('No hay simpatizantes visibles con estos filtros.')
        return
    st.dataframe([{'Folio': f"S-{r['id']:06d}", 'Nombre': r['name'], 'Teléfono': r['phone'],
        'Clave de elector': r['voter_key'], 'Campaña': r['campaign'], 'Estado': r['state'],
        'Municipio': r['municipality'], 'Sección': r['electoral_section'],
        'Autoriza información': 'Sí' if r['messaging_consent'] else 'No',
        'Registró': r['registered_by'], 'Fecha UTC': r['created_at']} for r in rows],
        hide_index=True, width='stretch')
