"""Panel autenticado para roles operativos; no abre pantallas generales sin filtrar."""
from contextlib import closing
import streamlit as st
from services.database import connection
from services.web_auth import require_user
from services.web_auth_ui import session_token
from services.field_permissions import can_access
from services.field_tasks import context, eligible_workers, assign_task_locally
from services.field_reports import review_report, STATUS_LABELS, folio


def portal_data(token):
    with closing(connection()) as conn:
        user = require_user(token, conn)
        tasks = [dict(t) for t in conn.execute('''SELECT t.*, a.worker_id, a.received_at, w.name AS worker_name
            FROM territorial_action_plans t LEFT JOIN field_task_assignments a ON a.task_id=t.id
            LEFT JOIN field_workers w ON w.id=a.worker_id ORDER BY t.id DESC''')
            if can_access(user['id'], 'tasks.view', conn=conn, **context(t, t['worker_id']))]
        reports = [dict(r) for r in conn.execute('''SELECT r.*, t.profile_id, t.state, t.municipality,
            v.note FROM field_reports r JOIN territorial_action_plans t ON t.id=r.task_id
            LEFT JOIN field_report_reviews v ON v.report_id=r.id ORDER BY r.id DESC''')
            if can_access(user['id'], 'reports.view', conn=conn, **context(r, r['worker_id']))]
        return user, tasks, reports


def assignment_candidates(token, task_id):
    with closing(connection()) as conn:
        user = require_user(token, conn)
        task = conn.execute('SELECT * FROM territorial_action_plans WHERE id=?', (task_id,)).fetchone()
        previous = conn.execute('SELECT worker_id FROM field_task_assignments WHERE task_id=?', (task_id,)).fetchone()
        if task is None or (previous and not can_access(user['id'], 'tasks.assign', conn=conn,
                                                       **context(task, previous['worker_id']))):
            return []
        return [w for w in eligible_workers(task_id) if can_access(user['id'], 'tasks.assign', conn=conn,
                                                                  **context(task, w['id']))]


def render_portal():
    try:
        user, tasks, reports = portal_data(session_token())
    except PermissionError as exc:
        st.error(str(exc))
        st.stop()
    st.title('Mi espacio Go2Win')
    st.caption('Solo se muestran actividades y reportes autorizados por tu rol, equipo y territorio.')
    st.button('Actualizar mi información')
    if user['role_key'] == 'coordinator':
        if not user['team'].strip():
            st.warning('Tu equipo aún no está configurado. Para asignar tareas, el administrador debe '
                       'asignarte el mismo equipo que tu personal en Personal y Telegram → Rol y equipo. '
                       'Ambos deben tener autorizada la campaña y el territorio de la tarea.')
        else:
            st.caption(f"Equipo: {user['team']}. Abre una tarea para elegir responsable y asignarla.")
    task_tab, report_tab = st.tabs(['Tareas', 'Reportes'])
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
            with st.expander(f"{folio(report['id'])} · tarea #{report['task_id']} · {STATUS_LABELS[report['status']]}"):
                st.text(report['body'])
                st.caption(f"Enviado: {report['created_at']} UTC")
                st.text(report['note'] or 'Sin observaciones de revisión')
                allowed = (report['worker_id'] != user['id'] and can_access(user['id'], 'reports.review',
                                                                           **context(report, report['worker_id'])))
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
