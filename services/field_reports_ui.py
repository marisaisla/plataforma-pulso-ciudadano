"""Revisión de reportes en la consola local de Go2Win."""
import streamlit as st
from services.field_reports import list_task_reports, review_report, STATUS_LABELS, folio
from services.web_auth_ui import require_admin, session_token


def render_task_reports(task_id):
    require_admin()
    st.markdown('### Reportes de campo')
    reports = list_task_reports(task_id)
    if not reports:
        st.caption('Esta actividad aún no tiene reportes de texto enviados desde Telegram.')
        return
    st.caption('Revisión desde la consola local de coordinación. Aceptar un reporte no concluye la actividad. '
               'El trabajador consulta la decisión con /mis_reportes; no se envía aviso automático.')
    for report in reports:
        with st.expander(f"{folio(report['id'])} · {report['name']} · {STATUS_LABELS[report['status']]}",
                         expanded=report['status'] == 'pending'):
            st.caption(f"Enviado: {report['created_at']} UTC · trabajador #{report['worker_id']}")
            st.text(report['body'])
            if report['status'] != 'pending':
                st.write(f"Revisión: {report['note'] or 'Sin observaciones'}")
                st.caption(f"{report['reviewed_at']} UTC · {report['actor']}")
                continue
            with st.form(f"report_review_{report['id']}"):
                decision = st.selectbox('Decisión', ['accepted', 'correction'],
                                        format_func=lambda x: 'Aceptar reporte' if x == 'accepted' else 'Solicitar corrección')
                note = st.text_area('Observaciones (obligatorias para corrección)', max_chars=500)
                if st.form_submit_button('Guardar revisión'):
                    try:
                        review_report(report['id'], decision, note, session_token=session_token())
                        st.rerun()
                    except (ValueError, PermissionError) as exc:
                        st.error(str(exc))
