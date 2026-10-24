"""Motor de indicadores: presentación por HTTP; sin SQL ni fórmulas locales."""
import json
from urllib.parse import urlencode
import pandas as pd
import streamlit as st

from services.profiles_api import request as api_request, ProfileAPIError
from services.web_auth_ui import session_token

STATUS={'computed':'Calculado','proxy':'Aproximación explícita','unavailable':'No disponible',
        'blocked':'Bloqueado','series':'Serie por unidad'}


def request(method,path,token,payload=None):
    return api_request(method,path,token,payload,timeout=60)


def choose_dataset(token,elections,key):
    labels={e['id']:e['name'] for e in elections}
    election=st.selectbox('Elección', [None]+list(labels),format_func=lambda value:labels.get(value,'Todas'),key=key+'_election')
    after=st.number_input('Lotes posteriores al ID',min_value=0,step=1,key=key+'_batch_cursor')
    batches=request('GET','/indicators/datasets?'+urlencode(dict(after=after,**({'election_id':election} if election else {}))),token)
    by_id={b['id']:b for b in batches}
    selected=st.selectbox('Lote y cobertura a analizar',[None]+list(by_id),key=key+'_dataset',
        format_func=lambda value:'Selecciona un lote' if value is None else
            f"#{value} · {by_id[value]['election_name']} · {by_id[value]['level']} · {by_id[value]['units']} unidades · {by_id[value]['vote_basis']}")
    if selected is None:
        return None,[]
    batch=by_id[selected]
    st.caption(batch['coverage_note'])
    if batch['vote_basis']=='legacy_reported':
        st.warning('Carga anterior pendiente de acreditación: los votos no tienen atribución partidista o de candidaturas acreditada.')
    options=request('GET',f'/indicators/datasets/{selected}/options',token)
    return batch,options


def selection_fields(batch,options,key,mode,proxy):
    labels={v['option_code']:v['option_name'] for v in options}
    option=st.selectbox('Partido para IP01, IP02, IP05 e IP11',[None]+list(labels),
        format_func=lambda value:labels.get(value,'Sin partido seleccionado'),key=key+'_option',disabled=batch['vote_basis']!='party')
    denominator=st.selectbox('Denominador del porcentaje partidista',['valid_votes','emitted_votes'],key=key+'_denominator',
        format_func=lambda value:{'valid_votes':'Votos válidos: emitidos menos nulos y no registrados','emitted_votes':'Votos emitidos: incluye nulos y no registrados'}[value])
    entity=st.text_input('Filtrar por entidad (EE, opcional)',key=key+'_entity')
    unit=st.text_input('Filtrar por clave completa de unidad (opcional)',key=key+'_unit')
    cursor=st.text_input('Continuar resultados desde clave',key=key+'_cursor')
    allow=st.checkbox('Reconozco que el lote fue sustituido y quiero reproducir esa versión',key=key+'_superseded') if batch['superseded_by'] else False
    return dict(import_id=batch['id'],mode=mode,option_code=option if batch['vote_basis']=='party' else None,
        denominator=denominator,participation_proxy=proxy,entity_code=entity or None,unit_code=unit or None,
        after=cursor,limit=100,allow_superseded=allow)


def show_metrics(metrics,names):
    st.dataframe([dict(codigo=code,indicador=names.get(code,code),valor=value['value'],estado=STATUS[value['status']],
        numerador=value.get('numerator'),denominador=value.get('denominator'),motivo=value.get('reason'))
        for code,value in metrics.items()],width='stretch',hide_index=True)


def show_page(result,names,key):
    items=result['items']
    if not items:
        st.info('No hay resultados por unidad para estos filtros o la comparación está bloqueada.')
        return
    codes=sorted({c for item in items for c in item['metrics']})
    indicator=st.selectbox('Indicador para tabla y gráfica de esta página',codes,
        format_func=lambda value:value+' · '+names.get(value,value),key=key+'_chart')
    rows=[dict(clave=item['unit_code'],territorio=item['name'],valor=item['metrics'].get(indicator,{}).get('value'),
        estado=STATUS.get(item['metrics'].get(indicator,{}).get('status')),
        motivo=item['metrics'].get(indicator,{}).get('reason')) for item in items]
    st.dataframe(rows,width='stretch',hide_index=True)
    available=[dict(clave=r['clave'],valor=r['valor']) for r in rows if r['valor'] is not None]
    if available:
        st.bar_chart(pd.DataFrame(available).set_index('clave'))
        st.caption('Gráfica de la página actual; los faltantes no se representan como cero. El resumen usa toda la cobertura seleccionada.')
    if result.get('next_after'):
        st.caption('Para continuar, usa esta clave en el cursor y vuelve a calcular: '+result['next_after'])


