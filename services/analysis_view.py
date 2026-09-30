"""Análisis conjunto y exploración de resultados guardados."""
import pandas as pd
import altair as alt
import streamlit as st
from services.message_analysis import message_results, analyze_messages, APPROACHES
from services.settings import get_setting


def render_analysis(options):
    st.caption("Mensaje → análisis completo → gráficas y resultados. Consultar lo guardado no llama a la IA.")
    if not options:
        st.info("Primero crea un perfil y captura publicaciones.")
        return
    chosen = st.selectbox("Persona o perfil", list(options), key="analysis_profile")
    profile_id = options[chosen]
    messages = message_results(profile_id)
    if not messages:
        st.info("No hay mensajes. Obtén publicaciones en Fuentes y actualización.")
        return
    pending = [m for m in messages if m["missing"]]
    complete = len(messages) - len(pending)
    st.write(f"**{len(messages)} mensajes · {complete} completos · {len(pending)} pendientes de completar**")
    st.caption("Cada mensaje recibe sentimiento, necesidades, gestión, tipo de contenido y territorio. Se completan enfoques faltantes o básicos; las versiones anteriores quedan guardadas en el historial.")
    if pending:
        batch = st.number_input("Mensajes a completar en esta ejecución", 1, min(10, len(pending)), min(10, len(pending)), key=f"batch_{profile_id}_{len(pending)}")
        st.caption(f"Costo de API: hasta {batch} consultas, una por mensaje. El importe depende del modelo y del texto. No se ejecutan consultas al cambiar filtros o abrir resultados.")
    else:
        batch = 0
        st.success("Todos los mensajes tienen sus cinco análisis guardados.")
    if not get_setting("OPENAI_API_KEY"):
        st.info("Para analizar, configura OpenAI en Conexiones privadas.")
    if st.button("Analizar mensajes pendientes", type="primary", disabled=not pending or not get_setting("OPENAI_API_KEY")):
        with st.spinner("Completando los análisis de los mensajes…"):
            result = analyze_messages(profile_id, [m["id"] for m in pending[:batch]])
        st.session_state.complete_analysis_notice = result
        st.rerun()
    notice = st.session_state.pop("complete_analysis_notice", None)
    if notice:
        st.info(f"Mensajes completados: {notice['analyzed']}. Consultas intentadas: {notice['requests']}.")
        for error in notice["errors"]:
            st.warning(error)

    st.divider()
    st.subheader("Consultar resultados")
    st.caption("Estos filtros sólo cambian lo que ves. No generan consultas ni costos de IA.")
    frame = pd.DataFrame([{
        "id": m["id"], "fecha": m["published_at"] or m["collected_at"], "fuente": m["source_type"],
        "sentimiento": m["sentiment"], "tema": m["topic"], "estado": m["status"],
        "texto": f"{m['title'] or ''} {m['text'] or ''}",
    } for m in messages])
    frame["fecha"] = pd.to_datetime(frame["fecha"], errors="coerce", utc=True, format="mixed")
    source = st.selectbox("Fuente", ["Todas", *sorted(frame.fuente.unique())], key=f"result_source_{profile_id}")
    period = st.selectbox("Periodo", ["Todo el historial", "Últimos 7 días", "Últimos 30 días"], key=f"result_period_{profile_id}")
    sentiment = st.selectbox("Sentimiento", ["Todos", *sorted(frame.sentimiento.unique())], key=f"result_sentiment_{profile_id}")
    status = st.selectbox("Estado del análisis", ["Todos", "Completo", "Parcial", "Sin analizar"], key=f"result_status_{profile_id}")
    search = st.text_input("Buscar en los mensajes o temas", key=f"result_search_{profile_id}")
    if source != "Todas": frame = frame[frame.fuente == source]
    if period != "Todo el historial":
        frame = frame[frame.fecha >= pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=7 if period == "Últimos 7 días" else 30)]
    if sentiment != "Todos": frame = frame[frame.sentimiento == sentiment]
    if status != "Todos": frame = frame[frame.estado == status]
    if search: frame = frame[frame.texto.str.contains(search, case=False, regex=False) | frame.tema.str.contains(search, case=False, regex=False)]
    st.write(f"**{len(frame)} mensajes en esta selección**")
    if frame.empty:
        st.info("No hay mensajes que coincidan con estos filtros.")
        return
    known = frame[frame.sentimiento != "Sin analizar"]
    cols = st.columns(3)
    for column, name in zip(cols, ["Positivo", "Negativo", "Neutral"]):
        count = int((known.sentimiento == name).sum())
        column.metric(name, f"{count}", f"{count / len(known):.0%} de los clasificados" if len(known) else None, delta_color="off")
    st.caption("El sentimiento corresponde al enfoque Perfil político; si falta, se muestra la clasificación anterior. Mixto y No relacionado conservan su categoría. Estos mensajes no son una encuesta de aprobación.")
    if not known.empty:
        colors = alt.Scale(domain=["Positivo", "Negativo", "Neutral", "Mixto", "No relacionado"],
                           range=["#16a34a", "#dc2626", "#64748b", "#d97706", "#2563eb"])
        st.markdown("#### Distribución del sentimiento")
        distribution = known.groupby("sentimiento").size().reset_index(name="Mensajes")
        st.altair_chart(alt.Chart(distribution).mark_arc(innerRadius=65).encode(
            theta="Mensajes:Q", color=alt.Color("sentimiento:N", scale=colors),
            tooltip=["sentimiento:N", "Mensajes:Q"]), width="stretch")
        dated = known.dropna(subset=["fecha"])
        if not dated.empty:
            st.markdown("#### Evolución del sentimiento")
            timeline = dated.groupby([pd.Grouper(key="fecha", freq="6h"), "sentimiento"]).size().reset_index(name="Mensajes")
            st.altair_chart(alt.Chart(timeline).mark_line(point=True).encode(
                x="fecha:T", y="Mensajes:Q", color=alt.Color("sentimiento:N", scale=colors),
                tooltip=["fecha:T", "sentimiento:N", "Mensajes:Q"]), width="stretch")
            st.caption("Cantidad de mensajes por sentimiento en intervalos de seis horas.")
        st.markdown("#### Temas principales")
        st.bar_chart(known.groupby("tema").size().nlargest(10).rename("Mensajes"), horizontal=True)
    if frame.fecha.isna().any():
        st.caption("Los mensajes sin fecha interpretable se conservan en el detalle y no aparecen en la gráfica temporal.")

    st.subheader("Explorar mensajes")
    by_id = {m["id"]: m for m in messages}
    ids = frame.id.tolist()
    position_key = f"message_position_{profile_id}"
    selection_key = f"message_selection_{profile_id}"
    signature = tuple(ids)
    if st.session_state.get(selection_key) != signature:
        st.session_state[selection_key] = signature
        st.session_state[position_key] = 0
    position = min(st.session_state.get(position_key, 0), len(ids) - 1)
    left, middle, right = st.columns([1, 2, 1])
    if left.button("← Anterior", disabled=position == 0):
        st.session_state[position_key] = position - 1
        st.rerun()
    middle.write(f"Mensaje **{position + 1} de {len(ids)}**")
    if right.button("Siguiente →", disabled=position == len(ids) - 1):
        st.session_state[position_key] = position + 1
        st.rerun()
    message = by_id[ids[position]]
    with st.container(border=True):
        st.write(message["title"] or "Mensaje sin título")
        if message["text"] != message["title"]:
            st.write(message["text"] or "Sin texto adicional")
        st.caption(f"{message['source_name']} · {message['published_at'] or message['collected_at']} · {message['status']}")
        if (message["url"] or "").startswith(("http://", "https://")):
            st.link_button("Abrir publicación original", message["url"])
        for approach in APPROACHES.values():
            st.markdown(f"**{approach}**")
            result = message["results"].get(approach)
            if result:
                st.write(result["explanation"] or result["topic"])
                st.caption(f"Tema: {result['topic'] or 'Sin tema'} · Tipo: {result['content_type'] or 'Pendiente'} · Tono: {result['sentiment'] or 'Sin clasificar'} · Urgencia: {result['urgency'] or 'Sin clasificar'}")
                st.caption(f"Método: {result['method']} · Fecha: {result['analyzed_at']}")
            else:
                st.caption("Pendiente de completar. No se generó una interpretación nueva al abrir esta vista.")
        if message["legacy"]:
            with st.expander("Clasificación anterior conservada"):
                st.write(message["legacy"])
    with st.expander("Tabla de mensajes de esta selección"):
        st.dataframe(frame.drop(columns="id"), hide_index=True, width="stretch")
