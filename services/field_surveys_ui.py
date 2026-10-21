"""Configurador y captura móvil de cuestionarios de campo."""
import json
import secrets
from urllib.parse import urlencode

import streamlit as st

from services import field_surveys as surveys
from services.web_auth_ui import session_token

TYPES = {'text': 'Texto', 'number': 'Número', 'choice': 'Una opción'}
METRICS = {'none': 'Sin indicador', 'count': 'Contar respuestas', 'sum': 'Sumar valores', 'average': 'Promediar valores'}


def question_inputs(questions, prefix):
    answers = {}
    for q in questions:
        label = q['label'] + (' *' if q['required'] else ' (opcional)')
        key = f"{prefix}_{q['id']}"
        if q['type'] == 'choice':
            value = st.selectbox(label, q['options'], index=None, placeholder='Selecciona una opción', key=key)
        elif q['type'] == 'number':
            value = st.number_input(label, value=None,
                                    min_value=float(q['min']) if q['min'] is not None else None,
                                    max_value=float(q['max']) if q['max'] is not None else None, key=key)
        else:
            value = st.text_area(label, max_chars=3000, key=key)
        answers[q['id']] = value
    return answers


def render_capture(task_id, assignment_generation, survey_generation):
    try:
        task, survey = surveys.capture_data(session_token(), task_id, assignment_generation, survey_generation)
    except (PermissionError, ValueError) as exc:
        st.error(str(exc))
        return
    prefix = f"survey_capture_{task_id}_{assignment_generation}_{survey_generation}"
    st.title(survey['title'])
    st.write(survey['description'])
    st.caption(f"Actividad #{task_id}: {task['activity_name']} · {task['state']} / {task['municipality']}")
    st.caption('Las preguntas con * son obligatorias. Las respuestas se contabilizan al enviarse.')
    if prefix + '_saved' in st.session_state:
        st.success(f"Respuestas guardadas. Folio ENC-{st.session_state[prefix + '_saved']:06d}. Indicadores actualizados.")
        if survey['mode'] == 'multiple' and st.button('Registrar otra encuesta', key=prefix+'_another'):
            for key in list(st.session_state):
                if key.startswith(prefix):
                    del st.session_state[key]
            st.rerun()
        return
    if prefix+'_key' not in st.session_state:
        st.session_state[prefix+'_key'] = secrets.token_hex(24)
    with st.form(prefix):
        answers = question_inputs(json.loads(survey['definition']), prefix)
        st.caption('Revisa tus respuestas antes de enviar. Un envío confirmado queda guardado como registro final.')
        if st.form_submit_button('Enviar respuestas', type='primary'):
            try:
                rid = surveys.submit_response(session_token(), task_id, assignment_generation, survey_generation,
                                              st.session_state[prefix+'_key'], answers)
                st.session_state[prefix+'_saved'] = rid
                st.rerun()
            except (ValueError, PermissionError) as exc:
                st.error(str(exc))


def render_builder(task_id, templates):
    options = {0: 'Crear cuestionario nuevo'}
    options.update({q['id']: f"{q['title']} · #{q['id']} · {q['status']}" for q in templates})
    chosen = st.selectbox('Borrador o cuestionario de referencia', list(options), format_func=options.get,
                          key=f'survey_edit_select_{task_id}')
    old = next((q for q in templates if q['id'] == chosen), None)
    editable = old and old['status'] == 'draft' and old['task_id'] == task_id
    prefix = f"survey_builder_{task_id}_{chosen}"
    if old and not editable:
        st.info('Se creará una copia como nueva versión para esta actividad. Las respuestas anteriores se conservan.')
    title = st.text_input('Nombre del cuestionario', value=old['title'] if old else '', max_chars=160, key=prefix+'_title')
    description = st.text_area('Instrucciones para campo', value=old['description'] if old else '', max_chars=2000, key=prefix+'_description')
    mode = st.selectbox('Modalidad', ['single', 'multiple'], index=1 if old and old['mode'] == 'multiple' else 0,
                        format_func=lambda v: 'Una respuesta por actividad' if v == 'single' else 'Varias entrevistas por actividad', key=prefix+'_mode')
    previous = json.loads(old['definition']) if old else []
    size = st.number_input('Número de preguntas', min_value=1, max_value=30, value=max(1, len(previous)), key=prefix+'_size')
    questions = []
    for i in range(size):
        q = previous[i] if i < len(previous) else {}
        k = f'{prefix}_{i}'
        with st.expander(f'Pregunta {i+1}', expanded=True):
            label = st.text_input('Pregunta', value=q.get('label', ''), max_chars=300, key=k+'_label')
            kind = st.selectbox('Tipo de respuesta', list(TYPES), index=list(TYPES).index(q.get('type', 'text')), format_func=TYPES.get, key=k+'_type')
            required = st.checkbox('Obligatoria', value=q.get('required', True), key=k+'_required')
            options_text = st.text_area('Opciones (una por línea)', value='\n'.join(q.get('options', [])), key=k+'_options') if kind == 'choice' else ''
            minimum = maximum = None
            if kind == 'number':
                minimum = st.number_input('Mínimo permitido (opcional)', value=float(q['min']) if q.get('min') is not None else None, key=k+'_min')
                maximum = st.number_input('Máximo permitido (opcional)', value=float(q['max']) if q.get('max') is not None else None, key=k+'_max')
            allowed = list(METRICS) if kind == 'number' else ['none', 'count']
            default = q.get('metric', 'none')
            metric = st.selectbox('Cálculo del indicador', allowed, index=allowed.index(default) if default in allowed else 0,
                                  format_func=METRICS.get, key=k+'_metric_'+kind)
            metric_label = st.text_input('Nombre del indicador', value=q.get('metric_label', ''), max_chars=120, key=k+'_metric_label') if metric != 'none' else ''
            questions.append(dict(label=label, type=kind, required=required, options=options_text.splitlines(),
                                  min=minimum, max=maximum, metric=metric, metric_label=metric_label))
    st.caption('Siempre se calculan el total de cuestionarios enviados y el avance contra la meta. '
               'Contar respuestas excluye preguntas sin responder; suma y promedio usan los valores numéricos capturados.')
    if st.checkbox('Mostrar vista previa', key=prefix+'_preview'):
        try:
            preview = surveys.validate_definition(questions)
            st.markdown('#### Vista previa — no guarda respuestas')
            question_inputs(preview, prefix+'_preview_input')
        except ValueError as exc:
            st.warning(str(exc))
    save, publish = st.columns(2)
    draft = save.button('Guardar borrador', key=prefix+'_save')
    published = publish.button('Publicar cuestionario', key=prefix+'_publish', type='primary')
    if draft or published:
        try:
            qid = surveys.save_questionnaire(session_token(), task_id, title, description, mode, questions,
                                             old['id'] if editable else None, publish=published)
            st.session_state[f'survey_notice_{task_id}'] = f"Cuestionario #{qid} {'publicado. Selecciónalo en la asignación.' if published else 'guardado como borrador.'}"
            st.rerun()
        except (ValueError, PermissionError) as exc:
            st.error(str(exc))


