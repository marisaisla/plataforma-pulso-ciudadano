"""45 dashboard cards; all observations and calculations are obtained over HTTP."""
from urllib.parse import urlencode
import pandas as pd
import streamlit as st

from services.profiles_api import ProfileAPIError
from services.indicators_ui import request
from services.web_auth_ui import session_token
from services.dashboard_research_ui import research_filters, related_evidence, show_research

EXPLORATORY = ('IT01','IT03','IT04','IT05')


def electoral_filters(token):
    st.caption('Se analiza un lote y un nivel. No se suman elecciones ni coberturas superpuestas.')
    st.info('Consulta exploratoria: las cargas heredadas conservan su acreditación pendiente. Los valores no se presentan como resultados certificados.')
    cursor=st.number_input('Buscar lotes posteriores al ID',min_value=0,step=1,key='dash_batch_cursor')
    batches=request('GET','/indicators/datasets?'+urlencode(dict(after=cursor,limit=100)),token)
    batches={b['id']:b for b in batches}
    if st.session_state.get('dash_batch') not in batches:
        st.session_state['dash_batch']=None
    selected=st.selectbox('Lote electoral',[None]+list(batches),key='dash_batch',
        format_func=lambda i:'Selecciona un lote' if i is None else
        f"#{i} · {batches[i]['election_name']} · {batches[i]['level']} · {batches[i]['units']} unidades")
    if selected is None:
        return None
    batch=batches[selected]
    st.caption(batch['coverage_note'])
    if batch.get('superseded_by'):
        st.warning('Este lote tiene una revisión posterior. Selecciona la revisión vigente.')
        return None
    unit=st.text_input('Clave de unidad electoral (opcional)',key='dash_unit')
    proxy=st.checkbox('Mostrar aproximaciones de participación y abstención con votos emitidos',key='dash_proxy',
        help='No representa un conteo de personas que votaron. Sin activarlo IT03 e IT04 quedan sin valor.')
    payload=dict(import_id=selected,mode='exploratory',participation_proxy=proxy,unit_code=unit or None,limit=100)
    if st.button('Consultar datos electorales',key='dash_calculate'):
        st.session_state.pop('_dash_electoral',None)
        result=request('POST','/indicators/evaluate',token,payload)
        st.session_state['_dash_electoral']=(payload,result)
    saved=st.session_state.get('_dash_electoral')
    return saved[1] if saved and saved[0]==payload else None


def inegi_filters(token):
    st.caption('Filtros independientes de la elección. Los valores conservan su periodo y fuente; no se extrapolan a secciones.')
    options=request('GET','/indicators/dashboard/inegi/options',token)
    state=st.selectbox('Entidad INEGI',[None]+options['states'],key='dash_inegi_state',
                       format_func=lambda v:v or 'Selecciona una entidad')
    if state is None:
        return None
    options=request('GET','/indicators/dashboard/inegi/options?'+urlencode(dict(state=state)),token)
    family=st.selectbox('Componente territorial',['IT10','IT11','IT12','IT13'],key='dash_inegi_family',
        format_func=lambda v:{'IT10':'IT10 · Población','IT11':'IT11 · Escolaridad',
                              'IT12':'IT12 · Condiciones socioeconómicas','IT13':'IT13 · Servicios'}[v])
    series={r['indicator_id']:r['indicator_name'] for r in options['series'] if r['family']==family}
    indicator=st.selectbox('Serie INEGI',[None]+list(series),key=f'dash_series_{state}_{family}',
        format_func=lambda v:'Selecciona una serie' if v is None else f'{v} · {series[v]}')
    period=st.selectbox('Periodo INEGI',[None]+options['periods'],key=f'dash_period_{state}')
    source=st.selectbox('Fuente INEGI',[None]+options['sources'],key=f'dash_source_{state}')
    municipalities={r['municipality_code']:r['municipality'] for r in options['municipalities']}
    municipality=st.selectbox('Municipio INEGI',[None]+list(municipalities),key=f'dash_municipality_{state}',
        format_func=lambda v:'Todos los municipios disponibles' if v is None else f'{v} · {municipalities[v]}')
    after=st.number_input('Continuar observaciones después del ID',min_value=0,step=1,key='dash_inegi_after')
    payload=dict(state=state,family=family,indicator_id=indicator,period=period,source=source,after=after,limit=100)
    if municipality:payload['municipality_code']=municipality
    if st.button('Consultar INEGI',disabled=not all((indicator,period,source)),key='dash_inegi_query'):
        st.session_state.pop('_dash_inegi',None)
        result=request('GET','/indicators/dashboard/inegi?'+urlencode(payload),token)
        st.session_state['_dash_inegi']=(payload,result)
    saved=st.session_state.get('_dash_inegi')
    return saved if saved and saved[0]==payload else None


