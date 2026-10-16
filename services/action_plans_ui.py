"""Planes de acción: interfaz que solo consume la API."""
from datetime import date
import pandas as pd
import streamlit as st
from services import field_api as api
from services.field_tasks_ui import render_task_assignment
from services.field_reports_ui import render_task_reports


def render_action_plans():
    try:
        _render_action_plans()
    except api.APIError as exc:
        st.error(str(exc))


def _render_action_plans() -> None:
    """Operational plan for already defined territorial strategies."""
    api.require_admin()
    st.subheader('Planes de acción')
    st.button('Actualizar actividades y recepciones')
    st.caption('Organiza la ejecución por actividad, responsable, fecha, prioridad, estatus y evidencia. El seguimiento se concentra en tareas territoriales, no en datos individuales de electores.')
    options = api.profile_options()
    if not options:
        st.info('Primero crea un perfil y registra una estrategia territorial.')
        return
    chosen_profile = st.selectbox('Perfil', list(options), key='action_profile')
    profile_id = options[chosen_profile]
    states = api.profile_states(profile_id)
    if not states:
        st.info('Asigna un estado al perfil antes de crear un plan de acción.')
        return
    selected_state = st.selectbox('Estado', states, key='action_state')
    strategy_rows = api.strategies(profile_id, selected_state)
    if not strategy_rows:
        st.info('Aún no hay estrategias guardadas. Primero define una en Estrategia territorial; después podrás programar sus actividades aquí.')
        return
    strategy_options = {f"{row['municipality']} · {row['strategic_focus']} · {row['status']}": row for row in strategy_rows}
    selected_strategy_label = st.selectbox('Estrategia territorial', list(strategy_options), key=f'action_strategy_{selected_state}')
    strategy = strategy_options[selected_strategy_label]
    st.info(f"**Objetivo:** {strategy['objective']}")
    st.markdown('### Programar actividad')
    with st.form(f"action_form_{strategy['id']}", clear_on_submit=True):
        activity_name = st.text_input('Nombre de la actividad', placeholder='Ejemplo: reunión de coordinación territorial')
        activity_description = st.text_area('Descripción y resultado esperado', placeholder='Qué se realizará, qué evidencia se espera y cómo se relaciona con el objetivo territorial.')
        action_columns = st.columns(3)
        responsible = action_columns[0].text_input('Responsable', placeholder='Nombre o equipo')
        due_date = action_columns[1].date_input('Fecha compromiso', value=date.today())
        priority_level = action_columns[2].selectbox('Prioridad', ['Alta', 'Media', 'Baja'], index=1)
        territory_columns = st.columns(2)
        district = territory_columns[0].text_input('Distrito (opcional)', placeholder='Ejemplo: 09')
        electoral_section = territory_columns[1].text_input('Sección electoral (opcional)', placeholder='Ejemplo: 0474')
        submitted = st.form_submit_button('Agregar actividad', type='primary')
    if submitted:
        if not activity_name.strip():
            st.error('Escribe el nombre de la actividad antes de agregarla.')
        else:
            api.create_activity(strategy['id'], {'district': district.strip() or None, 'electoral_section': electoral_section.strip() or None, 'activity_name': activity_name.strip(), 'activity_description': activity_description.strip() or None, 'responsible': responsible.strip() or None, 'due_date': str(due_date), 'priority_level': priority_level})
            st.success('Actividad agregada al plan de acción.')
            st.rerun()
    actions = api.activities(strategy['id'])
    st.markdown('### Actividades del municipio')
    if not actions:
        st.caption('Todavía no hay actividades. Registra la primera para poner la estrategia en operación.')
        return
    summary = pd.DataFrame(actions)
    counts = summary['status'].value_counts()
    action_metrics = st.columns(3)
    action_metrics[0].metric('Total', len(summary))
    action_metrics[1].metric('Pendientes', int(counts.get('Pendiente', 0)))
    action_metrics[2].metric('Concluidas', int(counts.get('Concluida', 0)))
    display_columns=['activity_name','activity_description','district','electoral_section','responsible',
                     'due_date','priority_level','status','evidence_note','completed_at',
                     'trabajador_telegram','recepcion_telegram_utc']
    st.dataframe(summary[display_columns], width='stretch', hide_index=True)
    action_lookup = {f"#{row['id']} · {row['activity_name']} · {row['due_date'] or 'sin fecha'}": row for row in actions}
    selected_action_label = st.selectbox('Actualizar una actividad', list(action_lookup), key=f"update_action_{strategy['id']}")
    selected_action = action_lookup[selected_action_label]
    render_task_assignment(selected_action)
    render_task_reports(selected_action['id'])
    update_columns = st.columns(2)
    new_status = update_columns[0].selectbox('Estatus', ['Pendiente', 'En curso', 'Concluida', 'Cancelada'], index=['Pendiente', 'En curso', 'Concluida', 'Cancelada'].index(selected_action['status']))
    evidence = update_columns[1].text_input('Evidencia o nota de avance', value=selected_action['evidence_note'] or '', placeholder='Ejemplo: minuta, enlace, fotografía o resultado reportado.')
    if st.button('Guardar avance de la actividad'):
        api.update_activity(selected_action['id'], new_status, evidence.strip() or None)
        st.success('Avance actualizado.')
        st.rerun()