def render_task_surveys(task_id, configure=True):
    try:
        task, assigned, templates, manage = surveys.task_data(session_token(), task_id)
        st.markdown('### Cuestionario de campo')
        notice = st.session_state.pop(f'survey_notice_{task_id}', None)
        if notice:
            st.success(notice)
        if assigned:
            st.write(f"**{assigned['title']}** · versión #{assigned['questionnaire_id']} · meta: {assigned['target']}")
            if task['worker_id'] is not None and task['status'] in {'Pendiente', 'En curso'}:
                if task['can_capture']:
                    query = urlencode(dict(field_survey=task_id, assignment=task['assignment_generation'], survey=assigned['generation']))
                    st.link_button('Responder cuestionario', '?' + query)
        else:
            st.caption('Esta actividad aún no tiene cuestionario asignado.')
        if configure and manage and task['status'] in {'Pendiente', 'En curso'}:
            with st.expander('Crear o editar cuestionario'):
                render_builder(task_id, templates)
            published = {q['id']: f"{q['title']} · versión #{q['id']}" for q in templates if q['status'] == 'published'}
            if published:
                with st.form(f'survey_assignment_{task_id}'):
                    ids = list(published)
                    qid = st.selectbox('Cuestionario publicado', ids, format_func=published.get,
                                       index=ids.index(assigned['questionnaire_id']) if assigned and assigned['questionnaire_id'] in ids else 0)
                    target = st.number_input('Meta de capturas', min_value=1, max_value=1000000, value=assigned['target'] if assigned else 1)
                    if st.form_submit_button('Asignar cuestionario a la actividad'):
                        surveys.assign_questionnaire(session_token(), task_id, qid, target)
                        st.rerun()
            if not task['public_url_configured']:
                st.info('El acceso desde Telegram requiere configurar la dirección HTTPS del sistema en el servidor de la API. '
                        'El trabajador también necesita su cuenta web, disponible en Administración de usuarios.')
        for group in surveys.results(session_token(), task_id):
            with st.expander(f"Indicadores y respuestas · {group['title']} · versión #{group['id']}", expanded=bool(assigned and assigned['questionnaire_id'] == group['id'])):
                st.caption('Calculados al enviar. Se muestran únicamente respuestas dentro de tu alcance. Los promedios excluyen respuestas vacías.')
                st.dataframe(group['metrics'], hide_index=True, use_container_width=True)
                if group['responses']:
                    records = []
                    for r in group['responses']:
                        a = json.loads(r['answers'])
                        records.append({'Folio': f"ENC-{r['id']:06d}", 'Trabajador': r['worker_id'], 'Fecha UTC': r['created_at'],
                                        'Estado': r['state'], 'Municipio': r['municipality'],
                                        **{f"{q['id']}: {q['label']}": a.get(q['id']) for q in group['questions']}})
                    st.dataframe(records, hide_index=True, use_container_width=True)
    except (ValueError, PermissionError) as exc:
        st.error(str(exc))


def render_manager():
    from services.web_portal import portal_data
    st.title('Cuestionarios de campo')
    st.caption('Selecciona una actividad para configurar su cuestionario, asignarlo y consultar sus indicadores.')
    _, tasks, _ = portal_data(session_token())
    if not tasks:
        st.info('No hay actividades disponibles dentro de tu alcance.')
        return
    options = {t['id']: f"#{t['id']} · {t['activity_name']} · {t['municipality']}" for t in tasks}
    task_id = st.selectbox('Actividad', list(options), format_func=options.get, key='survey_manager_task')
    render_task_surveys(task_id)
