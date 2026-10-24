"""Base histórica: carga y consulta mediante API, sin conexiones SQL."""
import hashlib
import json
from datetime import date
from urllib.parse import urlencode

import streamlit as st

from services.profiles_api import ProfileAPIError, request as api_request
from services.web_auth_ui import session_token

LEVELS = {'Entidad': 'entity', 'Municipio': 'municipality', 'Distrito federal': 'federal_district',
          'Distrito local': 'local_district', 'Sección': 'section'}
GEO_HEADER = 'level,code,name,entity_code,municipality_code,federal_district_code,local_district_code\n'
RESULT_HEADER = 'unit_code,nominal_list,total_votes,null_votes,unregistered_votes,option_code,option_name,votes\n'


def request(method, path, token, payload=None):
    # Lotes de miles de filas requieren un plazo mayor; no reintentar escrituras.
    return api_request(method, path, token, payload, timeout=60)


def source_form(key, geographic=False):
    st.caption('Registrar la publicación oficial y explicar la conversión al CSV normalizado. La URL no se descarga ni certifica automáticamente.')
    authority = st.text_input('Autoridad publicadora (INE u OPLE)', key=key+'_authority')
    title = st.text_input('Título de la publicación', key=key+'_title')
    url = st.text_input('Enlace HTTPS al archivo o publicación oficial', key=key+'_url')
    version = st.text_input('Versión de la fuente', key=key+'_version')
    a, b, c = st.columns(3)
    published = a.date_input('Publicación', key=key+'_published')
    retrieved = b.date_input('Consulta', key=key+'_retrieved')
    cutoff = c.date_input('Fecha de corte', key=key+'_cutoff')
    stage = 'geography' if geographic else st.selectbox('Etapa del resultado',
        ['official_computation', 'final_judgment'], key=key+'_stage',
        format_func=lambda v: {'official_computation':'Cómputo oficial','final_judgment':'Resultado modificado por sentencia'}[v],
        help='Cómputo oficial o resultado modificado por sentencia; no cargar PREP.')
    methodology = st.text_area('Procedimiento de normalización y alcance de la fuente', key=key+'_method')
    return dict(authority=authority, title=title, url=url, version=version,
                published_on=published.isoformat(), retrieved_on=retrieved.isoformat(),
                cutoff_on=cutoff.isoformat(), stage=stage, methodology=methodology)


def read_upload(upload):
    if upload is None:
        raise ValueError('Selecciona un CSV UTF-8.')
    if upload.size > 5_000_000:
        raise ValueError('El CSV supera 5 MB; dividir en lotes documentados.')
    try:
        return upload.getvalue().decode('utf-8-sig')
    except UnicodeDecodeError:
        raise ValueError('Guardar el CSV con codificación UTF-8.') from None