def render_cards(cards,electoral,inegi,research=None):
    for family,title in (('IC','Candidato y expediente'),('IP','Partidos y resultados'),('IT','Territorio')):
        st.markdown('### '+title)
        columns=st.columns(3)
        for index,card in enumerate(c for c in cards if c['family']==family):
            with columns[index%3]:
                with st.container(border=True):
                    st.markdown(f"**{card['code']} · {card['name']}**")
                    st.caption('Disponibilidad: '+card['availability'])
                    metric=(electoral or {}).get('summary',{}).get(card['code']) if card['code'] in EXPLORATORY else None
                    survey=research.get('selected_survey') if research else None
                    if survey and card['code'] in ('IC05','IC07'):
                        metric=survey['indicators'][card['code']]
                    if metric and metric['value'] is not None:
                        label='Porcentaje reportado' if metric['status']=='reported' else 'Aproximación explícita' if metric['status']=='proxy' else 'Valor exploratorio'
                        st.metric(label,
                                  f"{metric['value']:,.2f}" if card['unit']=='porcentaje' else f"{metric['value']:,}")
                        st.caption(card['unit'])
                        if survey and card['code'] in ('IC05','IC07'):
                            st.caption(f"{survey['name']} · {survey['fieldwork_date']} · {survey['pollster']}")
                    elif metric:
                        st.write('Sin cálculo')
                        st.caption(metric.get('reason') or 'No hay datos suficientes para estos filtros.')
                    elif inegi and inegi[0]['family']==card['code']:
                        st.write(f"{inegi[1]['total']} observaciones para los filtros")
                        st.caption('Valores individuales en la tabla INEGI. No es un valor agregado del indicador.')
                    elif research and card['code']=='IC08':
                        st.write(f"{research['bundle']['totals']['positions']} cargos registrados")
                        st.caption('Trayectoria capturada; no acredita por sí sola cada cargo.')
                    elif research and card['code']=='IP06':
                        st.write(f"{research['bundle']['totals']['coalitions']} escenarios registrados")
                        st.caption('Son escenarios del expediente; no convenios oficiales acreditados.')
                    elif related_evidence(research,card['code']):
                        st.write(f"{len(related_evidence(research,card['code']))} referencias temáticas del expediente")
                        st.caption('No equivalen a una medición validada ni a una resolución oficial.')
                    else:
                        st.write('Sin cálculo para esta selección')
                    with st.expander('Ficha y requisitos'):
                        st.write(card['formula'])
                        st.caption('Insumos revisados: '+card['evidence'])
                        st.caption('Presentación admisible: '+card['display'])
                        st.write('Falta: '+card['missing'])
                    refs=related_evidence(research,card['code'])
                    if refs:
                        with st.expander('Referencias del perfil seleccionado'):
                            for ref in refs:
                                st.write(ref['evidence_note'] or 'Sin nota')
                                st.caption(f"Código original: {ref['variable_code']} · Estado capturado: {ref['status']} · Fuente: {ref['source_label'] or 'No registrada'} · Fecha: {ref['reference_date'] or 'No registrada'}")
                                if ref['source_url']:st.caption(ref['source_url'])


def show_electoral(result):
    for warning in result['warnings']:st.warning(warning)
    st.caption(f"Cobertura: {result['coverage']['units_observed']} observaciones unidad–lote. La tabla muestra hasta 100.")
    rows=[dict(clave=r['unit_code'],territorio=r['name'],**{code:r['metrics'].get(code,{}).get('value') for code in EXPLORATORY})
          for r in result['items']]
    if rows:st.dataframe(rows,hide_index=True,width='stretch')
    if result.get('next_after'):st.caption('Hay más unidades. Filtra una clave concreta para inspeccionarla; el resumen considera toda la selección.')
    with st.expander('Fuente y cobertura del cálculo'):
        st.json(dict(provenance=result['provenance'],coverage=result['coverage'],request=result['request']))


def show_inegi(saved):
    filters,result=saved
    st.caption(result['scope'])
    st.write(f"Periodo: {filters['period']} · Fuente: {filters['source']}")
    if not result['items']:
        st.info('No hay observaciones para esta combinación de filtros.')
        return
    st.dataframe(result['items'],hide_index=True,width='stretch')
    values=[r for r in result['items'] if r['value'] is not None]
    units={r['unit'] for r in values}
    if values and len(units)==1 and next(iter(units)):
        frame=pd.DataFrame([dict(municipio=r['municipality']+' · '+str(r['id']),valor=r['value']) for r in values])
        st.bar_chart(frame.set_index('municipio'))
        st.caption('Valores reportados de la página actual, unidad: '+str(next(iter(units)))+'. No se promedian ni suman porcentajes.')
    else:
        st.caption('Sin gráfica cuando falta la unidad o las unidades difieren. Los valores se conservan en la tabla.')
    if result['next_after']:st.caption('Para continuar, introduce este ID: '+str(result['next_after']))


def render_indicator_dashboard():
    st.subheader('Dashboard de indicadores')
    st.write('45 variables con sus fuentes, disponibilidad y requisitos. Los faltantes no se muestran como cero.')
    token=session_token()
    try:
        response=request('GET','/indicators/dashboard/cards',token)
    except ProfileAPIError as exc:
        st.error(str(exc));return
    st.caption(f"Revisión de disponibilidad: {response['reviewed_on']}. {response['note']}")
    electoral=inegi=research=None
    left,right,profile_tab=st.tabs(['Filtros electorales','Filtros INEGI','Encuestas y expediente'])
    with left:
        try:electoral=electoral_filters(token)
        except ProfileAPIError as exc:st.error(str(exc))
    with right:
        try:inegi=inegi_filters(token)
        except ProfileAPIError as exc:st.error(str(exc))
    with profile_tab:
        try:research=research_filters(token)
        except ProfileAPIError as exc:st.error(str(exc))
    render_cards(response['items'],electoral,inegi,research)
    if electoral:
        st.markdown('### Detalle electoral exploratorio')
        show_electoral(electoral)
    if inegi:
        st.markdown('### Observaciones INEGI')
        show_inegi(inegi)
    if research:show_research(research)
