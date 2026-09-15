from datetime import date
import json
from pathlib import Path
import unicodedata

import pandas as pd
import pydeck as pdk
import requests
import streamlit as st
import streamlit.components.v1 as components

from services.database import DB_PATH, execute, initialize_database, query, record_obtainment_run
from services.capture import (
    analyze_pending,
    capture_media_headlines,
    capture_rss,
    capture_x_search,
    discover_rss,
    analyze_with_openai,
    analyze_approach_with_openai,
    matches_profile,
    run_prompt_query,
)
from services.settings import get_setting, import_private_setting, save_settings
from services.gis import (
    LAYER_INDICATOR_GROUPS,
    PED_SONORA_REGIONS,
    PED_SONORA_REGION_PROFILES,
    attach_district_results,
    attach_election_results,
    attach_ped_sonora_regions,
    attach_section_results,
    attach_indicator_values,
    available_indicators,
    colorize_geojson,
    contextual_view,
    load_electoral_sections_context,
    load_local_district_context,
    load_municipal_context,
    load_sonora_electoral_sections_context,
    load_sonora_local_district_context,
    municipal_dataframe,
)
from services.elections import (
    decode_election_rows,
    election_template_csv,
    fetch_sonora_local_district_2024,
    fetch_sonora_local_sections_2024,
    fetch_sonora_municipal_2024,
    parse_municipal_results,
)
from services.inegi import INDICATOR_GROUPS, collect_municipal_indicator, search_indicator_catalog
from services.territorial_pulse import (
    municipal_pulse_summary,
    rebuild_explicit_municipality_links,
)


st.set_page_config(page_title="Pulso Ciudadano · Dominio territorial", page_icon="📍", layout="wide")
initialize_database()