def render_indicators():
    st.subheader('Motor de indicadores electorales')
    st.write('Fórmulas reproducibles con fuente, versión, denominador y cobertura. Un resultado calculable no equivale a una probabilidad de victoria.')
    token=session_token()
    try:
        catalog=request('GET','/indicators/catalog',token)
        elections=request('GET','/history/elections',token)
    except ProfileAPIError as exc:
        st.error(str(exc))
        return
    names={item['code']:item['name'] for item in catalog['items']}
    single,comparison,definitions=st.tabs(['Indicadores por elección','Comparar elecciones','Catálogo y fórmulas'])
    with definitions:
        st.caption('La disponibilidad del motor indica que existe una fórmula implementada; cada carga puede carecer de los insumos necesarios.')
        st.dataframe(catalog['items'],width='stretch',hide_index=True)
        st.caption('Motor '+catalog['engine_version']+' · Catálogo '+catalog['catalog_version'])
    with single:
        try:
            batch,options=choose_dataset(token,elections,'indicator_single')
            if not batch:
                st.info('Selecciona una elección y un lote para calcular.')
            else:
                with st.form('indicator_evaluation'):
                    exploratory=st.checkbox('Explorar carga anterior sin acreditarla como oficial')
                    proxy=st.checkbox('Calcular proxy de participación con votos emitidos / lista nominal',
                        help='No equivale a contar personas que votaron. Valores mayores a 100% quedan sin calcular.')
                    payload=selection_fields(batch,options,'single','exploratory' if exploratory else 'validated',proxy)
                    if st.form_submit_button('Calcular indicadores'):
                        st.session_state.pop('_indicator_result',None)
                        st.session_state['_indicator_result']=request('POST','/indicators/evaluate',token,payload)
                result=st.session_state.get('_indicator_result')
                if result and result['request']==payload:
                    for warning in result['warnings']: st.warning(warning)
                    st.json(result['coverage'])
                    st.markdown('#### Resumen de la cobertura observada')
                    show_metrics(result['summary'],names)
                    show_page(result,names,'single_result')
                    with st.expander('Fuente, fechas, versión y reproducción del cálculo'):
                        st.json(dict(engine_version=result['engine_version'],request=result['request'],provenance=result['provenance']))
        except ProfileAPIError as exc:
            st.error(str(exc))
    with comparison:
        st.caption('A debe preceder a B. Se exige igual cargo, ámbito, principio, proceso, versión geográfica y base de votos. Las equivalencias no se deducen por similitud de nombres.')
        try:
            left,right=st.columns(2)
            with left:
                st.markdown('#### Elección A')
                a,options_a=choose_dataset(token,elections,'indicator_a')
            with right:
                st.markdown('#### Elección B')
                b,options_b=choose_dataset(token,elections,'indicator_b')
            if a and b:
                with st.form('indicator_comparison'):
                    exploratory=st.checkbox('Permitir lectura exploratoria; no elimina bloqueos de comparabilidad')
                    mode='exploratory' if exploratory else 'validated'
                    sa=selection_fields(a,options_a,'compare_a',mode,False)
                    sb=selection_fields(b,options_b,'compare_b',mode,False)
                    coverage=st.selectbox('Cobertura comparable',['exact','intersection'],
                        format_func=lambda value:{'exact':'Exigir las mismas unidades','intersection':'Comparar únicamente la intersección y mostrar exclusiones'}[value])
                    st.caption('Cada equivalencia debe declarar option_a, option_b, evidence_url HTTPS y note. Debe ser uno a uno; para volatilidad se exige cubrir todas las opciones. Sin equivalencias no se imputan ceros.')
                    mapping=st.text_area('Equivalencias documentadas (JSON)',value='[]')
                    payload=dict(a=sa,b=sb,coverage_mode=coverage)
                    if st.form_submit_button('Comprobar comparabilidad y calcular'):
                        st.session_state.pop('_indicator_comparison',None)
                        try:
                            payload['option_mapping']=json.loads(mapping)
                            result=request('POST','/indicators/compare',token,payload)
                            st.session_state['_indicator_comparison']=result
                            st.session_state['_indicator_comparison_input']=json.dumps(payload,sort_keys=True)
                        except json.JSONDecodeError:
                            st.error('Las equivalencias deben ser JSON válido.')
                result=st.session_state.get('_indicator_comparison')
                try: payload['option_mapping']=json.loads(mapping)
                except json.JSONDecodeError: payload['option_mapping']=None
                if result and st.session_state.get('_indicator_comparison_input')==json.dumps(payload,sort_keys=True):
                    st.json(result['comparability'])
                    if not result['comparability']['comparable']:
                        st.error('Comparación bloqueada: '+'; '.join(result['comparability']['reasons']))
                    show_metrics(result['summary'],names)
                    show_page(result,names,'comparison_result')
                    with st.expander('Fuentes y equivalencias utilizadas'):
                        st.json(dict(engine_version=result['engine_version'],request=result['request'],provenance=result['provenance']))
        except ProfileAPIError as exc:
            st.error(str(exc))
