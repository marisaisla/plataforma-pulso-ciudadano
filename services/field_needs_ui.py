"""Consulta de necesidades con filtros y autorización de backend."""
import streamlit as st
from services.field_needs import catalog
from services.web_auth_ui import session_token


def render_needs():
    st.subheader('Necesidades territoriales')
    st.caption('Capturadas desde /necesidad; consulta por campaña y territorio autorizado.')
    st.button('Actualizar necesidades', key='refresh_needs')
    try:
        rows = catalog(session_token())
    except PermissionError as exc:
        st.error(str(exc))
        return
    for key,label in [('campaign','Campaña'),('state','Estado'),('municipality','Municipio'),('electoral_section','Sección')]:
        options = sorted({r[key] for r in rows})
        value = st.selectbox(label, ['Todas'] + options, key=f'needs_{key}')
        if value != 'Todas':
            rows = [r for r in rows if r[key] == value]
    search = st.text_input('Buscar en las necesidades',key='needs_search').strip().casefold()
    if search:
        rows = [r for r in rows if search in r['description'].casefold()]
    st.caption(f'{len(rows)} necesidades visibles')
    if not rows:
        st.info('No hay necesidades visibles con estos filtros.')
        return
    st.dataframe([{'Folio': f"N-{r['id']:06d}",'Campaña':r['campaign'],'Estado':r['state'],
        'Municipio':r['municipality'],'Sección':r['electoral_section'],'Origen':r['origin'],
        'Necesidad':r['description'],'Registró':r['registered_by'],'Fecha UTC':r['created_at']} for r in rows],
        hide_index=True,width='stretch')
    for r in rows:
        with st.expander(f"N-{r['id']:06d} · {r['municipality']} · sección {r['electoral_section']}"):
            st.text(r['description'])
            st.caption(f"{r['campaign']} · {r['origin']} · {r['registered_by']} · {r['created_at']} UTC")