st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #083344 0%, #0f4c5c 48%, #0b2533 100%);
    }
    [data-testid="stSidebar"] * {
        color: #f8fafc;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label {
        background: rgba(255,255,255,.08);
        border: 1px solid rgba(255,255,255,.10);
        border-radius: 10px;
        margin: 3px 0;
        padding: 7px 10px;
        transition: background .2s ease;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
        background: rgba(255,255,255,.18);
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label p {
        font-weight: 600;
    }
    .pulso-kicker {
        color: #7dd3fc;
        font-size: .72rem;
        font-weight: 700;
        letter-spacing: .12em;
        margin-bottom: .35rem;
    }
    .pulso-title {
        color: #ffffff;
        font-size: 1.55rem;
        font-weight: 750;
        line-height: 1.05;
        margin-bottom: .5rem;
    }
    .pulso-subtitle {
        color: #cbd5e1;
        font-size: .82rem;
        line-height: 1.4;
        margin-bottom: 1rem;
    }
    .pulso-badge {
        display: inline-block;
        padding: .25rem .55rem;
        border: 1px solid rgba(125,211,252,.65);
        border-radius: 999px;
        color: #bae6fd;
        font-size: .72rem;
        font-weight: 700;
    }
    .stApp {
        background:
            radial-gradient(circle at 92% 3%, rgba(14, 116, 144, .12), transparent 30rem),
            linear-gradient(180deg, #f8fbfd 0%, #f1f5f9 100%);
    }
    .main .block-container {
        max-width: 1450px;
        padding-top: 2rem;
        padding-bottom: 3.5rem;
    }
    .domain-hero {
        position: relative;
        overflow: hidden;
        margin: 0 0 1.4rem 0;
        padding: 1.7rem 2rem;
        border-radius: 22px;
        color: #f8fafc;
        background: linear-gradient(122deg, var(--domain-dark), var(--domain-accent));
        box-shadow: 0 16px 36px rgba(15, 23, 42, .16);
    }
    .domain-hero:after {
        content: '';
        position: absolute;
        width: 280px;
        height: 280px;
        right: -70px;
        top: -170px;
        border: 34px solid rgba(255, 255, 255, .12);
        border-radius: 50%;
    }
    .domain-eyebrow {
        margin-bottom: .38rem;
        color: rgba(255,255,255,.72);
        font-size: .72rem;
        font-weight: 750;
        letter-spacing: .14em;
    }
    .domain-title {
        position: relative;
        z-index: 1;
        margin: 0 0 .42rem 0;
        color: #fff;
        font-size: 2rem;
        font-weight: 760;
        letter-spacing: -.035em;
    }
    .domain-description {
        position: relative;
        z-index: 1;
        max-width: 760px;
        margin: 0;
        color: rgba(255,255,255,.88);
        font-size: 1rem;
        line-height: 1.5;
    }
    .domain-section {
        margin: 1.6rem 0 .55rem;
        color: #0f172a;
        font-size: 1.15rem;
        font-weight: 750;
        letter-spacing: -.015em;
    }
    .domain-note {
        padding: .85rem 1rem;
        border-left: 4px solid #0f766e;
        border-radius: 0 12px 12px 0;
        background: #ecfeff;
        color: #164e63;
        font-size: .9rem;
    }
    [data-testid="stMetric"] {
        padding: .95rem 1rem;
        border: 1px solid #dbe5ec;
        border-radius: 14px;
        background: rgba(255,255,255,.92);
        box-shadow: 0 4px 12px rgba(15, 23, 42, .05);
    }
    [data-testid="stMetricLabel"] {
        color: #475569;
        font-size: .76rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: .045em;
    }
    [data-testid="stMetricValue"] { color: #0f172a; }
    [data-testid="stDataFrame"] {
        overflow: hidden;
        border: 1px solid #dbe5ec;
        border-radius: 14px;
        background: #fff;
    }
    div[data-testid="stExpander"] {
        border: 1px solid #dbe5ec;
        border-radius: 14px;
        background: rgba(255,255,255,.88);
    }
    .stButton > button, .stDownloadButton > button, .stLinkButton > a {
        border-radius: 10px;
        font-weight: 650;
    }
    [data-testid="stSidebar"] .pulso-subtitle { max-width: 220px; }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
        color: #a5d8e8;
        font-weight: 700;
        font-size: .68rem;
        letter-spacing: .08em;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

ACTOR_TYPES = ["Persona", "Partido político", "Institución pública", "Tema sin actor"]
CONDITIONS = ["Candidato/a", "En funciones", "Exfuncionario/a", "Otro"]
TERRITORY_TYPES = ["Estado", "Municipio", "Distrito", "Sección electoral", "Colonia", "Localidad"]
SOURCE_TYPES = [
    "X", "YouTube", "RSS", "Medio digital", "Fuente institucional",
    "Encuesta", "INEGI/DENUE", "Otra",
]
ELECTORAL_VOTE_LABELS = {
    "votes_pan": "PAN", "votes_pri": "PRI", "votes_prd": "PRD", "votes_pvem": "PVEM",
    "votes_pt": "PT", "votes_mc": "Movimiento Ciudadano", "votes_morena": "Morena",
    "votes_nueva_alianza": "Nueva Alianza", "votes_encuentro_solidario_sonora": "PES Sonora",
    "votes_partido_sonorense": "Partido Sonorense", "votes_coalicion_pan_pri_prd": "Coalición PAN-PRI-PRD",
    "votes_coalicion_pan_pri": "Coalición PAN-PRI", "votes_coalicion_pan_prd": "Coalición PAN-PRD",
    "votes_coalicion_pri_prd": "Coalición PRI-PRD",
    "votes_sigamos_haciendo_historia": "Sigamos Haciendo Historia",
    "votes_fuerza_y_corazon_sonora": "Fuerza y Corazón por Sonora",
    "votes_naem": "Nueva Alianza Estado de México",
    "votes_pan_pri_prd_naem": "Candidatura común PAN-PRI-PRD-NAEM",
    "votes_pvem_pt_morena": "Coalición PVEM-PT-Morena",
    "votes_pvem_pt_morena_naem": "Candidatura común PVEM-PT-Morena-NAEM",
    "votes_pvem_pt": "Coalición PVEM-PT",
    "votes_pvem_morena": "Coalición PVEM-Morena",
    "votes_pt_morena": "Coalición PT-Morena",
    "votes_pan_pri_prd": "Coalición PAN-PRI-PRD",
    "votes_pan_pri_naem": "Candidatura común PAN-PRI-NAEM",
    "votes_pan_prd_naem": "Candidatura común PAN-PRD-NAEM",
    "votes_pri_prd_naem": "Candidatura común PRI-PRD-NAEM",
    "votes_pan_naem": "Candidatura común PAN-NAEM",
    "votes_pri_naem": "Candidatura común PRI-NAEM",
    "votes_prd_naem": "Candidatura común PRD-NAEM",
    "votes_cc_pan_pri_prd_naem": "Candidatura común PAN-PRI-PRD-NAEM",
    "votes_cc_pvem_pt_morena": "Candidatura común PVEM-PT-Morena",
    "votes_pes": "Partido Encuentro Solidario", "votes_rsp": "Redes Sociales Progresistas",
    "votes_fxm": "Fuerza por México",
    "votes_pt_morena_naem": "Coalición PT-Morena-NAEM",
    "votes_cc_pt_morena_naem": "Candidatura común PT-Morena-NAEM",
    "votes_va_por_sonora": "Va por Sonora",
    "votes_juntos_haremos_historia_sonora": "Juntos Haremos Historia en Sonora",
}


def render_electoral_breakdown(payload: dict) -> None:
    """Render the official party/coalition columns available for one territory."""
    party_rows = [
        {"Partido o candidatura": label, "Votos": float(payload.get(key) or 0)}
        for key, label in ELECTORAL_VOTE_LABELS.items() if float(payload.get(key) or 0) > 0
    ]
    if not party_rows:
        st.caption("La base oficial no contiene columnas partidistas con voto para este territorio.")
        return
    party_frame = pd.DataFrame(party_rows).sort_values("Votos", ascending=False)
    chart_column, table_column = st.columns([1, 1])
    with chart_column:
        st.caption("Votación por partido o candidatura publicada")
        st.bar_chart(party_frame.set_index("Partido o candidatura"), height=250)
    with table_column:
        st.dataframe(
            party_frame, use_container_width=True, hide_index=True,
            column_config={"Votos": st.column_config.NumberColumn(format="%,d")},
        )
    st.caption("Las coaliciones y candidaturas comunes se muestran tal como fueron publicadas por la autoridad electoral.")


def profile_options() -> dict[str, int]:
    rows = query("SELECT id, name FROM profiles WHERE active = 1 ORDER BY name")
    return {f"{row['name']} (#{row['id']})": row["id"] for row in rows}


def municipality_match_key(value: object) -> str:
    """Compare municipality names without differences caused by accents or case."""
    normalized = unicodedata.normalize("NFD", str(value or "").casefold())
    return "".join(character for character in normalized if unicodedata.category(character) != "Mn").strip()


DOMAIN_PRESENTATION = {
    "Dominio territorial": {
        "eyebrow": "DOMINIO TERRITORIAL · VISOR INTEGRADO",
        "description": "Empieza en el mapa, selecciona un municipio y consulta en un solo lugar su ficha territorial, electoral e INEGI.",
        "dark": "#0f3b52",
        "accent": "#0f766e",
    },
    "Territorio": {
        "eyebrow": "DOMINIO TERRITORIAL · GEOGRAFÍA BASE",
        "description": "Ubica municipios, consulta su ficha territorial y navega el mapa como punto de partida para la toma de decisiones.",
        "dark": "#0f3b52",
        "accent": "#0f766e",
    },
    "Visor electoral": {
        "eyebrow": "DOMINIO TERRITORIAL · VISOR ELECTORAL",
        "description": "Navega resultados y participación por distrito local, municipio o sección electoral desde una vista especializada.",
        "dark": "#713f12",
        "accent": "#b45309",
    },
    "Electoral": {
        "eyebrow": "DOMINIO TERRITORIAL · LECTURA ELECTORAL",
        "description": "Revisa resultados, participación y votación por municipio, distrito local o sección electoral.",
        "dark": "#713f12",
        "accent": "#b45309",
    },
    "INEGI": {
        "eyebrow": "DOMINIO TERRITORIAL · CONTEXTO SOCIODEMOGRÁFICO",
        "description": "Compara indicadores oficiales para comprender población, vivienda, servicios y condiciones sociales por municipio.",
        "dark": "#312e81",
        "accent": "#6d28d9",
    },
    "Diagnóstico regional del PED": {
        "eyebrow": "DOMINIO TERRITORIAL · PLANEACIÓN REGIONAL",
        "description": "Explora las regiones del PED de Sonora y consulta los retos, vocaciones y municipios que las integran.",
        "dark": "#164e63",
        "accent": "#0e7490",
    },
}

def render_domain_header(domain: str) -> None:
    presentation = DOMAIN_PRESENTATION[domain]
    st.markdown(
        f"""
        <section class="domain-hero" style="--domain-dark:{presentation['dark']}; --domain-accent:{presentation['accent']};">
            <div class="domain-eyebrow">{presentation['eyebrow']}</div>
            <h1 class="domain-title">{domain}</h1>
            <p class="domain-description">{presentation['description']}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


OBJECTIVE_NAVIGATION = {
    "ⓘ  Objetivo del proyecto": "Inicio",
}
INFORMATION_NAVIGATION = {
    "01  Perfiles y trayectorias": "Perfiles y trayectorias",
    "02  Territorio y fuentes": "Territorio y fuentes",
    "03  Perfil territorial": "Perfil territorial",
    "04  Conexiones privadas": "Configuración de conexiones",
    "05  Obtención de información": "Obtención de información",
    "06  Bandeja de registros": "Bandeja de registros",
    "07  Vinculación territorial": "Vinculación territorial",
}
ANALYSIS_NAVIGATION = {
    "08  Diagnóstico territorial": "Diagnóstico territorial",
    "09  Priorización territorial": "Priorización territorial",
    "10  Visor territorial": "Dominio territorial",
    "11  Visor electoral": "Visor electoral",
    "12  Diagnóstico regional del PED": "Diagnóstico regional del PED",
    "13  Enfoques de análisis": "Enfoques de análisis",
    "14  Prompts y consultas IA": "Prompts y consultas IA",
    "15  Revisión e historial": "Revisión e historial",
}
STRATEGY_NAVIGATION = {
    "16  Estrategia territorial": "Estrategia territorial",
    "17  Planes de acción": "Planes de acción",
    "18  CRM territorial electoral": "CRM territorial electoral",
    "19  Seguimiento de campo": "Seguimiento de campo",
}
COORDINATION_NAVIGATION = {
    "20  Planeación estratégica": "Planeación",
    "21  Tableros y reportes": "Tableros y reportes",
    "22  Alertas territoriales": "Alertas territoriales",
    "23  Modelos y aprendizaje": "Machine Learning",
    "?  Manual de usuario": "Manual de usuario",
    "?  Manual técnico": "Manual técnico",
}


NAVIGATION_WIDGET_KEYS = (
    "objective_navigation", "information_navigation", "analysis_navigation",
    "strategy_navigation", "coordination_navigation",
)

FUTURE_MODULES = {
    "Estrategia territorial": {
        "subtitle": "Convierte hallazgos en prioridades, objetivos y tácticas por distrito, municipio, sección y localidad.",
        "inputs": "Resultados electorales, indicadores, escucha ciudadana, encuestas, estructura y hallazgos de campo.",
        "output": "Prioridades territoriales y tácticas documentadas.",
    },
    "Planes de acción": {
        "subtitle": "Organiza la ejecución de la estrategia mediante actividades, responsables, fechas, metas, evidencias y estatus.",
        "inputs": "Estrategia territorial, tácticas, responsables y cobertura disponible.",
        "output": "Agenda territorial medible y lista de pendientes.",
    },
    "CRM territorial electoral": {
        "subtitle": "Coordina equipos, responsables, territorios asignados, compromisos y tareas de operación autorizadas.",
        "inputs": "Estructura territorial, actividades, compromisos y evidencias agregadas.",
        "output": "Cobertura, responsables y avances por territorio, sin perfiles individuales de electores.",
    },
    "Seguimiento de campo": {
        "subtitle": "Registra recorridos, reuniones, consultas de campo, incidencias, resultados y retroalimentación territorial.",
        "inputs": "Planes de acción, actividades, necesidades y compromisos.",
        "output": "Evidencia de ejecución y ajustes informados a la estrategia.",
    },
    "Tableros y reportes": {
        "subtitle": "Presenta cortes ejecutivos sobre información, análisis, estrategia, ejecución y cobertura territorial.",
        "inputs": "Información integrada y avances de los módulos operativos.",
        "output": "Reportes para coordinación y equipos territoriales.",
    },
    "Alertas territoriales": {
        "subtitle": "Identifica cambios relevantes, vacíos de cobertura, necesidades recurrentes y actividades pendientes.",
        "inputs": "Indicadores, análisis, cobertura territorial y seguimiento de campo.",
        "output": "Prioridades que requieren revisión o acción oportuna.",
    },
}


def select_navigation(widget_key: str, items: dict[str, str]) -> None:
    st.session_state["active_page"] = items[st.session_state[widget_key]]
    for key in NAVIGATION_WIDGET_KEYS:
        if key != widget_key:
            st.session_state[key] = None


def render_territorial_diagnosis() -> None:
    """Aggregate existing, traceable information; this screen never captures data."""
    st.subheader("Diagnóstico territorial")
    st.caption(
        "Integra la información ya guardada para reconocer concentración territorial, tono, temas y urgencias. "
        "No consulta fuentes externas ni asigna ubicaciones que no estén explícitamente registradas."
    )
    options = profile_options()
    if not options:
        st.info("Primero crea un perfil y carga información para poder elaborar un diagnóstico.")
        return
    chosen_profile = st.selectbox("Perfil a diagnosticar", list(options), key="diagnosis_profile")
    profile_id = options[chosen_profile]
    states = profile_states(profile_id)
    if not states:
        st.info("Asigna un territorio al perfil para organizar el diagnóstico por estado.")
        return
    selected_state = st.selectbox("Estado", states, key="diagnosis_state")

    municipality_options = query(
        """
        SELECT municipality FROM territorial_election_results WHERE state = ?
        UNION
        SELECT municipality FROM territorial_indicators WHERE state = ?
        UNION
        SELECT municipality FROM publication_territories
        WHERE state = ? AND municipality IS NOT NULL
        ORDER BY municipality
        """,
        (selected_state, selected_state, selected_state),
    )
    municipalities = [row["municipality"] for row in municipality_options if row["municipality"]]
    if not municipalities:
        st.info(
            "No hay municipios cargados para este estado. Integra resultados electorales o indicadores INEGI "
            "desde Territorio y fuentes para iniciar el diagnóstico."
        )
        return
    selected_municipality = st.selectbox(
        "Municipio", municipalities, key=f"diagnosis_municipality_{selected_state}"
    )
    election_rows = query(
        """
        SELECT payload, election_type, election_year, source
        FROM territorial_election_results
        WHERE state = ? AND municipality = ?
        ORDER BY election_year DESC, imported_at DESC LIMIT 1
        """,
        (selected_state, selected_municipality),
    )
    election = json.loads(election_rows[0]["payload"]) if election_rows else {}
    selected_party_label = None
    selected_party_votes = 0
    party_share = 0.0
    party_rank = None
    votes_df = pd.DataFrame(columns=["Opción", "Votos"])
    territorial_messages = query(
        """
        SELECT COUNT(DISTINCT p.id) AS publicaciones,
               SUM(CASE WHEN a.id IS NOT NULL THEN 1 ELSE 0 END) AS analizadas,
               SUM(CASE WHEN a.urgency IN ('Alta', 'Crítica') THEN 1 ELSE 0 END) AS urgentes
        FROM publication_territories pt
        JOIN publications p ON p.id = pt.publication_id
        LEFT JOIN analyses a ON a.publication_id = p.id
        WHERE p.profile_id = ? AND pt.state = ? AND pt.municipality = ?
        """,
        (profile_id, selected_state, selected_municipality),
    )[0]

    st.markdown("### Ficha territorial · " + selected_municipality)
    if election:
        election_metrics = st.columns(4)
        election_metrics[0].metric("Lista nominal", f"{int(election.get('lista_nominal') or 0):,}")
        election_metrics[1].metric("Participación", f"{float(election.get('participacion_pct') or 0):.1f}%")
        election_metrics[2].metric("Votos totales", f"{int(election.get('votes_total') or 0):,}")
        election_metrics[3].metric("Votos válidos", f"{int(election.get('numero_votos_validos') or 0):,}")
        st.caption(
            f"Resultado disponible: {election_rows[0]['election_type']} {election_rows[0]['election_year']}. "
            f"Fuente: {election_rows[0]['source'] or 'registro local'}"
        )
        vote_rows = []
        for key, value in election.items():
            if key.startswith("votes_") and float(value or 0) > 0:
                vote_rows.append({
                    "clave": key,
                    "Opción": key.replace("votes_", "").replace("_", " ").upper(),
                    "Votos": int(float(value)),
                })
        if vote_rows:
            votes_df = pd.DataFrame(vote_rows).sort_values("Votos", ascending=False)
            party_labels = dict(zip(votes_df["Opción"], votes_df["clave"]))
            selected_party_label = st.selectbox(
                "Partido o coalición a revisar",
                list(party_labels),
                key=f"diagnosis_party_{selected_state}_{selected_municipality}",
            )
            selected_party_votes = int(
                votes_df.loc[votes_df["Opción"] == selected_party_label, "Votos"].iloc[0]
            )
            valid_votes = float(election.get("numero_votos_validos") or 0)
            party_share = (selected_party_votes / valid_votes * 100) if valid_votes else 0
            party_rank = int(votes_df.index.get_loc(
                votes_df.loc[votes_df["Opción"] == selected_party_label].index[0]
            )) + 1
            party_metrics = st.columns(4)
            party_metrics[0].metric("Opción seleccionada", selected_party_label)
            party_metrics[1].metric("Votos", f"{selected_party_votes:,}")
            party_metrics[2].metric("Porcentaje de votos válidos", f"{party_share:.1f}%")
            party_metrics[3].metric("Posición en el municipio", f"#{party_rank} de {len(votes_df)}")
            vote_left, vote_right = st.columns([1.2, 1])
            with vote_left:
                st.markdown("#### Votación por opción")
                st.bar_chart(votes_df.set_index("Opción")[["Votos"]], horizontal=True)
            with vote_right:
                st.dataframe(votes_df[["Opción", "Votos"]], use_container_width=True, hide_index=True)
    else:
        st.warning(
            "Este municipio todavía no tiene resultados electorales cargados. "
            "El diagnóstico conserva sus indicadores y cobertura disponible."
        )

    indicator_rows = query(
        """
        SELECT indicator_name AS indicador, value AS valor, unit AS unidad, period AS periodo
        FROM territorial_indicators
        WHERE state = ? AND municipality = ?
        ORDER BY indicator_name
        """,
        (selected_state, selected_municipality),
    )
    information_metrics = st.columns(3)
    information_metrics[0].metric("Indicadores INEGI", len(indicator_rows))
    information_metrics[1].metric("Mensajes vinculados", int(territorial_messages["publicaciones"] or 0))
    information_metrics[2].metric("Mensajes urgentes", int(territorial_messages["urgentes"] or 0))
    if indicator_rows:
        st.markdown("#### Indicadores disponibles")
        st.dataframe(pd.DataFrame(indicator_rows), use_container_width=True, hide_index=True)

    municipality_rows = municipal_pulse_summary(profile_id, selected_state)
    if municipality_rows:
        municipality_df = pd.DataFrame(municipality_rows)
        numeric_columns = ["publications", "positive", "negative", "neutral", "high_urgency"]
        for column in numeric_columns:
            municipality_df[column] = pd.to_numeric(municipality_df[column], errors="coerce").fillna(0).astype(int)
        municipality_df["balance"] = municipality_df["positive"] - municipality_df["negative"]
        municipality_df = municipality_df.sort_values(
            ["publications", "high_urgency"], ascending=[False, False]
        )
        st.markdown("### Contexto de conversación estatal")
        st.caption("Solo incluye municipios escritos expresamente en los mensajes o títulos guardados.")
        overview, tone = st.columns([1.2, 1])
        with overview:
            st.bar_chart(municipality_df.set_index("municipality")["publications"], horizontal=True)
        with tone:
            st.bar_chart(municipality_df.set_index("municipality")[["positive", "negative", "neutral"]], horizontal=True)
        st.dataframe(
            municipality_df.rename(
                columns={
                    "municipality": "Municipio", "publications": "Mensajes", "positive": "Positivos",
                    "negative": "Negativos", "neutral": "Neutros", "high_urgency": "Urgencia alta",
                    "balance": "Balance",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info(
            "Aún no hay mensajes vinculados explícitamente a municipios de este estado. "
            "La información general del perfil se conserva, pero todavía no permite un diagnóstico municipal."
        )

    topic_rows = query(
        """
        SELECT COALESCE(NULLIF(TRIM(a.topic), ''), 'Sin tema') AS tema,
               COUNT(DISTINCT p.id) AS mensajes,
               SUM(CASE WHEN a.urgency IN ('Alta', 'Crítica') THEN 1 ELSE 0 END) AS urgencia_alta
        FROM publication_territories pt
        JOIN publications p ON p.id = pt.publication_id
        JOIN analyses a ON a.publication_id = p.id
        WHERE p.profile_id = ? AND pt.state = ? AND pt.municipality = ?
        GROUP BY COALESCE(NULLIF(TRIM(a.topic), ''), 'Sin tema')
        ORDER BY mensajes DESC, urgencia_alta DESC
        LIMIT 10
        """,
        (profile_id, selected_state, selected_municipality),
    )
    source_rows = query(
        """
        SELECT s.name AS fuente, s.source_type AS tipo, COUNT(DISTINCT p.id) AS mensajes
        FROM publication_territories pt
        JOIN publications p ON p.id = pt.publication_id
        JOIN sources s ON s.id = p.source_id
        WHERE p.profile_id = ? AND pt.state = ? AND pt.municipality = ?
        GROUP BY s.id, s.name, s.source_type
        ORDER BY mensajes DESC, fuente
        LIMIT 10
        """,
        (profile_id, selected_state, selected_municipality),
    )
    left, right = st.columns(2)
    with left:
        st.markdown("### Temas que requieren lectura")
        if topic_rows:
            topic_df = pd.DataFrame(topic_rows)
            st.bar_chart(topic_df.set_index("tema")[["mensajes", "urgencia_alta"]], horizontal=True)
            st.dataframe(topic_df, use_container_width=True, hide_index=True)
        else:
            st.caption("Se requiere análisis de mensajes vinculados al estado para agrupar temas.")
    with right:
        st.markdown("### Fuentes con presencia territorial")
        if source_rows:
            st.dataframe(pd.DataFrame(source_rows), use_container_width=True, hide_index=True)
        else:
            st.caption("Aún no hay fuentes con mensajes vinculados a este estado.")

    st.markdown("### Preguntas de diagnóstico")
    question_options = [
        "¿Cómo quedó el partido o coalición seleccionado en este municipio?",
        "¿Qué opción ganó la elección municipal disponible?",
        "¿La participación del municipio está por encima o por debajo del promedio estatal?",
        "¿Qué peso electoral tiene este municipio dentro del estado?",
        "¿Qué información social disponible describe al municipio?",
        "¿Qué temas y mensajes requieren revisión en este municipio?",
    ]
    selected_question = st.selectbox(
        "Elige una pregunta", question_options, key=f"diagnosis_question_{selected_state}_{selected_municipality}"
    )
    state_election_rows = query(
        "SELECT payload FROM territorial_election_results WHERE state = ? AND election_type = 'Ayuntamientos' AND election_year = 2024",
        (selected_state,),
    )
    state_elections = []
    for row in state_election_rows:
        try:
            state_elections.append(json.loads(row["payload"]))
        except (TypeError, json.JSONDecodeError):
            continue
    state_nominal = sum(float(row.get("lista_nominal") or 0) for row in state_elections)
    state_votes = sum(float(row.get("votes_total") or 0) for row in state_elections)
    state_participation = (state_votes / state_nominal * 100) if state_nominal else 0
    answer = ""
    answer_source = ""
    if selected_question == question_options[0]:
        if selected_party_label:
            answer = (
                f"**{selected_party_label}** obtuvo **{selected_party_votes:,} votos** en {selected_municipality}, "
                f"equivalentes a **{party_share:.1f}% de los votos válidos**. "
                f"Ocupó la posición **{party_rank} de {len(votes_df)}** entre las opciones con votación."
            )
            answer_source = "Resultado municipal de ayuntamientos 2024 cargado en la plataforma."
        else:
            answer = "No hay una votación por partido o coalición disponible para contestar esta pregunta."
    elif selected_question == question_options[1]:
        if not votes_df.empty:
            winner = votes_df.iloc[0]
            valid_votes = float(election.get("numero_votos_validos") or 0)
            winner_share = (float(winner["Votos"]) / valid_votes * 100) if valid_votes else 0
            answer = (
                f"La opción con mayor votación registrada fue **{winner['Opción']}**, con "
                f"**{int(winner['Votos']):,} votos** ({winner_share:.1f}% de los votos válidos)."
            )
            answer_source = "Resultado municipal de ayuntamientos 2024 cargado en la plataforma."
        else:
            answer = "No hay resultados electorales municipales disponibles para identificar una opción ganadora."
    elif selected_question == question_options[2]:
        if election and state_participation:
            local_participation = float(election.get("participacion_pct") or 0)
            difference = local_participation - state_participation
            position = "por encima" if difference > 0 else "por debajo" if difference < 0 else "en el mismo nivel que"
            answer = (
                f"La participación de {selected_municipality} fue **{local_participation:.1f}%**, "
                f"{position} el promedio estatal ponderado de **{state_participation:.1f}%** "
                f"por **{abs(difference):.1f} puntos porcentuales**."
            )
            answer_source = "Cálculo propio con resultados municipales de ayuntamientos 2024 cargados para el estado."
        else:
            answer = "Faltan resultados electorales municipales suficientes para comparar la participación."
    elif selected_question == question_options[3]:
        local_nominal = float(election.get("lista_nominal") or 0) if election else 0
        if local_nominal and state_nominal:
            share = local_nominal / state_nominal * 100
            answer = (
                f"{selected_municipality} registra una lista nominal de **{int(local_nominal):,} personas**, "
                f"equivalente a **{share:.2f}%** de la lista nominal municipal integrada para {selected_state}."
            )
            answer_source = "Cálculo propio con resultados municipales de ayuntamientos 2024 cargados para el estado."
        else:
            answer = "Falta lista nominal electoral para estimar el peso territorial del municipio."
    elif selected_question == question_options[4]:
        if indicator_rows:
            preview = "; ".join(
                f"{row['indicador']}: {row['valor']} {row['unidad'] or ''} ({row['periodo']})".strip()
                for row in indicator_rows[:4]
            )
            answer = f"Hay **{len(indicator_rows)} indicadores** disponibles para {selected_municipality}. Destacan: {preview}."
            answer_source = "Indicadores INEGI almacenados en la plataforma; consulta la tabla para el detalle completo."
        else:
            answer = "Aún no hay indicadores INEGI cargados para este municipio."
    else:
        if topic_rows:
            main_topic = topic_rows[0]
            answer = (
                f"El tema con mayor presencia entre mensajes vinculados explícitamente a {selected_municipality} es "
                f"**{main_topic['tema']}**, con **{main_topic['mensajes']} mensajes** y "
                f"**{main_topic['urgencia_alta'] or 0}** clasificados con urgencia alta."
            )
            answer_source = "Mensajes conservados con vínculo territorial explícito; revisar evidencia original abajo."
        else:
            answer = "No hay mensajes vinculados explícitamente a este municipio para identificar temas con evidencia."
    st.success(answer)
    if answer_source:
        st.caption("Fuente de la respuesta: " + answer_source)

    evidence = query(
        """
        SELECT pt.municipality AS municipio, p.published_at AS fecha, s.name AS fuente,
               COALESCE(NULLIF(p.title, ''), p.text) AS mensaje,
               a.sentiment AS sentimiento, a.topic AS tema, a.urgency AS urgencia, p.url AS enlace
        FROM publication_territories pt
        JOIN publications p ON p.id = pt.publication_id
        JOIN sources s ON s.id = p.source_id
        LEFT JOIN analyses a ON a.publication_id = p.id
        WHERE p.profile_id = ? AND pt.state = ? AND pt.municipality = ?
        ORDER BY COALESCE(a.urgency = 'Alta', 0) DESC, p.collected_at DESC
        LIMIT 50
        """,
        (profile_id, selected_state, selected_municipality),
    )
    st.markdown("### Evidencia para revisión")
    if evidence:
        st.dataframe(
            pd.DataFrame(evidence),
            use_container_width=True,
            hide_index=True,
            column_config={"enlace": st.column_config.LinkColumn("Fuente original", display_text="Abrir")},
        )
    else:
        st.caption("No hay evidencia territorial vinculada para mostrar todavía.")


def render_territorial_prioritization() -> None:
    """Rank aggregate territorial units using documented electoral criteria only."""
    st.subheader("Priorización territorial")
    st.caption(
        "Ordena municipios para revisión de coordinación con criterios agregados y transparentes. "
        "No clasifica ni perfila a personas electoras."
    )
    options = profile_options()
    if not options:
        st.info("Primero crea un perfil y asigna un territorio.")
        return
    chosen_profile = st.selectbox("Perfil", list(options), key="priority_profile")
    profile_id = options[chosen_profile]
    states = profile_states(profile_id)
    if not states:
        st.info("Asigna un estado al perfil para poder priorizar territorios.")
        return
    selected_state = st.selectbox("Estado", states, key="priority_state")
    election_rows = query(
        """
        SELECT municipality, payload, election_year, source
        FROM territorial_election_results
        WHERE state = ? AND election_type = 'Ayuntamientos' AND election_year = 2024
        ORDER BY municipality
        """,
        (selected_state,),
    )
    if not election_rows:
        st.info(
            "No hay resultados municipales de ayuntamientos 2024 para este estado. "
            "Cárgalos desde Territorio y fuentes antes de usar la priorización."
        )
        return
    rows = []
    for row in election_rows:
        try:
            payload = json.loads(row["payload"])
        except (TypeError, json.JSONDecodeError):
            continue
        rows.append({"municipio": row["municipality"], **payload})
    if not rows:
        st.warning("Los resultados cargados no contienen valores utilizables.")
        return
    results = pd.DataFrame(rows)
    vote_keys = sorted(
        key for key in results.columns
        if key.startswith("votes_") and pd.to_numeric(results[key], errors="coerce").fillna(0).sum() > 0
    )
    if not vote_keys:
        st.warning("Los resultados no incluyen votación por partido o coalición.")
        return
    party_options = {
        key.replace("votes_", "").replace("_", " ").upper(): key for key in vote_keys
    }
    selected_party = st.selectbox(
        "Partido o coalición de referencia", list(party_options), key=f"priority_party_{selected_state}"
    )
    party_key = party_options[selected_party]
    for column in ["lista_nominal", "votes_total", "numero_votos_validos", "participacion_pct", party_key]:
        raw_values = results[column] if column in results else pd.Series(0, index=results.index)
        results[column] = pd.to_numeric(raw_values, errors="coerce").fillna(0)
    results["participacion_pct"] = results["participacion_pct"].where(
        results["participacion_pct"] > 0,
        (results["votes_total"] / results["lista_nominal"].replace(0, pd.NA) * 100),
    ).fillna(0)
    results["porcentaje_opcion"] = (
        results[party_key] / results["numero_votos_validos"].replace(0, pd.NA) * 100
    ).fillna(0)
    total_nominal = results["lista_nominal"].sum()
    total_votes = results["votes_total"].sum()
    state_participation = total_votes / total_nominal * 100 if total_nominal else 0
    results["peso_electoral_pct"] = results["lista_nominal"] / total_nominal * 100 if total_nominal else 0
    results["brecha_participacion"] = (state_participation - results["participacion_pct"]).clip(lower=0)
    max_nominal = results["lista_nominal"].max() or 1
    max_gap = results["brecha_participacion"].max() or 1
    max_party_share = results["porcentaje_opcion"].max() or 1
    results["indice_prioridad"] = (
        results["lista_nominal"] / max_nominal * 45
        + results["brecha_participacion"] / max_gap * 30
        + results["porcentaje_opcion"] / max_party_share * 25
    ).round(1)
    results["prioridad"] = pd.cut(
        results["indice_prioridad"], bins=[-1, 39.9, 69.9, 100], labels=["Baja", "Media", "Alta"]
    ).astype(str)
    results = results.sort_values(["indice_prioridad", "lista_nominal"], ascending=False).reset_index(drop=True)
    results.index = results.index + 1
    results["orden"] = results.index

    st.markdown("### Criterio de priorización")
    st.write(
        "El índice combina **45% volumen de lista nominal**, **30% brecha de participación respecto al promedio estatal** "
        f"y **25% porcentaje histórico de {selected_party}**. Sirve para ordenar revisión y coordinación territorial; "
        "no predice una elección ni determina decisiones sobre personas."
    )
    metric_a, metric_b, metric_c, metric_d = st.columns(4)
    metric_a.metric("Municipios evaluados", len(results))
    metric_b.metric("Participación estatal", f"{state_participation:.1f}%")
    metric_c.metric("Prioridad alta", int((results["prioridad"] == "Alta").sum()))
    metric_d.metric("Opción de referencia", selected_party)

    st.markdown("### Municipios con prioridad de revisión")
    display = results[
        ["orden", "municipio", "prioridad", "indice_prioridad", "lista_nominal", "participacion_pct",
         "brecha_participacion", party_key, "porcentaje_opcion", "peso_electoral_pct"]
    ].rename(columns={
        "orden": "Orden", "municipio": "Municipio", "prioridad": "Prioridad",
        "indice_prioridad": "Índice", "lista_nominal": "Lista nominal",
        "participacion_pct": "Participación %", "brecha_participacion": "Brecha participación (pp)",
        party_key: f"Votos {selected_party}", "porcentaje_opcion": f"% {selected_party}",
        "peso_electoral_pct": "Peso estatal %",
    })
    st.dataframe(display, use_container_width=True, hide_index=True)
    st.bar_chart(results.set_index("municipio")[["indice_prioridad"]].head(15), horizontal=True)

    municipality = st.selectbox("Explicar la prioridad de un municipio", list(results["municipio"]), key=f"priority_municipality_{selected_state}")
    detail = results.loc[results["municipio"] == municipality].iloc[0]
    st.info(
        f"**{municipality}** tiene prioridad **{detail['prioridad']}** (índice {detail['indice_prioridad']:.1f}/100): "
        f"lista nominal de {int(detail['lista_nominal']):,}, participación de {detail['participacion_pct']:.1f}% "
        f"frente a {state_participation:.1f}% estatal, y {selected_party} registra {int(detail[party_key]):,} votos "
        f"({detail['porcentaje_opcion']:.1f}% de los votos válidos)."
    )
    st.caption(
        "Fuente: resultados municipales de ayuntamientos 2024 cargados en la plataforma. "
        "El índice es reproducible y puede ajustarse cuando se integren cobertura territorial, actividades y seguimiento de campo."
    )
    st.divider()
    st.markdown("### Convertir prioridad en decisión de coordinación")
    st.write(
        "Selecciona los municipios que la coordinación desea conservar como prioridades. "
        "Esta acción guarda una decisión territorial y la deja disponible para Estrategia territorial y Planes de acción."
    )
    default_priorities = list(results.loc[results["prioridad"] == "Alta", "municipio"].head(10))
    selected_municipalities = st.multiselect(
        "Municipios a registrar como prioridad",
        list(results["municipio"]),
        default=default_priorities,
        key=f"priority_selection_{selected_state}_{selected_party}",
    )
    decision_status = st.selectbox(
        "Estatus de la decisión",
        ["Propuesta", "Validada por coordinación"],
        key=f"priority_status_{selected_state}_{selected_party}",
    )
    decision_note = st.text_area(
        "Nota de coordinación (opcional)",
        placeholder="Ejemplo: revisar presencia territorial y preparar un plan de trabajo municipal.",
        key=f"priority_note_{selected_state}_{selected_party}",
    )
    if st.button("Guardar prioridades territoriales", type="primary", disabled=not selected_municipalities):
        for municipality_name in selected_municipalities:
            selected_row = results.loc[results["municipio"] == municipality_name].iloc[0]
            automatic_rationale = (
                f"Índice {selected_row['indice_prioridad']:.1f}/100: lista nominal {int(selected_row['lista_nominal']):,}; "
                f"participación {selected_row['participacion_pct']:.1f}%; {selected_party} "
                f"{int(selected_row[party_key]):,} votos ({selected_row['porcentaje_opcion']:.1f}%)."
            )
            rationale = automatic_rationale + (f" Nota: {decision_note.strip()}" if decision_note.strip() else "")
            execute(
                """
                INSERT INTO territorial_priorities
                (profile_id, state, municipality, election_year, party_or_coalition, priority_level,
                 priority_index, rationale, status)
                VALUES (?, ?, ?, 2024, ?, ?, ?, ?, ?)
                ON CONFLICT(profile_id, state, municipality, election_year, party_or_coalition) DO UPDATE SET
                    priority_level = excluded.priority_level,
                    priority_index = excluded.priority_index,
                    rationale = excluded.rationale,
                    status = excluded.status,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    profile_id, selected_state, municipality_name, selected_party,
                    selected_row["prioridad"], float(selected_row["indice_prioridad"]), rationale, decision_status,
                ),
            )
        st.success(f"Se guardaron {len(selected_municipalities)} prioridades para {selected_party} en {selected_state}.")
        st.rerun()
    saved_priorities = query(
        """
        SELECT municipality AS municipio, priority_level AS prioridad, priority_index AS indice,
               status AS estatus, rationale AS fundamento, updated_at AS actualizado
        FROM territorial_priorities
        WHERE profile_id = ? AND state = ? AND party_or_coalition = ?
        ORDER BY priority_index DESC, municipality
        """,
        (profile_id, selected_state, selected_party),
    )
    if saved_priorities:
        st.markdown("#### Prioridades guardadas")
        st.dataframe(pd.DataFrame(saved_priorities), use_container_width=True, hide_index=True)


def render_territorial_strategy() -> None:
    """Turn validated aggregate priorities into municipality-level strategy records."""
    st.subheader("Estrategia territorial")
    st.caption(
        "Convierte prioridades territoriales guardadas en objetivos y tácticas por municipio. "
        "Trabaja con unidades territoriales agregadas, no con perfiles individuales de electores."
    )
    options = profile_options()
    if not options:
        st.info("Primero crea un perfil y guarda prioridades territoriales.")
        return
    chosen_profile = st.selectbox("Perfil", list(options), key="strategy_profile")
    profile_id = options[chosen_profile]
    states = profile_states(profile_id)
    if not states:
        st.info("Asigna un estado al perfil antes de definir estrategia territorial.")
        return
    selected_state = st.selectbox("Estado", states, key="strategy_state")
    priority_rows = query(
        """
        SELECT id, municipality, party_or_coalition, priority_level, priority_index, rationale, status
        FROM territorial_priorities
        WHERE profile_id = ? AND state = ?
        ORDER BY priority_index DESC, municipality
        """,
        (profile_id, selected_state),
    )
    if not priority_rows:
        st.info(
            "Aún no hay prioridades guardadas para este perfil y estado. "
            "Primero usa Priorización territorial y guarda los municipios que revisará la coordinación."
        )
        return
    priority_options = {
        f"{row['municipality']} · {row['party_or_coalition'] or 'Sin opción'} · prioridad {row['priority_level']}": row
        for row in priority_rows
    }
    selected_priority_label = st.selectbox("Municipio priorizado", list(priority_options), key=f"strategy_priority_{selected_state}")
    priority = priority_options[selected_priority_label]
    st.info(
        f"**Fundamento registrado:** {priority['rationale']}  \n\n"
        f"Estatus de prioridad: **{priority['status']}** · Índice: **{priority['priority_index']:.1f}/100**"
    )
    st.markdown("### Definir estrategia")
    focus_options = [
        "Presencia y coordinación territorial",
        "Escucha y atención de temas públicos",
        "Participación cívica e información comunitaria",
        "Fortalecimiento de estructura territorial",
        "Comunicación territorial y rendición de cuentas",
    ]
    saved_strategy = query(
        """
        SELECT * FROM territorial_strategies
        WHERE profile_id = ? AND state = ? AND municipality = ?
          AND COALESCE(party_or_coalition, '') = COALESCE(?, '')
        """,
        (profile_id, selected_state, priority["municipality"], priority["party_or_coalition"]),
    )
    current = saved_strategy[0] if saved_strategy else None
    default_objective = (
        f"Fortalecer la coordinación territorial en {priority['municipality']} mediante presencia, "
        "escucha documentada y seguimiento de prioridades públicas."
    )
    with st.form(f"strategy_form_{priority['id']}"):
        strategic_focus = st.selectbox(
            "Línea estratégica", focus_options,
            index=focus_options.index(current["strategic_focus"]) if current and current["strategic_focus"] in focus_options else 0,
        )
        objective = st.text_area("Objetivo territorial", value=current["objective"] if current else default_objective)
        tactics = st.text_area(
            "Tácticas de trabajo territorial",
            value=current["tactics"] if current else (
                "• Definir responsables de cobertura municipal.\n"
                "• Realizar espacios de escucha y documentar temas públicos.\n"
                "• Preparar actividades informativas y de vinculación comunitaria conforme a la normativa aplicable.\n"
                "• Revisar resultados y ajustar el plan con evidencia de campo."
            ),
            height=150,
        )
        success_measure = st.text_input(
            "Cómo se medirá el avance", value=current["success_measure"] if current and current["success_measure"] else "Cobertura de actividades, responsables asignados y evidencias registradas."
        )
        period = st.columns(2)
        start_value = current["starts_at"] if current and current["starts_at"] else str(date.today())
        end_value = current["ends_at"] if current and current["ends_at"] else ""
        starts_at = period[0].text_input("Inicio", value=start_value, help="Formato AAAA-MM-DD")
        ends_at = period[1].text_input("Fin (opcional)", value=end_value, help="Formato AAAA-MM-DD")
        status = st.selectbox("Estatus", ["Borrador", "Validada por coordinación", "En ejecución"], index=["Borrador", "Validada por coordinación", "En ejecución"].index(current["status"]) if current and current["status"] in ["Borrador", "Validada por coordinación", "En ejecución"] else 0)
        submitted = st.form_submit_button("Guardar estrategia territorial", type="primary")
    if submitted:
        if not objective.strip() or not tactics.strip():
            st.error("Escribe un objetivo y al menos una táctica antes de guardar.")
        else:
            execute(
                """
                INSERT INTO territorial_strategies
                (profile_id, state, municipality, party_or_coalition, priority_id, strategic_focus,
                 objective, tactics, success_measure, status, starts_at, ends_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(profile_id, state, municipality, party_or_coalition) DO UPDATE SET
                    priority_id = excluded.priority_id, strategic_focus = excluded.strategic_focus,
                    objective = excluded.objective, tactics = excluded.tactics,
                    success_measure = excluded.success_measure, status = excluded.status,
                    starts_at = excluded.starts_at, ends_at = excluded.ends_at,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (profile_id, selected_state, priority["municipality"], priority["party_or_coalition"], priority["id"],
                 strategic_focus, objective.strip(), tactics.strip(), success_measure.strip(), status,
                 starts_at.strip() or None, ends_at.strip() or None),
            )
            st.success("Estrategia guardada. Ya estará disponible para crear planes de acción por municipio.")
            st.rerun()
    strategies = query(
        """
        SELECT municipality AS municipio, party_or_coalition AS referencia, strategic_focus AS linea,
               objective AS objetivo, status AS estatus, updated_at AS actualizado
        FROM territorial_strategies
        WHERE profile_id = ? AND state = ?
        ORDER BY updated_at DESC
        """,
        (profile_id, selected_state),
    )
    if strategies:
        st.markdown("### Estrategias territoriales registradas")
        st.dataframe(pd.DataFrame(strategies), use_container_width=True, hide_index=True)


def render_action_plans() -> None:
    """Operational plan for already defined territorial strategies."""
    st.subheader("Planes de acción")
    st.caption(
        "Organiza la ejecución por actividad, responsable, fecha, prioridad, estatus y evidencia. "
        "El seguimiento se concentra en tareas territoriales, no en datos individuales de electores."
    )
    options = profile_options()
    if not options:
        st.info("Primero crea un perfil y registra una estrategia territorial.")
        return
    chosen_profile = st.selectbox("Perfil", list(options), key="action_profile")
    profile_id = options[chosen_profile]
    states = profile_states(profile_id)
    if not states:
        st.info("Asigna un estado al perfil antes de crear un plan de acción.")
        return
    selected_state = st.selectbox("Estado", states, key="action_state")
    strategy_rows = query(
        """
        SELECT id, municipality, party_or_coalition, strategic_focus, objective, status
        FROM territorial_strategies
        WHERE profile_id = ? AND state = ?
        ORDER BY municipality
        """,
        (profile_id, selected_state),
    )
    if not strategy_rows:
        st.info(
            "Aún no hay estrategias guardadas. Primero define una en Estrategia territorial; "
            "después podrás programar sus actividades aquí."
        )
        return
    strategy_options = {
        f"{row['municipality']} · {row['strategic_focus']} · {row['status']}": row for row in strategy_rows
    }
    selected_strategy_label = st.selectbox("Estrategia territorial", list(strategy_options), key=f"action_strategy_{selected_state}")
    strategy = strategy_options[selected_strategy_label]
    st.info(f"**Objetivo:** {strategy['objective']}")
    st.markdown("### Programar actividad")
    with st.form(f"action_form_{strategy['id']}", clear_on_submit=True):
        activity_name = st.text_input("Nombre de la actividad", placeholder="Ejemplo: reunión de coordinación territorial")
        activity_description = st.text_area(
            "Descripción y resultado esperado",
            placeholder="Qué se realizará, qué evidencia se espera y cómo se relaciona con el objetivo territorial.",
        )
        action_columns = st.columns(3)
        responsible = action_columns[0].text_input("Responsable", placeholder="Nombre o equipo")
        due_date = action_columns[1].date_input("Fecha compromiso", value=date.today())
        priority_level = action_columns[2].selectbox("Prioridad", ["Alta", "Media", "Baja"], index=1)
        submitted = st.form_submit_button("Agregar actividad", type="primary")
    if submitted:
        if not activity_name.strip():
            st.error("Escribe el nombre de la actividad antes de agregarla.")
        else:
            execute(
                """
                INSERT INTO territorial_action_plans
                (strategy_id, profile_id, state, municipality, activity_name, activity_description,
                 responsible, due_date, priority_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (strategy["id"], profile_id, selected_state, strategy["municipality"], activity_name.strip(),
                 activity_description.strip() or None, responsible.strip() or None, str(due_date), priority_level),
            )
            st.success("Actividad agregada al plan de acción.")
            st.rerun()

    actions = query(
        """
        SELECT id, activity_name, activity_description, responsible, due_date, priority_level,
               status, evidence_note, completed_at
        FROM territorial_action_plans
        WHERE strategy_id = ?
        ORDER BY CASE priority_level WHEN 'Alta' THEN 1 WHEN 'Media' THEN 2 ELSE 3 END, due_date, id
        """,
        (strategy["id"],),
    )
    st.markdown("### Actividades del municipio")
    if not actions:
        st.caption("Todavía no hay actividades. Registra la primera para poner la estrategia en operación.")
        return
    summary = pd.DataFrame(actions)
    counts = summary["status"].value_counts()
    action_metrics = st.columns(3)
    action_metrics[0].metric("Total", len(summary))
    action_metrics[1].metric("Pendientes", int(counts.get("Pendiente", 0)))
    action_metrics[2].metric("Concluidas", int(counts.get("Concluida", 0)))
    st.dataframe(
        summary.drop(columns=["id"]), use_container_width=True, hide_index=True,
    )
    action_lookup = {f"{row['activity_name']} · {row['due_date'] or 'sin fecha'}": row for row in actions}
    selected_action_label = st.selectbox("Actualizar una actividad", list(action_lookup), key=f"update_action_{strategy['id']}")
    selected_action = action_lookup[selected_action_label]
    update_columns = st.columns(2)
    new_status = update_columns[0].selectbox(
        "Estatus", ["Pendiente", "En curso", "Concluida", "Cancelada"],
        index=["Pendiente", "En curso", "Concluida", "Cancelada"].index(selected_action["status"]),
    )
    evidence = update_columns[1].text_input(
        "Evidencia o nota de avance", value=selected_action["evidence_note"] or "",
        placeholder="Ejemplo: minuta, enlace, fotografía o resultado reportado.",
    )
    if st.button("Guardar avance de la actividad"):
        execute(
            """
            UPDATE territorial_action_plans
            SET status = ?, evidence_note = ?,
                completed_at = CASE WHEN ? = 'Concluida' THEN CURRENT_TIMESTAMP ELSE completed_at END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (new_status, evidence.strip() or None, new_status, selected_action["id"]),
        )
        st.success("Avance actualizado.")
        st.rerun()


def profile_states(profile_id: int) -> list[str]:
    territories_for_profile = query(
        """
        SELECT DISTINCT t.state
        FROM profile_territories pt
        JOIN territories t ON t.id = pt.territory_id
        WHERE pt.profile_id = ? AND TRIM(COALESCE(t.state, '')) <> ''
        """,
        (profile_id,),
    )
    states = [row["state"] for row in territories_for_profile]
    if states:
        return states
    profile_context = query(
        """
        SELECT COALESCE(p.notes, '') || ' ' || COALESCE(pp.office, '') AS contexto
        FROM profiles p
        LEFT JOIN profile_positions pp ON pp.profile_id = p.id
        WHERE p.id = ?
        ORDER BY pp.is_current DESC, pp.starts_at DESC
        """,
        (profile_id,),
    )
    context_text = " ".join(row["contexto"] for row in profile_context).casefold()
    known_states = query(
        "SELECT DISTINCT state FROM territories WHERE TRIM(COALESCE(state, '')) <> '' ORDER BY state"
    )
    return [row["state"] for row in known_states if row["state"].casefold() in context_text]


def manage_territorial_data(context_state: str) -> None:
    """Administrative controls kept outside the daily map consultation."""
    st.caption("Estas acciones modifican únicamente las capas e indicadores territoriales locales.")
    uploaded_geojson = st.file_uploader(
        "Actualizar capa municipal GeoJSON (opcional)",
        type="geojson",
        key=f"admin_geojson_{context_state}",
        help="La capa se aplicará solo al estado activo y no altera mensajes ni análisis.",
    )
    if uploaded_geojson is not None:
        st.session_state["territorial_geojson_data"] = uploaded_geojson.getvalue()
        st.session_state["territorial_geojson_name"] = uploaded_geojson.name
        st.session_state["territorial_geojson_state"] = context_state
        st.success(f"Capa municipal preparada para {context_state}: {uploaded_geojson.name}")

    uploaded_district_geojson = st.file_uploader(
        "Incorporar capa GeoJSON de distritos locales (opcional)",
        type="geojson",
        key=f"admin_district_geojson_{context_state}",
        help=(
            "Carga la capa oficial de distritos locales del estado activo. "
            "La plataforma le unirá los resultados 2024 por clave de distrito."
        ),
    )
    if uploaded_district_geojson is not None:
        try:
            parsed_district_geojson = json.loads(uploaded_district_geojson.getvalue().decode("utf-8"))
            if not isinstance(parsed_district_geojson.get("features"), list):
                raise ValueError("no contiene una colección de entidades")
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            st.error(f"No fue posible leer la capa distrital: {error}.")
        else:
            st.session_state["territorial_district_geojson_data"] = uploaded_district_geojson.getvalue()
            st.session_state["territorial_district_geojson_name"] = uploaded_district_geojson.name
            st.session_state["territorial_district_geojson_state"] = context_state
            st.success(
                f"Capa distrital preparada para {context_state}: {uploaded_district_geojson.name} "
                f"({len(parsed_district_geojson['features'])} polígonos)."
            )
    if context_state == "Sonora":
        request_path = Path(__file__).with_name("SOLICITUD_CARTOGRAFIA_ELECTORAL_SONORA.md")
        if request_path.exists():
            st.download_button(
                "Descargar texto de solicitud para cartografía oficial de Sonora",
                data=request_path.read_bytes(),
                file_name=request_path.name,
                mime="text/markdown",
                help="Texto listo para solicitar al INE o IEE Sonora la capa oficial de distritos locales y secciones.",
            )

    st.markdown("#### Resultados electorales municipales")
    election_rows = query(
        """
        SELECT municipality_code, municipality, payload
        FROM territorial_election_results
        WHERE state = ? AND election_type = 'Ayuntamientos' AND election_year = 2024
        ORDER BY municipality
        """,
        (context_state,),
    )
    if context_state == "Sonora":
        if st.button("Descargar e integrar cómputos oficiales de Sonora 2024", key="fetch_sonora_2024"):
            with st.spinner("Descargando y agrupando los cómputos municipales oficiales de Sonora..."):
                try:
                    parsed_rows, official_source = fetch_sonora_municipal_2024()
                except (requests.RequestException, ValueError) as error:
                    st.error(f"No fue posible descargar la base oficial: {error}")
                else:
                    for election_row in parsed_rows:
                        execute(
                            """
                            INSERT INTO territorial_election_results
                            (state, municipality_code, municipality, election_type, election_year, payload, source)
                            VALUES (?, ?, ?, 'Ayuntamientos', 2024, ?, ?)
                            ON CONFLICT(state, municipality, election_type, election_year) DO UPDATE SET
                                municipality_code = excluded.municipality_code,
                                payload = excluded.payload,
                                source = excluded.source,
                                imported_at = CURRENT_TIMESTAMP
                            """,
                            (
                                context_state, election_row["municipality_code"], election_row["municipality"],
                                json.dumps(election_row["payload"], ensure_ascii=False), official_source,
                            ),
                        )
                    st.success(f"Se integraron {len(parsed_rows)} municipios desde la base oficial del IEE Sonora.")
                    st.rerun()
    else:
        st.caption("La descarga automática se habilita cuando existe una fuente oficial configurada para el estado.")
    st.download_button(
        "Descargar plantilla CSV de resultados municipales",
        data=election_template_csv(),
        file_name="plantilla_resultados_municipales_2024.csv",
        mime="text/csv",
    )
    election_file = st.file_uploader(
        "Cargar CSV municipal oficial", type="csv", key=f"election_csv_{context_state}"
    )
    if election_file is not None:
        parsed_rows, election_errors = parse_municipal_results(election_file.getvalue())
        st.caption(f"Se identificaron {len(parsed_rows)} municipios con indicadores utilizables.")
        if election_errors:
            st.warning(f"Se omitieron o ajustaron {len(election_errors)} valores. Revisa la plantilla si falta información.")
        if st.button("Guardar resultados municipales", key=f"save_election_{context_state}"):
            for election_row in parsed_rows:
                execute(
                    """
                    INSERT INTO territorial_election_results
                    (state, municipality_code, municipality, election_type, election_year, payload, source)
                    VALUES (?, ?, ?, 'Ayuntamientos', 2024, ?, ?)
                    ON CONFLICT(state, municipality, election_type, election_year) DO UPDATE SET
                        municipality_code = excluded.municipality_code,
                        payload = excluded.payload,
                        source = excluded.source,
                        imported_at = CURRENT_TIMESTAMP
                    """,
                    (
                        context_state, election_row["municipality_code"], election_row["municipality"],
                        json.dumps(election_row["payload"], ensure_ascii=False), f"CSV cargado: {election_file.name}",
                    ),
                )
            st.success(f"Se guardaron {len(parsed_rows)} resultados municipales para {context_state}.")
            st.rerun()
    if election_rows:
        st.success(f"Hay {len(election_rows)} municipios con resultados de ayuntamientos 2024 cargados.")
    else:
        st.info("Aún no hay resultados municipales cargados para este estado.")

    st.markdown("#### Diputaciones locales por distrito")
    district_rows = query(
        """
        SELECT district_code FROM territorial_district_results
        WHERE state = ? AND election_type = 'Diputaciones locales' AND election_year = 2024
        """,
        (context_state,),
    )
    if context_state == "Sonora":
        if st.button("Descargar e integrar resultados oficiales por distrito · Sonora 2024", key="fetch_sonora_districts_2024"):
            with st.spinner("Descargando y agrupando resultados de diputaciones locales por distrito..."):
                try:
                    district_results, official_source = fetch_sonora_local_district_2024()
                except (requests.RequestException, ValueError) as error:
                    st.error(f"No fue posible descargar la base oficial: {error}")
                else:
                    for district in district_results:
                        execute(
                            """
                            INSERT INTO territorial_district_results
                            (state, district_code, district_name, election_type, election_year, payload, source)
                            VALUES (?, ?, ?, 'Diputaciones locales', 2024, ?, ?)
                            ON CONFLICT(state, district_code, election_type, election_year) DO UPDATE SET
                                district_name = excluded.district_name, payload = excluded.payload,
                                source = excluded.source, imported_at = CURRENT_TIMESTAMP
                            """,
                            (
                                context_state, district["district_code"], district["district_name"],
                                json.dumps(district["payload"], ensure_ascii=False), official_source,
                            ),
                        )
                    st.success(f"Se integraron {len(district_results)} distritos locales de Sonora.")
                    st.rerun()
    else:
        st.caption("La descarga automática se habilitará cuando exista una fuente oficial para este estado.")
    if district_rows:
        st.success(f"Hay {len(district_rows)} distritos locales con resultados 2024 cargados.")
    else:
        st.info("Aún no hay resultados distritales cargados para este estado.")

    st.markdown("#### Secciones electorales")
    section_rows = query(
        """
        SELECT section_code FROM territorial_section_results
        WHERE state = ? AND election_type = 'Diputaciones locales' AND election_year = 2024
        """,
        (context_state,),
    )
    if context_state == "Sonora":
        if st.button("Descargar e integrar resultados oficiales por sección · Sonora 2024", key="fetch_sonora_sections_2024"):
            with st.spinner("Descargando y agrupando resultados por sección electoral..."):
                try:
                    section_results, official_source = fetch_sonora_local_sections_2024()
                except (requests.RequestException, ValueError) as error:
                    st.error(f"No fue posible descargar la base oficial: {error}")
                else:
                    for section in section_results:
                        execute(
                            """
                            INSERT INTO territorial_section_results
                            (state, district_code, section_code, municipality_code, municipality,
                             election_type, election_year, payload, source)
                            VALUES (?, ?, ?, ?, ?, 'Diputaciones locales', 2024, ?, ?)
                            ON CONFLICT(state, district_code, section_code, election_type, election_year) DO UPDATE SET
                                municipality_code = excluded.municipality_code,
                                municipality = excluded.municipality, payload = excluded.payload,
                                source = excluded.source, imported_at = CURRENT_TIMESTAMP
                            """,
                            (
                                context_state, section["district_code"], section["section_code"],
                                section["municipality_code"], section["municipality"],
                                json.dumps(section["payload"], ensure_ascii=False), official_source,
                            ),
                        )
                    st.success(f"Se integraron {len(section_results)} secciones electorales de Sonora.")
                    st.rerun()
    else:
        st.caption("La descarga automática se habilitará cuando exista una fuente oficial para el estado.")
    if section_rows:
        st.success(f"Hay {len(section_rows)} secciones con resultados 2024 cargados.")
    else:
        st.info("Aún no hay resultados por sección cargados para este estado.")


def manage_inegi_indicators(context_state: str, geojson: dict | None) -> None:
    """Controlled download of INEGI indicators from the territorial profile."""
    st.markdown("#### Indicadores oficiales INEGI")
    st.caption("Busca, selecciona y actualiza indicadores municipales. Después quedarán disponibles en el módulo INEGI.")
    inegi_token = get_setting("INEGI_INDICATORS_TOKEN")
    if not inegi_token:
        st.warning("Configura el token de Banco de Indicadores INEGI en Conexiones privadas para actualizar datos oficiales.")
        return
    if geojson is None:
        st.warning("Primero carga una capa municipal para poder consultar indicadores por municipio.")
        return
    inegi_mode = st.radio(
        "¿Qué indicador desea incorporar?",
        ["Indicadores sugeridos", "Buscar en el catálogo de INEGI", "Ingresar clave oficial"],
        horizontal=True,
        key="inegi_mode",
    )
    indicator_group = ""
    if inegi_mode == "Indicadores sugeridos":
        indicator_group = st.selectbox("Grupo de indicadores", list(INDICATOR_GROUPS), key="inegi_indicator_group")
        indicator_subgroup = st.selectbox(
            "Subgrupo", list(INDICATOR_GROUPS[indicator_group]),
            key=f"inegi_indicator_subgroup_v2_{indicator_group}",
        )
        inegi_label = st.selectbox(
            "Indicador a consultar", list(INDICATOR_GROUPS[indicator_group][indicator_subgroup]),
            key=f"inegi_indicator_v2_{indicator_group}_{indicator_subgroup}",
        )
        inegi_indicator_id = INDICATOR_GROUPS[indicator_group][indicator_subgroup][inegi_label]
        st.caption(f"Ruta seleccionada: {indicator_group} → {indicator_subgroup} → {inegi_label}.")
    elif inegi_mode == "Buscar en el catálogo de INEGI":
        search_text = st.text_input(
            "Buscar indicador por tema", placeholder="Ejemplo: salud, educación, agua, seguridad o pobreza",
            key="inegi_catalog_search",
        )
        if st.button("Buscar en catálogo de INEGI", key="search_inegi_catalog"):
            if len(search_text.strip()) < 3:
                st.warning("Escribe al menos tres letras para buscar.")
            else:
                with st.spinner("Buscando en el catálogo oficial de INEGI..."):
                    try:
                        st.session_state["inegi_catalog_matches"] = search_indicator_catalog(inegi_token, search_text)
                    except requests.RequestException as error:
                        st.error(f"No fue posible consultar el catálogo de INEGI: {error}")
                        st.session_state["inegi_catalog_matches"] = []
        matches = st.session_state.get("inegi_catalog_matches", [])
        if not matches:
            st.info("Busca un tema para mostrar hasta 50 indicadores oficiales relacionados.")
            return
        catalog_options = {f"{item['name']}  ·  clave {item['id']}": item["id"] for item in matches}
        inegi_label = st.selectbox("Resultado del catálogo", list(catalog_options), key="inegi_catalog_indicator")
        inegi_indicator_id = catalog_options[inegi_label]
    else:
        inegi_indicator_id = st.text_input(
            "Clave oficial del indicador INEGI", placeholder="Ejemplo: 1002000001",
            key="inegi_manual_indicator",
        ).strip()
        if not inegi_indicator_id:
            st.info("Escribe una clave oficial de INEGI para poder consultarla.")
            return
        if not inegi_indicator_id.isdigit():
            st.warning("La clave oficial debe contener únicamente números.")
            return
        inegi_label = f"Indicador con clave {inegi_indicator_id}"
    st.session_state["active_inegi_indicator_id"] = inegi_indicator_id
    if inegi_mode == "Indicadores sugeridos" and indicator_group == "Seguridad":
        st.caption("Estos datos describen capacidad institucional municipal; no equivalen a incidencia delictiva.")
    if st.button(f"Traer “{inegi_label}” para {context_state}", key="fetch_inegi_indicator"):
        with st.spinner(f"Consultando INEGI para los municipios de {context_state}..."):
            indicator_rows, inegi_errors, indicator_name = collect_municipal_indicator(
                context_state, geojson.get("features", []), inegi_indicator_id, inegi_token
            )
        for row in indicator_rows:
            execute(
                """
                INSERT INTO territorial_indicators
                (state, municipality_code, municipality, indicator_id, indicator_name, unit, value, period)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(state, municipality_code, indicator_id, period) DO UPDATE SET
                    municipality = excluded.municipality, indicator_name = excluded.indicator_name,
                    unit = excluded.unit, value = excluded.value, retrieved_at = CURRENT_TIMESTAMP
                """,
                (row["state"], row["municipality_code"], row["municipality"], row["indicator_id"],
                 row["indicator_name"], row["unit"], row["value"], row["period"]),
            )
        st.success(f"INEGI devolvió y guardó {len(indicator_rows)} municipios para “{indicator_name}”.")
        if inegi_errors:
            st.warning(f"{len(inegi_errors)} municipios no devolvieron dato en esta consulta.")
        st.rerun()


if "active_page" not in st.session_state:
    st.session_state["active_page"] = "Inicio"
if not st.session_state.get("navigation_groups_v11"):
    for widget_key in NAVIGATION_WIDGET_KEYS:
        st.session_state.pop(widget_key, None)
    st.session_state["navigation_groups_v11"] = True
    if st.session_state.get("active_page") == "Codex":
        st.session_state["active_page"] = "Inicio"


with st.sidebar:
    st.markdown(
        """
        <div class="pulso-kicker">INTELIGENCIA PÚBLICA</div>
        <div class="pulso-title">Pulso Ciudadano<br><span style="font-size:.68em;font-weight:600;letter-spacing:.04em">Dominio territorial</span></div>
        <div class="pulso-subtitle">Escucha, contexto territorial y cobertura de medios.</div>
        <span class="pulso-badge">ETAPA 1 · LOCAL</span>
        """,
        unsafe_allow_html=True,
    )
    st.divider()
    st.radio(
        "Objetivo",
        list(OBJECTIVE_NAVIGATION),
        index=None,
        key="objective_navigation",
        label_visibility="collapsed",
        on_change=select_navigation,
        args=("objective_navigation", OBJECTIVE_NAVIGATION),
    )
    st.divider()
    st.caption("1 · INFORMACIÓN Y TERRITORIO")
    st.caption("Perfiles, fuentes, datos originales y su vínculo territorial.")
    st.radio(
        "Módulos de información",
        list(INFORMATION_NAVIGATION),
        index=None,
        key="information_navigation",
        label_visibility="collapsed",
        on_change=select_navigation,
        args=("information_navigation", INFORMATION_NAVIGATION),
    )
    st.divider()
    st.caption("2 · ANÁLISIS TERRITORIAL")
    st.caption("Visores, análisis, IA y revisión de resultados.")
    st.radio(
        "Módulos de análisis",
        list(ANALYSIS_NAVIGATION),
        index=None,
        key="analysis_navigation",
        label_visibility="collapsed",
        on_change=select_navigation,
        args=("analysis_navigation", ANALYSIS_NAVIGATION),
    )
    st.divider()
    st.caption("3 · ESTRATEGIA Y ACCIÓN")
    st.caption("Módulos preparados para convertir análisis en operación territorial.")
    st.radio(
        "Módulos de estrategia",
        list(STRATEGY_NAVIGATION),
        index=None,
        key="strategy_navigation",
        label_visibility="collapsed",
        on_change=select_navigation,
        args=("strategy_navigation", STRATEGY_NAVIGATION),
    )
    st.divider()
    st.caption("4 · COORDINACIÓN Y CONTROL")
    st.radio(
        "Módulos de coordinación",
        list(COORDINATION_NAVIGATION),
        index=None,
        key="coordination_navigation",
        label_visibility="collapsed",
        on_change=select_navigation,
        args=("coordination_navigation", COORDINATION_NAVIGATION),
    )
    st.divider()
    st.caption("Flujo: información → análisis → estrategia → acción → seguimiento.")
    st.caption("Los datos se conservan en esta computadora.")

page = st.session_state["active_page"]

if page not in {"Dominio territorial", "Territorio", "Electoral", "Visor electoral", "INEGI", "Diagnóstico regional del PED", "Perfil territorial"}:
    st.title(page if page != "Inicio" else "Pulso Ciudadano · Dominio territorial")
    st.caption("Etapa 1 local: datos y análisis en tu computadora, sin costo de infraestructura.")

if page == "Planes de acción":
    render_action_plans()

elif page == "Estrategia territorial":
    render_territorial_strategy()

elif page == "Priorización territorial":
    render_territorial_prioritization()

elif page == "Diagnóstico territorial":
    render_territorial_diagnosis()

elif page == "Inicio":
    st.subheader("Objetivo del proyecto")
    st.markdown(
        "Gobernar o construir una propuesta pública exige entender dos cosas al mismo tiempo: "
        "qué ocurre en el territorio y qué está expresando la ciudadanía."
    )
    st.markdown(
        "**Pulso Ciudadano · Dominio territorial** integra ambas lecturas en una plataforma local, "
        "clara y auditable. Su propósito es ordenar información para hacer mejores preguntas y priorizar "
        "la atención pública."
    )
    st.markdown("### 1. Escucha ciudadana y cobertura pública")
    st.write(
        "Concentra publicaciones de X, medios digitales, RSS y otras fuentes autorizadas. "
        "Cada registro conserva su texto original y enlace para revisar la evidencia directamente."
    )
    st.markdown(
        "Los mensajes se pueden analizar por percepción pública, necesidades ciudadanas, asuntos de gobierno, "
        "cobertura de medios y referencias territoriales expresamente mencionadas."
    )
    st.markdown("### 2. Inteligencia territorial")
    st.write(
        "Organiza la información por municipio, distrito local y sección electoral. En Sonora incorpora "
        "cartografía y resultados oficiales de 2024 para revisar participación, lista nominal, votos totales "
        "y votación por partido, coalición o candidatura."
    )
    st.write(
        "La consulta usa selectores de municipio, distrito o sección. La ficha electoral se muestra antes "
        "del mapa para facilitar el análisis; el mapa funciona como apoyo visual."
    )
    st.markdown("### 3. Contexto social con información pública")
    st.write(
        "Los resultados y la conversación se pueden contrastar con indicadores de INEGI: población, conectividad, "
        "escolaridad, salud, agua, drenaje, discapacidad, lengua indígena y actividad económica."
    )
    st.markdown("### Preguntas que ayuda a responder")
    st.markdown(
        "- ¿En qué municipios se concentra la conversación sobre un tema?\n"
        "- ¿Qué necesidades aparecen y dónde se mencionan explícitamente?\n"
        "- ¿Cómo se relaciona la conversación con vivienda, conectividad o salud?\n"
        "- ¿Qué distritos o secciones muestran menor participación y cuál es su contexto?\n"
        "- ¿Qué mensaje original respalda un hallazgo?"
    )
    st.info(
        "Principio de operación: los datos deben ser comprensibles, verificables y útiles para la acción pública. "
        "La plataforma conserva la fuente original, separa la obtención del análisis y no atribuye ubicaciones "
        "cuando el mensaje no las menciona."
    )

elif page in FUTURE_MODULES:
    module = FUTURE_MODULES[page]
    st.subheader(page)
    st.write(module["subtitle"])
    st.info("Módulo incorporado al menú para su construcción gradual. Aún no captura ni modifica información.")
    left, middle, right = st.columns(3)
    left.metric("Entrada", "Información integrada")
    middle.metric("Proceso", "Gestión territorial")
    right.metric("Salida", "Decisión y seguimiento")
    st.markdown("### Información que utilizará")
    st.write(module["inputs"])
    st.markdown("### Resultado esperado")
    st.write(module["output"])
    st.caption(
        "Cuando se construya, este módulo conservará trazabilidad por territorio y fuente; "
        "no utilizará perfiles individuales de electores."
    )

elif page == "Perfiles y trayectorias":
    st.subheader("Perfiles")
    with st.form("new_profile", clear_on_submit=True):
        name = st.text_input("Nombre de la persona, institución o tema")
        actor_type = st.selectbox("Tipo de perfil", ACTOR_TYPES)
        notes = st.text_area("Notas opcionales")
        submitted = st.form_submit_button("Guardar perfil")
        if submitted:
            if not name.strip():
                st.error("Escribe un nombre para el perfil.")
            else:
                execute(
                    "INSERT INTO profiles (name, actor_type, notes) VALUES (?, ?, ?)",
                    (name.strip(), actor_type, notes.strip()),
                )
                st.success("Perfil guardado.")

    profiles = query("SELECT id, name, actor_type, active, notes FROM profiles ORDER BY name")
    if profiles:
        st.dataframe(pd.DataFrame(profiles), use_container_width=True, hide_index=True)

    st.subheader("Cargo, candidatura o condición")
    options = profile_options()
    if not options:
        st.info("Primero crea un perfil.")
    else:
        with st.form("new_position", clear_on_submit=True):
            chosen = st.selectbox("Perfil", list(options))
            office = st.text_input("Cargo o candidatura", placeholder="Presidencia municipal")
            condition = st.selectbox("Condición", CONDITIONS)
            col1, col2 = st.columns(2)
            starts_at = col1.date_input("Inicio", value=date.today())
            ends_at = col2.date_input("Fin estimado o real", value=None)
            party = st.text_input("Partido o coalición (opcional)")
            submitted = st.form_submit_button("Guardar trayectoria")
            if submitted:
                if not office.strip():
                    st.error("Indica el cargo o candidatura.")
                else:
                    execute(
                        """
                        INSERT INTO profile_positions
                        (profile_id, office, condition, starts_at, ends_at, party_or_coalition)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            options[chosen],
                            office.strip(),
                            condition,
                            starts_at.isoformat(),
                            ends_at.isoformat() if ends_at else None,
                            party.strip(),
                        ),
                    )
                    st.success("Trayectoria guardada.")

    positions = query(
        """
        SELECT p.name AS perfil, pp.office AS cargo, pp.condition AS condicion,
               pp.starts_at AS inicio, pp.ends_at AS fin, pp.party_or_coalition AS partido_coalicion
        FROM profile_positions pp
        JOIN profiles p ON p.id = pp.profile_id
        ORDER BY pp.starts_at DESC, p.name
        """
    )
    if positions:
        st.dataframe(pd.DataFrame(positions), use_container_width=True, hide_index=True)

elif page == "Territorio y fuentes":
    st.subheader("Territorios")
    with st.form("new_territory", clear_on_submit=True):
        territory_type = st.selectbox("Nivel territorial", TERRITORY_TYPES)
        state = st.text_input("Estado", value="Chihuahua")
        municipality = st.text_input("Municipio")
        col1, col2 = st.columns(2)
        district = col1.text_input("Distrito")
        electoral_section = col2.text_input("Sección electoral")
        locality = st.text_input("Colonia o localidad")
        submitted = st.form_submit_button("Guardar territorio")
        if submitted:
            if not state.strip():
                st.error("Indica al menos el estado.")
            else:
                execute(
                    """
                    INSERT INTO territories
                    (territory_type, state, municipality, district, electoral_section, locality)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (territory_type, state.strip(), municipality.strip(), district.strip(),
                     electoral_section.strip(), locality.strip()),
                )
                st.success("Territorio guardado.")

    territories = query(
        "SELECT id, territory_type AS nivel, state AS estado, municipality AS municipio, "
        "district AS distrito, electoral_section AS seccion, locality AS localidad FROM territories"
    )
    if territories:
        st.dataframe(pd.DataFrame(territories), use_container_width=True, hide_index=True)

    st.subheader("Asignar territorio a un perfil")
    profile_choices = profile_options()
    if not profile_choices or not territories:
        st.caption("Registra al menos un perfil y un territorio para poder crear la relación.")
    else:
        territory_choices = {
            f"#{row['id']} · {row['nivel']} · {row['estado']}"
            + (f" · {row['municipio']}" if row["municipio"] else "")
            + (f" · {row['distrito']}" if row["distrito"] else ""): row["id"]
            for row in territories
        }
        with st.form("assign_territory"):
            profile_choice = st.selectbox("Perfil", list(profile_choices), key="territory_assignment_profile")
            territory_choice = st.selectbox("Territorio", list(territory_choices), key="territory_assignment_territory")
            relationship_type = st.selectbox("Tipo de relación", ["cobertura", "origen", "representación"])
            if st.form_submit_button("Asignar territorio"):
                execute(
                    """
                    INSERT INTO profile_territories (profile_id, territory_id, relationship_type)
                    VALUES (?, ?, ?)
                    ON CONFLICT(profile_id, territory_id) DO UPDATE SET relationship_type = excluded.relationship_type
                    """,
                    (profile_choices[profile_choice], territory_choices[territory_choice], relationship_type),
                )
                st.success("Territorio asignado al perfil.")

    st.subheader("Fuentes por perfil")
    options = profile_options()
    if not options:
        st.info("Primero crea un perfil para asignarle fuentes.")
    else:
        st.caption("Puedes capturar una fuente manualmente o cargar una lista completa en CSV.")
        with st.form("new_source", clear_on_submit=True):
            chosen = st.selectbox("Perfil a monitorear", list(options))
            source_type = st.selectbox("Tipo de fuente", SOURCE_TYPES)
            source_name = st.text_input("Nombre de la fuente", placeholder="Nombre de cuenta, medio o feed")
            account_or_url = st.text_input("Cuenta o URL (opcional)")
            submitted = st.form_submit_button("Guardar fuente")
            if submitted:
                if not source_name.strip():
                    st.error("Indica un nombre para la fuente.")
                else:
                    execute(
                        "INSERT INTO sources (profile_id, source_type, name, account_or_url) VALUES (?, ?, ?, ?)",
                        (options[chosen], source_type, source_name.strip(), account_or_url.strip()),
                    )
                    st.success("Fuente guardada.")

        st.markdown("#### Carga masiva de fuentes")
        st.write(
            "Selecciona un perfil, descarga la plantilla, agrega una fila por fuente y vuelve a subir el archivo."
        )
        template = pd.DataFrame(
            [
                {"source_type": "RSS", "name": "Medio local", "account_or_url": "https://ejemplo.mx/feed"},
                {"source_type": "YouTube", "name": "Canal oficial", "account_or_url": "https://youtube.com/@canal"},
            ]
        )
        st.download_button(
            "Descargar plantilla CSV",
            data=template.to_csv(index=False).encode("utf-8-sig"),
            file_name="plantilla_fuentes.csv",
            mime="text/csv",
        )
        bulk_profile = st.selectbox("Perfil para todas las fuentes del archivo", list(options), key="bulk_profile")
        uploaded = st.file_uploader("Archivo CSV de fuentes", type="csv")
        if uploaded is not None:
            try:
                bulk_sources = pd.read_csv(uploaded).fillna("")
                required = {"source_type", "name", "account_or_url"}
                missing = required.difference(bulk_sources.columns)
                if missing:
                    st.error(
                        "Faltan estas columnas: " + ", ".join(sorted(missing))
                        + ". Usa la plantilla descargable."
                    )
                else:
                    st.dataframe(bulk_sources[list(required)], use_container_width=True, hide_index=True)
                    if st.button("Importar fuentes del archivo", type="primary"):
                        inserted = 0
                        duplicates = 0
                        invalid = 0
                        profile_id = options[bulk_profile]
                        for row in bulk_sources.to_dict("records"):
                            source_type_value = str(row["source_type"]).strip()
                            name_value = str(row["name"]).strip()
                            url_value = str(row["account_or_url"]).strip()
                            if not name_value or source_type_value not in SOURCE_TYPES:
                                invalid += 1
                                continue
                            existing = query(
                                """
                                SELECT id FROM sources
                                WHERE profile_id = ? AND source_type = ? AND name = ? AND account_or_url = ?
                                """,
                                (profile_id, source_type_value, name_value, url_value),
                            )
                            if existing:
                                duplicates += 1
                                continue
                            execute(
                                "INSERT INTO sources (profile_id, source_type, name, account_or_url) VALUES (?, ?, ?, ?)",
                                (profile_id, source_type_value, name_value, url_value),
                            )
                            inserted += 1
                        st.success(
                            f"Importación terminada: {inserted} fuentes nuevas, "
                            f"{duplicates} duplicadas omitidas y {invalid} filas no válidas."
                        )
            except Exception as error:
                st.error(f"No fue posible leer el CSV: {error}")

    sources = query(
        """
        SELECT p.name AS perfil, s.source_type AS tipo, s.name AS fuente, s.account_or_url AS cuenta_url
        FROM sources s JOIN profiles p ON p.id = s.profile_id
        ORDER BY p.name, s.source_type, s.name
        """
    )
    if sources:
        st.dataframe(pd.DataFrame(sources), use_container_width=True, hide_index=True)

elif page == "Perfil territorial":
    st.title("Perfil territorial")
    st.caption("Etapa 1 local: datos y análisis en tu computadora, sin costo de infraestructura.")
    st.caption("Define el perfil que utilizarán el mapa, los indicadores y la lectura territorial.")
    options = profile_options()
    if not options:
        st.info("Primero crea un perfil y registra al menos un territorio.")
        st.stop()
    chosen_profile = st.selectbox(
        "Perfil activo para el análisis territorial",
        list(options),
        key="territorial_profile",
    )
    territorial_profile_id = options[chosen_profile]
    st.session_state["territorial_profile_id"] = territorial_profile_id
    states_for_profile = profile_states(territorial_profile_id)
    if not states_for_profile:
        st.warning("Este perfil aún no tiene un estado identificado. Agrégalo en Territorio y fuentes.")
        st.stop()
    context_state = states_for_profile[0]
    territories_for_profile = query(
        """
        SELECT t.territory_type AS nivel, t.state AS estado, t.municipality AS municipio,
               t.district AS distrito, t.electoral_section AS seccion, t.locality AS localidad
        FROM profile_territories pt
        JOIN territories t ON t.id = pt.territory_id
        WHERE pt.profile_id = ?
        ORDER BY t.state, t.municipality, t.territory_type
        """,
        (territorial_profile_id,),
    )
    profile_sources = query(
        """
        SELECT source_type AS tipo, name AS fuente, account_or_url AS cuenta_url
        FROM sources WHERE profile_id = ?
        ORDER BY source_type, name
        """,
        (territorial_profile_id,),
    )
    col1, col2, col3 = st.columns(3)
    col1.metric("Estado activo", context_state)
    col2.metric("Territorios registrados", len(territories_for_profile))
    col3.metric("Fuentes asociadas", len(profile_sources))
    st.success(f"Contexto guardado: {chosen_profile} · {context_state}. Ahora puedes abrir Dominio territorial.")
    st.markdown("#### Territorios asociados")
    if territories_for_profile:
        st.dataframe(pd.DataFrame(territories_for_profile), use_container_width=True, hide_index=True)
    else:
        st.info("No hay territorios vinculados todavía. Agrégalos y asígnalos al perfil desde Territorio y fuentes.")
    st.markdown("#### Fuentes asociadas")
    if profile_sources:
        st.dataframe(pd.DataFrame(profile_sources), use_container_width=True, hide_index=True)
    else:
        st.caption("No hay fuentes asociadas a este perfil.")
    reference_documents = query(
        """
        SELECT id, title, document_type AS tipo, file_path AS archivo, notes AS nota, imported_at AS incorporado
        FROM reference_documents
        WHERE profile_id = ?
        ORDER BY imported_at DESC
        """,
        (territorial_profile_id,),
    )
    st.markdown("#### Documentos de referencia")
    st.caption(
        "Documentos de contexto para consulta del equipo. Se conservan separados de los resultados oficiales, "
        "indicadores INEGI y publicaciones capturadas."
    )
    if reference_documents:
        st.dataframe(pd.DataFrame(reference_documents), use_container_width=True, hide_index=True)
        for document in reference_documents:
            document_path = Path(document["archivo"])
            if document_path.exists():
                st.download_button(
                    f"Descargar: {document['title']}",
                    data=document_path.read_bytes(),
                    file_name=document_path.name,
                    mime="text/html" if document_path.suffix.casefold() == ".html" else "application/octet-stream",
                    key=f"reference_document_{document['id']}",
                )
            else:
                st.warning(f"No se encuentra el archivo: {document_path}")
    else:
        st.caption("No hay documentos de referencia incorporados para este perfil.")
    st.divider()
    st.subheader("Administrar datos territoriales")
    manage_territorial_data(context_state)
    admin_geojson = None
    if st.session_state.get("territorial_geojson_state") == context_state:
        try:
            admin_geojson = json.loads(st.session_state["territorial_geojson_data"].decode("utf-8"))
        except (KeyError, UnicodeDecodeError, json.JSONDecodeError):
            admin_geojson = None
    if admin_geojson is None:
        admin_geojson, _ = load_municipal_context(None, context_state)
    manage_inegi_indicators(context_state, admin_geojson)

elif page == "Machine Learning":
    st.title("Machine Learning")
    st.caption("Espacio para entrenar, evaluar y operar modelos locales cuando exista suficiente información validada.")
    left, middle, right = st.columns(3)
    with left:
        st.markdown("#### Datos de entrenamiento")
        st.write("Revisar mensajes clasificados y confirmados antes de usarlos como ejemplos de aprendizaje.")
    with middle:
        st.markdown("#### Modelos candidatos")
        st.write("Comparar modelos para temas, sentimiento, necesidades y clasificación territorial.")
    with right:
        st.markdown("#### Evaluación y control")
        st.write("Medir precisión, conservar versiones y mantener revisión humana antes de publicar resultados.")
    st.info(
        "Por ahora la plataforma opera con reglas y análisis bajo demanda. "
        "Este módulo queda preparado para incorporar modelos locales y evaluaciones sin mezclar sus resultados con datos originales."
    )

elif page == "Planeación":
    st.title("Planeación estratégica")
    st.caption("Consulta documentos de contexto y planeación asociados al perfil activo.")
    options = profile_options()
    if not options:
        st.info("Primero crea un perfil para consultar sus documentos de planeación.")
        st.stop()
    default_profile_id = st.session_state.get("territorial_profile_id")
    default_label = next(
        (label for label, profile_id in options.items() if profile_id == default_profile_id),
        next(iter(options)),
    )
    selected_planning_profile = st.selectbox(
        "Perfil", list(options), index=list(options).index(default_label), key="planning_profile"
    )
    planning_profile_id = options[selected_planning_profile]
    planning_documents = query(
        """
        SELECT id, state, title, document_type, file_path, source_url, notes, imported_at
        FROM reference_documents
        WHERE profile_id = ?
        ORDER BY imported_at DESC
        """,
        (planning_profile_id,),
    )
    if not planning_documents:
        st.info("Este perfil aún no tiene documentos de planeación incorporados.")
        st.stop()
    document_labels = [
        f"{row['document_type']} · {row['title']}" for row in planning_documents
    ]
    selected_document_label = st.selectbox(
        "Documento de planeación", document_labels, key="planning_document"
    )
    selected_document = planning_documents[document_labels.index(selected_document_label)]
    planning_path = Path(selected_document["file_path"])
    st.markdown(f"### {selected_document['title']}")
    st.caption(
        f"Tipo: {selected_document['document_type']} · Estado: {selected_document['state'] or 'No especificado'} · "
        f"Incorporado: {selected_document['imported_at']}"
    )
    if selected_document["notes"]:
        st.info(selected_document["notes"])
    if selected_document["source_url"]:
        st.link_button("Abrir fuente oficial", selected_document["source_url"])
    if not planning_path.exists():
        st.error("El archivo integrado ya no se encuentra en los datos locales de la plataforma.")
        st.stop()
    document_bytes = planning_path.read_bytes()
    st.download_button(
        "Descargar documento original",
        data=document_bytes,
        file_name=planning_path.name,
        mime="text/html" if planning_path.suffix.casefold() == ".html" else "application/octet-stream",
    )
    if planning_path.suffix.casefold() == ".html":
        st.markdown("#### Visor del documento")
        components.html(
            document_bytes.decode("utf-8", errors="replace"),
            height=1350,
            scrolling=True,
        )
    else:
        st.caption("El visor integrado está disponible para documentos HTML. Puedes descargar este archivo para consultarlo.")

elif page == "Configuración de conexiones":
    st.subheader("Configuración de conexiones")
    st.write(
        "Registra las claves una sola vez. No se guardan en la base de datos ni aparecen en los perfiles o fuentes."
    )
    connection_rows = [
        {"servicio": "X", "tipo de acceso": "Bearer Token", "estado": "Configurado" if get_setting("X_BEARER_TOKEN") else "Pendiente"},
        {"servicio": "YouTube", "tipo de acceso": "API key", "estado": "Configurado" if get_setting("YOUTUBE_API_KEY") else "Pendiente"},
        {"servicio": "OpenAI", "tipo de acceso": "API key", "estado": "Configurado" if get_setting("OPENAI_API_KEY") else "Pendiente"},
        {"servicio": "DENUE", "tipo de acceso": "Token", "estado": "Configurado" if get_setting("INEGI_DENUE_TOKEN") else "Pendiente"},
        {"servicio": "INEGI Indicadores", "tipo de acceso": "Token", "estado": "Configurado" if get_setting("INEGI_INDICATORS_TOKEN") else "Pendiente"},
    ]
    st.dataframe(pd.DataFrame(connection_rows), use_container_width=True, hide_index=True)
    with st.form("connection_settings"):
        st.caption("Deja un campo vacío si no deseas modificar esa conexión.")
        x_token = st.text_input("X Bearer Token", type="password")
        youtube_key = st.text_input("YouTube API key", type="password")
        openai_key = st.text_input("OpenAI API key", type="password")
        denue_token = st.text_input("Token de DENUE", type="password")
        indicators_token = st.text_input("Token de Banco de Indicadores INEGI", type="password")
        submitted = st.form_submit_button("Guardar configuración privada")
        if submitted:
            save_settings(
                {
                    "X_BEARER_TOKEN": x_token,
                    "YOUTUBE_API_KEY": youtube_key,
                    "OPENAI_API_KEY": openai_key,
                    "INEGI_DENUE_TOKEN": denue_token,
                    "INEGI_INDICATORS_TOKEN": indicators_token,
                }
            )
            st.success("Configuración guardada localmente. Las claves no se muestran en pantalla.")
    legacy_inegi_settings = Path(
        r"C:\Users\jorge\Documents\Codex\2026-09-02\Banco-Indicadores-Chihuahua\.env"
    )
    if not get_setting("INEGI_INDICATORS_TOKEN"):
        st.caption("Se detectó un proyecto local anterior con configuración de Banco de Indicadores.")
        if st.button("Importar token local de Banco de Indicadores INEGI"):
            if import_private_setting("INEGI_INDICATORS_TOKEN", legacy_inegi_settings):
                st.success("Token importado de forma privada. Ya se puede usar para consultas de INEGI.")
                st.rerun()
            else:
                st.error("No fue posible encontrar un token utilizable en el proyecto anterior.")
    st.info(
        "Esta sección prepara las conexiones. X, YouTube, INEGI y DENUE se habilitarán "
        "en Obtención de información conforme construyamos cada conector."
    )

elif page == "Obtención de información":
    st.subheader("Obtención de información")
    st.caption("Esta pantalla solo obtiene y guarda información cruda. No realiza análisis.")
    options = profile_options()
    if not options:
        st.info("Primero crea un perfil y registra sus fuentes.")
        st.stop()

    chosen = st.selectbox("Perfil para obtener información", list(options))
    profile_id = options[chosen]
    all_sources = query(
        """
        SELECT source_type AS tipo, name AS fuente, account_or_url AS cuenta_url
        FROM sources
        WHERE profile_id = ? AND active = 1
        ORDER BY source_type, name
        """,
        (profile_id,),
    )
    registered_media = [row for row in all_sources if row["tipo"] == "Medio digital"]
    institutional_sources = [row for row in all_sources if row["tipo"] == "Fuente institucional"]
    x_sources = [row for row in all_sources if row["tipo"] == "X"]
    rss_sources = query(
        "SELECT name, account_or_url FROM sources WHERE profile_id = ? AND source_type = 'RSS' AND active = 1",
        (profile_id,),
    )
    existing = query("SELECT COUNT(*) AS total FROM publications WHERE profile_id = ?", (profile_id,))[0]["total"]
    latest_runs = query(
        """
        SELECT source_type AS tipo, imported_at AS fecha, imported_records AS nuevos,
               duplicates AS duplicados, status AS estado
        FROM import_runs
        WHERE profile_id = ?
        ORDER BY imported_at DESC
        LIMIT 10
        """,
        (profile_id,),
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Medios digitales registrados", len(registered_media))
    col2.metric("Fuentes RSS activas", len(rss_sources))
    col3.metric("Otras fuentes configuradas", len(all_sources) - len(registered_media) - len(rss_sources))
    col4.metric("Registros crudos guardados", existing)

    st.subheader("Filtro de relevancia para RSS y medios web")
    st.caption(
        "Antes de guardar, RSS y medios web comparan el titular y el resumen contra estas "
        "palabras. Así se descartan notas que no se relacionan con el perfil."
    )
    configured_keywords = query(
        "SELECT keyword FROM profile_keywords WHERE profile_id = ? AND active = 1 ORDER BY keyword",
        (profile_id,),
    )
    keyword_value = "\n".join(row["keyword"] for row in configured_keywords)
    with st.form("profile_keywords"):
        keyword_input = st.text_area(
            "Palabras clave y alias (una por renglón o separadas por coma)",
            value=keyword_value,
            height=120,
            help="Incluye el nombre completo, apodos públicos, cargo y variantes relevantes.",
        )
        save_keywords = st.form_submit_button("Guardar filtro de relevancia")
        if save_keywords:
            keywords = sorted({
                item.strip() for item in keyword_input.replace(",", "\n").splitlines()
                if len(item.strip()) >= 3
            })
            if not keywords:
                st.error("Registra al menos una palabra clave de tres caracteres o más.")
            else:
                execute("DELETE FROM profile_keywords WHERE profile_id = ?", (profile_id,))
                for keyword in keywords:
                    execute(
                        "INSERT INTO profile_keywords (profile_id, keyword, active) VALUES (?, ?, 1)",
                        (profile_id, keyword),
                    )
                st.success(f"Filtro guardado con {len(keywords)} palabras clave.")
                st.rerun()

    st.subheader("Fuentes disponibles por tipo")
    source_types = ["Medio digital", "RSS", "X", "YouTube", "Fuente institucional", "Importación de archivo", "Encuesta"]
    cards = st.columns(3)
    for index, source_type in enumerate(source_types):
        configured = [row for row in all_sources if row["tipo"] == source_type]
        cards[index % 3].info(f"**{source_type}**\n\n{len(configured)} fuente(s) configurada(s)")

    if all_sources:
        st.dataframe(pd.DataFrame(all_sources), use_container_width=True, hide_index=True)
    else:
        st.warning("No hay fuentes activas registradas para este perfil.")

    st.subheader("Ejecutar obtención manual")
    st.write("Elige el botón del tipo de fuente que deseas consultar. Ninguna ejecución es automática.")
    media_button, rss_button = st.columns(2)
    if media_button.button("Ejecutar medios web", type="primary", disabled=not registered_media):
        with st.spinner("Leyendo titulares públicos de los medios registrados..."):
            result = capture_media_headlines(profile_id)
        record_obtainment_run(profile_id, "Medio digital", result)
        st.success(
            f"Consulta terminada: {result['new_publications']} titulares nuevos y "
            f"{result['duplicates']} duplicados y {result['not_relevant']} sin relación omitidos "
            f"en {result['sources']} medios."
        )
        if result["errors"]:
            st.warning("Algunos medios no respondieron:\n\n- " + "\n- ".join(result["errors"]))
        st.rerun()

    if rss_button.button("Ejecutar RSS", disabled=not rss_sources):
        with st.spinner("Leyendo feeds RSS..."):
            result = capture_rss(profile_id)
        record_obtainment_run(profile_id, "RSS", result)
        st.success(
            f"Consulta terminada: {result['new_publications']} publicaciones nuevas y "
            f"{result['duplicates']} duplicadas y {result['not_relevant']} sin relación omitidas."
        )
        if result["errors"]:
            st.warning("Algunas fuentes requieren revisión:\n\n- " + "\n- ".join(result["errors"]))
        st.rerun()

    x_default_query = (
        '("Maru Campos" OR "María Eugenia Campos") lang:es -is:retweet'
        if "María Eugenia Campos" in chosen
        else f'"{chosen.rsplit(" (#", 1)[0]}" lang:es -is:retweet'
    )
    with st.expander("Configurar búsqueda de X", expanded=bool(x_sources)):
        st.caption(
            "Busca conversación pública reciente. La fuente X identifica el perfil; "
            "los términos definen qué publicaciones se consultan."
        )
        x_query = st.text_input(
            "Términos de búsqueda de X",
            value=x_default_query,
            help='Ejemplo: ("Maru Campos" OR "María Eugenia Campos") lang:es -is:retweet',
        )
        x_limit = st.slider("Máximo de publicaciones por consulta", 10, 100, 25, 5)
        if st.button(
            "Ejecutar X",
            type="primary",
            disabled=not x_sources,
            help=None if x_sources else "Registra una fuente de tipo X para este perfil.",
        ):
            with st.spinner("Consultando publicaciones públicas recientes de X..."):
                result = capture_x_search(profile_id, x_query, x_limit)
            record_obtainment_run(profile_id, "X", result)
            if result["errors"]:
                st.error("La consulta de X terminó con observaciones:\n\n- " + "\n- ".join(result["errors"]))
            else:
                st.success(
                    f"Consulta terminada: {result['new_publications']} publicaciones nuevas y "
                    f"{result['duplicates']} duplicadas omitidas."
                )
            st.rerun()

    youtube_button, institutional_button, file_button = st.columns(3)
    youtube_button.button("Ejecutar YouTube", disabled=True, help="Pendiente registrar la clave privada de YouTube.")
    if institutional_button.button(
        "Ejecutar fuentes institucionales",
        disabled=not institutional_sources,
    ):
        with st.spinner("Leyendo titulares públicos de las fuentes institucionales..."):
            result = capture_media_headlines(profile_id, "Fuente institucional")
        record_obtainment_run(profile_id, "Fuente institucional", result)
        st.success(
            f"Consulta terminada: {result['new_publications']} registros nuevos y "
            f"{result['duplicates']} duplicados y {result['not_relevant']} sin relación omitidos."
        )
        if result["errors"]:
            st.warning("Algunas fuentes no respondieron:\n\n- " + "\n- ".join(result["errors"]))
        st.rerun()
    file_button.button(
        "Importar archivo",
        disabled=True,
        help="La importación de archivos se habilitará como conector independiente.",
    )

    st.subheader("Administrar feeds RSS")
    action_left, action_right = st.columns(2)
    if action_left.button("Buscar feeds RSS en medios registrados", disabled=not registered_media):
        with st.spinner("Buscando feeds RSS publicados por los medios..."):
            discovery = discover_rss(profile_id)
        st.success(
            f"Revisión terminada: {discovery['added']} feeds nuevos, "
            f"{discovery['existing']} ya registrados, {discovery['checked']} medios revisados."
        )
        if discovery["errors"]:
            st.warning("Algunos sitios no respondieron:\n\n- " + "\n- ".join(discovery["errors"]))
        st.rerun()
    with action_right.form("manual_rss", clear_on_submit=True):
        manual_name = st.text_input("Nombre del feed RSS")
        manual_url = st.text_input("URL completa del feed RSS")
        add_rss = st.form_submit_button("Agregar feed RSS")
        if add_rss:
            if not manual_name.strip() or not manual_url.strip().startswith(("http://", "https://")):
                st.error("Escribe nombre y una URL válida que inicie con http:// o https://.")
            else:
                execute(
                    "INSERT INTO sources (profile_id, source_type, name, account_or_url) VALUES (?, 'RSS', ?, ?)",
                    (profile_id, manual_name.strip(), manual_url.strip()),
                )
                st.success("Feed RSS agregado. Actualiza la página para verlo en la lista.")

    if not rss_sources:
        st.warning(
            "Todavía no hay feeds RSS detectados. Presiona “Buscar feeds RSS en medios registrados” "
            "para revisar los medios de la tabla anterior."
        )
    else:
        st.dataframe(pd.DataFrame(rss_sources), use_container_width=True, hide_index=True)

    st.subheader("Bitácora de ejecuciones")
    if latest_runs:
        st.dataframe(pd.DataFrame(latest_runs), use_container_width=True, hide_index=True)
    else:
        st.caption("Aún no se ha ejecutado ninguna obtención para este perfil.")

elif page == "Dominio territorial":
    render_domain_header("Dominio territorial")
    options = profile_options()
    if not options:
        st.warning("Primero crea un perfil y define su territorio para abrir el visor.")
        st.stop()
    chosen_profile = st.selectbox("Perfil territorial activo", list(options), key="territorial_viewer_profile")
    viewer_profile_id = options[chosen_profile]
    viewer_states = profile_states(viewer_profile_id)
    if not viewer_states:
        st.warning("El perfil activo no tiene un estado asociado en Perfil territorial.")
        st.stop()
    viewer_state = st.selectbox("Estado", viewer_states, key="territorial_viewer_state")
    viewer_geojson, viewer_source = load_municipal_context(None, viewer_state)
    if viewer_geojson is None:
        st.warning(f"No se encontró una capa municipal para {viewer_state}.")
        st.stop()
    viewer_municipalities = municipal_dataframe(viewer_geojson)
    if viewer_municipalities.empty:
        st.warning("La capa municipal no contiene municipios disponibles.")
        st.stop()
    viewer_geojson = json.loads(json.dumps(viewer_geojson))
    for feature in viewer_geojson.get("features", []):
        properties = feature.setdefault("properties", {})
        properties["municipio"] = properties.get("municipio") or properties.get("nom_agem", "Sin nombre")
        properties["clave_municipio"] = properties.get("clave_municipio") or properties.get("cve_agem", "")
    viewer_names = sorted(viewer_municipalities["municipio"].dropna().astype(str).unique().tolist())
    viewer_options = ["Selecciona un municipio"] + viewer_names
    viewer_election_options = query(
        """
        SELECT DISTINCT election_year, election_type
        FROM territorial_election_results
        WHERE state = ?
        ORDER BY election_year DESC, election_type
        """,
        (viewer_state,),
    )
    viewer_years = sorted({int(row["election_year"]) for row in viewer_election_options}, reverse=True)
    viewer_election_year = (
        st.selectbox("Elección visible", viewer_years, key="territorial_viewer_election_year")
        if viewer_years else None
    )
    viewer_types = {
        row["election_type"] for row in viewer_election_options
        if viewer_election_year is not None and int(row["election_year"]) == viewer_election_year
    }
    viewer_election_type = "Ayuntamientos" if "Ayuntamientos" in viewer_types else "Diputaciones locales"
    viewer_election_rows = query(
        """
        SELECT municipality_code, municipality, payload
        FROM territorial_election_results
        WHERE state = ? AND election_type = ? AND election_year = ?
        """,
        (viewer_state, viewer_election_type, viewer_election_year),
    ) if viewer_election_year is not None else []
    viewer_election_data = decode_election_rows(viewer_election_rows)
    election_layers = {"Mapa municipal base": None}
    for key, label in ELECTORAL_VOTE_LABELS.items():
        if any(float(row["payload"].get(key) or 0) > 0 for row in viewer_election_data):
            election_layers[f"Votos · {label}"] = key
    pending_map_municipality = st.session_state.pop("territorial_viewer_pending_municipality", None)
    if pending_map_municipality in viewer_options:
        st.session_state["territorial_viewer_municipality"] = pending_map_municipality
    if st.session_state.get("territorial_viewer_municipality") not in viewer_options:
        st.session_state["territorial_viewer_municipality"] = "Selecciona un municipio"
    control_layer, control_municipality = st.columns([1, 1])
    with control_layer:
        selected_election_layer = st.selectbox(
            "Capa electoral del mapa", list(election_layers), key="territorial_viewer_election_layer",
            help="Selecciona un partido, coalición o candidatura para colorear los municipios por votos publicados.",
        )
    with control_municipality:
        active_viewer_municipality = st.selectbox(
            "Municipio consultado", viewer_options, key="territorial_viewer_municipality",
            help="Este selector sincroniza el mapa y las tres fichas del municipio.",
        )
    selected_vote_column = election_layers[selected_election_layer]
    viewer_map_geojson = viewer_geojson
    map_fill_color = [203, 213, 225, 180]
    map_tooltip = "<b>{municipio}</b><br/>Clave municipal: {clave_municipio}"
    if selected_vote_column:
        viewer_map_geojson = attach_election_results(viewer_geojson, viewer_election_data)
        viewer_map_geojson = colorize_geojson(
            viewer_map_geojson, selected_vote_column,
            low_color=(255, 237, 213), high_color=(180, 83, 9),
        )
        map_fill_color = "properties.pulso_color"
        map_tooltip = f"<b>{{municipio}}</b><br/>{selected_election_layer}: {{{selected_vote_column}}}"
    selected_features = [
        feature for feature in viewer_map_geojson.get("features", [])
        if feature.get("properties", {}).get("municipio") == active_viewer_municipality
    ]
    st.markdown('<div class="domain-section">1. Selecciona un municipio en el mapa</div>', unsafe_allow_html=True)
    map_event = st.pydeck_chart(
        pdk.Deck(
            map_style="light",
            initial_view_state=pdk.ViewState(**contextual_view(
                {"type": "FeatureCollection", "features": selected_features}
                if selected_features else viewer_map_geojson
            )),
            layers=[
                pdk.Layer(
                    "GeoJsonLayer", id="territorial-viewer-map", data=viewer_map_geojson,
                    opacity=0.72, stroked=True, filled=True,
                    get_fill_color=map_fill_color, get_line_color=[71, 85, 105, 170],
                    line_width_min_pixels=1, pickable=True,
                ),
                *(
                    [pdk.Layer(
                        "GeoJsonLayer", id="territorial-viewer-selection",
                        data={"type": "FeatureCollection", "features": selected_features},
                        opacity=0.9, stroked=True, filled=True,
                        get_fill_color=[14, 116, 144, 185], get_line_color=[15, 23, 42, 255],
                        line_width_min_pixels=3, pickable=False,
                    )] if selected_features else []
                ),
            ],
            tooltip={
                "html": map_tooltip,
                "style": {"backgroundColor": "#0f172a", "color": "white"},
            },
        ),
        use_container_width=True, height=520, on_select="rerun", selection_mode="single-object",
        key=(
            f"territorial_viewer_map_{municipality_match_key(active_viewer_municipality)}_"
            f"{selected_vote_column or 'base'}"
        ),
    )
    selected_objects = map_event.selection.objects.get("territorial-viewer-map", [])
    if not selected_objects:
        selected_objects = [
            selected for objects in map_event.selection.objects.values() for selected in objects
        ]
    if selected_objects:
        selected_feature = selected_objects[-1]
        selected_properties = selected_feature.get("properties", {}) or selected_feature.get("object", {}).get("properties", {})
        clicked_municipality = (
            selected_feature.get("municipio")
            or selected_feature.get("nom_agem")
            or selected_properties.get("municipio")
            or selected_properties.get("nom_agem")
        )
        if clicked_municipality in viewer_names and clicked_municipality != active_viewer_municipality:
            st.session_state["territorial_viewer_pending_municipality"] = clicked_municipality
            st.rerun()
    if active_viewer_municipality == "Selecciona un municipio":
        st.info("Haz clic sobre el mapa o usa la lista. Al seleccionar un municipio se abrirán sus tres fichas.")
        st.caption(f"Capa municipal activa: {viewer_source}")
        st.stop()
    viewer_row = viewer_municipalities.loc[
        viewer_municipalities["municipio"].astype(str) == active_viewer_municipality
    ].iloc[0]
    st.markdown('<div class="domain-section">2. Consulta la información del municipio</div>', unsafe_allow_html=True)
    municipality_title, municipality_state, municipality_code = st.columns([2, 1, 1])
    municipality_title.metric("Municipio", active_viewer_municipality)
    municipality_state.metric("Estado", viewer_state)
    municipality_code.metric("Clave municipal", str(viewer_row.get("clave_municipio") or "No disponible"))
    territorial_tab, electoral_tab, inegi_tab = st.tabs(["Ficha territorial", "Ficha electoral", "Ficha INEGI"])
    with territorial_tab:
        st.markdown("#### Identificación territorial")
        region_geojson = attach_ped_sonora_regions(viewer_geojson) if viewer_state == "Sonora" else viewer_geojson
        region_feature = next(
            (feature for feature in region_geojson.get("features", [])
             if feature.get("properties", {}).get("municipio") == active_viewer_municipality),
            None,
        )
        region_name = (region_feature or {}).get("properties", {}).get("region_ped", "No aplica")
        territorial_a, territorial_b, territorial_c = st.columns(3)
        territorial_a.metric("Región PED", region_name)
        territorial_b.metric("Plan municipal", viewer_row.get("pmd_estatus") or "Sin registro")
        territorial_c.metric("Capa activa", "Municipal")
        st.markdown("#### Referencia poblacional")
        population_value = pd.to_numeric(pd.Series([viewer_row.get("poblacion")]), errors="coerce").iloc[0]
        housing_value = pd.to_numeric(pd.Series([viewer_row.get("viviendas")]), errors="coerce").iloc[0]
        population_a, population_b, population_c = st.columns(3)
        population_a.metric(
            "Población total",
            "No disponible" if pd.isna(population_value) else f"{population_value:,.0f}",
        )
        population_b.metric(
            "Viviendas",
            "No disponible" if pd.isna(housing_value) else f"{housing_value:,.0f}",
        )
        population_c.metric("Cobertura", "Municipal")
        if viewer_row.get("pmd_url"):
            st.link_button("Consultar plan municipal de desarrollo", viewer_row["pmd_url"])
        st.caption("Esta ficha ofrece una referencia rápida. Los indicadores sociales y de servicios se consultan completos en la ficha INEGI.")
    with electoral_tab:
        election_payloads = {
            municipality_match_key(row["municipality"]): row["payload"]
            for row in viewer_election_data
        }
        election_payload = election_payloads.get(municipality_match_key(active_viewer_municipality))
        if not election_payload:
            st.info("No hay resultados electorales municipales cargados para este municipio.")
        else:
            st.markdown(f"#### {viewer_election_type} {viewer_election_year}")
            electoral_a, electoral_b, electoral_c, electoral_d = st.columns(4)
            electoral_a.metric("Lista nominal", f"{float(election_payload.get('lista_nominal') or 0):,.0f}")
            electoral_b.metric("Votos totales", f"{float(election_payload.get('votes_total') or 0):,.0f}")
            electoral_c.metric("Participación", f"{float(election_payload.get('participacion_pct') or 0):.1f}%")
            electoral_d.metric("Votos nulos", f"{float(election_payload.get('votes_nulos') or 0):,.0f}")
            render_electoral_breakdown(election_payload)
            st.caption(f"Resultados oficiales integrados para {viewer_election_type} de {viewer_state}, {viewer_election_year}.")
    with inegi_tab:
        st.markdown("#### Indicadores municipales disponibles")
        inegi_base = [
            ("Población total", viewer_row.get("poblacion"), "habitantes"),
            ("Viviendas", viewer_row.get("viviendas"), "viviendas"),
            ("Acceso a internet", viewer_row.get("internet_pct"), "%"),
            ("Agua entubada", viewer_row.get("agua_pct"), "%"),
            ("Drenaje", viewer_row.get("drenaje_pct"), "%"),
            ("Afiliación a salud", viewer_row.get("salud_pct"), "%"),
        ]
        inegi_cards = [(label, value, unit) for label, value, unit in inegi_base if pd.notna(value)]
        if inegi_cards:
            card_columns = st.columns(min(3, len(inegi_cards)))
            for index, (label, value, unit) in enumerate(inegi_cards):
                numeric_value = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
                display_value = "No disponible" if pd.isna(numeric_value) else (
                    f"{numeric_value:.1f}%" if unit == "%" else f"{numeric_value:,.0f}"
                )
                card_columns[index % len(card_columns)].metric(label, display_value)
        stored_inegi = query(
            """
            SELECT indicator_name AS Indicador, value AS Valor, unit AS Unidad, period AS Periodo
            FROM territorial_indicators
            WHERE state = ? AND municipality_code = ?
            ORDER BY indicator_name, period DESC
            """,
            (viewer_state, str(viewer_row.get("clave_municipio") or "").zfill(3)),
        )
        if stored_inegi:
            st.markdown("##### Indicadores oficiales cargados")
            st.dataframe(pd.DataFrame(stored_inegi), use_container_width=True, hide_index=True)
        else:
            st.caption("No hay indicadores adicionales descargados para este municipio. Puedes incorporarlos desde Perfil territorial.")
    st.caption(f"Capa municipal activa: {viewer_source}")

elif page == "Diagnóstico regional del PED":
    render_domain_header("Diagnóstico regional del PED")
    regional_geojson_source, regional_source = load_municipal_context(None, "Sonora")
    if regional_geojson_source is None:
        st.error("No fue posible cargar la capa municipal de Sonora para mostrar la regionalización.")
        st.stop()
    regional_geojson = attach_ped_sonora_regions(regional_geojson_source)
    regional_rows = [
        {
            "Región PED": feature.get("properties", {}).get("region_ped", "Sin asignación"),
            "Municipio": feature.get("properties", {}).get("municipio", "Sin nombre"),
        }
        for feature in regional_geojson.get("features", [])
    ]
    regional_frame = pd.DataFrame(regional_rows)
    region_options = ["Todas las regiones"] + sorted(
        region for region in regional_frame["Región PED"].dropna().unique()
        if region != "Sin asignación"
    )
    pending_region = st.session_state.pop("pending_ped_region", None)
    if pending_region in region_options:
        st.session_state["ped_region_context_combo"] = pending_region
    selected_ped_region = st.selectbox(
        "Región del PED", region_options, key="ped_region_context_combo",
        help="Elige una región para consultar su ficha y resaltarla en el mapa.",
    )
    mapped_regions = len(regional_frame[regional_frame["Región PED"] != "Sin asignación"])
    metric_a, metric_b, metric_c = st.columns(3)
    metric_a.metric("Regiones", len(PED_SONORA_REGIONS))
    metric_b.metric("Municipios asignados", mapped_regions)
    metric_c.metric(
        "Municipios de la región",
        mapped_regions if selected_ped_region == "Todas las regiones" else int(
            (regional_frame["Región PED"] == selected_ped_region).sum()
        ),
    )
    if selected_ped_region == "Todas las regiones":
        st.info("Selecciona una región para consultar su ficha de diagnóstico del PED.")
    else:
        region_profile = PED_SONORA_REGION_PROFILES.get(selected_ped_region, {})
        region_municipalities = sorted(
            regional_frame.loc[regional_frame["Región PED"] == selected_ped_region, "Municipio"].tolist()
        )
        with st.container(border=True):
            st.markdown(f"### Ficha regional · {selected_ped_region}")
            ficha_a, ficha_b = st.columns([1, 2])
            with ficha_a:
                st.caption("MUNICIPIOS")
                st.write(", ".join(region_municipalities))
            with ficha_b:
                st.caption("VOCACIÓN TERRITORIAL")
                st.write(region_profile.get("vocacion", "Información no disponible."))
            st.caption("DIAGNÓSTICO DEL PED 2021–2027")
            st.write(region_profile.get("diagnostico", "Información no disponible."))
            st.caption("Fuente: Diagnóstico por Regiones del Plan Estatal de Desarrollo Sonora 2021–2027.")
    outline_features = (
        [] if selected_ped_region == "Todas las regiones" else [
            feature for feature in regional_geojson.get("features", [])
            if feature.get("properties", {}).get("region_ped") == selected_ped_region
        ]
    )
    st.markdown("### Mapa regional")
    st.caption("Cada color identifica una región; no representa un nivel de desempeño.")
    regional_map_event = st.pydeck_chart(
        pdk.Deck(
            map_style="light", initial_view_state=pdk.ViewState(**contextual_view(
                {"type": "FeatureCollection", "features": outline_features}
                if outline_features else regional_geojson
            )),
            layers=[
                pdk.Layer(
                    "GeoJsonLayer", id="regiones-ped-sonora", data=regional_geojson,
                    opacity=0.78, stroked=True, filled=True,
                    get_fill_color="properties.region_ped_color",
                    get_line_color=[51, 65, 85, 150], line_width_min_pixels=1, pickable=True,
                ),
                *(
                    [pdk.Layer(
                        "GeoJsonLayer", data={"type": "FeatureCollection", "features": outline_features},
                        opacity=1, stroked=True, filled=False,
                        get_line_color=[15, 23, 42, 255], line_width_min_pixels=4, pickable=False,
                    )] if outline_features else []
                ),
            ],
            tooltip={
                "html": "<b>{municipio}</b><br/>Región PED: {region_ped}",
                "style": {"backgroundColor": "#0f172a", "color": "white"},
            },
        ),
        use_container_width=True, height=560, on_select="rerun", selection_mode="single-object",
        key=f"ped_regional_map_{municipality_match_key(selected_ped_region)}",
    )
    selected_region_objects = regional_map_event.selection.objects.get("regiones-ped-sonora", [])
    if not selected_region_objects:
        selected_region_objects = [
            selected for objects in regional_map_event.selection.objects.values() for selected in objects
        ]
    if selected_region_objects:
        selected_region = selected_region_objects[-1]
        selected_properties = selected_region.get("properties", {}) or selected_region.get("object", {}).get("properties", {})
        clicked_region = selected_region.get("region_ped") or selected_properties.get("region_ped")
        if clicked_region in region_options and clicked_region != selected_ped_region:
            st.session_state["pending_ped_region"] = clicked_region
            st.rerun()
    summary = (
        regional_frame[regional_frame["Región PED"] != "Sin asignación"]
        .groupby("Región PED", as_index=False)
        .agg(Municipios=("Municipio", "count"), Integrantes=("Municipio", lambda values: ", ".join(sorted(values))))
        .sort_values("Región PED")
    )
    if selected_ped_region != "Todas las regiones":
        summary = summary[summary["Región PED"] == selected_ped_region]
    st.markdown("### Municipios que integran la región")
    st.dataframe(summary, use_container_width=True, hide_index=True)
    st.caption(f"Capa municipal: {regional_source}")

elif page in {"Territorio", "Electoral", "Visor electoral", "INEGI"}:
    render_domain_header(page)
    st.markdown(
        '<div class="domain-note">Selecciona un perfil, define el tema o nivel de consulta y utiliza el mapa como apoyo visual para comparar y profundizar.</div>',
        unsafe_allow_html=True,
    )

    options = profile_options()
    if not options:
        st.warning("Primero crea un perfil para abrir su lectura territorial en el mapa.")
        st.stop()
    previous_profile_id = st.session_state.get("territorial_profile_id")
    initial_profile = next(
        (label for label, value in options.items() if value == previous_profile_id),
        next(iter(options)),
    )
    profile_bar, profile_help = st.columns([2, 3])
    with profile_bar:
        chosen_profile = st.selectbox(
            "Perfil territorial activo",
            list(options),
            index=list(options).index(initial_profile),
            key="territorial_map_profile",
            help="El mapa, el pulso y los mensajes se consultarán para este perfil.",
        )
    with profile_help:
        st.caption(
            "Selecciona aquí a la persona, institución o tema que deseas consultar. "
            "Puedes crear o editar perfiles en ‘Perfiles y trayectorias’."
        )
    gis_profile_id = options[chosen_profile]
    st.session_state["territorial_profile_id"] = gis_profile_id
    state_options = profile_states(gis_profile_id)
    if not state_options:
        st.warning("El Perfil territorial activo no tiene un estado identificado.")
        st.stop()
    context_state = state_options[0]
    saved_geojson = None
    if st.session_state.get("territorial_geojson_state") == context_state:
        try:
            saved_geojson = json.loads(st.session_state["territorial_geojson_data"].decode("utf-8"))
        except (KeyError, UnicodeDecodeError, json.JSONDecodeError):
            saved_geojson = None
    if saved_geojson is not None:
        geojson = saved_geojson
        gis_source = st.session_state.get("territorial_geojson_name", "capa cargada")
    else:
        geojson, gis_source = load_municipal_context(None, context_state)
    if geojson is None:
        st.warning(
            f"No se encontró una capa municipal para {context_state}. Cárgala desde Perfil territorial."
        )
        st.stop()

    available_election_rows = query(
        """
        SELECT DISTINCT election_year, election_type
        FROM territorial_election_results
        WHERE state = ?
        ORDER BY election_year DESC, election_type
        """,
        (context_state,),
    )
    available_election_years = sorted(
        {int(row["election_year"]) for row in available_election_rows}, reverse=True
    )
    selected_election_year = (
        st.selectbox(
            "Elección consultada",
            available_election_years,
            key="territorial_election_year",
            help="Cambia el año para consultar los resultados históricos disponibles.",
        )
        if available_election_years else 2024
    )
    types_for_year = {
        row["election_type"] for row in available_election_rows
        if int(row["election_year"]) == selected_election_year
    }
    selected_municipal_election_type = (
        "Ayuntamientos" if "Ayuntamientos" in types_for_year else "Diputaciones locales"
    )

    # Resultados municipales: se conservan por año y tipo de elección, y se unen
    # a la capa del mismo estado sin reemplazar los procesos históricos.
    existing_election_rows = query(
        """
        SELECT municipality_code, municipality, payload
        FROM territorial_election_results
        WHERE state = ? AND election_type = ? AND election_year = ?
        ORDER BY municipality
        """,
        (context_state, selected_municipal_election_type, selected_election_year),
    )
    if existing_election_rows:
        geojson = attach_election_results(geojson, decode_election_rows(existing_election_rows))

    municipalities = municipal_dataframe(geojson)
    if municipalities.empty:
        st.warning("La capa no contiene municipios con atributos para mostrar.")
        st.stop()

    if page == "Territorio":
        st.markdown('<div class="domain-section">Mapa municipal</div>', unsafe_allow_html=True)
        st.caption("Esta vista sirve para ubicar y consultar municipios. Los indicadores comparativos se revisan en INEGI.")
        territory_municipalities = sorted(municipalities["municipio"].dropna().astype(str).unique().tolist())
        territory_options = ["Selecciona un municipio"] + territory_municipalities
        selected_territory_municipality = st.selectbox(
            "Municipio consultado", territory_options, key="territory_municipality_combo",
            help="Elige un municipio para abrir su ficha territorial.",
        )
        territory_metric_a, territory_metric_b, territory_metric_c = st.columns(3)
        territory_metric_a.metric("Municipios disponibles", len(territory_municipalities))
        territory_metric_b.metric("Estado activo", context_state)
        territory_metric_c.metric(
            "Municipio seleccionado",
            "Ninguno" if selected_territory_municipality == "Selecciona un municipio" else selected_territory_municipality,
        )
        territory_geojson = json.loads(json.dumps(geojson))
        for feature in territory_geojson.get("features", []):
            properties = feature.setdefault("properties", {})
            properties["municipio"] = properties.get("municipio") or properties.get("nom_agem", "Sin nombre")
            properties["clave_municipio"] = properties.get("clave_municipio") or properties.get("cve_agem", "")
        map_features = territory_geojson.get("features", [])
        selected_features = []
        if selected_territory_municipality != "Selecciona un municipio":
            selected_features = [
                feature for feature in map_features
                if str(feature.get("properties", {}).get("municipio", "")) == selected_territory_municipality
            ]
        st.pydeck_chart(
            pdk.Deck(
                map_style="light",
                initial_view_state=pdk.ViewState(**contextual_view(territory_geojson)),
                layers=[
                    pdk.Layer(
                        "GeoJsonLayer", id="territory-municipal-map", data=territory_geojson,
                        opacity=0.72, stroked=True, filled=True,
                        get_fill_color=[203, 213, 225, 180],
                        get_line_color=[71, 85, 105, 170], line_width_min_pixels=1,
                        pickable=True,
                    ),
                    *(
                        [pdk.Layer(
                            "GeoJsonLayer", id="territory-selected-municipality",
                            data={"type": "FeatureCollection", "features": selected_features},
                            opacity=0.9, stroked=True, filled=True,
                            get_fill_color=[14, 116, 144, 185],
                            get_line_color=[15, 23, 42, 255], line_width_min_pixels=3,
                            pickable=True,
                        )] if selected_features else []
                    ),
                ],
                tooltip={
                    "html": "<b>{municipio}</b><br/>Clave municipal: {clave_municipio}",
                    "style": {"backgroundColor": "#0f172a", "color": "white"},
                },
            ),
            use_container_width=True, height=560, key="territory_municipal_map",
        )
        st.markdown('<div class="domain-section">Ficha territorial</div>', unsafe_allow_html=True)
        if selected_territory_municipality == "Selecciona un municipio":
            st.info("Selecciona un municipio para consultar su ficha de identificación territorial.")
        else:
            territory_row = municipalities.loc[
                municipalities["municipio"].astype(str) == selected_territory_municipality
            ].iloc[0]
            ficha_left, ficha_middle, ficha_right = st.columns(3)
            ficha_left.metric("Municipio", selected_territory_municipality)
            ficha_middle.metric("Estado", context_state)
            ficha_right.metric("Clave municipal", str(territory_row.get("clave_municipio") or "No disponible"))
            st.caption(
                "La ficha identifica el territorio seleccionado. Para población, servicios, salud, educación "
                "u otros valores oficiales, abre el módulo INEGI."
            )
        st.markdown('<div class="domain-section">Municipios disponibles</div>', unsafe_allow_html=True)
        st.dataframe(
            municipalities[["clave_municipio", "municipio"]].sort_values("municipio"),
            use_container_width=True, hide_index=True,
        )
        st.caption(f"Capa municipal activa: {gis_source}")
        st.stop()

    st.markdown("### 1. Ruta de consulta")
    district_result_rows = query(
        """
        SELECT district_code, district_name, payload, source
        FROM territorial_district_results
        WHERE state = ? AND election_type = 'Diputaciones locales' AND election_year = ?
        ORDER BY district_code
        """,
        (context_state, selected_election_year),
    )
    section_result_rows = query(
        """
        SELECT district_code, section_code, municipality_code, municipality, payload, source
        FROM territorial_section_results
        WHERE state = ? AND election_type = 'Diputaciones locales' AND election_year = ?
        ORDER BY district_code, section_code
        """,
        (context_state, selected_election_year),
    )
    consultation_area = {
        "Territorio": "Territorio",
        "Electoral": "Electoral",
        "Visor electoral": "Electoral",
        "INEGI": "INEGI",
    }[page]
    st.caption(f"Dominio territorial activo: **{consultation_area}**.")
    district_level_label = f"Distritos locales · resultados {selected_election_year}"
    section_level_label = f"Secciones electorales · resultados {selected_election_year}"
    district_municipality_level_label = f"Municipios del distrito · resultados {selected_election_year}"
    district_section_level_label = f"Secciones del distrito · resultados {selected_election_year}"
    municipal_election_only = False
    if consultation_area == "Electoral":
        electoral_routes = []
        if district_result_rows:
            electoral_routes.append("Distritos locales")
        electoral_routes.append("Municipios")
        if section_result_rows:
            electoral_routes.append("Secciones electorales")
            electoral_routes.extend(["Distrito → Municipios", "Distrito → Secciones"])
        electoral_route = st.radio(
            "Ruta electoral", electoral_routes, horizontal=True, key="electoral_navigation_route",
        )
        if electoral_route == "Panorama estatal":
            municipal_results = decode_election_rows(existing_election_rows)
            municipal_payloads = [row["payload"] for row in municipal_results]
            total_list = sum(float(row.get("lista_nominal") or 0) for row in municipal_payloads)
            total_votes = sum(float(row.get("votes_total") or 0) for row in municipal_payloads)
            statewide_participation = (total_votes / total_list * 100) if total_list else 0
            st.markdown("### 2. Panorama estatal · Sonora 2024")
            panorama_left, panorama_middle, panorama_right = st.columns(3)
            panorama_left.metric("Municipios con resultado", len(municipal_results))
            panorama_middle.metric("Lista nominal", f"{total_list:,.0f}")
            panorama_right.metric("Participación agregada", f"{statewide_participation:.1f}%")
            if district_result_rows:
                st.metric("Distritos locales con resultado", len(district_result_rows))
            if municipal_results:
                overview = pd.DataFrame([
                    {
                        "Municipio": row["municipality"],
                        "Participación electoral (%)": row["payload"].get("participacion_pct"),
                        "Votos totales": row["payload"].get("votes_total"),
                    }
                    for row in municipal_results
                ]).sort_values("Participación electoral (%)", ascending=False)
                st.markdown("### 3. Participación municipal")
                st.bar_chart(overview.set_index("Municipio")[["Participación electoral (%)"]], height=360)
                st.dataframe(overview, use_container_width=True, hide_index=True)
            st.caption("Resultados oficiales integrados para 2024. Selecciona Municipios, Distritos o Secciones para profundizar.")
            st.stop()
        if electoral_route == "Distritos locales":
            selected_level = district_level_label
        elif electoral_route == "Secciones electorales":
            selected_level = section_level_label
        elif electoral_route == "Distrito → Municipios":
            selected_level = district_municipality_level_label
        elif electoral_route == "Distrito → Secciones":
            selected_level = district_section_level_label
        else:
            selected_level = "Municipios"
            municipal_election_only = electoral_route == "Municipios"
    else:
        selected_level = "Municipios"
    if selected_level == district_municipality_level_label:
        # Esta ruta no reutiliza los resultados municipales generales: suma
        # exclusivamente las secciones publicadas dentro del distrito elegido.
        section_rows = []
        for row in section_result_rows:
            try:
                payload = json.loads(row["payload"])
            except (TypeError, json.JSONDecodeError):
                continue
            section_rows.append({
                "Distrito": str(row["district_code"]).zfill(2),
                "Sección": str(row["section_code"]).zfill(4),
                "Municipio": row["municipality"] or "Sin municipio",
                "Clave municipio": str(row["municipality_code"] or "").zfill(3),
                "payload": payload,
            })
        district_options = sorted({row["Distrito"] for row in section_rows})
        chosen_district = st.selectbox(
            "Distrito de origen", district_options, key="district_municipality_route_district",
            help="Los municipios y sus cifras se calculan únicamente con las secciones de este distrito.",
        )
        district_sections = [row for row in section_rows if row["Distrito"] == chosen_district]
        aggregate: dict[tuple[str, str], dict] = {}
        for row in district_sections:
            key = (row["Clave municipio"], municipality_match_key(row["Municipio"]))
            bucket = aggregate.setdefault(key, {
                "Municipio": row["Municipio"], "Clave municipio": row["Clave municipio"],
                "Secciones con resultado": 0, "payload": {},
            })
            bucket["Secciones con resultado"] += 1
            for field, value in row["payload"].items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    bucket["payload"][field] = bucket["payload"].get(field, 0) + value
        municipal_records = []
        for bucket in aggregate.values():
            payload = bucket["payload"]
            total_votes = float(payload.get("votes_total") or 0)
            nominal = float(payload.get("lista_nominal") or 0)
            payload["participacion_pct"] = (total_votes / nominal * 100) if nominal else None
            municipal_records.append({
                "Municipio": bucket["Municipio"],
                "Clave municipio": bucket["Clave municipio"],
                "Secciones con resultado": bucket["Secciones con resultado"],
                "Lista nominal": nominal,
                "Votos totales": total_votes,
                "Participación electoral (%)": payload["participacion_pct"],
                "payload": payload,
            })
        district_municipal_frame = pd.DataFrame(municipal_records).sort_values("Municipio")
        st.markdown("### 2. Municipios que integran el distrito")
        metric_name = st.radio(
            "Indicador municipal del distrito",
            ["Participación electoral (%)", "Lista nominal", "Votos totales"], horizontal=True,
            key="district_municipality_route_metric",
        )
        total_nominal = district_municipal_frame["Lista nominal"].sum()
        total_votes = district_municipal_frame["Votos totales"].sum()
        top_a, top_b, top_c, top_d = st.columns(4)
        top_a.metric("Municipios con secciones", len(district_municipal_frame))
        top_b.metric("Secciones integradas", int(district_municipal_frame["Secciones con resultado"].sum()))
        top_c.metric("Lista nominal", f"{total_nominal:,.0f}")
        top_d.metric("Participación agregada", f"{(total_votes / total_nominal * 100) if total_nominal else 0:.1f}%")

        municipal_options = district_municipal_frame["Municipio"].tolist()
        pending_municipality = st.session_state.pop("pending_district_municipality", None)
        if pending_municipality in municipal_options:
            st.session_state["district_municipality_route_selected"] = pending_municipality
        chosen_municipality = st.selectbox(
            "Municipio dentro del distrito", municipal_options,
            key="district_municipality_route_selected",
            help="El municipio elegido se resalta en el mapa y muestra su desglose de votación.",
        )
        chosen_record = district_municipal_frame[
            district_municipal_frame["Municipio"] == chosen_municipality
        ].iloc[0]
        chosen_payload = chosen_record["payload"]
        with st.container(border=True):
            st.markdown(f"#### Ficha electoral · {chosen_municipality} · Distrito {chosen_district}")
            ficha_a, ficha_b, ficha_c, ficha_d = st.columns(4)
            ficha_a.metric("Secciones integradas", int(chosen_record["Secciones con resultado"]))
            ficha_b.metric("Lista nominal", f"{chosen_record['Lista nominal']:,.0f}")
            ficha_c.metric("Votos totales", f"{chosen_record['Votos totales']:,.0f}")
            ficha_d.metric("Participación", f"{float(chosen_record['Participación electoral (%)'] or 0):.1f}%")
            render_electoral_breakdown(chosen_payload)

        st.markdown("### 3. Mapa municipal del distrito")
        map_property = {
            "Participación electoral (%)": "participacion_pct",
            "Lista nominal": "lista_nominal",
            "Votos totales": "votes_total",
        }[metric_name]
        route_rows = [
            {"municipality_code": row["Clave municipio"], "municipality": row["Municipio"], "payload": row["payload"]}
            for _, row in district_municipal_frame.iterrows()
        ]
        route_geojson = colorize_geojson(
            attach_election_results(geojson, route_rows), map_property,
            low_color=(219, 234, 254), high_color=(30, 64, 175),
        )
        # El mapa se limita a los municipios que efectivamente tienen
        # secciones dentro del distrito. Así un clic siempre puede actualizar
        # el selector municipal, sin ofrecer polígonos ajenos a la ruta.
        route_codes = {
            str(row["Clave municipio"]).zfill(3)
            for _, row in district_municipal_frame.iterrows()
            if str(row["Clave municipio"]).strip("0")
        }
        route_names = {
            municipality_match_key(row["Municipio"])
            for _, row in district_municipal_frame.iterrows()
        }
        route_geojson["features"] = [
            feature for feature in route_geojson.get("features", [])
            if (
                str(feature.get("properties", {}).get("cve_agem", feature.get("properties", {}).get("cve_mun", ""))).zfill(3)
                in route_codes
                or municipality_match_key(feature.get("properties", {}).get("municipio", "")) in route_names
            )
        ]
        selected_features = [
            feature for feature in route_geojson.get("features", [])
            if municipality_match_key(feature.get("properties", {}).get("municipio", ""))
            == municipality_match_key(chosen_municipality)
        ]
        municipal_map_event = st.pydeck_chart(
            pdk.Deck(
                map_style="light",
                initial_view_state=pdk.ViewState(**contextual_view(
                    {"type": "FeatureCollection", "features": selected_features}
                    if selected_features else route_geojson
                )),
                layers=[
                    pdk.Layer("GeoJsonLayer", id="municipios-por-distrito", data=route_geojson,
                              opacity=0.78, stroked=True, filled=True,
                              get_fill_color="properties.pulso_color", get_line_color=[32, 73, 104, 150],
                              line_width_min_pixels=1, pickable=True),
                    *([pdk.Layer("GeoJsonLayer", data={"type": "FeatureCollection", "features": selected_features},
                                 opacity=1, stroked=True, filled=False, get_line_color=[15, 23, 42, 255],
                                 line_width_min_pixels=4, pickable=False)] if selected_features else []),
                ],
                tooltip={"html": f"<b>{{municipio}}</b><br/>{metric_name}: {{{map_property}}}",
                         "style": {"backgroundColor": "#0f172a", "color": "white"}},
            ), use_container_width=True, height=520, on_select="rerun", selection_mode="single-object",
            key=f"municipalities_in_district_map_{chosen_district}_{chosen_municipality}_{metric_name}",
        )
        clicked_objects = municipal_map_event.selection.objects.get("municipios-por-distrito", [])
        if clicked_objects:
            clicked_props = clicked_objects[-1].get("properties", {})
            clicked_name = clicked_props.get("municipio", clicked_props.get("nom_agem", ""))
            clicked_option = next(
                (option for option in municipal_options if municipality_match_key(option) == municipality_match_key(clicked_name)),
                None,
            )
            if clicked_option and clicked_option != chosen_municipality:
                st.session_state["pending_district_municipality"] = clicked_option
                st.rerun()
        st.caption(
            "El color solo representa las secciones con resultado disponibles dentro del distrito seleccionado; "
            "no sustituye el resultado municipal completo."
        )
        st.markdown("### 4. Comparativo municipal del distrito")
        st.bar_chart(district_municipal_frame.set_index("Municipio")[[metric_name]], height=360)
        st.dataframe(
            district_municipal_frame.drop(columns=["payload"]), use_container_width=True, hide_index=True,
            column_config={
                "Lista nominal": st.column_config.NumberColumn(format="%,d"),
                "Votos totales": st.column_config.NumberColumn(format="%,d"),
                "Participación electoral (%)": st.column_config.NumberColumn(format="%.2f%%"),
            },
        )
        st.markdown("### 5. Ficha municipal · electoral e INEGI")
        st.caption(
            "La ficha conserva el contexto del distrito seleccionado: la parte electoral suma solo sus secciones; "
            "la parte INEGI muestra los indicadores oficiales disponibles para el municipio completo."
        )
        ficha_municipality = st.selectbox(
            "Municipio para consultar su ficha", municipal_options,
            index=municipal_options.index(chosen_municipality),
            key="district_municipality_ficha_selected",
            help="Selecciona cualquier municipio que forme parte del distrito para ver su ficha electoral e INEGI.",
        )
        ficha_record = district_municipal_frame[
            district_municipal_frame["Municipio"] == ficha_municipality
        ].iloc[0]
        ficha_payload = ficha_record["payload"]
        route_electoral_tab, route_inegi_tab = st.tabs([
            "Ficha electoral del distrito", "Ficha INEGI del municipio",
        ])
        with route_electoral_tab:
            st.markdown(f"#### {ficha_municipality} · Distrito {chosen_district}")
            electoral_a, electoral_b, electoral_c, electoral_d = st.columns(4)
            electoral_a.metric("Secciones consideradas", int(ficha_record["Secciones con resultado"]))
            electoral_b.metric("Lista nominal", f"{ficha_record['Lista nominal']:,.0f}")
            electoral_c.metric("Votos totales", f"{ficha_record['Votos totales']:,.0f}")
            electoral_d.metric("Participación", f"{float(ficha_record['Participación electoral (%)'] or 0):.1f}%")
            render_electoral_breakdown(ficha_payload)
            st.caption("No es el resultado municipal completo: corresponde a las secciones disponibles de este distrito.")
        with route_inegi_tab:
            municipal_feature = next(
                (feature for feature in geojson.get("features", [])
                 if municipality_match_key(feature.get("properties", {}).get("municipio", feature.get("properties", {}).get("nom_agem", "")))
                 == municipality_match_key(ficha_municipality)),
                None,
            )
            municipal_properties = (municipal_feature or {}).get("properties", {})
            inegi_base = [
                ("Población total", municipal_properties.get("poblacion"), "habitantes"),
                ("Viviendas", municipal_properties.get("viviendas"), "viviendas"),
                ("Acceso a internet", municipal_properties.get("internet_pct"), "%"),
                ("Agua entubada", municipal_properties.get("agua_pct"), "%"),
                ("Drenaje", municipal_properties.get("drenaje_pct"), "%"),
                ("Afiliación a salud", municipal_properties.get("salud_pct"), "%"),
            ]
            inegi_cards = [(name, value, unit) for name, value, unit in inegi_base if pd.notna(value)]
            if inegi_cards:
                inegi_columns = st.columns(min(3, len(inegi_cards)))
                for index, (name, value, unit) in enumerate(inegi_cards):
                    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
                    display = f"{number:.1f}%" if unit == "%" else f"{number:,.0f}"
                    inegi_columns[index % len(inegi_columns)].metric(name, display)
            municipality_code = str(ficha_record["Clave municipio"] or "").zfill(3)
            stored_inegi = query(
                """
                SELECT indicator_name AS Indicador, value AS Valor, unit AS Unidad, period AS Periodo
                FROM territorial_indicators
                WHERE state = ? AND municipality_code = ?
                ORDER BY indicator_name, period DESC
                """,
                (context_state, municipality_code),
            )
            if stored_inegi:
                st.markdown("##### Indicadores oficiales cargados")
                st.dataframe(pd.DataFrame(stored_inegi), use_container_width=True, hide_index=True)
            elif not inegi_cards:
                st.info("Aún no hay indicadores INEGI cargados para este municipio.")
            else:
                st.caption("No hay indicadores INEGI adicionales descargados para este municipio.")
        st.stop()
    if selected_level in {section_level_label, district_section_level_label}:
        section_records = []
        join_rows = []
        for section_row in section_result_rows:
            try:
                payload = json.loads(section_row["payload"])
            except (TypeError, json.JSONDecodeError):
                continue
            join_rows.append({
                "district_code": section_row["district_code"],
                "section_code": section_row["section_code"],
                "municipality": section_row["municipality"],
                "payload": payload,
            })
            section_records.append({
                "Distrito": section_row["district_code"],
                "Sección": section_row["section_code"],
                "Municipio": section_row["municipality"],
                "Lista nominal": payload.get("lista_nominal"),
                "Votos totales": payload.get("votes_total"),
                "Participación electoral (%)": payload.get("participacion_pct"),
                "Opción con más votos": payload.get("opcion_mayor_votacion"),
                "Votos opción más votada": payload.get("votos_opcion_mayor"),
            })
        section_frame = pd.DataFrame(section_records)
        st.markdown("### 2. Tema de análisis")
        section_metric = st.radio(
            "Tema seccional",
            ["Participación electoral (%)", "Lista nominal", "Votos totales", "Votos opción más votada"],
            horizontal=True, key="section_result_metric", label_visibility="collapsed",
        )
        district_route = selected_level == district_section_level_label
        districts_for_sections = sorted(section_frame["Distrito"].dropna().unique().tolist())
        if not district_route:
            districts_for_sections = ["Todos los distritos"] + districts_for_sections
        selected_section_district = st.selectbox(
            "Distrito consultado", districts_for_sections,
            key="section_district_filter_by_route" if district_route else "section_district_filter",
            help=("Esta ruta muestra exclusivamente las secciones del distrito elegido."
                  if district_route else "Filtra las secciones dibujadas en el mapa para facilitar la lectura."),
        )
        if selected_section_district == "Todos los distritos":
            visible_sections = section_frame
            visible_geojson_rows = join_rows
        else:
            visible_sections = section_frame[section_frame["Distrito"] == selected_section_district]
            visible_geojson_rows = [
                row for row in join_rows if row["district_code"] == selected_section_district
            ]
        metric_values = pd.to_numeric(visible_sections[section_metric], errors="coerce")
        # The traffic light is descriptive: it only compares participation with
        # the other sections currently being viewed; it does not infer voter intent.
        participation_values = pd.to_numeric(
            visible_sections["Participación electoral (%)"], errors="coerce"
        )
        low_participation = participation_values.quantile(0.25)
        medium_participation = participation_values.median()
        visible_sections = visible_sections.copy()
        visible_sections["Semáforo territorial"] = pd.Series(
            pd.NA, index=visible_sections.index, dtype="object"
        )
        visible_sections.loc[
            participation_values.notna() & (participation_values <= low_participation),
            "Semáforo territorial",
        ] = "Atención alta · participación baja"
        visible_sections.loc[
            participation_values.notna()
            & (participation_values > low_participation)
            & (participation_values <= medium_participation),
            "Semáforo territorial",
        ] = "Atención media · participación bajo promedio"
        visible_sections.loc[
            participation_values.notna() & (participation_values > medium_participation),
            "Semáforo territorial",
        ] = "Referencia · participación sobre promedio"
        left_metric, middle_metric, right_metric = st.columns(3)
        left_metric.metric("Secciones con resultado", int(metric_values.notna().sum()))
        if section_metric == "Participación electoral (%)":
            middle_metric.metric("Promedio", f"{metric_values.mean():.1f}%")
            right_metric.metric("Rango", f"{metric_values.min():.1f}% — {metric_values.max():.1f}%")
        else:
            middle_metric.metric("Total", f"{metric_values.sum():,.0f}")
            right_metric.metric("Promedio por sección", f"{metric_values.mean():,.0f}")

        st.markdown("### 3. Ficha electoral de sección")
        section_options = [
            f"Sección {row['Sección']} · Distrito {row['Distrito']} · {row['Municipio']}"
            for _, row in visible_sections.iterrows()
        ]
        pending_section = st.session_state.pop("pending_electoral_section", None)
        if pending_section in section_options:
            st.session_state["selected_electoral_section_top"] = pending_section
        chosen_section_top = st.selectbox(
            "Sección consultada", section_options, key="selected_electoral_section_top",
            help="Selecciona la sección cuya ficha quieres revisar antes de consultar el mapa.",
        )
        chosen_section_row_top = visible_sections.iloc[section_options.index(chosen_section_top)]
        section_payload = next(
            (row["payload"] for row in visible_geojson_rows
             if row["district_code"] == chosen_section_row_top["Distrito"]
             and row["section_code"] == chosen_section_row_top["Sección"]),
            {},
        )
        with st.container(border=True):
            ficha_a, ficha_b, ficha_c, ficha_d = st.columns(4)
            ficha_a.metric("Lista nominal", f"{float(section_payload.get('lista_nominal') or 0):,.0f}")
            ficha_b.metric("Votos totales", f"{float(section_payload.get('votes_total') or 0):,.0f}")
            ficha_c.metric("Participación", f"{float(section_payload.get('participacion_pct') or 0):.1f}%")
            ficha_d.metric("Semáforo", chosen_section_row_top["Semáforo territorial"])
            render_electoral_breakdown(section_payload)
        st.markdown("### 4. Mapa seccional")
        map_column = st.container()
        ficha_column = st.empty()
        with map_column:
            section_geojson, section_source = load_electoral_sections_context(context_state)
            if section_geojson is None:
                st.warning("No se pudo cargar la capa oficial de secciones para este estado.")
            else:
                section_map_column = {
                    "Participación electoral (%)": "participacion_pct",
                    "Lista nominal": "lista_nominal",
                    "Votos totales": "votes_total",
                    "Votos opción más votada": "votos_opcion_mayor",
                }[section_metric]
                enriched_sections = attach_section_results(section_geojson, visible_geojson_rows)
                if selected_section_district != "Todos los distritos":
                    enriched_sections["features"] = [
                        feature for feature in enriched_sections["features"]
                        if str(feature.get("properties", {}).get("distrito_local", "")).zfill(2)
                        == str(selected_section_district).zfill(2)
                    ]
                colored_sections = colorize_geojson(
                    enriched_sections, section_map_column,
                    low_color=(220, 252, 231), high_color=(21, 128, 61),
                )
                selected_section_features = [
                    feature for feature in colored_sections.get("features", [])
                    if str(feature.get("properties", {}).get("seccion", "")).zfill(4)
                    == str(chosen_section_row_top["Sección"]).zfill(4)
                    and str(feature.get("properties", {}).get("distrito_local", "")).zfill(2)
                    == str(chosen_section_row_top["Distrito"]).zfill(2)
                ]
                section_map_event = st.pydeck_chart(
                    pdk.Deck(
                        map_style="light",
                        initial_view_state=pdk.ViewState(**contextual_view(
                            {"type": "FeatureCollection", "features": selected_section_features}
                            if selected_section_features else colored_sections
                        )),
                        layers=[
                            pdk.Layer(
                                "GeoJsonLayer", id="secciones-contextuales", data=colored_sections,
                                opacity=0.78, stroked=True, filled=True,
                                get_fill_color="properties.pulso_color",
                                get_line_color=[22, 101, 52, 150], line_width_min_pixels=1,
                                pickable=True,
                            ),
                            *([pdk.Layer(
                                "GeoJsonLayer", data={"type": "FeatureCollection", "features": selected_section_features},
                                opacity=1, stroked=True, filled=False, get_line_color=[15, 23, 42, 255],
                                line_width_min_pixels=3, pickable=False,
                            )] if selected_section_features else []),
                        ],
                        tooltip={
                            "html": f"<b>{{seccion_etiqueta}}</b><br/>{section_metric}: {{{section_map_column}}}",
                            "style": {"backgroundColor": "#0f172a", "color": "white"},
                        },
                    ), use_container_width=True, height=600, on_select="rerun", selection_mode="single-object",
                    key=f"section_context_map_{chosen_section_row_top['Distrito']}_{chosen_section_row_top['Sección']}_{section_metric}",
                )
                selected_section_objects = section_map_event.selection.objects.get("secciones-contextuales", [])
                if selected_section_objects:
                    section_properties = selected_section_objects[-1].get("properties", {})
                    clicked_section = str(
                        selected_section_objects[-1].get("seccion") or section_properties.get("seccion", "")
                    ).zfill(4)
                    clicked_district = str(
                        selected_section_objects[-1].get("distrito_local") or section_properties.get("distrito_local", "")
                    ).zfill(2)
                    clicked_option = next(
                        (option for option, (_, row) in zip(section_options, visible_sections.iterrows())
                         if str(row["Sección"]).zfill(4) == clicked_section
                         and str(row["Distrito"]).zfill(2) == clicked_district),
                        None,
                    )
                    if clicked_option and clicked_option != chosen_section_top:
                        st.session_state["pending_electoral_section"] = clicked_option
                        st.rerun()
                st.caption(
                    f"Capa seccional oficial: {section_source}. Se muestran {len(colored_sections['features'])} polígonos."
                )
        with ficha_column:
            st.markdown("#### Ficha de sección")
            chosen_section = chosen_section_top
            chosen_index = section_options.index(chosen_section)
            chosen_section_row = visible_sections.iloc[chosen_index]
            section_participation = pd.to_numeric(
                pd.Series([chosen_section_row["Participación electoral (%)"]]), errors="coerce"
            ).iloc[0]
            section_average = participation_values.mean()
            st.caption(f"{chosen_section_row['Municipio']} · Distrito {chosen_section_row['Distrito']}")
            st.metric("Lista nominal", f"{int(chosen_section_row['Lista nominal']):,}")
            st.metric("Votos totales", f"{int(chosen_section_row['Votos totales']):,}")
            st.metric(
                "Participación", f"{section_participation:.1f}%",
                f"{section_participation - section_average:+.1f} pp vs. promedio",
            )
            st.markdown("**Semáforo territorial**")
            st.info(chosen_section_row["Semáforo territorial"])
            st.caption(
                "Comparación con las secciones actualmente visualizadas; no representa intención de voto."
            )
        ficha_column.empty()
        st.markdown("### 5. Detalle por sección")
        st.dataframe(
            visible_sections,
            use_container_width=True, hide_index=True,
            column_config={
                "Lista nominal": st.column_config.NumberColumn(format="%,d"),
                "Votos totales": st.column_config.NumberColumn(format="%,d"),
                "Participación electoral (%)": st.column_config.NumberColumn(format="%.2f%%"),
                "Votos opción más votada": st.column_config.NumberColumn(format="%,d"),
            },
        )
        st.caption("Las secciones sin resultado publicado permanecen en la cartografía, pero no reciben valor de color.")
        st.stop()
    if selected_level == district_level_label:
        district_records = []
        for district_row in district_result_rows:
            try:
                payload = json.loads(district_row["payload"])
            except (TypeError, json.JSONDecodeError):
                continue
            district_records.append({
                "Distrito": f"{district_row['district_code']} · {district_row['district_name']}",
                "Clave distrito": district_row["district_code"],
                "Cabecera distrital": district_row["district_name"],
                "Lista nominal": payload.get("lista_nominal"),
                "Votos totales": payload.get("votes_total"),
                "Participación electoral (%)": payload.get("participacion_pct"),
                "Opción con más votos": payload.get("opcion_mayor_votacion"),
                "Votos opción más votada": payload.get("votos_opcion_mayor"),
            })
        district_frame = pd.DataFrame(district_records)
        st.markdown("### 2. Tema de análisis")
        district_metric = st.radio(
            "Tema distrital",
            ["Participación electoral (%)", "Lista nominal", "Votos totales", "Votos opción más votada"],
            horizontal=True,
            key="district_result_metric",
            label_visibility="collapsed",
        )
        st.caption(
            f"Resultados oficiales de diputaciones locales {selected_election_year}, agrupados por distrito. "
            "La opción con más votos corresponde a la columna partidista, coalición o candidatura común publicada por la autoridad electoral correspondiente."
        )
        metric_values = pd.to_numeric(district_frame[district_metric], errors="coerce")
        metric_left, metric_middle, metric_right = st.columns(3)
        metric_left.metric("Distritos con dato", int(metric_values.notna().sum()))
        if district_metric == "Participación electoral (%)":
            metric_middle.metric("Promedio estatal", f"{metric_values.mean():.1f}%")
            metric_right.metric("Rango", f"{metric_values.min():.1f}% — {metric_values.max():.1f}%")
        else:
            metric_middle.metric("Total", f"{metric_values.sum():,.0f}")
            metric_right.metric("Promedio distrital", f"{metric_values.mean():,.0f}")

        district_geojson = None
        if st.session_state.get("territorial_district_geojson_state") == context_state:
            try:
                district_geojson = json.loads(
                    st.session_state["territorial_district_geojson_data"].decode("utf-8")
                )
            except (KeyError, UnicodeDecodeError, json.JSONDecodeError):
                district_geojson = None
        district_geojson_source = st.session_state.get("territorial_district_geojson_name")
        if district_geojson is None:
            district_geojson, district_geojson_source = load_local_district_context(context_state)
        if district_geojson is not None:
            join_rows = []
            for district_row in district_result_rows:
                try:
                    join_rows.append({
                        "district_code": district_row["district_code"],
                        "district_name": district_row["district_name"],
                        "payload": json.loads(district_row["payload"]),
                    })
                except (TypeError, json.JSONDecodeError):
                    continue
            district_map_column = {
                "Participación electoral (%)": "participacion_pct",
                "Lista nominal": "lista_nominal",
                "Votos totales": "votes_total",
                "Votos opción más votada": "votos_opcion_mayor",
            }[district_metric]
            enriched_district_geojson = attach_district_results(district_geojson, join_rows)
            district_map_values = pd.to_numeric(
                pd.Series([
                    feature.get("properties", {}).get(district_map_column)
                    for feature in enriched_district_geojson.get("features", [])
                ]),
                errors="coerce",
            )
            matched_districts = int(district_map_values.notna().sum())
            st.markdown("### 3. Ficha electoral de distrito")
            district_options = district_frame["Distrito"].tolist()
            pending_district = st.session_state.pop("pending_electoral_district", None)
            if pending_district in district_options:
                st.session_state["selected_electoral_district_top"] = pending_district
            chosen_district_top = st.selectbox(
                "Distrito consultado", district_options, key="selected_electoral_district_top",
                help="Selecciona el distrito cuya ficha quieres revisar antes de consultar el mapa.",
            )
            chosen_district_row_top = district_frame[
                district_frame["Distrito"] == chosen_district_top
            ].iloc[0]
            district_payload = next(
                (json.loads(row["payload"]) for row in district_result_rows
                 if row["district_code"] == chosen_district_row_top["Clave distrito"]),
                {},
            )
            district_participation_top = float(district_payload.get("participacion_pct") or 0)
            district_average_top = pd.to_numeric(
                district_frame["Participación electoral (%)"], errors="coerce"
            ).mean()
            with st.container(border=True):
                ficha_a, ficha_b, ficha_c, ficha_d = st.columns(4)
                ficha_a.metric("Lista nominal", f"{float(district_payload.get('lista_nominal') or 0):,.0f}")
                ficha_b.metric("Votos totales", f"{float(district_payload.get('votes_total') or 0):,.0f}")
                ficha_c.metric("Participación", f"{district_participation_top:.1f}%", f"{district_participation_top - district_average_top:+.1f} pp vs. promedio estatal")
                ficha_d.metric("Cabecera", chosen_district_row_top["Cabecera distrital"])
                render_electoral_breakdown(district_payload)
            st.markdown("### 4. Mapa distrital")
            map_column = st.container()
            ficha_column = st.empty()
            with map_column:
                if matched_districts:
                    mapped_districts = colorize_geojson(
                        enriched_district_geojson, district_map_column,
                        low_color=(219, 234, 254), high_color=(30, 64, 175),
                    )
                    selected_district_features = [
                        feature for feature in mapped_districts.get("features", [])
                        if str(feature.get("properties", {}).get("distrito_local", "")).zfill(2)
                        == str(chosen_district_row_top["Clave distrito"]).zfill(2)
                    ]
                    district_map_event = st.pydeck_chart(
                        pdk.Deck(
                            map_style="light",
                            initial_view_state=pdk.ViewState(**contextual_view(
                                {"type": "FeatureCollection", "features": selected_district_features}
                                if selected_district_features else mapped_districts
                            )),
                            layers=[
                                pdk.Layer(
                                    "GeoJsonLayer", id="distritos-contextuales", data=mapped_districts,
                                    opacity=0.8, stroked=True, filled=True,
                                    get_fill_color="properties.pulso_color",
                                    get_line_color=[32, 73, 104, 180], line_width_min_pixels=1,
                                    pickable=True,
                                ),
                                *([pdk.Layer(
                                    "GeoJsonLayer", data={"type": "FeatureCollection", "features": selected_district_features},
                                    opacity=1, stroked=True, filled=False, get_line_color=[15, 23, 42, 255],
                                    line_width_min_pixels=4, pickable=False,
                                )] if selected_district_features else []),
                            ],
                            tooltip={
                                "html": f"<b>{{distrito}}</b><br/>{district_metric}: {{{district_map_column}}}",
                                "style": {"backgroundColor": "#0f172a", "color": "white"},
                            },
                        ),
                        use_container_width=True, height=560, on_select="rerun", selection_mode="single-object",
                        key=f"district_context_map_{chosen_district_row_top['Clave distrito']}_{district_metric}",
                    )
                    selected_district_objects = district_map_event.selection.objects.get("distritos-contextuales", [])
                    if selected_district_objects:
                        clicked_district_code = str(
                            selected_district_objects[-1].get("distrito_local")
                            or selected_district_objects[-1].get("properties", {}).get("distrito_local", "")
                        ).zfill(2)
                        clicked_district = next(
                            (option for option, code in zip(district_options, district_frame["Clave distrito"])
                             if str(code).zfill(2) == clicked_district_code),
                            None,
                        )
                        if clicked_district and clicked_district != chosen_district_top:
                            st.session_state["pending_electoral_district"] = clicked_district
                            st.rerun()
                    st.caption(
                        f"Capa distrital: {district_geojson_source or 'GeoJSON'}. "
                        f"{matched_districts} polígonos vinculados con resultados oficiales."
                    )
                else:
                    st.warning(
                        "La capa se cargó, pero no se reconocieron claves de distrito compatibles. "
                        "Verifica que incluya un campo como distrito, distrito_local, cve_distrito o dist_loc."
                    )
            with ficha_column:
                st.markdown("#### Ficha de distrito")
                chosen_district = chosen_district_top
                chosen_district_row = district_frame[
                    district_frame["Distrito"] == chosen_district
                ].iloc[0]
                participation_values = pd.to_numeric(
                    district_frame["Participación electoral (%)"], errors="coerce"
                )
                district_participation = float(chosen_district_row["Participación electoral (%)"])
                district_average = participation_values.mean()
                st.caption(f"Cabecera distrital: {chosen_district_row['Cabecera distrital']}")
                st.metric("Lista nominal", f"{int(chosen_district_row['Lista nominal']):,}")
                st.metric("Votos totales", f"{int(chosen_district_row['Votos totales']):,}")
                st.metric(
                    "Participación", f"{district_participation:.1f}%",
                    f"{district_participation - district_average:+.1f} pp vs. promedio estatal",
                )
                st.metric("Opción con más votos", chosen_district_row["Opción con más votos"])

            ficha_column.empty()

        st.markdown("### 5. Comparativo distrital")
        chart_data = district_frame[["Distrito", district_metric]].dropna().set_index("Distrito")
        st.bar_chart(chart_data, horizontal=True, height=520)
        st.markdown("### 6. Detalle por distrito")
        display_columns = [
            "Clave distrito", "Cabecera distrital", "Lista nominal", "Votos totales",
            "Participación electoral (%)", "Opción con más votos", "Votos opción más votada",
        ]
        st.dataframe(
            district_frame[display_columns], use_container_width=True, hide_index=True,
            column_config={
                "Lista nominal": st.column_config.NumberColumn(format="%,d"),
                "Votos totales": st.column_config.NumberColumn(format="%,d"),
                "Participación electoral (%)": st.column_config.NumberColumn(format="%.2f%%"),
                "Votos opción más votada": st.column_config.NumberColumn(format="%,d"),
            },
        )
        if district_geojson is None:
            st.info(
                "Los resultados distritales ya están listos. Cuando cargues la capa oficial del INE desde "
                "Perfil territorial, este mismo indicador se dibujará en el mapa sin aproximar límites territoriales."
            )
        if district_result_rows[0]["source"]:
            st.caption(f"Fuente de resultados: {district_result_rows[0]['source']}")
        st.stop()

    # El diagnóstico regional se presenta en su página propia del menú. Esta
    # ruta anterior queda desactivada para que Dominio territorial muestre
    # exclusivamente indicadores y pulso municipal.
    if False:
        territorial_view = st.radio(
            "Vista territorial",
            ["Indicadores y pulso", "Regiones del PED 2021–2027"],
            horizontal=True,
            key="sonora_territorial_view",
        )
        if territorial_view == "Regiones del PED 2021–2027":
            regional_geojson = attach_ped_sonora_regions(geojson)
            regional_rows = [
                {
                    "Región PED": feature.get("properties", {}).get("region_ped", "Sin asignación"),
                    "Municipio": feature.get("properties", {}).get("municipio", "Sin nombre"),
                }
                for feature in regional_geojson.get("features", [])
            ]
            regional_frame = pd.DataFrame(regional_rows)
            region_options = ["Todas las regiones"] + sorted(
                region for region in regional_frame["Región PED"].dropna().unique()
                if region != "Sin asignación"
            )
            selected_ped_region = st.selectbox(
                "Región PED consultada", region_options, key="ped_region_context_combo",
                help="Elige una región para resaltarla y revisar los municipios que la integran.",
            )
            mapped_regions = len(regional_frame[regional_frame["Región PED"] != "Sin asignación"])
            metric_a, metric_b, metric_c = st.columns(3)
            metric_a.metric("Regiones del PED", len(PED_SONORA_REGIONS))
            metric_b.metric("Municipios asignados", mapped_regions)
            metric_c.metric(
                "Municipios de la región",
                mapped_regions if selected_ped_region == "Todas las regiones" else int(
                    (regional_frame["Región PED"] == selected_ped_region).sum()
                ),
            )
            if selected_ped_region == "Todas las regiones":
                st.info("Selecciona una región para consultar su ficha de diagnóstico del PED.")
            else:
                region_profile = PED_SONORA_REGION_PROFILES.get(selected_ped_region, {})
                region_municipalities = sorted(
                    regional_frame.loc[
                        regional_frame["Región PED"] == selected_ped_region, "Municipio"
                    ].tolist()
                )
                with st.container(border=True):
                    st.markdown(f"#### Ficha regional · {selected_ped_region}")
                    ficha_a, ficha_b = st.columns([1, 2])
                    with ficha_a:
                        st.caption("MUNICIPIOS")
                        st.write(", ".join(region_municipalities))
                    with ficha_b:
                        st.caption("VOCACIÓN TERRITORIAL")
                        st.write(region_profile.get("vocacion", "Información no disponible."))
                    st.caption("DIAGNÓSTICO DEL PED 2021–2027")
                    st.write(region_profile.get("diagnostico", "Información no disponible."))
                    st.caption(
                        "Fuente: Diagnóstico por Regiones del Plan Estatal de Desarrollo Sonora 2021–2027. "
                        "Esta ficha es contexto de planeación; no equivale a una medición actual."
                    )
            st.markdown("### Capa regional del PED")
            st.caption(
                "Regionalización del Diagnóstico por Regiones del Plan Estatal de Desarrollo Sonora 2021–2027. "
                "El color identifica la región, no un nivel de desempeño."
            )
            outline_features = (
                [] if selected_ped_region == "Todas las regiones" else [
                    feature for feature in regional_geojson.get("features", [])
                    if feature.get("properties", {}).get("region_ped") == selected_ped_region
                ]
            )
            st.pydeck_chart(
                pdk.Deck(
                    map_style="light",
                    initial_view_state=pdk.ViewState(**contextual_view(regional_geojson)),
                    layers=[
                        pdk.Layer(
                            "GeoJsonLayer", id="regiones-ped-sonora", data=regional_geojson,
                            opacity=0.78, stroked=True, filled=True,
                            get_fill_color="properties.region_ped_color",
                            get_line_color=[51, 65, 85, 150], line_width_min_pixels=1,
                            pickable=True,
                        ),
                        *(
                            [pdk.Layer(
                                "GeoJsonLayer",
                                data={"type": "FeatureCollection", "features": outline_features},
                                opacity=1, stroked=True, filled=False,
                                get_line_color=[15, 23, 42, 255], line_width_min_pixels=4,
                                pickable=False,
                            )] if outline_features else []
                        ),
                    ],
                    tooltip={
                        "html": "<b>{municipio}</b><br/>Región PED: {region_ped}",
                        "style": {"backgroundColor": "#0f172a", "color": "white"},
                    },
                ),
                use_container_width=True,
                height=560,
            )
            summary = (
                regional_frame[regional_frame["Región PED"] != "Sin asignación"]
                .groupby("Región PED", as_index=False)
                .agg(Municipios=("Municipio", "count"), Integrantes=("Municipio", lambda values: ", ".join(sorted(values))))
                .sort_values("Región PED")
            )
            if selected_ped_region != "Todas las regiones":
                summary = summary[summary["Región PED"] == selected_ped_region]
            st.markdown("#### Municipios que integran la región")
            st.dataframe(summary, use_container_width=True, hide_index=True)
            st.stop()

    # La capa territorial puede contener indicadores de resultados, contexto
    # social y gestión. Solo se muestran si pertenecen al estado activo.
    layer_indicators = available_indicators(geojson)
    indicators = dict(layer_indicators)
    stored_indicator_groups = query(
        """
        SELECT indicator_id, indicator_name, COALESCE(NULLIF(unit, ''), '') AS unit, period,
               COUNT(*) AS municipios
        FROM territorial_indicators
        WHERE state = ?
        GROUP BY indicator_id, indicator_name, unit, period
        ORDER BY indicator_name, period DESC
        """,
        (context_state,),
    )
    stored_property_by_label = {}
    for group in stored_indicator_groups:
        label = f"INEGI: {group['indicator_name']} ({group['period']})"
        property_name = f"inegi_{group['indicator_id']}_{group['period']}"
        # El catálogo de INEGI expresa este indicador como porcentaje. Algunas
        # respuestas históricas no incluyen la unidad, por lo que la fijamos
        # aquí para conservar una lectura correcta en mapa y métricas.
        unit = group["unit"] or ("%" if group["indicator_id"] == "6207019042" else "dato oficial")
        indicators[label] = (property_name, unit)
        stored_property_by_label[label] = (property_name, group["indicator_id"], group["period"])
    if not indicators:
        st.warning("La capa no contiene indicadores que puedan representarse en el mapa.")
        st.stop()
    thematic_groups = {
        group: [label for label in labels if label in layer_indicators]
        for group, labels in LAYER_INDICATOR_GROUPS.items()
    }
    thematic_groups = {group: labels for group, labels in thematic_groups.items() if labels}
    inegi_labels = [label for label in stored_property_by_label if label in indicators]
    if inegi_labels:
        thematic_groups["Indicadores oficiales INEGI"] = inegi_labels
    if municipal_election_only:
        thematic_groups = {
            name: labels for name, labels in thematic_groups.items()
            if name in {"Participación electoral", "Resultados electorales"}
        }
    elif consultation_area == "INEGI":
        thematic_groups = {
            name: labels for name, labels in thematic_groups.items()
            if name not in {"Participación electoral", "Resultados electorales", "Pulso ciudadano", "Gestión municipal"}
        }
    elif consultation_area == "Territorio":
        thematic_groups = {
            name: labels for name, labels in thematic_groups.items()
            if name not in {"Participación electoral", "Resultados electorales"}
        }
    if not thematic_groups:
        st.warning("No hay temas territoriales disponibles para el estado activo.")
        st.stop()

    st.markdown("### 2. Tema de análisis")
    if st.session_state.get("territorial_theme") not in thematic_groups:
        st.session_state["territorial_theme"] = next(iter(thematic_groups))
    selected_theme = st.radio(
        "Tema", list(thematic_groups), horizontal=True, key="territorial_theme",
        label_visibility="collapsed",
    )
    theme_indicators = thematic_groups[selected_theme]
    st.markdown("### 3. Filtro específico")
    if len(theme_indicators) == 1:
        selected_indicator = theme_indicators[0]
        st.caption(f"Consulta activa: Municipios · {selected_theme} · {selected_indicator}.")
    else:
        selected_indicator = st.selectbox(
            "Indicador", theme_indicators, key=f"territorial_indicator_{selected_theme}",
        )
        st.caption(f"Consulta activa: Municipios · {selected_theme} · {selected_indicator}.")
    indicator_column, indicator_unit = indicators[selected_indicator]
    map_geojson = geojson
    if selected_indicator in stored_property_by_label:
        property_name, stored_indicator_id, stored_period = stored_property_by_label[selected_indicator]
        stored_rows = query(
            """
            SELECT municipality_code, value FROM territorial_indicators
            WHERE state = ? AND indicator_id = ? AND period = ?
            """,
            (context_state, stored_indicator_id, stored_period),
        )
        map_geojson = attach_indicator_values(geojson, stored_rows, property_name)
    values = pd.to_numeric(
        pd.Series([feature.get("properties", {}).get(indicator_column) for feature in map_geojson.get("features", [])]),
        errors="coerce",
    )

    metric_left, metric_middle, metric_right = st.columns(3)
    metric_left.metric("Municipios con dato", int(values.notna().sum()))
    if indicator_unit == "MXN":
        metric_middle.metric("Total de la capa", f"${values.sum():,.0f}")
        metric_right.metric("Promedio municipal", f"${values.mean():,.0f}")
    elif indicator_unit == "%":
        metric_middle.metric("Promedio municipal", f"{values.mean():.1f}%")
        metric_right.metric("Rango", f"{values.min():.1f}% — {values.max():.1f}%")
    else:
        metric_middle.metric("Total", f"{values.sum():,.0f}")
        metric_right.metric("Promedio municipal", f"{values.mean():,.0f}")

    indicator_text = selected_indicator.casefold()
    if "seguridad" in indicator_text:
        context_title = "Capacidad institucional de seguridad"
        context_description = "Permite ubicar la disponibilidad relativa de personal municipal de seguridad."
        palette = ((255, 237, 213), (194, 65, 12))
    elif "internet" in indicator_text or "computadora" in indicator_text:
        context_title = "Conectividad y brecha digital"
        context_description = "Identifica municipios con menor y mayor acceso a herramientas de conectividad."
        palette = ((207, 250, 254), (14, 116, 144))
    elif "vivienda" in indicator_text or any(
        term in indicator_text for term in ("energía", "agua", "drenaje", "sanitario", "lavadora")
    ):
        context_title = "Condiciones de vivienda y servicios"
        context_description = "Muestra la distribución territorial de servicios y equipamiento en las viviendas."
        palette = ((220, 252, 231), (21, 128, 61))
    elif "población" in indicator_text:
        context_title = "Distribución de población"
        context_description = "Ayuda a dimensionar dónde se concentra la población del territorio seleccionado."
        palette = ((219, 234, 254), (29, 78, 216))
    else:
        context_title = "Indicador territorial oficial"
        context_description = "Visualización municipal del indicador seleccionado en el Banco de Indicadores INEGI."
        palette = ((237, 233, 254), (109, 40, 217))

    map_values = pd.DataFrame(
        {
            "municipio": [
                feature.get("properties", {}).get("municipio", feature.get("properties", {}).get("nom_agem", "Sin nombre"))
                for feature in map_geojson.get("features", [])
            ],
            "valor": values,
        }
    ).dropna(subset=["valor"])
    municipality_options = ["Todos los municipios"] + sorted(map_values["municipio"].dropna().unique().tolist())

    # El combo es el control principal; el clic en el mapa queda como atajo.
    clicked_municipality = st.session_state.pop("map_clicked_municipality", None)
    if clicked_municipality in municipality_options:
        st.session_state["map_context_municipality"] = clicked_municipality
        st.session_state["municipality_context_combo"] = clicked_municipality
    elif st.session_state.get("map_context_municipality") not in municipality_options:
        st.session_state["map_context_municipality"] = "Todos los municipios"
    active_municipality = st.session_state["map_context_municipality"]
    selected_municipality_combo = st.selectbox(
        "Municipio consultado",
        municipality_options,
        index=municipality_options.index(active_municipality),
        key="municipality_context_combo",
        help="Elige directamente el municipio; el mapa se actualiza como apoyo visual.",
    )
    if selected_municipality_combo != active_municipality:
        st.session_state["map_context_municipality"] = selected_municipality_combo
        active_municipality = selected_municipality_combo

    def format_context_value(value: float) -> str:
        if indicator_unit == "%":
            return f"{value:.1f}%"
        if indicator_unit == "MXN":
            return f"${value:,.0f}"
        return f"{value:,.0f}"

    colored_geojson = colorize_geojson(
        map_geojson, indicator_column, low_color=palette[0], high_color=palette[1]
    )
    tooltip_value = indicator_unit if indicator_unit != "MXN" else "pesos"
    if municipal_election_only:
        st.markdown("### 4. Ficha municipal electoral")
        if active_municipality == "Todos los municipios":
            st.info("Selecciona un municipio en el mapa para abrir su ficha electoral detallada arriba del mapa.")
        else:
            selected_row = map_values[map_values["municipio"] == active_municipality].iloc[0]
            election_payloads = {
                row["municipality"].casefold(): row["payload"]
                for row in decode_election_rows(existing_election_rows)
            }
            election_payload = election_payloads.get(active_municipality.casefold(), {})
            with st.container(border=True):
                st.markdown(f"#### {active_municipality} · {selected_municipal_election_type} {selected_election_year}")
                ficha_a, ficha_b, ficha_c, ficha_d, ficha_e = st.columns(5)
                ficha_a.metric("Lista nominal", f"{float(election_payload.get('lista_nominal') or 0):,.0f}")
                ficha_b.metric("Votos totales", f"{float(election_payload.get('votes_total') or 0):,.0f}")
                ficha_c.metric("Participación", f"{float(election_payload.get('participacion_pct') or 0):.1f}%")
                ficha_d.metric("Votos válidos", f"{float(election_payload.get('numero_votos_validos') or 0):,.0f}")
                ficha_e.metric("Votos nulos", f"{float(election_payload.get('votes_nulos') or 0):,.0f}")
                party_rows = [
                    {"Partido o candidatura": label, "Votos": float(election_payload.get(key) or 0)}
                    for key, label in ELECTORAL_VOTE_LABELS.items() if float(election_payload.get(key) or 0) > 0
                ]
                if party_rows:
                    party_frame = pd.DataFrame(party_rows).sort_values("Votos", ascending=False)
                    chart_column, table_column = st.columns([1, 1])
                    with chart_column:
                        st.caption("Votación por partido o candidatura publicada")
                        st.bar_chart(party_frame.set_index("Partido o candidatura"), height=250)
                    with table_column:
                        st.dataframe(
                            party_frame, use_container_width=True, hide_index=True,
                            column_config={"Votos": st.column_config.NumberColumn(format="%,d")},
                        )
                else:
                    st.caption("La base oficial no contiene columnas partidistas con voto para este municipio.")
                st.caption("Las coaliciones y candidaturas comunes se muestran tal como fueron publicadas por la autoridad electoral.")
        st.markdown("### 5. Mapa municipal electoral")
        st.caption(f"Indicador activo: {selected_indicator}. Haz clic en un municipio para actualizar la ficha superior.")
        map_column = st.container()
        context_column = st.empty()
    else:
        st.markdown("### 4. Mapa y ficha territorial")
        st.subheader(f"Mapa contextual · {context_title}")
        st.caption(f"Indicador activo: {selected_indicator}. {context_description}")
        map_column, context_column = st.columns([3, 1])
    with map_column:
        selected_municipal_features = [
            feature for feature in colored_geojson.get("features", [])
            if feature.get("properties", {}).get("municipio") == active_municipality
        ]
        view = contextual_view(
            {"type": "FeatureCollection", "features": selected_municipal_features}
            if selected_municipal_features else map_geojson
        )
        map_event = st.pydeck_chart(
            pdk.Deck(
                map_style="light",
                initial_view_state=pdk.ViewState(**view),
                layers=[
                    pdk.Layer(
                        "GeoJsonLayer",
                        id="municipios-contextuales",
                        data=colored_geojson,
                        opacity=0.78,
                        stroked=True,
                        filled=True,
                        get_fill_color="properties.pulso_color",
                        get_line_color=[32, 73, 104, 150],
                        line_width_min_pixels=1,
                        pickable=True,
                    ),
                    *(
                        [
                            pdk.Layer(
                                "GeoJsonLayer",
                                data={
                                    "type": "FeatureCollection",
                                    "features": selected_municipal_features,
                                },
                                opacity=1,
                                stroked=True,
                                filled=False,
                                get_line_color=[15, 23, 42, 255],
                                line_width_min_pixels=4,
                                pickable=False,
                            )
                        ]
                        if active_municipality != "Todos los municipios"
                        else []
                    ),
                ],
                tooltip={
                    "html": f"<b>{{municipio}}</b><br/>{selected_indicator}: {{{indicator_column}}} {tooltip_value}",
                    "style": {"backgroundColor": "#0f172a", "color": "white"},
                },
            ),
            use_container_width=True,
            height=560,
            on_select="rerun",
            selection_mode="single-object",
            key=f"municipal_context_map_{municipality_match_key(active_municipality)}_{indicator_column}",
        )
        selected_objects = map_event.selection.objects.get("municipios-contextuales", [])
        if selected_objects:
            selected_feature = selected_objects[-1]
            map_selected_municipality = (
                selected_feature.get("municipio")
                or selected_feature.get("nom_agem")
                or selected_feature.get("NOMGEO")
                or selected_feature.get("properties", {}).get("municipio")
            )
            if (
                map_selected_municipality in municipality_options
                and map_selected_municipality != active_municipality
            ):
                st.session_state["map_clicked_municipality"] = map_selected_municipality
                st.rerun()
        st.caption(
            "Haz clic en un municipio para actualizar la ficha superior."
            if municipal_election_only else
            "Haz clic en un municipio para actualizar la ficha lateral. Escala: tono claro = menor valor relativo · tono intenso = mayor valor relativo."
        )
    with context_column:
        with st.container(border=True):
            if map_values.empty:
                st.info("El indicador no devolvió valores municipales para esta capa.")
            elif active_municipality == "Todos los municipios":
                lowest = map_values.loc[map_values["valor"].idxmin()]
                highest = map_values.loc[map_values["valor"].idxmax()]
                st.caption("FICHA TERRITORIAL")
                st.markdown("#### Selecciona un municipio")
                st.write("Haz clic sobre un polígono del mapa para abrir su ficha territorial.")
                st.divider()
                st.caption("TEMA SELECCIONADO")
                st.write(selected_indicator)
                st.metric("Menor valor", format_context_value(float(lowest["valor"])), lowest["municipio"])
                st.metric("Mayor valor", format_context_value(float(highest["valor"])), highest["municipio"])
                st.caption(f"Cobertura: {len(map_values)} municipios con dato.")
            else:
                selected_row = map_values[map_values["municipio"] == active_municipality].iloc[0]
                ordered_values = map_values["valor"].rank(method="min", ascending=False)
                selected_rank = int(ordered_values.loc[selected_row.name])
                detail_rows = municipalities[municipalities["municipio"] == active_municipality]
                detail_row = detail_rows.iloc[0] if not detail_rows.empty else pd.Series(dtype=object)
                st.caption("MUNICIPIO SELECCIONADO")
                st.markdown(f"#### {active_municipality}")
                st.caption("TEMA SELECCIONADO")
                st.write(selected_indicator)
                st.metric("Valor", format_context_value(float(selected_row["valor"])))
                st.divider()
                st.caption("LECTURA ESTATAL")
                st.write(f"Posición: **{selected_rank} de {len(map_values)}** municipios.")
                st.caption("CONTEXTO MUNICIPAL")
                context_items = [
                    ("Población", detail_row.get("poblacion"), "habitantes"),
                    ("Lista nominal", detail_row.get("lista nominal"), "personas"),
                    ("Participación electoral", detail_row.get("participación electoral (%)"), "%"),
                ]
                for label, value, unit in context_items:
                    if pd.notna(value):
                        formatted = f"{float(value):,.1f}%" if unit == "%" else f"{float(value):,.0f} {unit}"
                        st.write(f"**{label}:** {formatted}")
                st.caption("El polígono resaltado corresponde al municipio consultado.")

    if municipal_election_only:
        context_column.empty()

    if page == "Electoral":
        st.markdown('<div class="domain-section">Ficha de indicadores electorales</div>', unsafe_allow_html=True)
        if active_municipality == "Todos los municipios":
            st.info("Selecciona un municipio para consultar su ficha electoral completa.")
        else:
            election_payloads = {
                row["municipality"].casefold(): row["payload"]
                for row in decode_election_rows(existing_election_rows)
            }
            election_payload = election_payloads.get(active_municipality.casefold(), {})
            party_rows = [
                {"Partido o candidatura": label, "Votos": float(election_payload.get(key) or 0)}
                for key, label in ELECTORAL_VOTE_LABELS.items()
                if float(election_payload.get(key) or 0) > 0
            ]
            party_frame = pd.DataFrame(party_rows).sort_values("Votos", ascending=False) if party_rows else pd.DataFrame()
            winner = party_frame.iloc[0] if not party_frame.empty else None
            second_place = party_frame.iloc[1] if len(party_frame) > 1 else None
            margin = (float(winner["Votos"]) - float(second_place["Votos"])) if second_place is not None else 0
            with st.container(border=True):
                st.markdown(f"#### {active_municipality} · Ayuntamiento 2024")
                ficha_a, ficha_b, ficha_c, ficha_d = st.columns(4)
                ficha_a.metric("Lista nominal", f"{float(election_payload.get('lista_nominal') or 0):,.0f}")
                ficha_b.metric("Votos totales", f"{float(election_payload.get('votes_total') or 0):,.0f}")
                ficha_c.metric("Participación", f"{float(election_payload.get('participacion_pct') or 0):.1f}%")
                ficha_d.metric("Votos válidos", f"{float(election_payload.get('numero_votos_validos') or 0):,.0f}")
                result_a, result_b, result_c = st.columns(3)
                result_a.metric("Primera fuerza", winner["Partido o candidatura"] if winner is not None else "No disponible")
                result_b.metric("Votos de primera fuerza", f"{float(winner['Votos']):,.0f}" if winner is not None else "No disponible")
                result_c.metric("Margen sobre segundo lugar", f"{margin:,.0f}" if second_place is not None else "No disponible")
                st.caption("Votos nulos: " + f"{float(election_payload.get('votes_nulos') or 0):,.0f}" + " · La primera fuerza se calcula con la votación publicada por partido, coalición o candidatura.")
                if not party_frame.empty:
                    st.markdown("##### Votación publicada")
                    st.dataframe(
                        party_frame, use_container_width=True, hide_index=True,
                        column_config={"Votos": st.column_config.NumberColumn(format="%,d")},
                    )
        st.caption(f"Fuente: resultados oficiales integrados para {context_state}, {selected_election_year}.")
        st.stop()

    st.markdown("### 5. Detalle municipal")
    st.subheader("Detalle municipal")
    municipality_filter = active_municipality
    municipal_detail = municipalities.copy()
    detail_inegi_rows = query(
        """
        SELECT municipality_code, indicator_name, indicator_id, period, value
        FROM territorial_indicators
        WHERE state = ?
        """,
        (context_state,),
    )
    if detail_inegi_rows:
        inegi_detail = pd.DataFrame(detail_inegi_rows)
        inegi_detail["clave_municipio"] = inegi_detail["municipality_code"].astype(str).str.zfill(3)
        inegi_detail["columna"] = (
            "INEGI: " + inegi_detail["indicator_name"].astype(str)
            + " (" + inegi_detail["period"].astype(str) + ")"
        )
        inegi_pivot = inegi_detail.pivot_table(
            index="clave_municipio", columns="columna", values="value", aggfunc="first"
        ).reset_index()
        municipal_detail = municipal_detail.merge(inegi_pivot, on="clave_municipio", how="left")
        # Los datos descargados deben verse primero: en capas externas hay
        # atributos vacíos que de otro modo obligaban a desplazarse mucho.
        inegi_columns = sorted(
            [column for column in inegi_pivot.columns if column != "clave_municipio"],
            key=lambda column: (0 if "Internet" in column else 1, column),
        )
        leading_columns = ["municipio"] + inegi_columns + ["poblacion", "viviendas"]
        remaining_columns = [
            column for column in municipal_detail.columns
            if column not in leading_columns and column != "clave_municipio"
            and not municipal_detail[column].isna().all()
        ]
        municipal_detail = municipal_detail[
            [column for column in leading_columns if column in municipal_detail.columns] + remaining_columns
        ]
    if municipality_filter != "Todos los municipios":
        municipal_detail = municipal_detail[municipal_detail["municipio"] == municipality_filter]
    municipal_detail = municipal_detail.rename(
        columns={
            "municipio": "municipio",
            "poblacion": "población",
            "internet_pct": "internet %",
            "agua_pct": "agua entubada %",
            "drenaje_pct": "drenaje %",
            "salud_pct": "afiliación a salud %",
            "ramo28_pesos": "ramo 28 (pesos)",
            "pmd_url": "plan municipal de desarrollo",
            "pmd_estatus": "estatus PMD",
        }
    )
    st.dataframe(
        municipal_detail,
        use_container_width=True,
        hide_index=True,
        key=f"municipal_detail_inegi_v3_{active_municipality}",
        column_config={
            "plan municipal de desarrollo": st.column_config.LinkColumn(
                "Plan municipal de desarrollo", display_text="Consultar documento"
            )
        },
    )
    if detail_inegi_rows:
        st.caption("Las columnas que inician con ‘INEGI:’ son los indicadores descargados y guardados para este estado.")
    st.caption(f"Capa activa: {gis_source}")

elif page == "Vinculación territorial":
    st.subheader("Vinculación territorial de publicaciones")
    st.caption(
        "Relaciona publicaciones con un municipio solo cuando su nombre aparece expresamente en el texto o título. "
        "No altera el registro original ni supone ubicaciones."
    )
    options = profile_options()
    if not options:
        st.info("Primero crea un perfil y obtiene publicaciones.")
        st.stop()
    chosen_profile = st.selectbox("Perfil", list(options), key="linking_profile")
    linking_profile_id = options[chosen_profile]
    states_for_linking = profile_states(linking_profile_id)
    if not states_for_linking:
        st.warning("El perfil no tiene un estado asociado en Perfil territorial.")
        st.stop()
    linking_state = st.selectbox("Estado", states_for_linking, key="linking_state")
    linking_geojson, linking_source = load_municipal_context(None, linking_state)
    if linking_geojson is None:
        st.warning(f"No se encontró una capa municipal para {linking_state}.")
        st.stop()
    linking_municipalities = municipal_dataframe(linking_geojson)
    municipality_names = linking_municipalities["municipio"].dropna().astype(str).tolist()
    existing_pulse_links = query(
        """
        SELECT COUNT(*) AS total
        FROM publication_territories pt
        JOIN publications p ON p.id = pt.publication_id
        WHERE p.profile_id = ? AND pt.state = ? AND pt.municipality IS NOT NULL
        """,
        (linking_profile_id, linking_state),
    )[0]["total"]
    publication_count = query(
        "SELECT COUNT(*) AS total FROM publications WHERE profile_id = ?",
        (linking_profile_id,),
    )[0]["total"]
    first_metric, second_metric = st.columns(2)
    first_metric.metric("Publicaciones del perfil", publication_count)
    second_metric.metric("Vínculos municipales actuales", existing_pulse_links)
    if st.button("Vincular por mención explícita de municipio", type="primary"):
        with st.spinner("Revisando textos y títulos de las publicaciones..."):
            link_result = rebuild_explicit_municipality_links(
                linking_profile_id, linking_state, municipality_names
            )
        st.success(
            f"Se revisaron {link_result['publications_reviewed']:,} publicaciones y se crearon "
            f"{link_result['links_created']:,} vínculos territoriales."
        )
        st.rerun()
    pulse_summary_rows = municipal_pulse_summary(linking_profile_id, linking_state)
    if pulse_summary_rows:
        summary_frame = pd.DataFrame(pulse_summary_rows).rename(columns={
            "municipality": "Municipio", "publications": "Publicaciones",
            "positive": "Positivas", "negative": "Negativas", "neutral": "Neutras",
        })
        st.markdown("#### Resumen de vínculos por municipio")
        st.dataframe(summary_frame, use_container_width=True, hide_index=True)
    st.caption(f"Capa municipal utilizada: {linking_source}")

elif page == "Bandeja de registros":
    st.subheader("Bandeja de registros")
    st.caption(
        "Aquí se consultan los registros originales capturados. Todavía no se modifican ni se clasifican."
    )
    options = profile_options()
    if not options:
        st.info("Primero crea un perfil.")
        st.stop()
    chosen = st.selectbox("Perfil", list(options), key="inbox_profile")
    profile_id = options[chosen]
    source_types = query(
        """
        SELECT DISTINCT s.source_type AS tipo
        FROM publications p JOIN sources s ON s.id = p.source_id
        WHERE p.profile_id = ? ORDER BY s.source_type
        """,
        (profile_id,),
    )
    source_choices = ["Todas las fuentes"] + [row["tipo"] for row in source_types]
    chosen_source = st.selectbox("Fuente", source_choices, key="inbox_source")
    inbox_filter = "" if chosen_source == "Todas las fuentes" else "AND s.source_type = ?"
    inbox_parameters = (profile_id,) if not inbox_filter else (profile_id, chosen_source)
    records = query(
        f"""
        SELECT p.collected_at AS capturado, s.source_type AS tipo_fuente,
               s.name AS fuente, p.title AS autor_o_titulo, p.text AS texto,
               p.published_at AS fecha_original, p.url AS enlace,
               CASE WHEN a.id IS NULL THEN 'Pendiente de análisis' ELSE 'Analizado' END AS estado
        FROM publications p
        JOIN sources s ON s.id = p.source_id
        LEFT JOIN analyses a ON a.publication_id = p.id
        WHERE p.profile_id = ? {inbox_filter}
        ORDER BY p.collected_at DESC
        LIMIT 500
        """,
        inbox_parameters,
    )
    pending_count = sum(row["estado"] == "Pendiente de análisis" for row in records)
    left, right = st.columns(2)
    left.metric("Registros en bandeja", len(records))
    right.metric("Pendientes de análisis", pending_count)
    if records:
        st.dataframe(
            pd.DataFrame(records),
            use_container_width=True,
            hide_index=True,
            column_config={
                "enlace": st.column_config.LinkColumn(
                    "Registro original", display_text="Abrir fuente"
                )
            },
        )
    else:
        st.info("No hay registros para este filtro.")

elif page == "Enfoques de análisis":
    st.subheader("Enfoques de análisis")
    st.caption("Este módulo analiza información que ya fue obtenida. No consulta fuentes externas.")
    options = profile_options()
    if not options:
        st.info("Primero crea un perfil.")
        st.stop()
    chosen = st.selectbox("Perfil para analizar", list(options), key="analysis_profile")
    profile_id = options[chosen]
    available_types = query(
        """
        SELECT DISTINCT s.source_type AS tipo
        FROM publications p
        JOIN sources s ON s.id = p.source_id
        WHERE p.profile_id = ?
        ORDER BY s.source_type
        """,
        (profile_id,),
    )
    source_type_options = ["Todas las fuentes"] + [row["tipo"] for row in available_types]
    selected_source_type = st.selectbox(
        "Fuente que deseas analizar",
        source_type_options,
        index=source_type_options.index("X") if "X" in source_type_options else 0,
        help="El filtro solo limita qué registros se analizan; no elimina ni modifica los demás.",
    )
    approaches = query(
        "SELECT name, description FROM analysis_approaches WHERE active = 1 ORDER BY id"
    )
    approach_names = [row["name"] for row in approaches]
    if "selected_approach" not in st.session_state:
        st.session_state.selected_approach = approach_names[0]
    st.markdown("#### Paso 1. Elige un enfoque")
    approach_buttons = st.columns(len(approach_names))
    for index, approach in enumerate(approaches):
        is_selected = st.session_state.selected_approach == approach["name"]
        if approach_buttons[index].button(
            f"Elegir: {approach['name']}",
            key=f"approach_{approach['name']}",
            type="primary" if is_selected else "secondary",
            use_container_width=True,
        ):
            st.session_state.selected_approach = approach["name"]
            st.rerun()
    selected_approach = st.session_state.selected_approach
    selected_description = next(
        row["description"] for row in approaches if row["name"] == selected_approach
    )
    st.info(f"**Enfoque activo: {selected_approach}.** {selected_description}")
    source_filter = "" if selected_source_type == "Todas las fuentes" else "AND s.source_type = ?"
    source_parameters = (profile_id,) if not source_filter else (profile_id, selected_source_type)
    pending = query(
        f"""
        SELECT p.id, s.name AS fuente, p.title AS titulo, p.collected_at AS obtenido
        FROM publications p
        JOIN sources s ON s.id = p.source_id
        LEFT JOIN analyses a ON a.publication_id = p.id
        WHERE p.profile_id = ? AND a.id IS NULL {source_filter}
        ORDER BY p.collected_at DESC
        """,
        source_parameters,
    )
    analyzed_count = query(
        f"""
        SELECT COUNT(*) AS total FROM publications p
        JOIN analyses a ON a.publication_id = p.id
        JOIN sources s ON s.id = p.source_id
        WHERE p.profile_id = ? {source_filter}
        """,
        source_parameters,
    )[0]["total"]
    left, right = st.columns(2)
    left.metric("Registros pendientes de análisis", len(pending))
    right.metric("Registros analizados", analyzed_count)
    st.caption("Reglas locales: clasificación rápida por palabras clave.")
    if st.button("Analizar registros pendientes", type="primary", disabled=not pending):
        result = analyze_pending(
            profile_id,
            None if selected_source_type == "Todas las fuentes" else selected_source_type,
        )
        st.success(f"Análisis terminado: {result['analyzed']} registros clasificados.")
        if result["errors"]:
            st.warning("\n".join(result["errors"]))
        st.rerun()

    st.divider()
    st.subheader("Análisis contextual con OpenAI")
    st.markdown("#### Paso 2. Procesa los registros pendientes")
    st.caption(
        "Reconoce contexto, ironía y si el mensaje se refiere realmente al perfil. "
        "Esta prueba procesa como máximo 10 publicaciones de X por ejecución."
    )
    approach_pending = query(
        """
        SELECT COUNT(*) AS total
        FROM publications p
        JOIN sources s ON s.id = p.source_id
        JOIN analysis_approaches ap ON ap.name = ?
        LEFT JOIN analysis_results ar
          ON ar.publication_id = p.id AND ar.approach_id = ap.id
        WHERE p.profile_id = ? AND s.source_type = ? AND ar.id IS NULL
        """,
        (selected_approach, profile_id, selected_source_type),
    )[0]["total"] if selected_source_type != "Todas las fuentes" else 0
    approach_done = query(
        """
        SELECT COUNT(*) AS total
        FROM analysis_results ar
        JOIN analysis_approaches ap ON ap.id = ar.approach_id
        JOIN publications p ON p.id = ar.publication_id
        JOIN sources s ON s.id = p.source_id
        WHERE ap.name = ? AND p.profile_id = ? AND s.source_type = ?
        """,
        (selected_approach, profile_id, selected_source_type),
    )[0]["total"] if selected_source_type != "Todas las fuentes" else 0
    approach_left, approach_right = st.columns(2)
    approach_left.metric("Pendientes para este enfoque", approach_pending)
    approach_right.metric("Procesados con este enfoque", approach_done)
    openai_ready = bool(get_setting("OPENAI_API_KEY"))
    openai_limit = st.slider("Registros de X para esta prueba", 1, 10, 10)
    can_use_openai = selected_source_type != "Todas las fuentes" and openai_ready
    st.caption("Acciones directas: procesa un enfoque sin cambiar el enfoque activo.")
    direct_buttons = st.columns(3)
    for index, approach in enumerate(approach_names):
        if direct_buttons[index % 3].button(
            f"Procesar: {approach}",
            key=f"process_direct_{approach}",
            disabled=not can_use_openai,
            use_container_width=True,
        ):
            with st.spinner(f"Procesando “{approach}” con OpenAI..."):
                direct_result = analyze_approach_with_openai(
                    profile_id, selected_source_type, approach, openai_limit
                )
            if direct_result["errors"]:
                st.warning(
                    f"“{approach}” terminó con observaciones:\n\n- "
                    + "\n- ".join(direct_result["errors"])
                )
            else:
                st.success(
                    f"“{approach}” procesó {direct_result['analyzed']} registro(s)."
                )
    if st.button(
        f"Procesar hasta {openai_limit} registros de {selected_source_type} con “{selected_approach}”",
        type="primary",
        disabled=not can_use_openai,
        help=(
            "Selecciona una fuente específica y configura la API key de OpenAI."
            if not can_use_openai else None
        ),
    ):
        with st.spinner("Aplicando el enfoque seleccionado con OpenAI..."):
            result = analyze_approach_with_openai(
                profile_id, selected_source_type, selected_approach, openai_limit
            )
        if result["errors"]:
            st.warning("La prueba terminó con observaciones:\n\n- " + "\n- ".join(result["errors"]))
        if result["analyzed"]:
            st.success(
                f"OpenAI analizó {result['analyzed']} registro(s) con el enfoque "
                f"“{selected_approach}” y el modelo {result['model']}."
            )

    approach_results = query(
        """
        SELECT p.published_at AS fecha, s.name AS fuente, p.title AS titulo,
               ar.sentiment AS sentimiento, ar.content_type AS tipo_contenido,
               ar.topic AS tema, ar.urgency AS urgencia, ar.relation_to_profile AS relacion,
               ar.explanation AS explicacion, ar.method AS metodo, p.url AS enlace
        FROM analysis_results ar
        JOIN analysis_approaches ap ON ap.id = ar.approach_id
        JOIN publications p ON p.id = ar.publication_id
        JOIN sources s ON s.id = p.source_id
        WHERE p.profile_id = ? AND ap.name = ?
        ORDER BY ar.analyzed_at DESC LIMIT 100
        """,
        (profile_id, selected_approach),
    )
    if approach_results:
        st.subheader(f"Resultados: {selected_approach}")
        st.dataframe(
            pd.DataFrame(approach_results),
            use_container_width=True,
            hide_index=True,
            column_config={"enlace": st.column_config.LinkColumn("Publicación original", display_text="Abrir fuente")},
        )
    if pending:
        st.subheader("Información pendiente")
        st.dataframe(pd.DataFrame(pending), use_container_width=True, hide_index=True)

    records = query(
        f"""
        SELECT p.published_at AS fecha, s.name AS fuente, p.title AS titulo,
               a.sentiment AS sentimiento, a.content_type AS tipo_contenido,
               a.topic AS tema, a.urgency AS urgencia, a.relation_to_profile AS relacion,
               a.explanation AS explicacion, a.method AS metodo, p.url AS enlace
        FROM publications p
        JOIN sources s ON s.id = p.source_id
        JOIN analyses a ON a.publication_id = p.id
        WHERE p.profile_id = ? {source_filter}
        ORDER BY p.collected_at DESC
        LIMIT 100
        """,
        source_parameters,
    )
    if records:
        st.subheader("Resultados analizados")
        results_table = pd.DataFrame(records)
        contextual_columns = ["tipo_contenido", "relacion", "explicacion"]
        for column in contextual_columns:
            results_table[column] = results_table[column].fillna(
                "Pendiente de análisis con OpenAI"
            )
        results_table["metodo"] = results_table["metodo"].fillna("Sin método registrado")
        st.dataframe(
            results_table,
            use_container_width=True,
            hide_index=True,
            column_config={
                "enlace": st.column_config.LinkColumn(
                    "Publicación original",
                    display_text="Abrir en X",
                    help="Abre la publicación pública original en X.",
                ),
            },
        )
        summary = (
            pd.DataFrame(records)
            .groupby("sentimiento", as_index=False)
            .size()
            .rename(columns={"size": "publicaciones"})
        )
        st.subheader("Resumen inicial")
        st.bar_chart(summary.set_index("sentimiento"))

elif page == "Prompts y consultas IA":
    st.subheader("Prompts y consultas IA")
    st.caption(
        "Consulta OpenAI sobre mensajes que ya están guardados. No obtiene datos nuevos ni reemplaza análisis existentes."
    )
    options = profile_options()
    if not options:
        st.info("Primero crea un perfil y obtiene al menos un registro.")
        st.stop()

    chosen = st.selectbox("Perfil", list(options), key="prompt_profile")
    profile_id = options[chosen]
    source_rows = query(
        """
        SELECT DISTINCT s.source_type AS tipo FROM publications p
        JOIN sources s ON s.id = p.source_id
        WHERE p.profile_id = ? ORDER BY s.source_type
        """,
        (profile_id,),
    )
    source_options = ["Todas las fuentes"] + [row["tipo"] for row in source_rows]
    default_source_index = source_options.index("X") if "X" in source_options else 0
    query_mode = st.radio(
        "Tipo de consulta",
        ["Basada en mensajes de la base", "Chat IA general"],
        horizontal=True,
        help="El primer modo usa registros originales; el chat general no utiliza mensajes ni fuentes de la base.",
    )
    if query_mode == "Basada en mensajes de la base":
        filter_left, filter_right = st.columns(2)
        selected_source = filter_left.selectbox(
            "Fuente de los mensajes", source_options, index=default_source_index, key="prompt_source"
        )
        period = filter_right.selectbox(
            "Periodo", ["Todo el historial", "Hoy", "Últimos 7 días"], key="prompt_period"
        )
        only_related = st.checkbox(
            "Usar solo mensajes relacionados con el perfil según sus palabras clave",
            value=True,
            help="Evita incluir notas generales de la fuente que no mencionan al perfil.",
        )
    else:
        selected_source = "Todas las fuentes"
        period = "Todo el historial"
        only_related = False
        st.info(
            "Este modo usa el mismo catálogo, pero no envía mensajes de tu base. "
            "La respuesta será general y no tendrá fuentes de tus registros."
        )

    source_filter = "" if selected_source == "Todas las fuentes" else "AND s.source_type = ?"
    parameters: list[object] = [profile_id]
    if selected_source != "Todas las fuentes":
        parameters.append(selected_source)
    date_from = None
    if period == "Hoy":
        date_from = date.today().isoformat()
    elif period == "Últimos 7 días":
        date_from = (date.today() - pd.Timedelta(days=6)).isoformat()
    date_filter = ""
    if date_from:
        date_filter = "AND DATE(COALESCE(NULLIF(p.published_at, ''), p.collected_at)) >= ?"
        parameters.append(date_from)
    candidate_records = query(
        f"""
        SELECT p.id, p.title, p.text, p.url, p.published_at, p.collected_at,
               s.source_type, s.name AS fuente
        FROM publications p JOIN sources s ON s.id = p.source_id
        WHERE p.profile_id = ? {source_filter} {date_filter}
        ORDER BY COALESCE(NULLIF(p.published_at, ''), p.collected_at) DESC, p.id DESC
        LIMIT 500
        """,
        tuple(parameters),
    )
    if only_related:
        keywords = query(
            "SELECT keyword FROM profile_keywords WHERE profile_id = ? AND active = 1",
            (profile_id,),
        )
        terms = [row["keyword"] for row in keywords]
        candidate_records = [
            record for record in candidate_records
            if matches_profile(f"{record['title'] or ''} {record['text'] or ''}", terms)
        ]
    if query_mode == "Chat IA general":
        candidate_records = []

    templates = query(
        "SELECT id, name, description, prompt_text FROM prompt_catalog WHERE active = 1 ORDER BY id"
    )
    template_by_name = {row["name"]: row for row in templates}
    choices = list(template_by_name) + ["Prompt libre"]
    selected_template = st.selectbox("Catálogo de prompts", choices, key="prompt_template")
    template = template_by_name.get(selected_template)
    if template:
        st.info(template["description"])
    initial_prompt = template["prompt_text"] if template else ""
    prompt_text = st.text_area(
        "Instrucción para la IA",
        value=initial_prompt,
        height=150,
        key=f"prompt_text_{selected_template}",
        help=(
            "Puedes ajustar la plantilla."
            if query_mode == "Chat IA general"
            else "Puedes ajustar la plantilla. La respuesta se limitará a los mensajes seleccionados."
        ),
    )

    if query_mode == "Basada en mensajes de la base":
        st.markdown("#### Mensajes que se usarán como evidencia")
        metric_left, metric_right = st.columns(2)
        metric_left.metric("Mensajes candidatos", len(candidate_records))
        if candidate_records:
            limit = metric_right.slider(
                "Máximo de mensajes a enviar", 1, min(30, len(candidate_records)), min(10, len(candidate_records))
            )
            selected_records = candidate_records[:limit]
            st.caption(
                "Se enviarán los mensajes más recientes del filtro. Puedes reducir el número para controlar el costo."
            )
            preview = pd.DataFrame(selected_records)[
                ["id", "source_type", "fuente", "title", "text", "published_at", "url"]
            ].rename(columns={
                "source_type": "tipo", "title": "autor_o_titulo", "text": "texto",
                "published_at": "fecha", "url": "enlace",
            })
            st.dataframe(
                preview,
                use_container_width=True,
                hide_index=True,
                column_config={"enlace": st.column_config.LinkColumn("Fuente original", display_text="Abrir")},
            )
        else:
            selected_records = []
            st.warning("No hay mensajes que coincidan con los filtros seleccionados.")
    else:
        selected_records = []
        st.caption("No se enviarán registros de la base de datos en esta consulta.")

    openai_ready = bool(get_setting("OPENAI_API_KEY"))
    if not openai_ready:
        st.warning("Configura la API key de OpenAI en Conexiones privadas para ejecutar una consulta.")
    if st.button(
        (
            f"Ejecutar consulta con {len(selected_records)} mensaje(s)"
            if query_mode == "Basada en mensajes de la base"
            else "Ejecutar Chat IA general"
        ),
        type="primary",
        disabled=(
            not openai_ready or not prompt_text.strip()
            or (query_mode == "Basada en mensajes de la base" and not selected_records)
        ),
    ):
        with st.spinner("Consultando OpenAI..."):
            prompt_result = run_prompt_query(
                profile_id=profile_id,
                prompt_text=prompt_text,
                publication_ids=[record["id"] for record in selected_records],
                prompt_catalog_id=template["id"] if template else None,
                source_filter=(None if query_mode == "Chat IA general" or selected_source == "Todas las fuentes" else selected_source),
                date_from=date_from if query_mode == "Basada en mensajes de la base" else None,
            )
        if prompt_result["errors"]:
            st.error("La consulta no pudo completarse:\n\n- " + "\n- ".join(prompt_result["errors"]))
        else:
            st.success(
                f"Consulta guardada. Se usó el modelo {prompt_result['model']} y "
                f"{len(prompt_result['sources'])} mensaje(s)."
            )
            st.markdown("#### Respuesta de IA")
            st.write(prompt_result["response"])
            if prompt_result["sources"]:
                with st.expander("Fuentes usadas en esta respuesta"):
                    sources_table = pd.DataFrame(prompt_result["sources"])[
                        ["id", "source_type", "source_name", "title", "published_at", "url"]
                    ].rename(columns={
                        "source_type": "tipo", "source_name": "fuente", "title": "autor_o_titulo",
                        "published_at": "fecha", "url": "enlace",
                    })
                    st.dataframe(
                        sources_table,
                        use_container_width=True,
                        hide_index=True,
                        column_config={"enlace": st.column_config.LinkColumn("Fuente original", display_text="Abrir")},
                    )
            else:
                st.caption("Consulta general: no se utilizaron registros de la base de datos.")

    st.divider()
    st.subheader("Historial de consultas")
    history = query(
        """
        SELECT pr.created_at AS fecha, COALESCE(pc.name, 'Prompt libre') AS catalogo,
               pr.records_sent AS mensajes, pr.model AS modelo, pr.status AS estado,
               pr.prompt_text AS instruccion, res.response_text AS respuesta
        FROM prompt_runs pr
        LEFT JOIN prompt_catalog pc ON pc.id = pr.prompt_catalog_id
        LEFT JOIN prompt_results res ON res.prompt_run_id = pr.id
        WHERE pr.profile_id = ?
        ORDER BY pr.created_at DESC LIMIT 20
        """,
        (profile_id,),
    )
    if history:
        st.dataframe(pd.DataFrame(history), use_container_width=True, hide_index=True)
    else:
        st.caption("Aún no hay consultas guardadas para este perfil.")

elif page == "Revisión e historial":
    st.subheader("Revisión e historial")
    st.caption(
        "Consulta el método usado y conserva las clasificaciones anteriores cuando un registro se procesa de nuevo."
    )
    options = profile_options()
    if not options:
        st.info("Primero crea un perfil.")
        st.stop()
    chosen = st.selectbox("Perfil", list(options), key="history_profile")
    profile_id = options[chosen]
    current_results = query(
        """
        SELECT p.published_at AS fecha, s.source_type AS tipo_fuente, s.name AS fuente,
               a.sentiment AS sentimiento, a.content_type AS tipo_contenido,
               a.topic AS tema, a.urgency AS urgencia, a.method AS metodo,
               a.model AS modelo, a.analyzed_at AS analizado
        FROM analyses a
        JOIN publications p ON p.id = a.publication_id
        JOIN sources s ON s.id = p.source_id
        WHERE p.profile_id = ?
        ORDER BY a.analyzed_at DESC
        LIMIT 200
        """,
        (profile_id,),
    )
    history_rows = query(
        """
        SELECT h.replaced_at AS reemplazado, s.source_type AS tipo_fuente,
               h.sentiment AS sentimiento_anterior, h.topic AS tema_anterior,
               h.urgency AS urgencia_anterior, h.method AS metodo_anterior,
               h.model AS modelo_anterior
        FROM analysis_history h
        JOIN publications p ON p.id = h.publication_id
        JOIN sources s ON s.id = p.source_id
        WHERE p.profile_id = ?
        ORDER BY h.replaced_at DESC
        LIMIT 200
        """,
        (profile_id,),
    )
    left, right = st.columns(2)
    left.metric("Resultados actuales", len(current_results))
    right.metric("Versiones en historial", len(history_rows))
    if current_results:
        st.markdown("#### Resultados actuales")
        st.dataframe(pd.DataFrame(current_results), use_container_width=True, hide_index=True)
    if history_rows:
        st.markdown("#### Clasificaciones anteriores")
        st.dataframe(pd.DataFrame(history_rows), use_container_width=True, hide_index=True)
    if not current_results and not history_rows:
        st.info("Todavía no hay resultados ni versiones anteriores para este perfil.")

elif page == "Manual de usuario":
    st.subheader("Manual de usuario")
    manual_path = Path(__file__).resolve().with_name("MANUAL_USUARIO.md")
    st.markdown(manual_path.read_text(encoding="utf-8"))

else:
    st.subheader("Manual técnico")
    technical_manual_path = Path(__file__).resolve().with_name("MANUAL_TECNICO.md")
    st.markdown(technical_manual_path.read_text(encoding="utf-8"))
