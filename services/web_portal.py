"""Panel autenticado para roles operativos; no abre pantallas generales sin filtrar."""
import streamlit as st
from services.web_auth_ui import session_token
from services.field_api import portal_data,eligible_workers,assign_task_locally,review_report,APIError
from services.field_reports import STATUS_LABELS, folio, INCIDENT_PREFIX
from services.field_reports_ui import render_report_photo


def assignment_candidates(token, task_id):
    try: return eligible_workers(task_id,token=token)
    except APIError as exc:
        if exc.status_code!=403: st.error(str(exc))
        return []


def render_portal():
    try:
        user, tasks, reports = portal_data(session_token())
    except (ValueError,PermissionError) as exc:
        st.error(str(exc))
        st.stop()
    st.title('Mi espacio Go2Win')
    st.caption('Solo se muestran actividades y reportes autorizados por tu rol, equipo y territorio.')
    st.button('Actualizar mi información')
    if user['role_key'] == 'coordinator':
        if not user['team'].strip():
            st.warning('Tu equipo aún no está configurado. Para asignar tareas, el administrador debe '
                       'asignarte el mismo equipo que tu personal en Administración de usuarios → Rol y equipo. '
                       'Ambos deben tener autorizada la campaña y el territorio de la tarea.')
        else:
            st.caption(f"Equipo: {user['team']}. Abre una tarea para elegir responsable y asignarla.")
    task_tab, report_tab, supporters_tab, needs_tab, surveys_tab = st.tabs(['Tareas', 'Reportes', 'Simpatizantes', 'Necesidades', 'Cuestionarios'])
    with surveys_tab:
        from services.field_surveys_ui import render_manager
        render_manager()
    with needs_tab:
        from services.field_needs_ui import render_needs
        render_needs()
    with supporters_tab:
        from services.supporters_ui import render_supporters
        render_supporters()
    with task_tab:
        if not tasks:
            st.info('No hay tareas visibles. Solicita al administrador revisar tu asignación y alcance.')
        for task in tasks:
            assignment_label = ' · Sin asignar' if task['worker_id'] is None else ''
            with st.expander(f"#{task['id']} · {task['activity_name']} · {task['status']}{assignment_label}"):
                st.text(task['activity_description'] or 'Sin descripción')
                st.write(f"{task['state']} / {task['municipality']} · Fecha: {task['due_date'] or 'Sin fecha'}")
                st.write(f"Responsable: {task['worker_name'] or 'Sin asignar'}")
                st.caption(f"Recepción: {task['received_at'] or 'Por confirmar'}")
                candidates = assignment_candidates(session_token(), task['id'])
                if candidates and task['status'] in {'Pendiente', 'En curso'}:
                    options = {w['id']: w['name'] for w in candidates}
                    with st.form(f"portal_assign_{task['id']}"):
                        ids = list(options)
                        selected = st.selectbox('Responsable', ids, format_func=options.get,
                                                index=ids.index(task['worker_id']) if task['worker_id'] in ids else 0)
                        if st.form_submit_button('Asignar tarea'):
                            try:
                                assign_task_locally(task['id'], selected, session_token=session_token())
                                st.rerun()
                            except (ValueError, PermissionError) as exc:
                                st.error(str(exc))
                elif user['role_key'] == 'coordinator' and task['status'] in {'Pendiente', 'En curso'}:
                    st.info('No hay responsables elegibles para esta tarea. Revisa con el administrador '
                            'que el personal esté activo, tenga rol de campo o supervisor, '
                            'pertenezca a tu equipo y tenga autorizados esta campaña y territorio.')
        st.caption('Confirma recepción y envía avances desde Telegram con /mis_tareas y /reportar.')
    with report_tab:
        if not reports:
            st.info('No hay reportes visibles en tu ámbito.')
        for report in reports:
            kind = 'Incidencia · ' if report['body'].startswith(INCIDENT_PREFIX) else ''
            with st.expander(f"{kind}{folio(report['id'])} · tarea #{report['task_id']} · {STATUS_LABELS[report['status']]}"):
                st.text(report['body'])
                render_report_photo(report['id'])
                st.caption(f"Enviado: {report['created_at']} UTC")
                st.text(report['note'] or 'Sin observaciones de revisión')
                allowed = report['can_review']
                if allowed and report['status'] == 'pending':
                    with st.form(f"portal_review_{report['id']}"):
                        decision = st.selectbox('Decisión', ['accepted','correction'], format_func=STATUS_LABELS.get)
                        note = st.text_area('Observaciones', max_chars=500)
                        if st.form_submit_button('Guardar revisión'):
                            try:
                                review_report(report['id'], decision, note, session_token=session_token())
                                st.rerun()
                            except (ValueError, PermissionError) as exc:
                                st.error(str(exc))
