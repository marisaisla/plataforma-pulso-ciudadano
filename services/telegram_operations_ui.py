"""Vinculación y registros de Telegram separados de la administración de usuarios."""
import streamlit as st
from services.field_api import require_admin,list_workers,issue_code,unlink_worker
from services.field_permissions import ROLE_LABELS


def _render_telegram_operations():
    require_admin()
    st.caption('Vincula las cuentas de Telegram y consulta simpatizantes y necesidades capturadas desde el bot. Los usuarios, roles y territorios se configuran en Administración de usuarios.')
    st.info('Las tareas se asignan y los reportes e incidencias se revisan desde Planes de acción.')
    linking,supporters,needs=st.tabs(['Vinculación de Telegram','Simpatizantes','Necesidades territoriales'])
    with linking:
        workers=list_workers()
        st.button('Actualizar estado de vinculación',key='telegram_refresh_link')
        if not workers:
            st.info('Primero registra al personal en Administración de usuarios.')
        else:
            st.dataframe([{'Folio':w['id'],'Nombre':w['name'],'Equipo':w['team'],
                           'Rol':ROLE_LABELS.get(w['role_key'],'Sin rol válido'),
                           'Acceso':'Activo' if w['active'] else 'Desactivado',
                           'Telegram':'Vinculado' if w['telegram_user_id'] is not None else 'Sin vincular'} for w in workers],
                          hide_index=True,width='stretch')
            selected=st.selectbox('Trabajador',[w['id'] for w in workers],
                                  format_func=lambda wid:next(f"{w['name']} · #{wid}" for w in workers if w['id']==wid),
                                  key='telegram_worker')
            worker=next(w for w in workers if w['id']==selected)
            if not worker['active']:
                st.warning('Este usuario está desactivado. Reactiva su acceso desde Administración de usuarios antes de generar un código.')
            if worker['active'] and worker['telegram_user_id'] is None:
                if st.button('Generar código de activación',key='telegram_issue_code'):
                    try:
                        code=issue_code(selected)
                        st.code(f'/start {code}',language=None)
                        st.info('Entrega el comando solo al trabajador seleccionado para que lo envíe al bot en privado. Vence en 30 minutos y se usa una vez. Un código nuevo invalida el anterior; cópialo antes de cambiar de pantalla.')
                    except ValueError as exc: st.error(str(exc))
            if worker['telegram_user_id'] is not None:
                st.success('La cuenta de Telegram está vinculada.')
                confirm=st.checkbox('Quiero retirar el vínculo con la cuenta actual',key=f'telegram_unlink_{selected}')
                if st.button('Desvincular Telegram',disabled=not confirm,key='telegram_unlink_button'):
                    unlink_worker(selected)
                    st.rerun()
    with supporters:
        from services.supporters_ui import render_supporters
        render_supporters()
    with needs:
        from services.field_needs_ui import render_needs
        render_needs()


def render_telegram_operations():
    from services.field_api import APIError
    try: _render_telegram_operations()
    except APIError as exc: st.error(str(exc))
