"""Profile survey/dossier controls; HTTP only, with no local metric extraction."""
from urllib.parse import urlencode
import streamlit as st
from services.indicators_ui import request

KINDS={'internal_preference':'Preferencia interna','hypothetical_matchup':'Careo hipotético',
       'coalition_scenario':'Escenario de coalición','approval':'Aprobación de gestión',
       'party_preference':'Preferencia partidista','context':'Referencia cualitativa',
       'excluded':'Excluido del cálculo','unreviewed':'Pendiente de clasificación'}


def research_filters(token):
    st.caption('Selecciona el perfil del expediente. Estos filtros son independientes de los electorales e INEGI.')
    inactive=st.checkbox('Incluir perfiles inactivos',key='dash_research_inactive')
    profiles=request('GET','/profiles?'+urlencode(dict(active_only='false' if inactive else 'true')),token)
    labels={p['id']:p['name'] for p in profiles}
    if st.session_state.get('dash_research_profile') not in labels:
        st.session_state['dash_research_profile']=None
    profile=st.selectbox('Perfil para encuestas y expediente',[None]+list(labels),key='dash_research_profile',
        format_func=lambda p:'Selecciona un perfil' if p is None else f'{labels[p]} (#{p})')
    if profile is None:return None
    if st.button('Consultar encuestas y expediente',key='dash_research_query'):
        st.session_state.pop('_dash_research',None)
        result=request('GET','/indicators/dashboard/research?'+urlencode(dict(profile_id=profile)),token)
        st.session_state['_dash_research']=(profile,result)
    saved=st.session_state.get('_dash_research')
    if not saved or saved[0]!=profile:return None
    result=saved[1]
    surveys={s['id']:s for s in result['surveys']}
    key=f'dash_research_survey_{profile}'
    if st.session_state.get(key) not in surveys:st.session_state[key]=None
    survey=st.selectbox('Medición para las tarjetas IC05 e IC07',[None]+list(surveys),key=key,
        format_func=lambda i:'Sin medición seleccionada' if i is None else
        f"#{i} · {surveys[i]['name']} · {KINDS[surveys[i]['kind']]} · {surveys[i]['fieldwork_date'] or 'Sin fecha'}")
    if survey is not None:
        chosen=surveys[survey]
        st.info(KINDS[chosen['kind']]+': '+chosen['review_note'])
        st.caption(f"Fuente: {chosen['pollster'] or 'No identificada'} · Territorio: {chosen['territory'] or 'No identificado'} · Muestra: {chosen['sample_size'] or 'No registrada'}")
        st.caption('Enlace registrado: '+(chosen['source_url'] or 'No registrado'))
    return dict(bundle=result,selected_survey=surveys.get(survey))


def related_evidence(research,code):
    return [e for e in research['bundle']['evidence'] if code in e['related_cards']] if research else []


def show_research(research):
    bundle=research['bundle']
    st.markdown('### Encuestas y expediente · '+bundle['profile']['name'])
    for warning in bundle['warnings']:st.warning(warning)
    if bundle['truncated']:st.warning('Hay más de 500 registros en alguna categoría; se muestran los primeros 500, no el expediente completo.')
    selected=research['selected_survey']
    if selected:
        with st.expander('Medición seleccionada: metodología, notas y trazabilidad'):
            st.write(selected['methodology'] or 'Metodología no registrada')
            st.write(selected['notes'] or 'Sin notas')
            st.json(dict(id=selected['id'],fingerprint=selected['fingerprint'],
                         classification_status=selected['classification_status'],
                         fieldwork_date=selected['fieldwork_date'],metadata_missing=selected['metadata_missing'],
                         source_url=selected['source_url'],indicators=selected['indicators']))
    sections=st.tabs(['Mediciones del perfil','Cargos registrados','Documentos del expediente','Evidencias relacionadas','Escenarios de coalición'])
    with sections[0]:
        if bundle['surveys']:
            st.dataframe([dict(id=s['id'],nombre=s['name'],tipo=KINDS[s['kind']],fecha=s['fieldwork_date'],
                territorio=s['territory'],muestra=s['sample_size'],porcentaje_original=s['profile_result_pct'],
                preferencia_para_tarjeta=s['indicators']['IC05']['value'],indecision_para_tarjeta=s['indicators']['IC07']['value'],
                fuente=s['pollster'],enlace=s['source_url'],clasificacion=s['classification_status'],
                faltantes=', '.join(s['metadata_missing'])) for s in bundle['surveys']],hide_index=True,width='stretch')
            st.caption('Los porcentajes originales pertenecen a reactivos distintos. No representan una serie comparable ni se promedian; IC06 sigue pendiente de revisión de comparabilidad.')
        else:st.info('Este perfil no tiene registros de encuestas.')
    for section,key,empty in ((sections[1],'positions','cargos'),(sections[2],'documents','documentos'),
                              (sections[3],'evidence','evidencias'),(sections[4],'coalitions','escenarios de coalición')):
        with section:
            if bundle[key]:st.dataframe(bundle[key],hide_index=True,width='stretch')
            else:st.info('Este perfil no tiene '+empty+' registrados.')
    st.caption('Registros existentes por categoría: '+', '.join(f'{k}: {n}' for k,n in bundle['totals'].items()))