def render_history():
    st.subheader('Base histórica electoral')
    st.write('Catálogos versionados y resultados oficiales con trazabilidad. Esta base es independiente de los perfiles y de las cargas electorales anteriores.')
    token = session_token()
    try:
        geographies = request('GET', '/history/geographies', token)
        elections = request('GET', '/history/elections', token)
    except ProfileAPIError as exc:
        st.error(str(exc))
        st.caption('Requiere sesión de administrador y la migración de base histórica aplicada. Consulta backend/README.md.')
        return
    notice = st.session_state.pop('_history_notice', None)
    if notice:
        st.success(notice)
    consulta, geography_tab, election_tab, import_tab, legacy_tab = st.tabs(
        ['Consulta y fuentes', 'Catálogo geográfico', 'Elecciones', 'Importar resultados', 'Cargas anteriores y conciliación'])
    geo_labels = {g['id']: f"{g['version']} · {g['valid_on'] or 'vigencia pendiente de acreditar'} (#{g['id']})" for g in geographies}
    election_labels = {e['id']: f"{e['name']} · {e['election_date'] or str(e.get('legacy_election_year'))+' (fecha pendiente)'} · {e['principle']} (#{e['id']})" for e in elections}
    with geography_tab:
        st.write('Cada catálogo es una fotografía geográfica inmutable. Los municipios no se subordinan a un distrito; la sección identifica su municipio y ambos distritos cuando se conocen.')
        st.code(GEO_HEADER.strip(), language='text')
        st.caption('Claves compuestas: entidad EE; municipio EEMMM; distrito EEDD; sección EESSSS. Mantener ceros iniciales. Incluir las unidades padre y referenciadas en el mismo archivo.')
        with st.form('history_geography'):
            version = st.text_input('Versión del catálogo (única)')
            valid_on = st.date_input('Vigencia/corte del catálogo')
            upload = st.file_uploader('Catálogo normalizado CSV', type=['csv'], key='history_geo_csv')
            source = source_form('history_geo_source', geographic=True)
            if st.form_submit_button('Validar y guardar catálogo'):
                try:
                    result = request('POST', '/history/geographies', token,
                        dict(version=version, valid_on=valid_on.isoformat(), source=source, csv_content=read_upload(upload)))
                    st.session_state['_history_notice'] = f"Catálogo #{result['id']}: {result['units']} unidades."
                    st.rerun()
                except (ValueError, ProfileAPIError) as exc:
                    st.error(str(exc))
        if geographies:
            gid = st.selectbox('Consultar catálogo', list(geo_labels), format_func=geo_labels.get)
            level_label = st.selectbox('Nivel geográfico', list(LEVELS))
            cursor = st.text_input('Continuar catálogo desde cursor', help='Usar next_after para ver las siguientes unidades.')
            try:
                page = request('GET', f'/history/geographies/{gid}/units?'+urlencode(dict(level=LEVELS[level_label], after=cursor)), token)
                st.dataframe(page['items'], width='stretch', hide_index=True)
                if page['next_after']:
                    st.caption('Siguiente cursor: ' + page['next_after'])
                st.json(next(g['source'] for g in geographies if g['id'] == gid))
            except ProfileAPIError as exc:
                st.error(str(exc))
    with election_tab:
        with st.form('history_election'):
            code = st.text_input('Código único del proceso y cargo', placeholder='MX_2024_PRES_MR')
            name = st.text_input('Nombre de la elección')
            election_date = st.date_input('Fecha de jornada electoral', value=date(2024, 6, 2))
            jurisdiction = st.selectbox('Ámbito', ['federal', 'local'], format_func=lambda v: v.capitalize())
            office = st.text_input('Cargo', placeholder='Presidencia de la República')
            principle = st.selectbox('Principio', ['MR', 'RP', 'NA'])
            process = st.selectbox('Tipo de proceso', ['ordinary', 'extraordinary'],
                format_func=lambda v: {'ordinary':'Ordinario','extraordinary':'Extraordinario'}[v])
            entity = st.text_input('Clave de entidad (dos dígitos; vacía para federal nacional)')
            if st.form_submit_button('Registrar elección'):
                try:
                    result = request('POST', '/history/elections', token,
                        dict(code=code, name=name, election_date=election_date.isoformat(), jurisdiction=jurisdiction,
                             office=office, principle=principle, process=process, entity_code=entity or None))
                    st.session_state['_history_notice'] = f"Elección #{result['id']} registrada."
                    st.rerun()
                except ProfileAPIError as exc:
                    st.error(str(exc))
        st.dataframe(elections, width='stretch', hide_index=True)
    with import_tab:
        st.code(RESULT_HEADER.strip(), language='text')
        st.caption('Una fila por unidad/opción. Repetir los mismos totales por unidad. Vacío significa desconocido; cero significa cero publicado. No mezclar partidos, candidaturas ni combinaciones de boleta.')
        if not geographies or not elections:
            st.info('Primero registra un catálogo geográfico y una elección.')
        else:
            with st.form('history_import'):
                gid = st.selectbox('Catálogo de la carga', list(geo_labels), format_func=geo_labels.get)
                eid = st.selectbox('Elección de la carga', list(election_labels), format_func=election_labels.get)
                level = st.selectbox('Nivel de los resultados', list(LEVELS))
                basis = st.selectbox('Base de votos', ['party', 'candidacy', 'ballot_combination'],
                    format_func=lambda v: {'party':'Partido con atribución oficial','candidacy':'Candidatura o coalición consolidada',
                                           'ballot_combination':'Combinación de marcas de boleta'}[v])
                coverage = st.text_area('Cobertura del lote y faltantes', help='Indicar si es parcial, unidades incluidas y exclusiones.')
                supersedes = st.text_input('ID del lote que sustituye (solo para una revisión)')
                upload = st.file_uploader('Resultados normalizados CSV', type=['csv'], key='history_results_csv')
                source = source_form('history_results_source')
                validated = st.form_submit_button('Validar sin guardar')
                save = st.form_submit_button('Guardar lote validado')
                if validated or save:
                    try:
                        payload = dict(election_id=eid, geography_id=gid, level=LEVELS[level], vote_basis=basis,
                            coverage_note=coverage, supersedes_id=int(supersedes) if supersedes else None,
                            source=source, csv_content=read_upload(upload))
                        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
                        if validated:
                            report = request('POST', '/history/imports/preview', token, payload)
                            st.session_state['_history_validated'] = fingerprint
                            st.success('Validación terminada; revisa advertencias antes de guardar.')
                            st.json(report)
                        elif st.session_state.get('_history_validated') != fingerprint:
                            st.error('Valida primero estos mismos datos. Un cambio de archivo o metadatos requiere nueva validación.')
                        else:
                            result = request('POST', '/history/imports', token, payload)
                            st.session_state.pop('_history_validated', None)
                            st.session_state['_history_notice'] = f"Lote #{result['id']} guardado; {result['units']} unidades."
                            st.rerun()
                    except (ValueError, ProfileAPIError) as exc:
                        st.error(str(exc))
    with consulta:
        st.caption('Selecciona una carga explícita. Los lotes parciales, niveles y bases no se suman automáticamente. Las cargas anteriores aparecen como legacy_reported y siguen pendientes de acreditación oficial.')
        try:
            eid = st.selectbox('Filtrar por elección', [None]+list(election_labels),
                format_func=lambda value: election_labels.get(value, 'Todas'))
            after = st.number_input('Lotes posteriores al ID', min_value=0, step=1)
            batches = request('GET', '/history/imports?'+urlencode(dict(after=after, **({'election_id': eid} if eid else {}))), token)
            st.dataframe(batches, width='stretch', hide_index=True)
            if batches:
                bid = st.selectbox('Lote para consultar', [b['id'] for b in batches])
                detail = request('GET', f'/history/imports/{bid}', token)
                if detail['source']['stage'] == 'legacy_snapshot':
                    st.warning('Carga anterior preservada. Su migración no acredita la fuente, fecha geográfica ni atribución de votos. Consultar las observaciones en Cargas anteriores y conciliación.')
                st.json({k: v for k, v in detail.items() if k != 'csv_content'})
                st.caption('El hash corresponde al CSV normalizado recibido, no certifica el archivo original de la autoridad.')
                entity = st.text_input('Filtrar resultados por entidad (EE)')
                unit = st.text_input('Filtrar por clave completa de unidad')
                cursor = st.text_input('Continuar resultados desde clave', help='Usar next_after para la siguiente página.')
                page = request('GET', f'/history/imports/{bid}/results?'+urlencode(dict(after=cursor,
                    **({'entity_code': entity} if entity else {}), **({'unit_code': unit} if unit else {}))), token)
                st.dataframe([{k: v for k, v in row.items() if k != 'options'} for row in page['items']], width='stretch', hide_index=True)
                st.dataframe([dict(unit_code=row['unit_code'], **{k:v for k,v in option.items() if k != 'unit_code'})
                    for row in page['items'] for option in row['options']], width='stretch', hide_index=True)
                if page['next_after']:
                    st.caption('Siguiente clave: ' + page['next_after'])
        except ProfileAPIError as exc:
            st.error(str(exc))
    with legacy_tab:
        st.write('Los originales se conservan completos. Normalizado significa que sus claves y conteos pudieron copiarse al modelo; no significa validado contra la publicación oficial. Los pendientes no se descartan.')
        try:
            runs = request('GET','/history/legacy/runs',token)
            if not runs:
                st.info('Todavía no se ha ejecutado una migración de cargas anteriores.')
            else:
                run_id = st.selectbox('Ejecución de migración',[r['id'] for r in runs])
                run = next(r for r in runs if r['id']==run_id)
                report = run['report']
                a,b,c=st.columns(3)
                a.metric('Originales conservados',report['archived_rows'])
                b.metric('Normalizados',report['normalized'])
                c.metric('Pendientes de normalizar',report['pending'])
                st.json(report)
                status = st.selectbox('Estado de normalización',['pending','normalized'],
                    format_func=lambda value: {'pending':'Pendiente; original íntegro conservado','normalized':'Copiado al modelo; acreditación pendiente'}[value])
                state=st.text_input('Entidad de las cargas anteriores (nombre exacto)')
                after=st.text_input('Continuar originales desde cursor')
                page=request('GET',f'/history/legacy/runs/{run_id}/records?'+urlencode(dict(status=status,after=after,**({'state':state} if state else {}))),token)
                st.dataframe(page['items'],width='stretch',hide_index=True)
                if page['next_after']:
                    st.caption('Siguiente cursor: '+page['next_after'])
                if page['items']:
                    options={r['source_table']+':'+str(r['source_id']):r for r in page['items']}
                    selected=st.selectbox('Consultar original completo',list(options))
                    row=options[selected]
                    detail=request('GET',f"/history/legacy/runs/{run_id}/records/{row['source_table']}/{row['source_id']}",token)
                    st.json(detail)
        except ProfileAPIError as exc:
            st.error(str(exc))
