"""Asignación de actividades desde la consola local de coordinación."""
import streamlit as st

from services.field_tasks import assign_task_locally, eligible_workers, get_assignment, task_is_open
from services.web_auth_ui import require_admin, session_token


def render_task_assignment(task):
    require_admin()
    st.markdown('### Asignación a Telegram')
    current = get_assignment(task['id'])
    if current:
        st.write(f"Responsable de Telegram: **{current['name']}** · trabajador #{current['worker_id']}")
        st.write(f"Recepción: {current['received_at'] + ' UTC' if current['received_at'] else 'Por confirmar'}")
    else:
        st.caption('Sin trabajador asignado en Telegram. El nombre libre del responsable no vincula una cuenta automáticamente.')
    if not task_is_open(task):
        st.info('Las actividades concluidas o canceladas no aparecen en /mis_tareas y no admiten nuevas asignaciones.')
        return
    candidates = eligible_workers(task['id'])
    lookup = {w['id']: w for w in candidates}
    options = [None] + list(lookup)
    if current and current['worker_id'] not in options:
        options.append(current['worker_id'])
        st.warning('El responsable actual ya no tiene acceso operativo a esta actividad. Revisa su rol y alcance o reasigna.')
    def label(wid):
        if wid is None:
            return 'Sin asignar'
        if wid not in lookup:
            return f"{current['name']} · #{wid} (sin acceso actual)"
        worker = lookup[wid]
        return f"{worker['name']} · #{wid}" + (' (Telegram pendiente)' if worker['telegram_user_id'] is None else '')
    with st.form(f"telegram_assignment_{task['id']}"):
        selected = st.selectbox('Trabajador registrado', options,
                                index=options.index(current['worker_id']) if current else 0,
                                format_func=label)
        st.caption('Solo se ofrecen trabajadores activos con permiso de recepción para esta campaña y territorio. '
                   'Cambiar de trabajador reinicia la recepción y deja historial de la asignación anterior.')
        if st.form_submit_button('Guardar asignación de Telegram'):
            try:
                assign_task_locally(task['id'], selected, session_token=session_token())
                st.rerun()
            except (ValueError, PermissionError) as exc:
                st.error(str(exc))
    if not candidates:
        st.info('Configura el trabajador y su alcance en Personal y Telegram para poder asignarlo.')
    st.caption('La asignación estará disponible cuando el trabajador envíe /mis_tareas. No se envía aviso automático en esta etapa.')
