from datetime import date
import json
from html import escape
import math
from pathlib import Path
import re
import unicodedata

import altair as alt
import pandas as pd
import numpy as np
import pydeck as pdk
import pymupdf
import requests
import streamlit as st
import streamlit.components.v1 as components
from pypdf import PdfReader

from services.database import DB_PATH, execute, initialize_database, query, record_obtainment_run
from services.field_staff_ui import render_field_staff
from services.field_staff import initialize_staff
from services.field_tasks_ui import render_task_assignment
from services.field_reports_ui import render_task_reports
from services.web_auth import initialize_auth
from services.web_auth_ui import require_login, session_token
from services.web_portal import render_portal
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


st.set_page_config(page_title="Go2Win · Tablero de mando electoral", page_icon="📍", layout="wide")
initialize_database()
initialize_staff()
initialize_auth()
web_user = require_login()
if web_user['role_key'] != 'administrator':
    render_portal()
    st.stop()

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
        padding-top: 1.35rem;
        padding-bottom: 3.5rem;
    }
    html { scroll-behavior: smooth; }
    [data-testid="stAppViewContainer"], [data-testid="stMain"] {
        overflow-y: auto;
        scroll-behavior: smooth;
    }
    [data-testid="stSidebarContent"] {
        height: 100vh;
        overflow-y: auto;
        scrollbar-width: thin;
        scrollbar-color: rgba(186, 230, 253, .65) transparent;
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
    .domain-subnav {
        position: sticky;
        top: .75rem;
        z-index: 20;
        display: flex;
        gap: .55rem;
        align-items: center;
        overflow-x: auto;
        margin: -.15rem 0 1.15rem;
        padding: .65rem .75rem;
        border: 1px solid rgba(203, 213, 225, .9);
        border-radius: 14px;
        background: rgba(255,255,255,.93);
        box-shadow: 0 8px 24px rgba(15, 23, 42, .08);
        backdrop-filter: blur(12px);
    }
    .domain-subnav-label {
        flex: 0 0 auto;
        color: #0f766e;
        font-size: .72rem;
        font-weight: 800;
        letter-spacing: .08em;
    }
    .domain-subnav a {
        flex: 0 0 auto;
        padding: .38rem .68rem;
        border: 1px solid #dbe5ec;
        border-radius: 999px;
        color: #0f3b52 !important;
        background: #f8fafc;
        font-size: .82rem;
        font-weight: 700;
        text-decoration: none;
    }
    .domain-subnav a:hover { background: #ecfeff; border-color: #5eead4; }
    /* Tablero Electoral: composición ejecutiva tipo ficha de candidatura. */
    .electoral-hero {
        position: relative;
        overflow: hidden;
        margin: .2rem 0 1rem;
        padding: 1.75rem 2rem;
        border: 1px solid rgba(255,255,255,.16);
        border-radius: 22px;
        color: #fff;
        background: linear-gradient(120deg, #102a43 0%, #1d4e72 54%, #0f766e 100%);
        box-shadow: 0 18px 36px rgba(15, 40, 67, .20);
    }
    .electoral-hero::after {
        content: '';
        position: absolute;
        width: 310px;
        height: 310px;
        right: -105px;
        top: -155px;
        border: 42px solid rgba(255,255,255,.10);
        border-radius: 50%;
    }
    .electoral-eyebrow { color: #a7f3d0; font-size: .72rem; font-weight: 800; letter-spacing: .14em; }
    .electoral-name { position: relative; z-index: 1; margin: .35rem 0 .15rem; font-size: 2.15rem; font-weight: 800; letter-spacing: -.045em; }
    .electoral-detail { position: relative; z-index: 1; margin: 0; max-width: 760px; color: rgba(255,255,255,.85); font-size: .98rem; }
    .electoral-chip { display: inline-block; position: relative; z-index: 1; margin: .8rem .35rem 0 0; padding: .28rem .62rem; border: 1px solid rgba(255,255,255,.26); border-radius: 999px; background: rgba(255,255,255,.10); font-size: .78rem; font-weight: 700; }
    .electoral-kpi { min-height: 112px; margin: .15rem 0 1rem; padding: 1rem 1.05rem; border: 1px solid #dce7ee; border-radius: 16px; background: #fff; box-shadow: 0 8px 18px rgba(15, 40, 67, .07); }
    .electoral-kpi-label { color: #64748b; font-size: .69rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
    .electoral-kpi-value { margin-top: .3rem; color: #102a43; font-size: 1.35rem; font-weight: 800; line-height: 1.05; }
    .electoral-kpi-note { margin-top: .36rem; color: #475569; font-size: .78rem; line-height: 1.25; }
    .electoral-section-title { margin: 1.1rem 0 .35rem; color: #102a43; font-size: 1.08rem; font-weight: 800; letter-spacing: -.015em; }
    .scroll-anchor { position: relative; top: -90px; visibility: hidden; }
    [data-testid="stPyDeckChart"] {
        overflow: hidden;
        border: 1px solid #dbe5ec;
        border-radius: 18px;
        box-shadow: 0 10px 24px rgba(15, 23, 42, .08);
        background: #fff;
    }
    [data-testid="stTabs"] [role="tablist"] {
        gap: .3rem;
        padding: .3rem;
        border: 1px solid #dbe5ec;
        border-radius: 12px;
        background: #f8fafc;
    }
    [data-testid="stTabs"] [role="tab"] {
        height: 2.25rem;
        border-radius: 8px;
        font-weight: 700;
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
    .dictamen-reader-hero {
        background: linear-gradient(115deg, #082f49, #0f4c5c 62%, #164e63);
        border-radius: 18px;
        padding: 1.35rem 1.5rem;
        color: #fff;
        margin: .15rem 0 1rem;
        box-shadow: 0 14px 30px rgba(8,47,73,.18);
    }
    .dictamen-reader-hero small { color: #67e8f9; font-weight: 800; letter-spacing: .1em; }
    .dictamen-reader-hero h2 { color: #fff; margin: .35rem 0; font-size: 1.7rem; }
    .dictamen-reader-hero p { color: #dbeafe; margin: 0; }
    .dictamen-reading-note {
        border-left: 4px solid #f59e0b;
        background: #fff7ed;
        color: #7c2d12;
        border-radius: 0 10px 10px 0;
        padding: .65rem .8rem;
        font-size: .86rem;
    }
    .market-pie-wrap { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 1.2rem; min-height: 550px; padding: .5rem 0; }
    .market-pie {
        width: 430px; height: 430px; flex: 0 0 430px;
        filter: drop-shadow(0 10px 16px rgba(15, 23, 42, .16));
    }
    .market-pie svg { width: 100%; height: 100%; overflow: visible; }
    .market-pie-slice { stroke: #fff; stroke-width: 2px; cursor: pointer; transition: opacity .15s ease, transform .15s ease; transform-origin: 250px 250px; }
    .market-pie-slice:hover { opacity: .8; transform: scale(1.035); }
    .market-pie-center { fill: #fff; stroke: #e2e8f0; stroke-width: 1px; }
    .market-pie-center-label { fill: #0f172a; font-weight: 800; font-size: 20px; text-anchor: middle; }
    .market-pie-center-detail { fill: #64748b; font-size: 14px; text-anchor: middle; }
    .market-pie-legend { display: grid; grid-template-columns: repeat(3, minmax(160px, 1fr)); gap: .5rem 1rem; width: min(100%, 740px); }
    .market-pie-legend-item { font-size: .72rem; color: #475569; line-height: 1.3; }
    .market-pie-legend-item b { color: #0f172a; font-size: .75rem; }
    .market-pie-legend-item span { display: inline-block; width: .65rem; height: .65rem; border-radius: 50%; margin-right: .3rem; }
    @media (max-width: 900px) {
        .market-pie-wrap { min-height: 0; }
        .market-pie { width: 300px; height: 300px; flex-basis: 300px; }
        .market-pie-legend { width: 100%; }
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
    "votes_nay": "Nueva Alianza Yucatán", "votes_independent": "Candidatura independiente",
    "votes_pan_pri_prd_nay": "Candidatura común PAN-PRI-PRD-NAY",
    "votes_pan_pri_nay": "Candidatura común PAN-PRI-NAY",
    "votes_pan_prd_nay": "Candidatura común PAN-PRD-NAY",
    "votes_pri_prd_nay": "Candidatura común PRI-PRD-NAY",
    "votes_pan_nay": "Candidatura común PAN-NAY", "votes_pri_nay": "Candidatura común PRI-NAY",
    "votes_prd_nay": "Candidatura común PRD-NAY", "votes_prd_nay_2": "Candidatura común PRD-NAY",
    "votes_qi": "Querétaro Independiente", "votes_fm": "Fuerza México",
    "votes_qs": "Querétaro Seguro",
    "votes_pan_qi": "Coalición PAN-QI", "votes_pri_pvem": "Coalición PRI-PVEM",
    "votes_pan_prd_qi": "Coalición PAN-PRD-QI", "votes_prd_qi": "Coalición PRD-QI",
    "votes_pt_qi": "Coalición PT-QI",
    "votes_pt_morena_naem": "Coalición PT-Morena-NAEM",
    "votes_cc_pt_morena_naem": "Candidatura común PT-Morena-NAEM",
    "votes_morena_naem": "Candidatura común Morena-NAEM",
    "votes_pt_naem": "Candidatura común PT-NAEM",
    "votes_coalicion_pt_morena": "Coalición PT-Morena",
    "votes_coalicion_pt_morena_nach": "Coalición PT-Morena-Nueva Alianza Chihuahua",
    "votes_coalicion_morena_nach": "Coalición Morena-Nueva Alianza Chihuahua",
    "votes_coalicion_pt_nach": "Coalición PT-Nueva Alianza Chihuahua",
    "votes_pt_pvem_morena_nan": "Juntos Haremos Historia Nayarit",
    "votes_shh": "Sigamos Haciendo Historia",
    "votes_jdch": "Juntos Defendamos Chihuahua",
    "votes_va_por_sonora": "Va por Sonora",
    "votes_juntos_haremos_historia_sonora": "Juntos Haremos Historia en Sonora",
}


# Estas agrupaciones convierten el desglose de marcas de boleta publicado por
# la autoridad en una lectura de fuerza por candidatura/bloque. Sólo se suman
# columnas que corresponden al mismo bloque; los demás partidos permanecen
# visibles de manera independiente.
ELECTORAL_BLOCKS = (
    (
        "Morena–PT–PVEM",
        {
            "votes_morena", "votes_pt", "votes_pvem", "votes_sigamos_haciendo_historia",
            "votes_juntos_haremos_historia_sonora", "votes_pvem_pt_morena",
            "votes_pvem_pt_morena_naem", "votes_cc_pvem_pt_morena",
            "votes_pt_morena_naem", "votes_cc_pt_morena_naem",
            "votes_morena_naem", "votes_pt_naem", "votes_pvem_pt", "votes_pvem_morena", "votes_pt_morena",
            "votes_coalicion_pt_morena", "votes_coalicion_pt_morena_nach",
            "votes_coalicion_morena_nach", "votes_coalicion_pt_nach",
            "votes_pt_pvem_morena_nan", "votes_shh",
        },
    ),
    (
        "PAN–PRI–PRD",
        {
            "votes_pan", "votes_pri", "votes_prd", "votes_coalicion_pan_pri_prd",
            "votes_coalicion_pan_pri", "votes_coalicion_pan_prd", "votes_coalicion_pri_prd",
            "votes_fuerza_y_corazon_sonora", "votes_va_por_sonora", "votes_pan_pri_prd",
            "votes_jdch",
        },
    ),
    (
        "PAN–PRI–PRD–Nueva Alianza",
        {
            "votes_pan_pri_prd_naem", "votes_cc_pan_pri_prd_naem",
            "votes_pan_pri_naem", "votes_pan_prd_naem", "votes_pri_prd_naem",
            "votes_pan_naem", "votes_pri_naem", "votes_prd_naem",
        },
    ),
    (
        "PAN–PRI–PRD–Nueva Alianza Yucatán",
        {
            "votes_pan_pri_prd_nay", "votes_pan_pri_nay", "votes_pan_prd_nay",
            "votes_pri_prd_nay", "votes_pan_nay", "votes_pri_nay", "votes_prd_nay",
            "votes_prd_nay_2",
        },
    ),
)

# Algunas fuentes ya incluyen, además de las marcas partidistas, el total de
# cada candidatura. En esos casos las marcas de los partidos que la integran
# son componentes informativos y no deben volver a sumarse en el pastel.
PREAGGREGATED_CANDIDATURES = {
    ("Chihuahua", 2024, "Diputaciones locales"): {
        "votes_shh": "Sigamos Haciendo Historia",
        "votes_jdch": "Juntos Defendamos Chihuahua",
        "votes_mc": "Movimiento Ciudadano",
        "votes_pvem": "PVEM",
        "votes_pueblo": "PUEBLO",
        "votes_mxrep": "México Republicano",
    },
}


def consolidated_electoral_blocks(
    market: pd.DataFrame,
    option_keys: list[str],
    state: str | None = None,
    election_year: int | None = None,
    election_type: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return a candidate/block reading and the official, unaggregated ballot reading."""
    official = pd.DataFrame([
        {"Opción oficial en boleta": ELECTORAL_VOTE_LABELS.get(key, key.replace("votes_", "").replace("_", " ").upper()),
         "Votos": int(market[key].sum()), "clave": key}
        for key in option_keys
    ]).sort_values("Votos", ascending=False).reset_index(drop=True)

    preaggregated = PREAGGREGATED_CANDIDATURES.get((state, election_year, election_type), {})
    if preaggregated:
        blocks = [
            {"Opción": label, "Votos": int(market[key].sum())}
            for key, label in preaggregated.items()
            if key in option_keys and market[key].sum() > 0
        ]
        return pd.DataFrame(blocks).sort_values("Votos", ascending=False).reset_index(drop=True), official

    pending = set(option_keys)
    blocks: list[dict] = []
    for block_name, block_keys in ELECTORAL_BLOCKS:
        present_keys = pending.intersection(block_keys)
        if not present_keys:
            continue
        # Un bloque se consolida sólo cuando la fuente trae al menos una
        # combinación/coalición de esa misma candidatura. Si sólo aparecen
        # partidos individuales, se conservan como partidos separados.
        has_alliance_mark = any(key not in {"votes_morena", "votes_pt", "votes_pvem", "votes_pan", "votes_pri", "votes_prd"} for key in present_keys)
        if not has_alliance_mark:
            continue
        blocks.append({"Opción": block_name, "Votos": int(sum(market[key].sum() for key in present_keys))})
        pending.difference_update(present_keys)
    for key in sorted(pending):
        blocks.append({
            "Opción": ELECTORAL_VOTE_LABELS.get(key, key.replace("votes_", "").replace("_", " ").upper()),
            "Votos": int(market[key].sum()),
        })
    return pd.DataFrame(blocks).sort_values("Votos", ascending=False).reset_index(drop=True), official


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


def render_domain_scroll_nav(items: list[tuple[str, str]]) -> None:
    """Render a compact in-page navigator for long territorial screens."""
    links = "".join(f'<a href="#{anchor}">{label}</a>' for label, anchor in items)
    st.markdown(
        f'<nav class="domain-subnav"><span class="domain-subnav-label">RECORRIDO</span>{links}</nav>',
        unsafe_allow_html=True,
    )


OBJECTIVE_NAVIGATION = {
    "ⓘ  Inicio y objetivo": "Inicio",
    "ⓘ  Orden de cargas": "Orden de cargas",
}
PROFILE_NAVIGATION = {
    "01  Perfil y elección": "Perfiles y trayectorias",
    "02  Dictamen de viabilidad": "Recorrido del dictamen",
    "03  Fuentes y cobertura del expediente": "Dictamen de viabilidad",
    "04  Información estratégica del candidato": "Tablero Electoral",
}
GIS_NAVIGATION = {
    "04  Visor electoral": "Visor electoral",
    "05  Visor territorial": "Dominio territorial",
    "06  Visor regional y PED": "Diagnóstico regional del PED",
}
DIAGNOSTIC_NAVIGATION = {
    "07  Mercado electoral": "Mercado electoral",
    "08  Diagnóstico territorial": "Diagnóstico territorial",
    "09  Mapa de oportunidad electoral": "Mapa de oportunidad electoral",
    "09A  Cruce INEGI + INE": "Cruce INEGI + INE",
}
DECISION_NAVIGATION = {
    "10  Escenarios electorales": "Escenarios electorales",
    "11  Metas y control territorial": "Metas y control territorial",
}
EXECUTION_NAVIGATION = {
    "12  Priorización territorial": "Priorización territorial",
    "13  Estrategia territorial": "Estrategia territorial",
    "14  Planes de acción": "Planes de acción",
    "15  Mapa de estrategia y operación": "Mapa de estrategia y operación",
    "16  CRM territorial electoral": "CRM territorial electoral",
    "17  Seguimiento de campo": "Seguimiento de campo",
    "18  Tablero de evidencia y seguimiento": "Tableros y reportes",
    "19  Alertas territoriales": "Alertas territoriales",
}
EVIDENCE_NAVIGATION = {
    "20  Fuentes y actualización": "Fuentes y actualización",
    "21  Bandeja de evidencia": "Bandeja de registros",
    "22  Enfoques de análisis": "Enfoques de análisis",
    "23  Vinculación territorial": "Vinculación territorial",
    "24  Prompts y consultas IA": "Prompts y consultas IA",
    "25  Revisión e historial": "Revisión e historial",
}
SETTINGS_NAVIGATION = {
    "Personal y Telegram": "Personal y Telegram",
    "26  Territorios y fuentes": "Territorio y fuentes",
    "27  Perfil territorial": "Perfil territorial",
    "28  Conexiones privadas": "Configuración de conexiones",
    "29  Planeación estratégica": "Planeación",
    "29A  Seguimiento del PMD": "Seguimiento del PMD",
    "30  Modelos y aprendizaje": "Machine Learning",
    "?  Manual de usuario": "Manual de usuario",
    "?  Manual técnico": "Manual técnico",
}


NAVIGATION_WIDGET_KEYS = (
    "objective_navigation", "profile_navigation", "evidence_navigation", "gis_navigation", "diagnostic_navigation",
    "decision_navigation", "execution_navigation", "settings_navigation",
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
        non_option_vote_keys = {"votes_total", "votes_nulos", "votes_no_reg", "votes_validos"}
        for key, value in election.items():
            # Los totales y votos nulos no son una opción política. Incluirlos
            # aquí podía mostrar porcentajes superiores a 100% al dividir el
            # total emitido entre votos válidos.
            if key.startswith("votes_") and key not in non_option_vote_keys and float(value or 0) > 0:
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


def render_electoral_dashboard() -> None:
    """Reusable executive electoral dashboard, scoped to the selected profile and state."""
    st.caption("TABLERO ELECTORAL · FICHA EJECUTIVA DE CANDIDATURA")
    options = profile_options()
    if not options:
        st.info("Registra un perfil para abrir su tablero electoral.")
        return
    selected_label = st.selectbox("Perfil del tablero", list(options), key="electoral_dashboard_profile")
    profile_id = options[selected_label]
    profile_name = selected_label.rsplit(" (#", 1)[0]
    profile_row = query("SELECT actor_type, notes FROM profiles WHERE id = ?", (profile_id,))[0]
    position_rows = query(
        """SELECT office, condition, party_or_coalition, starts_at, ends_at
           FROM profile_positions WHERE profile_id = ? ORDER BY is_current DESC, id DESC LIMIT 1""",
        (profile_id,),
    )
    position = position_rows[0] if position_rows else None
    state_rows = query(
        """
        SELECT DISTINCT state FROM (
            SELECT state FROM profile_territories pt JOIN territories t ON t.id = pt.territory_id WHERE pt.profile_id = ?
            UNION
            SELECT state FROM reference_documents WHERE profile_id = ? AND state IS NOT NULL
        ) WHERE state IS NOT NULL AND TRIM(state) <> '' ORDER BY state
        """,
        (profile_id, profile_id),
    )
    states = [row["state"] for row in state_rows]
    selected_state = st.selectbox(
        "Territorio de lectura", states, key=f"electoral_dashboard_state_{profile_id}"
    ) if states else None
    if not selected_state:
        st.warning("Este perfil aún no tiene un estado asociado. Puedes asignarlo desde Perfil territorial.")
        return
    associated_municipalities = query(
        """SELECT t.municipality
           FROM profile_territories pt JOIN territories t ON t.id = pt.territory_id
           WHERE pt.profile_id = ? AND t.state = ? AND t.territory_type = 'Municipio'
           ORDER BY t.municipality""",
        (profile_id, selected_state),
    )

    evidence_count = int(query("SELECT COUNT(*) AS total FROM publications WHERE profile_id = ?", (profile_id,))[0]["total"] or 0)
    document_count = int(query("SELECT COUNT(*) AS total FROM reference_documents WHERE profile_id = ?", (profile_id,))[0]["total"] or 0)
    conclusion_rows = query("SELECT * FROM viability_conclusions WHERE profile_id = ?", (profile_id,))
    conclusion = conclusion_rows[0] if conclusion_rows else None
    assessment_count = int(query("SELECT COUNT(*) AS total FROM viability_variable_assessments WHERE profile_id = ?", (profile_id,))[0]["total"] or 0)
    competitor_count = int(query("SELECT COUNT(*) AS total FROM viability_competitors WHERE profile_id = ?", (profile_id,))[0]["total"] or 0)
    survey_count = int(query("SELECT COUNT(*) AS total FROM viability_surveys WHERE profile_id = ?", (profile_id,))[0]["total"] or 0)
    structure_count = int(query("SELECT COUNT(*) AS total FROM viability_structure_records WHERE profile_id = ?", (profile_id,))[0]["total"] or 0)
    coalition_count = int(query("SELECT COUNT(*) AS total FROM viability_coalition_scenarios WHERE profile_id = ?", (profile_id,))[0]["total"] or 0)
    resource_count = int(query("SELECT COUNT(*) AS total FROM viability_resource_records WHERE profile_id = ?", (profile_id,))[0]["total"] or 0)
    source_count = int(query("SELECT COUNT(*) AS total FROM sources WHERE profile_id = ? AND active = 1", (profile_id,))[0]["total"] or 0)
    analysis_count = int(query("SELECT COUNT(*) AS total FROM analyses a JOIN publications p ON p.id = a.publication_id WHERE p.profile_id = ?", (profile_id,))[0]["total"] or 0)
    action_count = int(query("SELECT COUNT(*) AS total FROM territorial_action_plans tap JOIN territorial_strategies ts ON ts.id = tap.strategy_id WHERE ts.profile_id = ?", (profile_id,))[0]["total"] or 0)
    assessment_rows = query(
        "SELECT variable_code, status, evidence_note, actual_value, metric_unit FROM viability_variable_assessments WHERE profile_id = ?",
        (profile_id,),
    )
    assessment_by_code = {row["variable_code"]: row for row in assessment_rows}
    data_status = {
        "municipal": int(query("SELECT COUNT(*) AS total FROM territorial_election_results WHERE state = ?", (selected_state,))[0]["total"] or 0),
        "district": int(query("SELECT COUNT(*) AS total FROM territorial_district_results WHERE state = ?", (selected_state,))[0]["total"] or 0),
        "section": int(query("SELECT COUNT(*) AS total FROM territorial_section_results WHERE state = ?", (selected_state,))[0]["total"] or 0),
        "indicators": int(query("SELECT COUNT(*) AS total FROM territorial_indicators WHERE state = ?", (selected_state,))[0]["total"] or 0),
    }
    is_cholula_case = profile_name.startswith("Raymundo Cuautli") and selected_state == "Puebla"
    viability_score_model = [
        ("vote_intent", "Intención de voto personal", 10, 42, "Brecha relevante frente a la puntera"),
        ("name_recognition", "Conocimiento del candidato", 6, 70, "Presencia acumulada"),
        ("favorable_opinion", "Opinión positiva / negativos", 5, 62, "Requiere medición propia"),
        ("territorial_structure", "Estructura territorial", 7, 80, "Activo principal"),
        ("party_brand", "Fortaleza de marca partidista", 7, 76, "Impulso partidista"),
        ("brand_transfer", "Transferencia marca-candidato", 5, 64, "No automática"),
        ("electoral_experience", "Experiencia electoral", 4, 78, "Trayectoria amplia"),
        ("institutional_position", "Posición institucional", 4, 78, "Exposición territorial"),
        ("internal_unity", "Unidad interna", 6, 62, "Competencia abierta"),
        ("nomination_probability", "Probabilidad de nominación", 7, 75, "Media-alta"),
        ("party_vote_history", "Voto histórico del partido", 5, 58, "Debajo del PAN en 2024"),
        ("mobilization", "Capacidad de movilización", 5, 75, "Potencial organizativo"),
        ("strategic_territories", "Territorios estratégicos", 4, 78, "Clave territorial"),
        ("urban_segments", "Segmentos urbanos / residenciales", 4, 56, "Área a fortalecer"),
        ("undecided_voters", "Atracción de indecisos", 4, 60, "17.2% en julio"),
        ("useful_vote", "Voto útil", 3, 68, "Depende de fragmentación"),
        ("main_rival", "Fortaleza rival principal", 5, 38, "PAN / Lupita fuertes"),
        ("opposition_fragmentation", "Fragmentación opositora", 3, 58, "Efecto ambiguo"),
        ("reputational_risk", "Riesgo reputacional", 3, 45, "Flanco político"),
        ("growth_potential", "Potencial de crecimiento", 3, 82, "Alto si consolida"),
    ]
    # Marco Bonilla cuenta con un dictamen base de 15 variables (15-sep-2026)
    # y un modelo Go2Win ampliado a 20 variables.  Esta versión conserva las
    # equivalencias semánticas del dictamen: seguridad no se presenta como
    # transferencia de marca; campo/agua no como experiencia electoral; y la
    # comunicación digital vuelve a ser una variable explícita.
    if profile_id == 4:
        viability_score_model = [
            ("vote_intent", "Intención de voto personal", 9, 0, "Careos comparables; no es pronóstico."),
            ("nomination_probability", "Posición interna y probabilidad de nominación", 8, 0, "Liderazgo interno PAN."),
            ("institutional_position", "Gestión municipal", 8, 0, "Activo de gestión demostrable."),
            ("name_recognition", "Conocimiento estatal", 6, 0, "Desigual fuera de la capital."),
            ("territorial_structure", "Estructura de la capital", 6, 0, "Bastión que requiere auditoría."),
            ("urban_segments", "Penetración en Ciudad Juárez", 9, 0, "Brecha territorial decisiva."),
            ("strategic_territories", "Fortaleza en el centro-sur", 6, 0, "Base de compensación."),
            ("party_brand", "Fortaleza de marca PAN", 5, 0, "Competitiva, debajo de Morena."),
            ("party_vote_history", "Base electoral histórica del PAN", 3, 0, "Resultado histórico comparable."),
            ("opposition_fragmentation", "Viabilidad de coalición y no fragmentación", 4, 0, "Sujeta a acuerdos y transferencia."),
            ("brand_transfer", "Atributos de gestión y seguridad", 5, 0, "Fortaleza con riesgo de contraste."),
            ("electoral_experience", "Agenda territorial: campo y agua", 4, 0, "Relevancia regional."),
            ("mobilization", "Comunicación digital", 5, 0, "Debe ampliar alcance en el norte."),
            ("internal_unity", "Unidad interna", 4, 0, "Ventaja relativa; requiere consolidación."),
            ("favorable_opinion", "Margen de opinión positiva y bajo rechazo", 4, 0, "Mejor margen de crecimiento."),
            ("reputational_risk", "Control de riesgo reputacional y legal", 3, 0, "Fiscalización y actos anticipados."),
            ("growth_potential", "Potencial de crecimiento", 3, 0, "Alto con expansión territorial."),
            ("main_rival", "Capacidad competitiva frente al rival principal", 4, 0, "Requiere tracking comparable."),
            ("undecided_voters", "Capacidad de atraer indecisos", 2, 0, "Pendiente de medición propia."),
            ("useful_vote", "Potencial de voto útil", 2, 0, "Sujeto a escenarios de coalición."),
        ]
    elif profile_name.startswith("Cecilia Anunciación Patrón"):
        # El dictamen de Mérida contiene un modelo propio de ocho componentes.
        # Se conserva sin forzarlo al modelo genérico de 20 variables.
        viability_score_model = [
            ("previous_election", "Resultado electoral previo", 16, 0, "Ventaja comprobada en 2024."),
            ("approval_knowledge", "Aprobación y conocimiento", 15, 0, "Posición favorable en 2026."),
            ("structure_nomination", "Estructura y nominación", 12, 0, "Incumbencia y control de red."),
            ("management_results", "Gestión y resultados", 16, 0, "Activos visibles; escrutinio alto."),
            ("territorial_coverage", "Cobertura territorial", 12, 0, "Brechas entre zonas de la ciudad."),
            ("coalition_alliances", "Coalición y alianzas", 9, 0, "Configuración 2027 abierta."),
            ("political_context", "Entorno político", 10, 0, "El gobierno estatal eleva la competencia."),
            ("reputational_risk", "Control de riesgo reputacional", 10, 0, "Prevención permanente."),
        ]
    saved_scores = query(
        "SELECT variable_code, score, notes FROM viability_electoral_scores WHERE profile_id = ?",
        (profile_id,),
    )
    score_by_code = {row["variable_code"]: row for row in saved_scores}
    electoral_evidence_rows = query(
        """SELECT variable_code, status, evidence_note, source_label, source_url, reference_date
           FROM viability_electoral_evidence WHERE profile_id = ?""",
        (profile_id,),
    )
    electoral_evidence_by_code = {row["variable_code"]: row for row in electoral_evidence_rows}

    office = position["office"] if position and position["office"] else "Cargo por documentar"
    condition = position["condition"] if position and position["condition"] else profile_row["actor_type"]
    party = position["party_or_coalition"] if position and position["party_or_coalition"] else "Partido o coalición por documentar"
    st.markdown(
        f"""
        <section class="electoral-hero">
            <div class="electoral-eyebrow">EXPEDIENTE DE CANDIDATURA · {escape(selected_state.upper())}</div>
            <div class="electoral-name">{escape(profile_name)}</div>
            <p class="electoral-detail">{escape(str(office))} · {escape(str(condition))}</p>
            <span class="electoral-chip">{escape(str(party))}</span>
            <span class="electoral-chip">Corte de información local</span>
        </section>
        """,
        unsafe_allow_html=True,
    )
    top = st.columns(5)
    kpis = [
        ("Condición", str(condition), str(office)),
        ("Viabilidad", conclusion["assessment_status"] if conclusion else "Pendiente", "Resultado de la valoración"),
        ("Evidencia", f"{evidence_count} registros", "Publicaciones vinculadas"),
        ("Análisis", f"{analysis_count} procesados", "Conversación y temas"),
        ("Territorio", f"{len(associated_municipalities)} municipios", f"Documentos: {document_count}"),
    ]
    for column, (label, value, note) in zip(top, kpis):
        column.markdown(
            f'<div class="electoral-kpi"><div class="electoral-kpi-label">{escape(str(label))}</div>'
            f'<div class="electoral-kpi-value">{escape(str(value))}</div>'
            f'<div class="electoral-kpi-note">{escape(str(note))}</div></div>',
            unsafe_allow_html=True,
        )
    if is_cholula_case:
        st.info("Línea base del dictamen de San Andrés Cholula: índice global **67/100**, viabilidad de candidatura **75/100** y posición observada **12.1%**. No es una encuesta actual ni un pronóstico electoral.")

    model_tab, executive_tab, variables_tab, coverage_tab, route_tab = st.tabs([
        "Modelo de viabilidad", "Ficha del candidato", "Posicionamiento y competencia", "Territorio, estructura y escenarios", "Modelo y cobertura"
    ])
    with executive_tab:
        st.markdown("#### Identidad política y territorio")
        identity_a, identity_b, identity_c = st.columns(3)
        identity_a.write(f"**Perfil:** {profile_name}")
        identity_b.write(f"**Cargo o aspiración:** {position['office'] if position else 'Por documentar'}")
        identity_c.write(f"**Ámbito:** {selected_state}")
        if associated_municipalities:
            st.caption(f"Municipios asociados al perfil: **{len(associated_municipalities)}**.")
            with st.expander("Ver municipios asociados al perfil"):
                municipality_frame = pd.DataFrame(associated_municipalities).rename(columns={"municipality": "Municipio"})
                st.dataframe(municipality_frame, use_container_width=True, hide_index=True, height=240)
        if position and position["party_or_coalition"]:
            st.caption(f"Partido o coalición registrada: {position['party_or_coalition']}.")
        if profile_row["notes"]:
            st.caption(profile_row["notes"])
        st.markdown("#### Información disponible en el expediente")
        available_a, available_b, available_c, available_d = st.columns(4)
        available_a.metric("Publicaciones", f"{evidence_count:,}", "Registros originales")
        available_b.metric("Análisis", f"{analysis_count:,}", "Registros procesados")
        available_c.metric("Documentos", f"{document_count:,}", "Dictámenes y referencias")
        available_d.metric("Fuentes activas", f"{source_count:,}", "Fuentes vinculadas")
        left, right = st.columns([1.15, 1])
        with left:
            st.markdown("#### Condición de candidatura")
            if conclusion:
                st.write(conclusion["conditions"] or conclusion["next_step"] or "El perfil cuenta con un dictamen documentado.")
            else:
                st.info("Aún no hay una conclusión de viabilidad registrada para este perfil.")
            st.markdown("#### Activos del perfil")
            st.write(conclusion["strengths"] if conclusion and conclusion["strengths"] else "Pendiente de documentar fortalezas con evidencia.")
        with right:
            st.markdown("#### Riesgos y condiciones")
            st.write(conclusion["risks"] if conclusion and conclusion["risks"] else "Pendiente de documentar riesgos y condiciones de competencia.")
            st.caption(f"Perfil: {profile_name} · Territorio: {selected_state} · Documentos cargados: {document_count}.")
        documents = query(
            """SELECT title AS documento, document_type AS tipo, source_url AS liga
               FROM reference_documents WHERE profile_id = ? ORDER BY id DESC""",
            (profile_id,),
        )
        if documents:
            with st.expander(f"Ver {len(documents)} documento(s) incorporado(s) al expediente"):
                st.dataframe(
                    pd.DataFrame(documents),
                    use_container_width=True,
                    hide_index=True,
                    column_config={"liga": st.column_config.LinkColumn("Documento / fuente", display_text="Abrir")},
                )

        st.markdown("#### Evidencia incorporada al expediente")
        evidence_left, evidence_right = st.columns([1, 1.15])
        with evidence_left:
            source_rows = query(
                """SELECT source_type AS tipo, name AS fuente, account_or_url AS referencia
                   FROM sources WHERE profile_id = ? AND active = 1 ORDER BY source_type, name""",
                (profile_id,),
            )
            st.markdown(f"**Fuentes activas ({len(source_rows)})**")
            if source_rows:
                st.dataframe(
                    pd.DataFrame(source_rows),
                    use_container_width=True,
                    hide_index=True,
                    height=210,
                    column_config={"referencia": st.column_config.LinkColumn("Referencia", display_text="Abrir")},
                )
            else:
                st.caption("No hay fuentes activas vinculadas a este perfil.")
        with evidence_right:
            topic_rows = query(
                """SELECT COALESCE(a.topic, 'Sin tema') AS tema, COUNT(*) AS menciones,
                          SUM(CASE WHEN a.urgency = 'Alta' THEN 1 ELSE 0 END) AS urgentes
                   FROM analyses a JOIN publications p ON p.id = a.publication_id
                   WHERE p.profile_id = ?
                   GROUP BY COALESCE(a.topic, 'Sin tema')
                   ORDER BY menciones DESC LIMIT 8""",
                (profile_id,),
            )
            st.markdown("**Temas identificados en la conversación**")
            if topic_rows:
                st.dataframe(pd.DataFrame(topic_rows), use_container_width=True, hide_index=True, height=210)
            else:
                st.caption("Aún no hay publicaciones analizadas para identificar temas.")

        recent_evidence = query(
            """SELECT COALESCE(p.title, substr(p.text, 1, 110)) AS evidencia,
                      p.published_at AS fecha, a.sentiment AS sentimiento,
                      a.topic AS tema, a.urgency AS urgencia, p.url AS liga
               FROM publications p LEFT JOIN analyses a ON a.publication_id = p.id
               WHERE p.profile_id = ? ORDER BY COALESCE(p.published_at, p.collected_at) DESC LIMIT 8""",
            (profile_id,),
        )
        if recent_evidence:
            with st.expander("Ver evidencia reciente vinculada al perfil"):
                st.dataframe(
                    pd.DataFrame(recent_evidence),
                    use_container_width=True,
                    hide_index=True,
                    column_config={"liga": st.column_config.LinkColumn("Fuente original", display_text="Abrir")},
                )

    with variables_tab:
        competition_left, competition_right = st.columns(2)
        with competition_left:
            st.markdown("#### Competencia registrada")
            competitors = query(
                """SELECT name AS perfil, party_or_coalition AS partido_o_coalicion, condition AS condición,
                          territory AS territorio, positioning_note AS lectura
                   FROM viability_competitors WHERE profile_id = ? ORDER BY name""",
                (profile_id,),
            )
            if competitors:
                st.dataframe(pd.DataFrame(competitors), use_container_width=True, hide_index=True)
            else:
                st.caption("Sin perfiles competidores registrados para este caso.")
        with competition_right:
            st.markdown("#### Estudios y posicionamiento")
            surveys = query(
                """SELECT name AS estudio, pollster AS casa, fieldwork_date AS levantamiento,
                          sample_size AS muestra, profile_result_pct AS resultado_pct
                   FROM viability_surveys WHERE profile_id = ? ORDER BY created_at DESC""",
                (profile_id,),
            )
            if surveys:
                st.dataframe(pd.DataFrame(surveys), use_container_width=True, hide_index=True)
            else:
                st.caption("Sin estudios registrados. Agrega sólo encuestas con fuente y ficha técnica identificable.")
        st.caption("El modelo ponderado de candidatura se consulta y actualiza en la primera pestaña: **Modelo de viabilidad**.")

    with coverage_tab:
        structural, scenarios = st.columns(2)
        with structural:
            st.markdown("#### Estructura territorial")
            structure_rows = query(
                """SELECT COALESCE(municipality, district, electoral_section, locality, state) AS territorio,
                          coverage_status AS estatus, responsible AS responsable, evidence_note AS evidencia
                   FROM viability_structure_records WHERE profile_id = ? ORDER BY state, municipality""",
                (profile_id,),
            )
            if structure_rows:
                st.dataframe(pd.DataFrame(structure_rows), use_container_width=True, hide_index=True)
            else:
                st.caption("Aún no hay estructura territorial registrada.")
        with scenarios:
            st.markdown("#### Escenarios y recursos")
            coalition_rows = query(
                """SELECT scenario_name AS escenario, parties AS fuerzas, scope AS alcance, status AS estatus
                   FROM viability_coalition_scenarios WHERE profile_id = ? ORDER BY updated_at DESC""",
                (profile_id,),
            )
            if coalition_rows:
                st.dataframe(pd.DataFrame(coalition_rows), use_container_width=True, hide_index=True)
            else:
                st.caption("Aún no hay escenarios o coaliciones documentados.")
        coverage = pd.DataFrame([
            ("Dictamen de viabilidad", "Disponible" if document_count else "Pendiente", f"{document_count:,} documentos cargados"),
            ("Modelo de variables", "Disponible" if assessment_count else "Pendiente", f"{assessment_count:,} variables documentadas"),
            ("Competidores y encuestas", "Disponible" if (competitor_count or survey_count) else "Pendiente", f"{competitor_count:,} competidores · {survey_count:,} estudios"),
            ("Resultados municipales oficiales", "Pendiente" if not data_status["municipal"] else "Cargado", f"{data_status['municipal']:,} registros"),
            ("Resultados por distrito", "Pendiente" if not data_status["district"] else "Cargado", f"{data_status['district']:,} registros"),
            ("Resultados por sección", "Pendiente" if not data_status["section"] else "Cargado", f"{data_status['section']:,} registros"),
            ("Indicadores INEGI municipales", "Pendiente" if not data_status["indicators"] else "Cargado", f"{data_status['indicators']:,} indicadores"),
            ("Escucha digital y medios del perfil", "Pendiente" if not evidence_count else "Cargado", f"{evidence_count:,} publicaciones; se revisan en el tablero de evidencia"),
            ("Encuesta propia con ficha técnica", "Pendiente", "Necesaria para actualizar preferencia, conocimiento e imagen"),
            ("Estructura, actividades y seguimiento de campo", "Pendiente", "Se captura en CRM territorial y Seguimiento de campo"),
        ], columns=["Componente", "Estatus", "Cobertura actual"])
        st.dataframe(coverage, use_container_width=True, hide_index=True)
        st.warning(
            f"El tablero no reemplaza los datos faltantes. Para **{selected_state}**, la cobertura mostrada arriba indica "
            "qué fuentes ya sustentan el análisis y cuáles deben incorporarse antes de tomar decisiones operativas."
        )

    with model_tab:
        st.markdown("#### Modelo de viabilidad electoral")
        if profile_id == 4:
            st.info(
                "**Dos lecturas complementarias.** El dictamen base de Marco Bonilla usa 15 variables y reporta "
                "**78/100** con corte al 15 de septiembre de 2026. Este tablero usa el modelo Go2Win ampliado "
                "a 20 variables; incorpora intención de voto, base histórica, rival, indecisos y voto útil. "
                "Por ello su índice se muestra como **preliminar** y no sustituye el 78/100 del dictamen."
            )
        elif profile_name.startswith("Cecilia Anunciación Patrón"):
            st.info(
                "**Modelo base del dictamen de Mérida.** Sus 8 variables y el índice de **84/100** corresponden "
                "al corte del 25 de septiembre de 2026. No son una predicción: deberán actualizarse con tracking "
                "comparable, evidencia de servicios y operación territorial por zona."
            )
        else:
            st.caption(
                "Es el tablero principal del dictamen: pondera posición competitiva, candidatura, estructura, territorio y riesgos. "
                "No reemplaza encuestas ni predice una elección; ordena la evidencia para tomar decisiones."
            )
        score_rows = []
        for code, label, weight, cholula_score, cholula_note in viability_score_model:
            stored = score_by_code.get(code, {})
            evidence = electoral_evidence_by_code.get(code, {})
            score = stored.get("score")
            if score is None and is_cholula_case:
                score = cholula_score
            score_rows.append({
                "Variable": label,
                "Peso": f"{weight}%",
                "Puntaje": "—" if score is None else f"{float(score):.0f}/100",
                "Aporte ponderado": "—" if score is None else round(float(score) * weight / 100, 1),
                "Estatus": evidence.get("status", "Pendiente"),
                "Fuente y corte": " · ".join(filter(None, [evidence.get("source_label"), evidence.get("reference_date")])) or "Por documentar",
                "Lectura": stored.get("notes") or evidence.get("evidence_note") or (cholula_note if is_cholula_case else "Pendiente de evaluación"),
                "_score": score,
                "_code": code,
            })
        scored = [row for row in score_rows if row["_score"] is not None]
        global_score = sum(float(row["_score"]) * next(weight for code, _, weight, _, _ in viability_score_model if code == row["_code"]) / 100 for row in scored)
        score_col, completion_col, note_col = st.columns(3)
        scoring_stage = (
            "Modelo Go2Win ampliado · preliminar"
            if profile_id == 4
            else ("Modelo base del dictamen" if profile_name.startswith("Cecilia Anunciación Patrón")
                  else ("Precalibración" if profile_id == 2 and len(scored) == 20 else ("Provisional" if len(scored) < 20 else "Modelo completo")))
        )
        score_col.metric("Índice ponderado", f"{global_score:.1f}/100", scoring_stage)
        completion_col.metric("Variables calificadas", f"{len(scored)}/20", f"{round(len(scored) / 20 * 100)}%")
        note_col.metric("Peso evaluado", f"{sum(next(weight for code, _, weight, _, _ in viability_score_model if code == row['_code']) for row in scored)}%")
        st.dataframe(
            pd.DataFrame(score_rows).drop(columns=["_score", "_code"]),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Peso": st.column_config.TextColumn("Peso", width="small"),
                "Puntaje": st.column_config.TextColumn("Puntaje", width="small"),
                "Estatus": st.column_config.TextColumn("Estatus", width="small"),
            },
        )
        st.caption("Los pesos suman 100%. Los puntajes deben asignarse con evidencia verificable y con fecha de corte.")
        if profile_id == 2 and len(scored) == 20:
            st.warning(
                "Precalificación inicial basada en el dictamen de Colosio–Sonora con corte en septiembre de 2026. "
                "Es una línea base analítica, no una encuesta, pronóstico ni medición actualizada."
            )

        with st.expander("Registrar o actualizar puntaje de una variable"):
            variable_options = {label: code for code, label, _, _, _ in viability_score_model}
            with st.form(f"electoral_score_form_{profile_id}"):
                selected_label = st.selectbox("Variable", list(variable_options))
                selected_code = variable_options[selected_label]
                current = score_by_code.get(selected_code, {})
                score_value = st.number_input("Puntaje (0 a 100)", min_value=0.0, max_value=100.0, value=float(current.get("score") or 0.0), step=1.0)
                score_notes = st.text_area("Lectura y fuente de respaldo", value=current.get("notes") or "")
                if st.form_submit_button("Guardar puntaje"):
                    execute(
                        """INSERT INTO viability_electoral_scores (profile_id, variable_code, score, notes, updated_at)
                           VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                           ON CONFLICT(profile_id, variable_code) DO UPDATE SET
                               score = excluded.score, notes = excluded.notes, updated_at = CURRENT_TIMESTAMP""",
                        (profile_id, selected_code, score_value, score_notes.strip() or None),
                    )
                    st.success("Puntaje actualizado.")
                    st.rerun()

        with st.expander("Evidencia, fuente y fecha de corte"):
            evidence_rows = []
            for code, label, _, _, _ in viability_score_model:
                linked = electoral_evidence_by_code.get(code, {})
                evidence_rows.append({
                    "Variable": label,
                    "Estatus": linked.get("status", "Pendiente"),
                    "Evidencia": linked.get("evidence_note") or "Sin evidencia registrada.",
                    "Fuente": linked.get("source_label") or "—",
                    "Corte": linked.get("reference_date") or "—",
                    "Liga": linked.get("source_url"),
                })
            st.dataframe(
                pd.DataFrame(evidence_rows),
                use_container_width=True,
                hide_index=True,
                column_config={"Liga": st.column_config.LinkColumn("Fuente", display_text="Abrir")},
            )
            variable_options = {label: code for code, label, _, _, _ in viability_score_model}
            with st.form(f"electoral_evidence_form_{profile_id}"):
                evidence_variable = st.selectbox("Variable a documentar", list(variable_options), key=f"evidence_variable_{profile_id}")
                evidence_code = variable_options[evidence_variable]
                current_evidence = electoral_evidence_by_code.get(evidence_code, {})
                evidence_status = st.selectbox(
                    "Estatus de evidencia",
                    ["Pendiente", "En revisión", "Documentada", "Validada", "No aplica"],
                    index=["Pendiente", "En revisión", "Documentada", "Validada", "No aplica"].index(current_evidence.get("status", "Pendiente")),
                )
                evidence_note = st.text_area("Evidencia o lectura", value=current_evidence.get("evidence_note") or "")
                evidence_source = st.text_input("Nombre de la fuente", value=current_evidence.get("source_label") or "")
                evidence_url = st.text_input("Liga de la fuente", value=current_evidence.get("source_url") or "")
                evidence_date = st.text_input("Fecha de corte", value=current_evidence.get("reference_date") or "")
                if st.form_submit_button("Guardar evidencia"):
                    execute(
                        """INSERT INTO viability_electoral_evidence
                           (profile_id, variable_code, status, evidence_note, source_label, source_url, reference_date, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                           ON CONFLICT(profile_id, variable_code) DO UPDATE SET
                               status=excluded.status, evidence_note=excluded.evidence_note,
                               source_label=excluded.source_label, source_url=excluded.source_url,
                               reference_date=excluded.reference_date, updated_at=CURRENT_TIMESTAMP""",
                        (profile_id, evidence_code, evidence_status, evidence_note.strip() or None, evidence_source.strip() or None, evidence_url.strip() or None, evidence_date.strip() or None),
                    )
                    st.success("Evidencia actualizada.")
                    st.rerun()

    with route_tab:
        st.markdown("#### Orden recomendado de incorporación")
        st.markdown(
            f"1. **Perfil territorial:** asignar el estado y municipios de cobertura de {profile_name}.\n"
            "2. **Territorio y fuentes:** cargar cartografía municipal/seccional y resultados oficiales comparables.\n"
            "3. **Perfil territorial:** descargar indicadores INEGI municipales.\n"
            "4. **Fuentes y actualización:** configurar medios, RSS y cuentas públicas autorizadas.\n"
            "5. **Escenarios electorales:** documentar supuestos y generar metas agregadas.\n"
            "6. **Estrategia, planes y CRM:** convertir hallazgos en tareas, responsables y evidencia de campo."
        )
        st.success("Cuando se carguen esas fuentes, el tablero mostrará evidencia actualizada para el perfil y territorio seleccionados.")


def electoral_market_summary(
    state: str, election_year: int, election_type: str
) -> dict[str, object] | None:
    """Aggregate one loaded historical election for the market comparison."""
    section_rows = query(
        """SELECT payload FROM territorial_section_results
           WHERE state = ? AND election_year = ? AND election_type = ?""",
        (state, election_year, election_type),
    )
    municipal_rows = query(
        """SELECT payload FROM territorial_election_results
           WHERE state = ? AND election_year = ? AND election_type = ?""",
        (state, election_year, election_type),
    )
    records = []
    for row in section_rows or municipal_rows:
        try:
            records.append(json.loads(row["payload"]))
        except (TypeError, json.JSONDecodeError):
            continue
    if not records:
        return None
    frame = pd.DataFrame(records)
    numeric_columns = [
        column for column in frame.columns
        if column.startswith("votes_") or column in {"lista_nominal", "votes_total", "numero_votos_validos"}
    ]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
    valid_votes = int(frame.get("numero_votos_validos", pd.Series(dtype=float)).sum())
    total_votes = int(frame.get("votes_total", pd.Series(dtype=float)).sum())
    nominal = int(frame.get("lista_nominal", pd.Series(dtype=float)).sum())
    options = {
        ELECTORAL_VOTE_LABELS.get(column, column.replace("votes_", "").replace("_", " ").upper()): int(frame[column].sum())
        for column in frame.columns
        if column.startswith("votes_")
        and column not in {"votes_total", "votes_nulos", "votes_no_reg"}
        and frame[column].sum() > 0
    }
    return {
        "year": election_year,
        "nominal": nominal,
        "total_votes": total_votes,
        "valid_votes": valid_votes,
        "participation": total_votes / nominal * 100 if nominal else 0.0,
        "options": options,
    }


def render_electoral_market() -> None:
    """Explain the aggregate electoral universe before defining a scenario or goal."""
    st.subheader("Mercado electoral")
    st.caption(
        "Lectura agregada del universo electoral histórico: lista nominal, participación, votos válidos "
        "y votación por opción política. Es una línea base para construir escenarios; no es una encuesta ni un pronóstico."
    )
    options = profile_options()
    if not options:
        st.info("Primero registra un perfil y asígnale un estado.")
        return
    selected_profile = st.selectbox("Perfil", list(options), key="market_profile")
    profile_id = options[selected_profile]
    states = profile_states(profile_id)
    if not states:
        st.info("Asigna un estado al perfil antes de consultar el mercado electoral.")
        return
    state = st.selectbox("Estado", states, key="market_state")
    section_elections = query(
        """SELECT DISTINCT election_year, election_type FROM territorial_section_results
           WHERE state = ? ORDER BY election_year DESC, election_type""",
        (state,),
    )
    municipal_elections = query(
        """SELECT DISTINCT election_year, election_type FROM territorial_election_results
           WHERE state = ? ORDER BY election_year DESC, election_type""",
        (state,),
    )
    available_elections = {
        (int(row["election_year"]), str(row["election_type"]))
        for row in section_elections + municipal_elections
    }
    available_years = sorted({year for year, _ in available_elections}, reverse=True)
    if not available_years:
        st.info("Aún no hay resultados electorales cargados para este estado. Incorpóralos desde Territorio y fuentes.")
        return
    election_year = st.selectbox("Elección histórica de referencia", available_years, key=f"market_year_{state}")
    election_types = sorted(
        election_type for year, election_type in available_elections if year == election_year
    )
    election_type = st.selectbox(
        "Tipo de elección",
        election_types,
        key=f"market_election_type_{state}_{election_year}",
        help="Selecciona el mismo tipo de elección al comparar resultados. Las diputaciones, ayuntamientos y gubernatura no se deben mezclar.",
    )
    section_rows = query(
        """SELECT payload FROM territorial_section_results
           WHERE state = ? AND election_year = ? AND election_type = ?""",
        (state, election_year, election_type),
    )
    municipal_rows = query(
        """SELECT payload FROM territorial_election_results
           WHERE state = ? AND election_year = ? AND election_type = ?""",
        (state, election_year, election_type),
    )
    raw_rows = section_rows or municipal_rows
    records = []
    for row in raw_rows:
        try:
            payload = json.loads(row["payload"])
        except (TypeError, json.JSONDecodeError):
            continue
        records.append(payload)
    if not records:
        st.warning("Los resultados cargados no contienen datos que se puedan interpretar.")
        return
    market = pd.DataFrame(records)
    numeric_columns = [
        column for column in market.columns
        if column.startswith("votes_") or column in {"lista_nominal", "votes_total", "numero_votos_validos", "participacion_pct"}
    ]
    for column in numeric_columns:
        market[column] = pd.to_numeric(market[column], errors="coerce").fillna(0)
    valid_votes = int(market.get("numero_votos_validos", pd.Series(dtype=float)).sum())
    total_votes = int(market.get("votes_total", pd.Series(dtype=float)).sum())
    nominal = int(market.get("lista_nominal", pd.Series(dtype=float)).sum())
    participation = total_votes / nominal * 100 if nominal else 0
    option_keys = sorted(
        column for column in market.columns
        if column.startswith("votes_") and column not in {"votes_total", "votes_nulos", "votes_no_reg"}
        and market[column].sum() > 0
    )
    if not option_keys:
        st.warning("Esta carga no incluye votación por partido, coalición o candidatura.")
        return
    consolidated_distribution, official_distribution = consolidated_electoral_blocks(
        market, option_keys, state, election_year, election_type
    )
    consolidated_distribution["Porcentaje"] = (
        consolidated_distribution["Votos"] / valid_votes * 100 if valid_votes else 0.0
    )
    selected_option_label = st.selectbox(
        "Bloque o partido de referencia",
        list(consolidated_distribution["Opción"]),
        key=f"market_block_{state}_{election_year}_{election_type}",
        help="Esta lectura suma las marcas de boleta que pertenecen a una misma candidatura o alianza; los partidos sin alianza se muestran solos.",
    )
    reference_votes = int(consolidated_distribution.loc[
        consolidated_distribution["Opción"] == selected_option_label, "Votos"
    ].iloc[0])
    reference_share = reference_votes / valid_votes * 100 if valid_votes else 0

    cards = st.columns(5)
    cards[0].metric("Lista nominal", f"{nominal:,}")
    cards[1].metric("Participación histórica", f"{participation:.1f}%")
    cards[2].metric("Votos válidos", f"{valid_votes:,}")
    cards[3].metric(f"Votos {selected_option_label}", f"{reference_votes:,}")
    cards[4].metric(f"Participación {selected_option_label}", f"{reference_share:.1f}%")
    st.markdown("### Cómo se usa esta lectura")
    st.markdown(
        "1. **Mercado electoral:** dimensiona el universo y la votación histórica disponible.  \n"
        "2. **Escenario electoral:** documenta la hipótesis de participación, competencia y meta porcentual.  \n"
        "3. **Metas territoriales:** distribuye esa hipótesis a distrito, municipio y sección.  \n"
        "4. **Mapa de oportunidad:** permite visualizar la brecha, la meta y la cobertura operativa."
    )
    scenario_rows = query(
        """SELECT name, target_percentage, participation_assumption, competition_context, coalition_context, active
           FROM electoral_scenarios
           WHERE profile_id = ? AND state = ? AND election_year = ?
           ORDER BY active DESC, target_percentage""",
        (profile_id, state, election_year),
    )
    active = next((row for row in scenario_rows if row["active"]), None)
    # Se usan contenedores consecutivos: primero el escenario y, debajo, la
    # distribución completa del mercado para aprovechar todo el ancho.
    left = st.container()
    right = st.container()
    with left:
        st.markdown("### Escenario conectado")
        if active:
            target_votes = round(valid_votes * float(active["target_percentage"]) / 100)
            gap = max(target_votes - reference_votes, 0)
            st.success(
                f"**{active['name']}** está activo: meta de **{active['target_percentage']:.1f}%** "
                f"({target_votes:,} votos de referencia). Brecha frente a {selected_option_label}: **{gap:,} votos**."
            )
            st.caption(
                f"Competencia: {active['competition_context'] or 'Por documentar'} · "
                f"Alianzas: {active['coalition_context'] or 'Por documentar'}"
            )
        else:
            st.info("No hay un escenario activo. El siguiente paso es registrarlo y validarlo en Escenarios electorales.")
    with right:
        st.markdown(f"### Fuerza electoral consolidada · {election_year}")
        st.caption(
            "El gráfico agrupa las marcas de boleta de una misma candidatura o alianza. "
            "No compara un partido aislado contra su propia coalición."
        )
        distribution = consolidated_distribution
        # Un pastel con todas las candidaturas menores sería ilegible. Conserva
        # las ocho fuerzas principales y agrupa el resto sin perder su peso.
        pie_distribution = distribution.head(8).copy()
        remaining_votes = int(distribution.iloc[8:]["Votos"].sum())
        if remaining_votes:
            pie_distribution = pd.concat([
                pie_distribution,
                pd.DataFrame([{
                    "Opción": "Otras opciones",
                    "Votos": remaining_votes,
                    "Porcentaje": remaining_votes / valid_votes * 100 if valid_votes else 0.0,
                }]),
            ], ignore_index=True)
        # Se renderiza como SVG/CSS en lugar del componente Vega. Así cada
        # cambio de elección reconstruye también la geometría del pastel y no
        # sólo su título o leyenda.
        pie_colors = ["#0f766e", "#2563eb", "#ea580c", "#7c3aed", "#dc2626", "#0891b2", "#ca8a04", "#be123c", "#64748b"]
        pie_total = int(pie_distribution["Votos"].sum())
        start_pct = 0.0
        slice_paths, legend_items = [], []
        center, radius = 250, 225
        for position, item in pie_distribution.reset_index(drop=True).iterrows():
            color = pie_colors[position % len(pie_colors)]
            share = float(item["Votos"]) / pie_total * 100 if pie_total else 0.0
            end_pct = start_pct + share
            start_angle = -90 + (start_pct * 3.6)
            end_angle = -90 + (end_pct * 3.6)
            start_x = center + radius * math.cos(math.radians(start_angle))
            start_y = center + radius * math.sin(math.radians(start_angle))
            end_x = center + radius * math.cos(math.radians(end_angle))
            end_y = center + radius * math.sin(math.radians(end_angle))
            large_arc = 1 if share > 50 else 0
            path = (
                f"M {center} {center} L {start_x:.2f} {start_y:.2f} "
                f"A {radius} {radius} 0 {large_arc} 1 {end_x:.2f} {end_y:.2f} Z"
            )
            tooltip = f"{item['Opción']}: {int(item['Votos']):,} votos ({share:.1f}% de votos válidos)"
            slice_paths.append(
                f"<path class='market-pie-slice' fill='{color}' d='{path}'><title>{escape(tooltip)}</title></path>"
            )
            legend_items.append(
                "<div class='market-pie-legend-item'>"
                f"<span style='background:{color}'></span>"
                f"<b>{escape(str(item['Opción']))}</b><br>"
                f"{int(item['Votos']):,} votos · {share:.1f}%"
                "</div>"
            )
            start_pct = end_pct
        st.markdown(
            "<div class='market-pie-wrap'>"
            "<div class='market-pie'>"
            "<svg viewBox='0 0 500 500' role='img' aria-label='Distribución de votos válidos; pasa el cursor por un segmento para ver su detalle'>"
            f"{''.join(slice_paths)}"
            "<circle class='market-pie-center' cx='250' cy='250' r='95'></circle>"
            "<text class='market-pie-center-label' x='250' y='244'>Votos</text>"
            "<text class='market-pie-center-detail' x='250' y='267'>válidos</text>"
            "</svg></div>"
            f"<div class='market-pie-legend'>{''.join(legend_items)}</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.caption(
            f"Distribución consolidada de votos válidos de la elección histórica {election_year}. "
            "Las ocho fuerzas con mayor votación se muestran por separado; las demás se agrupan como Otras opciones."
        )
        with st.expander("Ver detalle oficial de marcas en boleta"):
            official_distribution["Porcentaje de votos válidos"] = (
                official_distribution["Votos"] / valid_votes * 100 if valid_votes else 0.0
            )
            st.caption(
                "Este desglose reproduce las opciones publicadas por la autoridad. Úsalo para auditoría; "
                "la gráfica principal es la lectura recomendable para comparar fuerzas electorales."
            )
            st.dataframe(
                official_distribution.drop(columns="clave"),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Votos": st.column_config.NumberColumn(format="%,d"),
                    "Porcentaje de votos válidos": st.column_config.NumberColumn(format="%.1f%%"),
                },
            )
    st.caption(
        f"Fuente: resultados de **{election_type} {election_year}** cargados en la plataforma. "
        "El detalle de boleta conserva las columnas oficiales; la gráfica principal consolida alianzas identificables."
    )
    comparison_elections = sorted(
        (year, result_type)
        for year, result_type in available_elections
        if (year, result_type) != (election_year, election_type)
    )
    if comparison_elections:
        st.divider()
        st.markdown("### Análisis entre elecciones")
        st.caption(
            "Compara la elección activa con otra elección histórica ya cargada para este perfil y estado. "
            "Es una lectura de resultados agregados; no convierte automáticamente coaliciones de un proceso a otro."
        )
        base_year, base_election_type = st.selectbox(
            "Elección base para comparar",
            comparison_elections,
            format_func=lambda item: f"{item[0]} · {item[1]}",
            key=f"market_comparison_election_{state}_{election_year}_{election_type}",
        )
        current_summary = electoral_market_summary(state, election_year, election_type)
        base_summary = electoral_market_summary(state, base_year, base_election_type)
        if current_summary and base_summary:
            participation_delta = float(current_summary["participation"]) - float(base_summary["participation"])
            valid_delta = int(current_summary["valid_votes"]) - int(base_summary["valid_votes"])
            nominal_delta = int(current_summary["nominal"]) - int(base_summary["nominal"])
            comparison_cards = st.columns(4)
            comparison_cards[0].metric(
                "Participación", f"{current_summary['participation']:.1f}%", f"{participation_delta:+.1f} pp"
            )
            comparison_cards[1].metric(
                "Votos válidos", f"{int(current_summary['valid_votes']):,}", f"{valid_delta:+,}"
            )
            comparison_cards[2].metric(
                "Lista nominal", f"{int(current_summary['nominal']):,}", f"{nominal_delta:+,}"
            )
            current_options = current_summary["options"]
            base_options = base_summary["options"]
            current_leader, current_leader_votes = max(current_options.items(), key=lambda item: item[1])
            base_leader, base_leader_votes = max(base_options.items(), key=lambda item: item[1])
            current_leader_share = current_leader_votes / int(current_summary["valid_votes"]) * 100 if current_summary["valid_votes"] else 0
            base_leader_share = base_leader_votes / int(base_summary["valid_votes"]) * 100 if base_summary["valid_votes"] else 0
            comparison_cards[3].metric(
                f"Primera fuerza {election_year}",
                f"{current_leader_share:.1f}%",
                current_leader,
            )

            st.markdown("#### Lectura automática")
            participation_direction = "aumentó" if participation_delta >= 0 else "disminuyó"
            vote_direction = "más" if valid_delta >= 0 else "menos"
            st.write(
                f"Entre **{base_election_type} {base_year}** y **{election_type} {election_year}**, la participación {participation_direction} "
                f"**{abs(participation_delta):.1f} puntos porcentuales**. Hubo **{abs(valid_delta):,} votos válidos {vote_direction}**. "
                f"La primera opción registrada pasó de **{base_leader}** ({base_leader_share:.1f}%) "
                f"a **{current_leader}** ({current_leader_share:.1f}%)."
            )

            comparable_labels = sorted(set(current_options) | set(base_options))
            option_comparison = pd.DataFrame([
                {
                    "Opción registrada": label,
                    f"Votos {base_year}": int(base_options.get(label, 0)),
                    f"Votos {election_year}": int(current_options.get(label, 0)),
                    "Variación de votos": int(current_options.get(label, 0)) - int(base_options.get(label, 0)),
                }
                for label in comparable_labels
            ])
            option_comparison["Participación " + str(base_year)] = (
                option_comparison[f"Votos {base_year}"] / int(base_summary["valid_votes"]) * 100
                if base_summary["valid_votes"] else 0.0
            )
            option_comparison["Participación " + str(election_year)] = (
                option_comparison[f"Votos {election_year}"] / int(current_summary["valid_votes"]) * 100
                if current_summary["valid_votes"] else 0.0
            )
            option_comparison = option_comparison.sort_values(
                f"Votos {election_year}", ascending=False
            ).reset_index(drop=True)
            st.dataframe(
                option_comparison,
                use_container_width=True,
                hide_index=True,
                column_config={
                    f"Votos {base_year}": st.column_config.NumberColumn(format="%,d"),
                    f"Votos {election_year}": st.column_config.NumberColumn(format="%,d"),
                    "Variación de votos": st.column_config.NumberColumn(format="%+d"),
                    "Participación " + str(base_year): st.column_config.NumberColumn(format="%.1f%%"),
                    "Participación " + str(election_year): st.column_config.NumberColumn(format="%.1f%%"),
                },
            )
            st.info(
                "Precaución de interpretación: una coalición, candidatura común o partido puede cambiar de nombre, "
                "integración o columna entre elecciones. Compara directamente las filas equivalentes sólo cuando la "
                "autoridad electoral las haya publicado de manera comparable."
            )
            if base_election_type != election_type:
                st.warning(
                    "Los dos procesos son de tipo distinto. La comparación sirve para dimensionar el mercado, "
                    "pero no para concluir un cambio directo de preferencia entre diputaciones, ayuntamientos o gubernatura."
                )


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
    available_elections = query(
        """
        SELECT election_type, election_year, COUNT(*) AS municipios
        FROM territorial_election_results
        WHERE state = ? AND municipality IS NOT NULL AND TRIM(municipality) <> ''
        GROUP BY election_type, election_year
        ORDER BY
            CASE WHEN election_type = 'Ayuntamientos' AND election_year = 2024 THEN 0 ELSE 1 END,
            election_year DESC, election_type
        """,
        (selected_state,),
    )
    if not available_elections:
        st.info(
            "No hay resultados municipales cargados para este estado. "
            "Cárgalos desde Territorio y fuentes antes de usar la priorización."
        )
        return
    election_options = {
        f"{row['election_type']} · {int(row['election_year'])} ({int(row['municipios'])} municipios)": row
        for row in available_elections
    }
    selected_election_label = st.selectbox(
        "Elección de referencia",
        list(election_options),
        help="La priorización usa esta elección como línea base histórica. Puedes cambiarla cuando haya más procesos cargados.",
        key=f"priority_election_{selected_state}",
    )
    selected_election = election_options[selected_election_label]
    election_type = selected_election["election_type"]
    election_year = int(selected_election["election_year"])
    election_label = f"{election_type} {election_year}"
    election_rows = query(
        """
        SELECT municipality, payload, election_year, source
        FROM territorial_election_results
        WHERE state = ? AND election_type = ? AND election_year = ?
        ORDER BY municipality
        """,
        (selected_state, election_type, election_year),
    )
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
        "Partido o coalición de referencia", list(party_options),
        key=f"priority_party_{selected_state}_{election_type}_{election_year}"
    )
    party_key = party_options[selected_party]
    priority_models = {
        "Equilibrado": {
            "weights": (45, 30, 25),
            "third": "fuerza histórica de la opción de referencia",
            "description": "Combina tamaño electoral, potencial de participación y antecedente de votación.",
        },
        "Movilización": {
            "weights": (25, 60, 15),
            "third": "fuerza histórica de la opción de referencia",
            "description": "Da más peso a municipios con brecha de participación para orientar esfuerzos de movilización.",
        },
        "Defensa del voto": {
            "weights": (20, 15, 65),
            "third": "fuerza histórica de la opción de referencia",
            "description": "Da más peso a los municipios donde la opción elegida ya cuenta con mayor respaldo histórico.",
        },
        "Competencia cerrada": {
            "weights": (35, 20, 45),
            "third": "competitividad histórica entre las dos principales opciones",
            "description": "Da prioridad a municipios con mayor tamaño y menor diferencia entre las dos fuerzas más votadas.",
        },
    }
    selected_model = st.selectbox(
        "Enfoque de priorización",
        list(priority_models),
        help="Cambia los pesos del índice para comparar distintas decisiones territoriales usando la misma elección base.",
        key=f"priority_model_{selected_state}_{election_type}_{election_year}",
    )
    priority_model = priority_models[selected_model]
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
    vote_matrix = results[vote_keys].apply(pd.to_numeric, errors="coerce").fillna(0)
    if len(vote_keys) >= 2:
        top_two = pd.DataFrame(
            np.sort(vote_matrix.to_numpy(), axis=1)[:, -2:],
            index=results.index,
            columns=["segundo", "primero"],
        )
        results["margen_competencia"] = (
            (top_two["primero"] - top_two["segundo"])
            / results["numero_votos_validos"].replace(0, pd.NA) * 100
        ).fillna(100)
    else:
        results["margen_competencia"] = 100.0
    total_nominal = results["lista_nominal"].sum()
    total_votes = results["votes_total"].sum()
    state_participation = total_votes / total_nominal * 100 if total_nominal else 0
    results["peso_electoral_pct"] = results["lista_nominal"] / total_nominal * 100 if total_nominal else 0
    results["brecha_participacion"] = (state_participation - results["participacion_pct"]).clip(lower=0)
    max_nominal = results["lista_nominal"].max() or 1
    max_gap = results["brecha_participacion"].max() or 1
    max_party_share = results["porcentaje_opcion"].max() or 1
    max_margin = results["margen_competencia"].max() or 1
    results["competitividad"] = (1 - results["margen_competencia"] / max_margin).clip(lower=0, upper=1)
    weight_nominal, weight_gap, weight_third = priority_model["weights"]
    third_factor = (
        results["competitividad"] if selected_model == "Competencia cerrada"
        else results["porcentaje_opcion"] / max_party_share
    )
    results["indice_prioridad"] = (
        results["lista_nominal"] / max_nominal * weight_nominal
        + results["brecha_participacion"] / max_gap * weight_gap
        + third_factor * weight_third
    ).round(1)
    results["prioridad"] = pd.cut(
        results["indice_prioridad"], bins=[-1, 39.9, 69.9, 100], labels=["Baja", "Media", "Alta"]
    ).astype(str)
    results = results.sort_values(["indice_prioridad", "lista_nominal"], ascending=False).reset_index(drop=True)
    results.index = results.index + 1
    results["orden"] = results.index

    st.markdown("### Criterio de priorización")
    st.caption(f"Elección base: **{election_label}** · {len(results)} municipios con información disponible.")
    st.write(
        f"Enfoque seleccionado: **{selected_model}**. {priority_model['description']} "
        f"El índice combina **{weight_nominal}% volumen de lista nominal**, "
        f"**{weight_gap}% brecha de participación respecto al promedio estatal** y "
        f"**{weight_third}% {priority_model['third']}**. Sirve para ordenar revisión y coordinación territorial; "
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

    municipality = st.selectbox(
        "Explicar la prioridad de un municipio", list(results["municipio"]),
        key=f"priority_municipality_{selected_state}_{election_type}_{election_year}"
    )
    detail = results.loc[results["municipio"] == municipality].iloc[0]
    st.info(
        f"**{municipality}** tiene prioridad **{detail['prioridad']}** (índice {detail['indice_prioridad']:.1f}/100): "
        f"lista nominal de {int(detail['lista_nominal']):,}, participación de {detail['participacion_pct']:.1f}% "
        f"frente a {state_participation:.1f}% estatal, y {selected_party} registra {int(detail[party_key]):,} votos "
        f"({detail['porcentaje_opcion']:.1f}% de los votos válidos)."
    )
    st.caption(
        f"Fuente: resultados municipales de {election_label} cargados en la plataforma. "
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
        key=f"priority_selection_{selected_state}_{election_type}_{election_year}_{selected_party}",
    )
    decision_status = st.selectbox(
        "Estatus de la decisión",
        ["Propuesta", "Validada por coordinación"],
        key=f"priority_status_{selected_state}_{election_type}_{election_year}_{selected_party}",
    )
    decision_note = st.text_area(
        "Nota de coordinación (opcional)",
        placeholder="Ejemplo: revisar presencia territorial y preparar un plan de trabajo municipal.",
        key=f"priority_note_{selected_state}_{election_type}_{election_year}_{selected_party}",
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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(profile_id, state, municipality, election_year, party_or_coalition) DO UPDATE SET
                    priority_level = excluded.priority_level,
                    priority_index = excluded.priority_index,
                    rationale = excluded.rationale,
                    status = excluded.status,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    profile_id, selected_state, municipality_name, election_year, selected_party,
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
        WHERE profile_id = ? AND state = ? AND election_year = ? AND party_or_coalition = ?
        ORDER BY priority_index DESC, municipality
        """,
        (profile_id, selected_state, election_year, selected_party),
    )
    if saved_priorities:
        st.markdown("#### Prioridades guardadas")
        st.dataframe(pd.DataFrame(saved_priorities), use_container_width=True, hide_index=True)


def render_electoral_scenarios() -> None:
    """Register the assumptions that authorize a territorial vote-goal model."""
    st.subheader("Escenarios electorales")
    st.caption(
        "Un escenario expresa una hipótesis de competencia, participación y meta porcentual. "
        "No es una encuesta ni un pronóstico; es el punto de partida documentado para las metas territoriales."
    )
    options = profile_options()
    if not options:
        st.info("Primero crea un perfil y asígnale un estado.")
        return
    selected_profile = st.selectbox("Perfil", list(options), key="scenario_profile")
    profile_id = options[selected_profile]
    states = profile_states(profile_id)
    if not states:
        st.info("Asigna un estado al perfil antes de crear escenarios.")
        return
    state = st.selectbox("Estado", states, key="scenario_state")
    years = query(
        """SELECT DISTINCT election_year FROM territorial_section_results
           WHERE state = ? ORDER BY election_year DESC""",
        (state,),
    )
    if not years:
        st.info("Carga primero resultados por sección desde Visor electoral.")
        return
    election_year = st.selectbox(
        "Elección histórica de referencia", [int(row["election_year"]) for row in years],
        key=f"scenario_year_{state}",
    )
    scenarios = query(
        """SELECT * FROM electoral_scenarios
           WHERE profile_id = ? AND state = ? AND election_year = ?
           ORDER BY active DESC, target_percentage, name""",
        (profile_id, state, election_year),
    )
    if not scenarios:
        st.info("Aún no hay escenarios. Puedes crear uno o cargar los tres escenarios iniciales sugeridos.")
    if st.button("Cargar escenarios iniciales sugeridos"):
        suggested = [
            ("Competir", 35.0, "Escenario de competencia abierta", "Sin coalición confirmada", "Meta inicial para competir con posibilidad de victoria."),
            ("Contienda cerrada", 38.0, "Tres bloques competitivos", "Por confirmar", "Escenario central para una contienda competida."),
            ("Margen robusto", 40.0, "Competencia fuerte o concentrada", "Por confirmar", "Meta con mayor margen frente a una contienda exigente."),
        ]
        for name, target, competition, coalition, rationale in suggested:
            execute(
                """INSERT INTO electoral_scenarios
                   (profile_id, state, election_year, name, target_percentage, competition_context,
                    coalition_context, rationale, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Borrador')
                   ON CONFLICT(profile_id, state, election_year, name) DO NOTHING""",
                (profile_id, state, election_year, name, target, competition, coalition, rationale),
            )
        st.success("Se cargaron los escenarios sugeridos. Revísalos y activa el que deseas usar.")
        st.rerun()
    with st.expander("Crear o ajustar un escenario", expanded=not scenarios):
        with st.form(f"scenario_form_{profile_id}_{state}_{election_year}", clear_on_submit=True):
            name = st.text_input("Nombre del escenario", placeholder="Ejemplo: Contienda cerrada")
            cols = st.columns(2)
            target_percentage = cols[0].number_input("Meta porcentual", min_value=1.0, max_value=100.0, value=38.0, step=0.5)
            participation = cols[1].number_input("Participación esperada (opcional)", min_value=0.0, max_value=100.0, value=0.0, step=0.5)
            competition = st.text_input("Contexto de competencia", placeholder="Ejemplo: tres bloques competitivos")
            coalition = st.text_input("Supuesto de alianzas", placeholder="Ejemplo: sin coalición confirmada")
            rationale = st.text_area("Fundamento del escenario", placeholder="Explica por qué se usará esta hipótesis.")
            status = st.selectbox("Estatus", ["Borrador", "Validado por coordinación", "En uso"], index=0)
            if st.form_submit_button("Guardar escenario", type="primary"):
                if not name.strip() or not rationale.strip():
                    st.error("Escribe un nombre y el fundamento del escenario.")
                else:
                    execute(
                        """INSERT INTO electoral_scenarios
                           (profile_id, state, election_year, name, target_percentage, participation_assumption,
                            competition_context, coalition_context, rationale, status)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                           ON CONFLICT(profile_id, state, election_year, name) DO UPDATE SET
                             target_percentage = excluded.target_percentage,
                             participation_assumption = excluded.participation_assumption,
                             competition_context = excluded.competition_context,
                             coalition_context = excluded.coalition_context,
                             rationale = excluded.rationale, status = excluded.status,
                             updated_at = CURRENT_TIMESTAMP""",
                        (profile_id, state, election_year, name.strip(), float(target_percentage),
                         float(participation) if participation else None, competition.strip() or None,
                         coalition.strip() or None, rationale.strip(), status),
                    )
                    st.success("Escenario guardado.")
                    st.rerun()
    if scenarios:
        scenario_frame = pd.DataFrame(scenarios)[[
            "name", "target_percentage", "participation_assumption", "competition_context",
            "coalition_context", "status", "active", "rationale",
        ]].rename(columns={
            "name": "Escenario", "target_percentage": "Meta %", "participation_assumption": "Participación %",
            "competition_context": "Competencia", "coalition_context": "Alianzas", "status": "Estatus",
            "active": "Activo", "rationale": "Fundamento",
        })
        st.markdown("### Escenarios registrados")
        st.dataframe(scenario_frame, use_container_width=True, hide_index=True)
        selector = {f"{row['name']} · {row['target_percentage']:.1f}% · {row['status']}": row for row in scenarios}
        selected_label = st.selectbox("Escenario que se utilizará para metas territoriales", list(selector), key="scenario_active_choice")
        selected = selector[selected_label]
        if st.button("Activar escenario para metas territoriales", type="primary"):
            execute(
                """UPDATE electoral_scenarios SET active = 0, updated_at = CURRENT_TIMESTAMP
                   WHERE profile_id = ? AND state = ? AND election_year = ?""",
                (profile_id, state, election_year),
            )
            execute(
                """UPDATE electoral_scenarios SET active = 1, status = 'En uso', updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (int(selected["id"]),),
            )
            st.success(f"Escenario activo: {selected['name']}.")
            st.rerun()


def _section_target_frame(state: str, election_year: int, reference_option: str) -> pd.DataFrame:
    """Build a reproducible planning frame from aggregate, official section results."""
    rows = query(
        """
        SELECT district_code, section_code, municipality, payload
        FROM territorial_section_results
        WHERE state = ? AND election_year = ?
        ORDER BY district_code, section_code
        """,
        (state, election_year),
    )
    records = []
    for row in rows:
        try:
            payload = json.loads(row["payload"])
        except (TypeError, json.JSONDecodeError):
            continue
        valid_votes = pd.to_numeric(payload.get("numero_votos_validos", 0), errors="coerce")
        reference_votes = pd.to_numeric(payload.get(reference_option, 0), errors="coerce")
        nominal_list = pd.to_numeric(payload.get("lista_nominal", 0), errors="coerce")
        participation = pd.to_numeric(payload.get("participacion_pct", 0), errors="coerce")
        records.append({
            "Distrito": str(row["district_code"] or "").zfill(2),
            "Municipio": row["municipality"] or "Sin municipio",
            "Sección": str(row["section_code"] or "").zfill(4),
            "Votos válidos": int(valid_votes) if pd.notna(valid_votes) else 0,
            "Votos referencia": int(reference_votes) if pd.notna(reference_votes) else 0,
            "Lista nominal": int(nominal_list) if pd.notna(nominal_list) else 0,
            "Participación": float(participation) if pd.notna(participation) else 0.0,
        })
    return pd.DataFrame(records)


def _municipal_target_frame(state: str, election_year: int, reference_option: str) -> pd.DataFrame:
    """Use the official municipal aggregate when sections lack municipal assignment."""
    rows = query(
        """
        SELECT municipality, payload
        FROM territorial_election_results
        WHERE state = ? AND election_year = ? AND TRIM(COALESCE(municipality, '')) <> ''
        ORDER BY municipality
        """,
        (state, election_year),
    )
    records = []
    for row in rows:
        try:
            payload = json.loads(row["payload"])
        except (TypeError, json.JSONDecodeError):
            continue
        valid_votes = pd.to_numeric(payload.get("numero_votos_validos", 0), errors="coerce")
        reference_votes = pd.to_numeric(payload.get(reference_option, 0), errors="coerce")
        nominal_list = pd.to_numeric(payload.get("lista_nominal", 0), errors="coerce")
        participation = pd.to_numeric(payload.get("participacion_pct", 0), errors="coerce")
        records.append({
            "Municipio": str(row["municipality"]).strip(),
            "Votos válidos": int(valid_votes) if pd.notna(valid_votes) else 0,
            "Votos referencia": int(reference_votes) if pd.notna(reference_votes) else 0,
            "Lista nominal": int(nominal_list) if pd.notna(nominal_list) else 0,
            "Participación": float(participation) if pd.notna(participation) else 0.0,
        })
    return pd.DataFrame(records)


def _contextual_target_allocation(
    units: pd.DataFrame, total_target: int, max_growth_share: float = 0.10,
    minimum_floor: int = 25,
) -> pd.DataFrame:
    """Distribute a target with transparent territorial opportunity factors.

    The total target is fixed by the parent territory. Targets are
    not a uniform percentage: each receives a small minimum growth assignment,
    then the remaining gap is distributed by electoral size, recoverable
    participation, and historical competitiveness.
    """
    frame = units.copy()
    if frame.empty:
        return frame
    reference_total = int(frame["Votos referencia"].sum())
    statewide_gap = max(int(total_target) - reference_total, 0)
    if statewide_gap == 0:
        frame["Meta propuesta"] = frame["Votos referencia"].astype(int)
        frame["Brecha propuesta"] = 0
        return frame

    valid_total = float(frame["Votos válidos"].sum()) or 1.0
    state_participation = (
        float(frame["Votos válidos"].sum()) / float(frame["Lista nominal"].sum()) * 100
        if float(frame["Lista nominal"].sum()) else 0.0
    )
    current_share = frame["Votos referencia"] / frame["Votos válidos"].replace(0, pd.NA) * 100
    volume = frame["Votos válidos"] / valid_total
    participation_opportunity = (state_participation - frame["Participación"]).clip(lower=0)
    competitiveness = 1 - (current_share - (total_target / valid_total * 100)).abs() / 100

    def normalize(values: pd.Series) -> pd.Series:
        values = pd.to_numeric(values, errors="coerce").fillna(0.0)
        span = values.max() - values.min()
        return (values - values.min()) / span if span else pd.Series(1.0, index=values.index)

    # Each component is converted into a statewide share. This prevents a
    # small municipality from receiving an outsized allocation merely because
    # it ranks first on one isolated factor.
    def share(values: pd.Series) -> pd.Series:
        values = pd.to_numeric(values, errors="coerce").fillna(0.0).clip(lower=0)
        return values / float(values.sum() or 1.0)

    score = (
        share(volume) * 0.60
        + share(normalize(participation_opportunity)) * 0.25
        + share(normalize(competitiveness)) * 0.15
    )
    # Cada municipio participa en el plan. En la cascada hacia secciones no se
    # aplica este mínimo: de otro modo varios mínimos se sumarían y excederían
    # la meta municipal que deben repartir.
    minimum = (
        pd.concat([
            (frame["Votos referencia"] * 0.01).round(),
            pd.Series(minimum_floor, index=frame.index),
        ], axis=1).max(axis=1).astype(int)
        if minimum_floor > 0 else pd.Series(0, index=frame.index, dtype=int)
    )
    # At municipal level, no unit is asked to grow more than ten percentage
    # points of its valid vote universe above its historic base.
    # This prevents an apparently mathematical but operationally implausible
    # target in small municipalities.
    ceiling = pd.concat([
        frame["Votos referencia"] + pd.concat([
            (frame["Votos válidos"] * max_growth_share).round(), minimum,
        ], axis=1).max(axis=1),
        frame["Votos válidos"],
    ], axis=1).min(axis=1).astype(int)
    capacity = (ceiling - frame["Votos referencia"]).clip(lower=0).astype(int)
    allocation = pd.concat([minimum, capacity], axis=1).min(axis=1).astype(int)
    remaining = statewide_gap - int(allocation.sum())
    while remaining > 0:
        available = (capacity - allocation).clip(lower=0)
        eligible = available > 0
        if not eligible.any():
            break
        weighted = score.where(eligible, 0.0)
        proposed = (weighted / float(weighted.sum() or 1.0) * remaining).map(math.floor).astype(int)
        proposed = pd.concat([proposed, available], axis=1).min(axis=1).astype(int)
        if int(proposed.sum()) == 0:
            top = weighted.sort_values(ascending=False).index[0]
            proposed.loc[top] = 1
        allocation += proposed
        remaining = statewide_gap - int(allocation.sum())

    frame["Brecha propuesta"] = allocation
    frame["Meta propuesta"] = frame["Votos referencia"].astype(int) + frame["Brecha propuesta"].astype(int)
    frame["Peso de oportunidad"] = score
    return frame


def _cascade_section_targets(sections: pd.DataFrame, municipal_targets: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Allocate each municipal goal to linked sections; retain unmapped sections for control."""
    all_sections = sections.copy()
    all_sections["Meta propuesta"] = all_sections["Votos referencia"].astype(int)
    linked = all_sections[all_sections["Municipio"] != "Pendiente de vincular"].copy()
    target_by_municipality = municipal_targets.set_index("Municipio")["Meta propuesta"].to_dict()
    for municipality, target in target_by_municipality.items():
        indexes = linked.index[linked["Municipio"] == municipality]
        if len(indexes) == 0:
            continue
        # Sections inherit their municipality target. Their only hard ceiling
        # is the valid-vote universe, so the municipal total can be reconciled.
        allocated = _contextual_target_allocation(
            linked.loc[indexes], int(target), max_growth_share=1.0, minimum_floor=0,
        )
        linked.loc[indexes, "Meta propuesta"] = allocated["Meta propuesta"].astype(int)
    all_sections.loc[linked.index, "Meta propuesta"] = linked["Meta propuesta"].astype(int)
    return all_sections, linked


def _target_classification(reference_votes: int, valid_votes: int, target_pct: float) -> str:
    """Classify aggregate territorial units; it does not classify individual voters."""
    current_pct = (reference_votes / valid_votes * 100) if valid_votes else 0
    if current_pct >= target_pct * 0.75:
        return "Consolidación"
    if current_pct >= target_pct * 0.25:
        return "Crecimiento"
    return "Recuperación"


def _save_vote_targets(
    profile_id: int, state: str, election_year: int, reference_option: str,
    target_pct: float, sections: pd.DataFrame, scenario_id: int | None = None,
    municipalities: pd.DataFrame | None = None,
    district_sections: pd.DataFrame | None = None,
) -> int:
    """Store the same goal model at state, district, municipal, and section levels."""
    if sections.empty:
        return 0

    official_state_source = municipalities if municipalities is not None and not municipalities.empty else sections
    district_source = district_sections if district_sections is not None and not district_sections.empty else sections
    levels: list[tuple[str, pd.DataFrame, list[str]]] = [
        # State and municipal goals must reconcile with the official municipal
        # concentrate. Section files can have a smaller coverage universe.
        ("Estado", official_state_source.assign(**{"_state": state}), ["_state"]),
        ("Distrito", district_source, ["Distrito"]),
        ("Sección", sections, ["Distrito", "Municipio", "Sección"]),
    ]
    # The section file for some states has no municipality column.  In that case
    # the municipal official aggregate is the reliable source for this level.
    municipal_source = official_state_source
    levels.insert(2, ("Municipio", municipal_source, ["Municipio"]))
    execute(
        """DELETE FROM territorial_vote_targets
           WHERE profile_id = ? AND state = ? AND election_year = ?
             AND territorial_level IN ('Estado', 'Municipio') AND reference_option = ?""",
        (profile_id, state, election_year, reference_option),
    )
    # Las secciones sin municipio confirmado no deben conservar una meta
    # operativa anterior: se informan como pendientes hasta contar con la
    # clave territorial correcta, sin inventar una distribución.
    if district_sections is not None:
        execute(
            """DELETE FROM territorial_vote_targets
               WHERE profile_id = ? AND state = ? AND election_year = ?
                 AND territorial_level = 'Sección' AND reference_option = ?
                 AND municipality IN ('Sin municipio', 'Pendiente de vincular')""",
            (profile_id, state, election_year, reference_option),
        )
    saved = 0
    for level, source, group_columns in levels:
        value_columns = ["Votos válidos", "Votos referencia"]
        if "Meta propuesta" in source.columns:
            value_columns.append("Meta propuesta")
        grouped = source.groupby(group_columns, dropna=False, as_index=False)[value_columns].sum()
        for _, row in grouped.iterrows():
            district = str(row.get("Distrito", "") or "")
            municipality = str(row.get("Municipio", "") or "")
            section = str(row.get("Sección", "") or "")
            valid_votes = int(row["Votos válidos"])
            reference_votes = int(row["Votos referencia"])
            contextual_goal = "Meta propuesta" in grouped.columns
            target_votes = int(row["Meta propuesta"]) if contextual_goal else round(valid_votes * target_pct / 100)
            vote_gap = max(target_votes - reference_votes, 0)
            effective_target_pct = (target_votes / valid_votes * 100) if valid_votes else target_pct
            execute(
                """
                INSERT INTO territorial_vote_targets
                (profile_id, state, election_year, territorial_level, district, municipality,
                 electoral_section, scenario_id, reference_option, historical_valid_votes,
                 historical_reference_votes, target_percentage, target_votes, vote_gap, classification)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(profile_id, state, election_year, territorial_level, district, municipality,
                            electoral_section, reference_option) DO UPDATE SET
                    historical_valid_votes = excluded.historical_valid_votes,
                    historical_reference_votes = excluded.historical_reference_votes,
                    scenario_id = excluded.scenario_id,
                    target_percentage = excluded.target_percentage,
                    target_votes = excluded.target_votes,
                    vote_gap = excluded.vote_gap,
                    classification = excluded.classification,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    profile_id, state, election_year, level, district, municipality, section, scenario_id,
                    reference_option, valid_votes, reference_votes, effective_target_pct, target_votes,
                    vote_gap, _target_classification(reference_votes, valid_votes, effective_target_pct),
                ),
            )
            saved += 1
    return saved


def render_territorial_goals() -> None:
    """Configure an aggregate goal cascade and control the work needed to support it."""
    st.subheader("Metas y control territorial")
    st.caption(
        "Distribuye una meta estatal de referencia a distritos, municipios y secciones con resultados públicos. "
        "Sirve para planeación y seguimiento territorial; no predice ni determina el voto de personas."
    )
    options = profile_options()
    if not options:
        st.info("Primero crea un perfil y asígnale un estado.")
        return
    selected_profile = st.selectbox("Perfil", list(options), key="goal_profile")
    profile_id = options[selected_profile]
    states = profile_states(profile_id)
    if not states:
        st.info("Asigna un estado al perfil antes de configurar metas.")
        return
    # Scope the selector to the profile so a previous profile's state cannot
    # remain selected after the analyst changes candidate.
    state = st.selectbox("Estado", states, key=f"goal_state_{profile_id}")
    years = query(
        """SELECT DISTINCT election_year FROM territorial_section_results
           WHERE state = ? ORDER BY election_year DESC""",
        (state,),
    )
    if not years:
        st.info("Aún no hay resultados por sección para este estado. Cárgalos desde Visor electoral.")
        return
    year_options = [int(row["election_year"]) for row in years]
    election_year = st.selectbox("Elección de referencia", year_options, key=f"goal_year_{profile_id}_{state}")
    sample = query(
        """SELECT payload FROM territorial_section_results
           WHERE state = ? AND election_year = ? LIMIT 1""",
        (state, election_year),
    )
    try:
        sample_payload = json.loads(sample[0]["payload"]) if sample else {}
    except (TypeError, json.JSONDecodeError):
        sample_payload = {}
    option_keys = [
        key for key in sample_payload
        if key.startswith("votes_") and key not in {"votes_total", "votes_nulos", "votes_no_reg"}
    ]
    if not option_keys:
        st.warning("Los resultados cargados no contienen votación por opción política.")
        return
    option_labels = {key.replace("votes_", "").replace("_", " ").upper(): key for key in option_keys}
    active_scenarios = query(
        """SELECT id, name, target_percentage, participation_assumption, competition_context, coalition_context
           FROM electoral_scenarios
           WHERE profile_id = ? AND state = ? AND election_year = ? AND active = 1
           LIMIT 1""",
        (profile_id, state, election_year),
    )
    if not active_scenarios:
        st.info("Primero define y activa un escenario en “Escenarios electorales”. La meta territorial debe provenir de una hipótesis documentada.")
        return
    active_scenario = active_scenarios[0]
    config_a, config_b = st.columns(2)
    option_names = sorted(option_labels)
    # Marco Bonilla's Chihuahua scenario is based on the Juntos Defendamos
    # Chihuahua coalition; keep that reference visible by default.
    preferred_reference = "votes_jdch" if profile_id == 4 and state == "Chihuahua" else None
    preferred_label = next(
        (label for label, value in option_labels.items() if value == preferred_reference),
        option_names[0],
    )
    selected_option_label = config_a.selectbox(
        "Opción de referencia", option_names,
        index=option_names.index(preferred_label), key=f"goal_option_{profile_id}_{state}_v3",
    )
    reference_option = option_labels[selected_option_label]
    config_b.metric("Escenario activo", f"{active_scenario['name']} · {active_scenario['target_percentage']:.1f}%")
    target_pct = float(active_scenario["target_percentage"])
    st.caption(
        f"Hipótesis: {active_scenario['competition_context'] or 'Sin contexto registrado'} · "
        f"Alianzas: {active_scenario['coalition_context'] or 'Sin supuesto registrado'}"
    )
    sections = _section_target_frame(state, election_year, reference_option)
    if sections.empty:
        st.warning("No fue posible interpretar los resultados por sección.")
        return
    municipalities = _municipal_target_frame(state, election_year, reference_option)
    goal_basis = municipalities if not municipalities.empty else sections
    projected_target = round(goal_basis["Votos válidos"].sum() * target_pct / 100)
    historical_reference = int(goal_basis["Votos referencia"].sum())
    gap = max(projected_target - historical_reference, 0)
    contextual_municipalities = (
        _contextual_target_allocation(municipalities, projected_target)
        if not municipalities.empty else municipalities
    )
    _cascaded_sections, linked_sections = _cascade_section_targets(sections, contextual_municipalities)
    cards = st.columns(4)
    cards[0].metric("Secciones disponibles", f"{len(sections):,}")
    cards[1].metric("Voto histórico", f"{historical_reference:,}")
    cards[2].metric("Meta estatal", f"{projected_target:,}", f"{target_pct:.1f}% de votos válidos")
    cards[3].metric("Brecha de referencia", f"{gap:,}")
    st.caption(
        "La meta estatal se calcula sobre votos válidos del concentrado municipal oficial. "
        "Las metas municipales distribuyen la brecha estatal sin imponer el mismo porcentaje a cada municipio."
    )
    if not municipalities.empty:
        st.caption(
            "Fórmula municipal: 60% tamaño electoral, 25% participación recuperable y 15% competitividad histórica; "
            "cada municipio recibe además una asignación mínima de crecimiento."
        )
    linked_target_total = int(linked_sections["Meta propuesta"].sum()) if not linked_sections.empty else 0
    if not municipalities.empty and linked_target_total != projected_target:
        st.warning(
            "Validación de cobertura: la base municipal oficial y el archivo por sección no cubren exactamente el mismo "
            "universo electoral. Las metas de municipios se conservan como referencia estatal; las metas de distrito y "
            "sección son operativas para la cobertura disponible. No se fuerza una suma artificial entre ambos niveles."
        )
    if st.button("Generar o actualizar metas territoriales", type="primary"):
        saved = _save_vote_targets(
            profile_id, state, election_year, reference_option, target_pct, linked_sections,
            scenario_id=int(active_scenario["id"]),
            municipalities=contextual_municipalities,
            district_sections=linked_sections,
        )
        st.success(f"Se actualizaron {saved:,} metas: estado, distritos, municipios y secciones.")
        st.rerun()

    stored = query(
        """SELECT * FROM territorial_vote_targets
           WHERE profile_id = ? AND state = ? AND election_year = ? AND reference_option = ?""",
        (profile_id, state, election_year, reference_option),
    )
    # Repair older goal sets created from section files that did not contain a
    # municipality.  This keeps the municipal control tab useful immediately.
    existing_municipal_goals = sum(row["territorial_level"] == "Municipio" for row in stored)
    if len(municipalities) > 1 and existing_municipal_goals < len(municipalities):
        _save_vote_targets(
            profile_id, state, election_year, reference_option, target_pct, linked_sections,
            scenario_id=int(active_scenario["id"]), municipalities=contextual_municipalities,
            district_sections=linked_sections,
        )
        stored = query(
            """SELECT * FROM territorial_vote_targets
               WHERE profile_id = ? AND state = ? AND election_year = ? AND reference_option = ?""",
            (profile_id, state, election_year, reference_option),
        )
        st.info("Se reconstruyeron las metas municipales a partir de los resultados municipales oficiales.")
    if not stored:
        st.info("Configura la meta y presiona “Generar o actualizar” para habilitar el control operativo.")
        return
    target_frame = pd.DataFrame(stored)
    tabs = st.tabs(["Distritos", "Municipios", "Secciones", "Control semanal"])
    display_columns = [
        "district", "municipality", "electoral_section", "historical_valid_votes",
        "historical_reference_votes", "target_votes", "vote_gap", "classification",
        "responsible", "coverage_status", "status",
    ]
    labels = {
        "district": "Distrito", "municipality": "Municipio", "electoral_section": "Sección",
        "historical_valid_votes": "Votos válidos", "historical_reference_votes": "Voto histórico",
        "target_votes": "Meta", "vote_gap": "Brecha", "classification": "Tipo",
        "responsible": "Responsable", "coverage_status": "Cobertura", "status": "Estatus",
    }
    with tabs[0]:
        frame = target_frame[target_frame["territorial_level"] == "Distrito"].copy()
        district_columns = [
            "district", "historical_valid_votes", "historical_reference_votes", "target_votes",
            "vote_gap", "classification", "responsible", "coverage_status", "status",
        ]
        st.caption("Cada fila es un distrito local. Municipio y sección se consultan en sus propias pestañas.")
        st.dataframe(frame[district_columns].rename(columns=labels), use_container_width=True, hide_index=True)
    with tabs[1]:
        frame = target_frame[target_frame["territorial_level"] == "Municipio"].copy()
        municipal_columns = [
            "municipality", "historical_valid_votes", "historical_reference_votes", "target_votes",
            "target_percentage", "vote_gap", "classification", "responsible", "coverage_status", "status",
        ]
        municipal_labels = {**labels, "target_percentage": "Meta municipal %", "vote_gap": "Aporte requerido"}
        st.caption("Cada fila es un municipio. La meta estatal se distribuye por oportunidad local, no como porcentaje uniforme.")
        st.dataframe(frame[municipal_columns].rename(columns=municipal_labels), use_container_width=True, hide_index=True)
    with tabs[2]:
        frame = target_frame[target_frame["territorial_level"] == "Sección"].copy()
        mapped_sections = len(frame)
        pending_sections = max(len(sections) - mapped_sections, 0)
        st.caption(
            f"{mapped_sections:,} secciones tienen meta y están vinculadas a municipio mediante la referencia electoral 2021. "
            f"{pending_sections:,} quedan pendientes de validación y no reciben una meta hasta contar con su municipio correcto."
        )
        district_filter = st.selectbox("Distrito", ["Todos"] + sorted(frame["district"].unique().tolist()), key="goal_section_district")
        visible = frame if district_filter == "Todos" else frame[frame["district"] == district_filter]
        st.dataframe(visible[display_columns].rename(columns=labels), use_container_width=True, hide_index=True, height=380)
        section_options = {
            f"D{row['district']} · {row['municipality']} · sección {row['electoral_section']}": row
            for _, row in visible.iterrows()
        }
        chosen_label = st.selectbox("Asignar o actualizar una sección", list(section_options), key="goal_section_assignment")
        chosen = section_options[chosen_label]
        assign_a, assign_b, assign_c = st.columns(3)
        responsible = assign_a.text_input("Responsable o equipo", value=chosen["responsible"] or "")
        coverage = assign_b.selectbox(
            "Cobertura", ["Sin asignar", "Planeada", "Activa", "Verificada", "Incompleta"],
            index=["Sin asignar", "Planeada", "Activa", "Verificada", "Incompleta"].index(
                chosen["coverage_status"] if chosen["coverage_status"] in ["Sin asignar", "Planeada", "Activa", "Verificada", "Incompleta"] else "Sin asignar"
            ),
        )
        target_status = assign_c.selectbox(
            "Estatus", ["Propuesta", "Validada", "En ejecución", "Completada"],
            index=["Propuesta", "Validada", "En ejecución", "Completada"].index(
                chosen["status"] if chosen["status"] in ["Propuesta", "Validada", "En ejecución", "Completada"] else "Propuesta"
            ),
        )
        evidence = st.text_input("Nota o evidencia de cobertura", value=chosen["evidence_note"] or "")
        if st.button("Guardar control de sección"):
            execute(
                """UPDATE territorial_vote_targets
                   SET responsible = ?, coverage_status = ?, status = ?, evidence_note = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (responsible.strip() or None, coverage, target_status, evidence.strip() or None, int(chosen["id"])),
            )
            st.success("Control de sección actualizado.")
            st.rerun()
    with tabs[3]:
        section_targets = target_frame[target_frame["territorial_level"] == "Sección"]
        active = section_targets[section_targets["coverage_status"].isin(["Activa", "Verificada"])]
        assigned = section_targets[section_targets["responsible"].fillna("").str.strip().ne("")]
        actions = query(
            """SELECT status, COUNT(*) AS total FROM territorial_action_plans
               WHERE profile_id = ? AND state = ? GROUP BY status""",
            (profile_id, state),
        )
        action_counts = {row["status"]: row["total"] for row in actions}
        control_cards = st.columns(4)
        control_cards[0].metric("Secciones con responsable", f"{len(assigned):,}", f"de {len(section_targets):,}")
        control_cards[1].metric("Cobertura activa/verificada", f"{len(active):,}")
        control_cards[2].metric("Actividades en curso", action_counts.get("En curso", 0))
        control_cards[3].metric("Actividades concluidas", action_counts.get("Concluida", 0))
        st.markdown("#### Secciones que requieren prioridad operativa")
        needs_attention = section_targets[
            section_targets["coverage_status"].isin(["Sin asignar", "Incompleta"])
        ].sort_values(["vote_gap", "historical_valid_votes"], ascending=False).head(25)
        st.dataframe(needs_attention[display_columns].rename(columns=labels), use_container_width=True, hide_index=True)


def render_strategy_operation_map() -> None:
    """Visualize the saved operating plan, not only historic electoral results."""
    st.subheader("Mapa de estrategia y operación")
    st.caption(
        "Consulta metas, brecha, cobertura, responsables y actividades sobre el territorio. "
        "Los datos representan unidades territoriales agregadas; no se muestran perfiles individuales de electores."
    )
    options = profile_options()
    if not options:
        st.info("Primero crea un perfil y genera metas territoriales.")
        return
    selected_profile = st.selectbox("Perfil", list(options), key="strategy_map_profile")
    profile_id = options[selected_profile]
    states = profile_states(profile_id)
    if not states:
        st.info("Asigna un estado al perfil antes de abrir el mapa operativo.")
        return
    state = st.selectbox("Estado", states, key="strategy_map_state")
    scenario_rows = query(
        """SELECT DISTINCT vt.scenario_id, vt.election_year, vt.reference_option,
                  COALESCE(es.name, 'Escenario sin nombre') AS scenario_name,
                  vt.target_percentage
           FROM territorial_vote_targets vt
           LEFT JOIN electoral_scenarios es ON es.id = vt.scenario_id
           WHERE vt.profile_id = ? AND vt.state = ?
           ORDER BY vt.election_year DESC, scenario_name""",
        (profile_id, state),
    )
    if not scenario_rows:
        st.info("Aún no hay metas generadas. Activa un escenario y genera las metas en “Metas y control territorial”.")
        return
    scenario_options = {
        f"{row['scenario_name']} · {row['target_percentage']:.1f}% · {row['election_year']}": row
        for row in scenario_rows
    }
    selected_scenario = scenario_options[st.selectbox("Escenario operativo", list(scenario_options), key="strategy_map_scenario")]
    targets = query(
        """SELECT * FROM territorial_vote_targets
           WHERE profile_id = ? AND state = ? AND election_year = ?
             AND reference_option = ? AND COALESCE(scenario_id, -1) = COALESCE(?, -1)""",
        (profile_id, state, int(selected_scenario["election_year"]), selected_scenario["reference_option"], selected_scenario["scenario_id"]),
    )
    if not targets:
        st.info("No hay registros territoriales para el escenario seleccionado.")
        return
    target_frame = pd.DataFrame(targets)
    level_label = st.radio("Nivel territorial", ["Distrito", "Municipio", "Sección"], horizontal=True, key="strategy_map_level")
    metric_label = st.selectbox("Color del mapa", ["Brecha de votos", "Meta de votos", "Cobertura"], key="strategy_map_metric")
    level_frame = target_frame[target_frame["territorial_level"] == level_label].copy()
    if level_frame.empty:
        st.info("No hay metas para este nivel territorial.")
        return
    coverage_value = {"Sin asignar": 0, "Planeada": 1, "Incompleta": 1, "Activa": 2, "Verificada": 3}
    metric_column = {"Brecha de votos": "vote_gap", "Meta de votos": "target_votes", "Cobertura": "coverage_status"}[metric_label]
    level_frame["valor_mapa"] = (
        level_frame[metric_column].map(coverage_value).fillna(0)
        if metric_label == "Cobertura" else pd.to_numeric(level_frame[metric_column], errors="coerce").fillna(0)
    )
    cards = st.columns(4)
    cards[0].metric("Unidades en mapa", f"{len(level_frame):,}")
    cards[1].metric("Meta agregada", f"{int(level_frame['target_votes'].sum()):,}")
    cards[2].metric("Brecha agregada", f"{int(level_frame['vote_gap'].sum()):,}")
    cards[3].metric("Cobertura activa/verificada", int(level_frame["coverage_status"].isin(["Activa", "Verificada"]).sum()))

    if level_label == "Municipio":
        geojson, geometry_source = load_municipal_context(state=state)
        lookup = {municipality_match_key(row["municipality"]): row for _, row in level_frame.iterrows()}
        def target_for(properties: dict):
            return lookup.get(municipality_match_key(properties.get("municipio", properties.get("nom_agem", ""))))
        def label_for(properties: dict):
            return properties.get("municipio", properties.get("nom_agem", "Municipio"))
    elif level_label == "Distrito":
        geojson, geometry_source = load_local_district_context(state)
        lookup = {str(row["district"]).zfill(2): row for _, row in level_frame.iterrows()}
        def target_for(properties: dict):
            return lookup.get(str(properties.get("distrito_local", properties.get("distrito", ""))).zfill(2))
        def label_for(properties: dict):
            return f"Distrito {str(properties.get('distrito_local', properties.get('distrito', ''))).zfill(2)}"
    else:
        geojson, geometry_source = load_electoral_sections_context(state)
        lookup = {
            (str(row["district"]).zfill(2), str(row["electoral_section"]).zfill(4)): row
            for _, row in level_frame.iterrows()
        }
        def target_for(properties: dict):
            return lookup.get((str(properties.get("distrito_local", "")).zfill(2), str(properties.get("seccion", "")).zfill(4)))
        def label_for(properties: dict):
            return f"Sección {str(properties.get('seccion', '')).zfill(4)} · Distrito {str(properties.get('distrito_local', '')).zfill(2)}"
    if not geojson:
        st.warning("No se encontró una capa GIS para el estado y nivel territorial seleccionados.")
        return
    enriched = json.loads(json.dumps(geojson))
    for feature in enriched.get("features", []):
        properties = feature.setdefault("properties", {})
        target = target_for(properties)
        properties["territorio_operativo"] = label_for(properties)
        properties["valor_mapa"] = float(target["valor_mapa"]) if target is not None else None
        properties["target_id"] = int(target["id"]) if target is not None else None
        properties["meta"] = int(target["target_votes"]) if target is not None else None
        properties["brecha"] = int(target["vote_gap"]) if target is not None else None
        properties["tipo"] = target["classification"] if target is not None else "Sin meta"
        properties["cobertura"] = target["coverage_status"] if target is not None else "Sin meta"
        properties["responsable"] = target["responsible"] if target is not None and target["responsible"] else "Sin asignar"
    mapped_geojson = colorize_geojson(enriched, "valor_mapa", low_color=(254, 226, 226), high_color=(153, 27, 27))
    map_event = st.pydeck_chart(
        pdk.Deck(
            map_style="light",
            initial_view_state=pdk.ViewState(**contextual_view(mapped_geojson)),
            layers=[pdk.Layer(
                "GeoJsonLayer", id="strategy-operation-map", data=mapped_geojson, opacity=0.78,
                stroked=True, filled=True, get_fill_color="properties.pulso_color", get_line_color=[71, 85, 105, 150],
                line_width_min_pixels=1, pickable=True,
            )],
            tooltip={"html": "<b>{territorio_operativo}</b><br/>Meta: {meta}<br/>Brecha: {brecha}<br/>Cobertura: {cobertura}<br/>Responsable: {responsable}", "style": {"backgroundColor": "#0f172a", "color": "white"}},
        ),
        use_container_width=True, height=560, on_select="rerun", selection_mode="single-object",
        key=f"strategy_operation_{state}_{selected_scenario['scenario_id']}_{level_label}_{metric_label}",
    )
    selected_objects = map_event.selection.objects.get("strategy-operation-map", [])
    if not selected_objects:
        selected_objects = [item for values in map_event.selection.objects.values() for item in values]
    target_id = None
    if selected_objects:
        selected = selected_objects[-1]
        properties = selected.get("properties", {}) or selected.get("object", {}).get("properties", {})
        target_id = properties.get("target_id") or selected.get("target_id")
    st.caption(f"Capa GIS: {geometry_source}. El color representa {metric_label.lower()} del escenario seleccionado.")
    if not target_id:
        st.info("Haz clic en una unidad coloreada para abrir su ficha estratégica y operativa.")
        return
    selected_target = next((row for row in targets if int(row["id"]) == int(target_id)), None)
    if not selected_target:
        st.warning("La unidad elegida no tiene una meta registrada.")
        return
    st.markdown("### Ficha de estrategia territorial")
    title = selected_target["electoral_section"] or selected_target["municipality"] or selected_target["district"] or state
    st.markdown(f"#### {title} · {level_label}")
    detail = st.columns(5)
    detail[0].metric("Voto histórico", f"{int(selected_target['historical_reference_votes']):,}")
    detail[1].metric("Meta", f"{int(selected_target['target_votes']):,}")
    detail[2].metric("Brecha", f"{int(selected_target['vote_gap']):,}")
    detail[3].metric("Tipo", selected_target["classification"])
    detail[4].metric("Cobertura", selected_target["coverage_status"])
    st.write(f"**Responsable:** {selected_target['responsible'] or 'Sin asignar'}")
    actions = query(
        """SELECT activity_name, district, municipality, electoral_section, responsible, due_date, priority_level, status, evidence_note
           FROM territorial_action_plans
           WHERE profile_id = ? AND state = ?
             AND (COALESCE(district, '') = ? OR COALESCE(municipality, '') = ? OR COALESCE(electoral_section, '') = ?)
           ORDER BY due_date, id""",
        (profile_id, state, selected_target["district"], selected_target["municipality"], selected_target["electoral_section"]),
    )
    if actions:
        st.markdown("#### Actividades vinculadas")
        st.dataframe(pd.DataFrame(actions), use_container_width=True, hide_index=True)
    else:
        st.caption("No hay actividades vinculadas a esta unidad. Puedes agregarlas desde Planes de acción.")


def render_inegi_ine_cross_analysis() -> None:
    """Compare public INEGI context with official electoral aggregates.

    Municipal observations are the appropriate common geography currently
    loaded in the local database. Electoral sections are also available for
    Hermosillo, but census data must not be assigned to a section unless an
    official AGEB/manzana-to-section geographic intersection is loaded.
    """
    st.subheader("Cruce INEGI + INE")
    st.caption(
        "Explora relaciones entre población, vivienda y escolaridad de INEGI, y los resultados "
        "electorales oficiales de 2024. Cambia los ejes para formular y revisar hipótesis territoriales."
    )
    with st.expander("Cómo leer y usar este tablero", expanded=True):
        st.markdown(
            """
            **Qué compara.** Cada punto representa un municipio del estado seleccionado. Elige una variable en el eje **X** y otra en el eje **Y**: por ejemplo, viviendas y votación total, escolaridad y participación, o jóvenes y abstencionismo.

            **Cómo interpretar.** Una concentración ascendente sugiere que, en este conjunto de municipios, los dos valores tienden a crecer juntos; una concentración dispersa indica que conviene revisar municipio por municipio. La gráfica **no prueba causalidad ni describe preferencias individuales**: sirve para segmentar el territorio y definir preguntas de campo, comunicación o movilización.

            **Nivel de detalle.** La vista municipal permite cruzar INEGI e INE porque ambos datos están disponibles por municipio. La vista de secciones está disponible cuando existe un cruce geográfico verificable entre resultados electorales y datos censales.
            """
        )

    available_states = query(
        """SELECT DISTINCT state FROM territorial_election_results
           WHERE state IN (SELECT DISTINCT state FROM territorial_indicators)
           ORDER BY state"""
    )
    states = [row["state"] for row in available_states]
    if not states:
        st.info("Se requieren resultados electorales e indicadores INEGI para construir este cruce.")
        return
    # The section view is only available for Sonora.  Resetting the level when
    # the state changes prevents a previously selected Sonora-only view from
    # leaving the user with an empty panel for Chihuahua (or another state).
    def _reset_cross_geography_level() -> None:
        st.session_state["cross_inegi_ine_level"] = "Municipios · comparativo estatal"

    default_state = states.index("Sonora") if "Sonora" in states else 0
    state = st.selectbox(
        "Estado",
        states,
        index=default_state,
        key="cross_inegi_ine_state",
        on_change=_reset_cross_geography_level,
    )
    level_options = ["Municipios · comparativo estatal"]
    if state == "Sonora":
        level_options.append("Secciones electorales · Hermosillo")
    level = st.radio(
        "Nivel de análisis",
        level_options,
        horizontal=True,
        key="cross_inegi_ine_level",
    )

    if level == "Municipios · comparativo estatal":
        election_rows = query(
            """SELECT municipality, municipality_code, payload, election_type, election_year, source
               FROM territorial_election_results
               WHERE state = ? AND election_year = 2024
               ORDER BY municipality""",
            (state,),
        )
        if not election_rows:
            st.info("No hay resultados municipales de 2024 cargados para este estado.")
            return
        records = []
        election_types = set()
        sources = set()
        for row in election_rows:
            try:
                payload = json.loads(row["payload"])
            except (TypeError, json.JSONDecodeError):
                continue
            election_types.add(str(row["election_type"]))
            if row["source"]:
                sources.add(str(row["source"]))
            records.append({
                "Municipio": row["municipality"],
                "Clave municipio": str(row["municipality_code"] or "").zfill(3),
                **payload,
            })
        frame = pd.DataFrame(records)
        if frame.empty:
            st.warning("Los resultados electorales municipales no contienen valores utilizables.")
            return

        indicator_rows = query(
            """SELECT municipality, municipality_code, indicator_id, indicator_name, value, period
               FROM territorial_indicators WHERE state = ?""",
            (state,),
        )
        indicator_frame = pd.DataFrame(indicator_rows)
        indicator_labels: dict[str, str] = {}
        if not indicator_frame.empty:
            indicator_frame["_municipality"] = indicator_frame["municipality"].map(municipality_match_key)
            for indicator_id, group in indicator_frame.groupby("indicator_id"):
                name = str(group["indicator_name"].iloc[0]).replace("�", "í")
                label = f"INEGI · {name}"
                column = f"inegi_{indicator_id}"
                indicator_labels[column] = label
                by_name = group.set_index("_municipality")["value"].to_dict()
                frame[column] = frame["Municipio"].map(municipality_match_key).map(by_name)

        numeric_election = [
            column for column in frame.columns
            if column.startswith("votes_") or column in {"lista_nominal", "numero_votos_validos", "participacion_pct"}
        ]
        for column in numeric_election:
            frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
        if "participacion_pct" not in frame:
            frame["participacion_pct"] = 0.0
        frame["participacion_pct"] = frame["participacion_pct"].where(
            frame["participacion_pct"] > 0,
            frame.get("votes_total", pd.Series(0, index=frame.index))
            / frame.get("lista_nominal", pd.Series(0, index=frame.index)).replace(0, pd.NA) * 100,
        ).fillna(0)
        frame["abstencionismo"] = (
            frame.get("lista_nominal", pd.Series(0, index=frame.index))
            - frame.get("votes_total", pd.Series(0, index=frame.index))
        ).clip(lower=0)
        frame["abstencionismo_pct"] = (100 - frame["participacion_pct"]).clip(lower=0)

        aggregate_vote_keys = {"votes_total", "votes_nulos", "votes_no_reg", "votes_validos"}
        vote_keys = [
            column for column in frame.columns
            if column.startswith("votes_") and column not in aggregate_vote_keys
            and pd.to_numeric(frame[column], errors="coerce").fillna(0).sum() > 0
        ]
        for column in vote_keys:
            label = ELECTORAL_VOTE_LABELS.get(column, column.replace("votes_", "").replace("_", " ").title())
            percentage_column = f"share_{column}"
            frame[percentage_column] = (
                frame[column] / frame.get("numero_votos_validos", pd.Series(0, index=frame.index)).replace(0, pd.NA) * 100
            ).fillna(0)
            indicator_labels[column] = f"INE · Votos {label}"
            indicator_labels[percentage_column] = f"INE · % votos válidos {label}"

        indicator_labels.update({
            "lista_nominal": "INE · Lista nominal",
            "votes_total": "INE · Votación total",
            "numero_votos_validos": "INE · Votos válidos",
            "participacion_pct": "INE · Participación (%)",
            "abstencionismo": "INE · Abstencionismo (personas)",
            "abstencionismo_pct": "INE · Abstencionismo (%)",
        })
        available_metrics = [
            column for column in indicator_labels
            if column in frame.columns and pd.to_numeric(frame[column], errors="coerce").notna().sum() >= 2
        ]
        labels_to_columns = {indicator_labels[column]: column for column in available_metrics}
        default_x = next((label for label in labels_to_columns if "Población total" in label), list(labels_to_columns)[0])
        default_y = next((label for label in labels_to_columns if label == "INE · Votación total"), list(labels_to_columns)[0])
        controls = st.columns([1, 1, .75])
        with controls[0]:
            x_label = st.selectbox("Eje X", list(labels_to_columns), index=list(labels_to_columns).index(default_x), key="cross_municipal_x")
        with controls[1]:
            y_label = st.selectbox("Eje Y", list(labels_to_columns), index=list(labels_to_columns).index(default_y), key="cross_municipal_y")
        with controls[2]:
            size_by = st.selectbox(
                "Tamaño del punto", ["Uniforme", "Lista nominal", "Votación total"], key="cross_municipal_size"
            )
        x_column, y_column = labels_to_columns[x_label], labels_to_columns[y_label]
        frame["Es Hermosillo"] = frame["Municipio"].map(municipality_match_key).eq("hermosillo")
        size_column = {"Lista nominal": "lista_nominal", "Votación total": "votes_total"}.get(size_by)
        tooltip_columns = ["Municipio", x_column, y_column, "lista_nominal", "votes_total", "participacion_pct", "abstencionismo_pct"]
        tooltip = [alt.Tooltip("Municipio:N", title="Municipio")]
        for column in tooltip_columns[1:]:
            if column in frame.columns:
                title = indicator_labels.get(column, column)
                tooltip.append(alt.Tooltip(f"{column}:Q", title=title, format=",.2f"))
        encoding = {
            "x": alt.X(f"{x_column}:Q", title=x_label, scale=alt.Scale(zero=False)),
            "y": alt.Y(f"{y_column}:Q", title=y_label, scale=alt.Scale(zero=False)),
            "color": alt.Color("Es Hermosillo:N", title="Referencia", scale=alt.Scale(domain=[False, True], range=["#94a3b8", "#d97706"])),
            "tooltip": tooltip,
        }
        if size_column:
            encoding["size"] = alt.Size(f"{size_column}:Q", title=size_by, scale=alt.Scale(range=[70, 850]))
        chart = alt.Chart(frame).mark_circle(opacity=.82, stroke="#ffffff", strokeWidth=1).encode(**encoding).properties(height=510).interactive()
        st.altair_chart(chart, use_container_width=True)

        hermosillo = frame[frame["Es Hermosillo"]]
        if not hermosillo.empty:
            row = hermosillo.iloc[0]
            cards = st.columns(5)
            cards[0].metric("Población total", f"{int(row.get('inegi_1002000001') or 0):,}")
            cards[1].metric("Viviendas", f"{int(row.get('inegi_1003000001') or 0):,}")
            cards[2].metric("Jóvenes 15–29", f"{float(row.get('inegi_1002000004') or 0):.1f}%")
            cards[3].metric("Personas 65+", f"{int(row.get('inegi_6207140357') or 0):,}")
            cards[4].metric("Participación 2024", f"{float(row.get('participacion_pct') or 0):.1f}%")
            st.caption(
                "Ficha de Hermosillo: población, sexo y escolaridad corresponden a INEGI; "
                "viviendas y población 65+ usan el último periodo publicado en el Banco de Indicadores. "
                "La elección se muestra según la carga oficial disponible."
            )
        st.markdown("#### Datos detrás de la gráfica")
        table_columns = ["Municipio", x_column, y_column, "lista_nominal", "votes_total", "participacion_pct", "abstencionismo_pct"]
        table_columns = list(dict.fromkeys(column for column in table_columns if column in frame.columns))
        st.dataframe(
            frame[table_columns].sort_values(y_column, ascending=False).rename(columns=indicator_labels),
            use_container_width=True, hide_index=True,
        )
        st.caption(
            f"Cobertura: {len(frame):,} municipios · elección 2024: {', '.join(sorted(election_types))}. "
            "Fuentes: INEGI Banco de Indicadores e instituto electoral estatal/INE conforme a la carga local."
        )
        return

    if state != "Sonora":
        st.info("La vista seccional de esta primera versión está preparada con la carga 2024 de Hermosillo, Sonora.")
        return
    section_rows = query(
        """SELECT district_code, section_code, payload
           FROM territorial_section_results
           WHERE state = ? AND municipality = ? AND election_year = 2024
           ORDER BY district_code, section_code""",
        (state, "Hermosillo"),
    )
    records = []
    for row in section_rows:
        try:
            payload = json.loads(row["payload"])
        except (TypeError, json.JSONDecodeError):
            continue
        records.append({"Distrito": str(row["district_code"]), "Sección": str(row["section_code"]), **payload})
    section_frame = pd.DataFrame(records)
    if section_frame.empty:
        st.info("No hay secciones electorales 2024 cargadas para Hermosillo.")
        return
    for column in [column for column in section_frame if column.startswith("votes_") or column in {"lista_nominal", "participacion_pct"}]:
        section_frame[column] = pd.to_numeric(section_frame[column], errors="coerce").fillna(0)
    section_frame["abstencionismo"] = (section_frame["lista_nominal"] - section_frame["votes_total"]).clip(lower=0)
    section_frame["abstencionismo_pct"] = (100 - section_frame["participacion_pct"]).clip(lower=0)
    section_labels = {
        "lista_nominal": "INE · Lista nominal", "votes_total": "INE · Votación total",
        "numero_votos_validos": "INE · Votos válidos", "participacion_pct": "INE · Participación (%)",
        "abstencionismo": "INE · Abstencionismo (personas)", "abstencionismo_pct": "INE · Abstencionismo (%)",
    }
    for column in section_frame.columns:
        if column.startswith("votes_") and column not in {"votes_total", "votes_nulos", "votes_no_reg"}:
            section_labels[column] = "INE · Votos " + ELECTORAL_VOTE_LABELS.get(column, column.replace("votes_", "").replace("_", " ").title())
    options = {label: key for key, label in section_labels.items() if key in section_frame.columns}
    axes = st.columns(2)
    with axes[0]:
        x_label = st.selectbox("Eje X", list(options), index=list(options).index("INE · Lista nominal"), key="cross_sections_x")
    with axes[1]:
        y_label = st.selectbox("Eje Y", list(options), index=list(options).index("INE · Votación total"), key="cross_sections_y")
    x_column, y_column = options[x_label], options[y_label]
    section_chart = alt.Chart(section_frame).mark_circle(opacity=.7, color="#0f766e").encode(
        x=alt.X(f"{x_column}:Q", title=x_label, scale=alt.Scale(zero=False)),
        y=alt.Y(f"{y_column}:Q", title=y_label, scale=alt.Scale(zero=False)),
        tooltip=[
            alt.Tooltip("Distrito:N", title="Distrito"), alt.Tooltip("Sección:N", title="Sección"),
            alt.Tooltip(f"{x_column}:Q", title=x_label, format=",.2f"),
            alt.Tooltip(f"{y_column}:Q", title=y_label, format=",.2f"),
            alt.Tooltip("participacion_pct:Q", title="Participación (%)", format=".2f"),
        ],
    ).properties(height=510).interactive()
    st.altair_chart(section_chart, use_container_width=True)
    st.warning(
        "Datos demográficos por sección aún no cargados. INEGI publica población, edad, escolaridad y viviendas por "
        "AGEB o manzana; antes de asignarlos a una sección INE debe realizarse un cruce geográfico oficial. "
        "Por ello esta vista muestra únicamente resultados electorales verificables por sección."
    )
    section_table_columns = list(dict.fromkeys([
        "Distrito", "Sección", x_column, y_column, "lista_nominal", "votes_total",
        "participacion_pct", "abstencionismo_pct",
    ]))
    section_table = section_frame[section_table_columns].drop_duplicates().sort_values(y_column, ascending=False)
    st.dataframe(
        section_table.rename(columns=section_labels),
        use_container_width=True, hide_index=True,
    )
    st.caption("Cobertura: 433 secciones electorales de Hermosillo · Diputaciones locales 2024 · fuente oficial cargada del IEE Sonora.")


def render_electoral_opportunity_map() -> None:
    """Turn the municipal electoral and INEGI data already loaded into a clear opportunity map.

    This is an aggregate territorial view.  It supports planning and review of
    municipalities; it does not infer, score, or target individual voters.
    """
    st.subheader("Mapa de oportunidad electoral")
    st.caption(
        "Cruza resultados electorales municipales e indicadores INEGI para ordenar dónde conviene "
        "revisar participación, volumen electoral, presencia histórica y contexto territorial."
    )
    with st.expander("¿Cómo leer esta pantalla?", expanded=False):
        st.markdown(
            """
            Esta pantalla ayuda a identificar, comparar y revisar municipios a partir de resultados electorales históricos e información territorial pública. No es un pronóstico: es una herramienta para ordenar la conversación estratégica.

            **1. Configuración del análisis**

            - **Perfil:** persona, candidatura o institución para la cual se consulta el territorio.
            - **Estado:** delimita los municipios, resultados y cartografía disponibles.
            - **Elección de referencia:** define el año y tipo de elección usados como base histórica.
            - **Opción de referencia:** partido, coalición o candidatura cuya votación histórica se quiere revisar.
            - **Contexto INEGI:** agrega una variable social —población, conectividad, salud, agua, escolaridad, discapacidad u otra disponible— para interpretar cada municipio.
            - **Color del mapa:** permite cambiar la variable que se representa geográficamente.

            **2. Resumen estatal**

            Las tarjetas muestran cuántos municipios tienen información, la lista nominal agregada, la participación estatal de la elección elegida y el número de municipios en prioridad alta. Sirven para entender el tamaño total del escenario antes de entrar al detalle.

            **3. Cómo interpretar el mapa**

            El mapa muestra municipios con tonos de azul: el tono más intenso representa un valor relativamente mayor para el criterio seleccionado. Puedes analizar:

            - **Índice de oportunidad:** combina volumen electoral, participación pendiente de recuperar y presencia histórica de la opción.
            - **Peso electoral:** resalta municipios con mayor lista nominal.
            - **Participación baja:** identifica territorios por debajo del promedio estatal de participación.
            - **Porcentaje de la opción:** muestra la fuerza histórica de la opción de referencia.
            - **Indicador INEGI:** distribuye territorialmente la condición social elegida.

            Selecciona un municipio con el control **Municipio activo** o haciendo clic en el mapa. El borde ámbar indica el municipio que está abierto en la ficha.

            **4. Ficha de oportunidad**

            La ficha lateral explica el municipio seleccionado: prioridad, índice, lista nominal, participación, brecha frente al promedio estatal, porcentaje histórico de la opción y su cambio frente a la elección anterior, cuando existe una comparación. También presenta el indicador INEGI elegido y una lectura de trabajo: movilizar participación, consolidar presencia o revisar competitividad.

            **5. Ranking de municipios**

            El ranking permite comparar los principales municipios sin depender del mapa. Úsalo para revisar qué territorios concentran mayor tamaño electoral, dónde hay brecha de participación o dónde existe mayor presencia histórica de la opción.

            **Cómo se calcula la prioridad**

            El índice de oportunidad combina **45% peso electoral**, **30% brecha de participación** y **25% presencia histórica de la opción elegida**. La prioridad alta corresponde al grupo superior de municipios comparados dentro del estado; no significa que un resultado electoral esté asegurado.

            **Alcance de la información**

            Los datos son agregados por municipio. INEGI aporta contexto territorial, no una relación causal con el voto. La pantalla orienta la revisión y planeación; no predice ni determina decisiones o preferencias de personas.
            """
        )
    profiles = profile_options()
    if not profiles:
        st.info("Primero crea un perfil y asigna su estado desde Perfil territorial.")
        return
    profile_label = st.selectbox("Perfil", list(profiles), key="opportunity_profile")
    profile_id = profiles[profile_label]
    states = profile_states(profile_id)
    if not states:
        st.info("El perfil aún no tiene un estado asociado.")
        return
    state = st.selectbox("Estado", states, key="opportunity_state")
    election_options_rows = query(
        """SELECT DISTINCT election_type, election_year
           FROM territorial_election_results WHERE state = ?
           ORDER BY election_year DESC, election_type""",
        (state,),
    )
    if not election_options_rows:
        st.info("No hay resultados electorales municipales cargados para este estado.")
        return
    election_options = {
        f"{row['election_type']} · {row['election_year']}": row
        for row in election_options_rows
    }
    selected_election = election_options[st.selectbox(
        "Elección de referencia", list(election_options), key="opportunity_election"
    )]
    election_type = selected_election["election_type"]
    election_year = int(selected_election["election_year"])
    rows = query(
        """SELECT municipality, municipality_code, payload
           FROM territorial_election_results
           WHERE state = ? AND election_type = ? AND election_year = ?
           ORDER BY municipality""",
        (state, election_type, election_year),
    )
    decoded = decode_election_rows(rows)
    records = [{"municipio": row["municipality"], "clave_municipio": row["municipality_code"], **row["payload"]} for row in decoded]
    if not records:
        st.warning("Los resultados cargados no contienen valores que puedan analizarse.")
        return
    frame = pd.DataFrame(records)
    aggregate_vote_fields = {"votes_total", "votes_nulos", "votes_no_reg", "votes_validos"}
    vote_keys = sorted(
        key for key in frame.columns
        if key.startswith("votes_")
        and key not in aggregate_vote_fields
        and pd.to_numeric(frame[key], errors="coerce").fillna(0).sum() > 0
    )
    if not vote_keys:
        st.warning("La elección elegida no contiene votos por partido o coalición.")
        return
    party_options = {ELECTORAL_VOTE_LABELS.get(key, key.replace("votes_", "").replace("_", " ").title()): key for key in vote_keys}
    controls = st.columns([1.15, 1.15, 1])
    with controls[0]:
        party_label = st.selectbox("Opción de referencia", list(party_options), key="opportunity_party")
    party_key = party_options[party_label]
    indicator_rows = query(
        """SELECT indicator_id, indicator_name, unit
           FROM territorial_indicators WHERE state = ?
           GROUP BY indicator_id, indicator_name, unit ORDER BY indicator_name""",
        (state,),
    )
    indicator_options = {"Sin indicador INEGI": None}
    indicator_options.update({f"{row['indicator_name']} ({row['unit']})": row for row in indicator_rows})
    with controls[1]:
        indicator_label = st.selectbox("Contexto INEGI", list(indicator_options), key="opportunity_indicator")
    with controls[2]:
        map_metric = st.selectbox(
            "Color del mapa",
            ["Índice de oportunidad", "Peso electoral", "Participación baja", f"% {party_label}", "Indicador INEGI"],
            key="opportunity_metric",
        )

    for column in ["lista_nominal", "votes_total", "numero_votos_validos", "participacion_pct", party_key]:
        frame[column] = pd.to_numeric(frame.get(column, pd.Series(0, index=frame.index)), errors="coerce").fillna(0)
    frame["participacion_pct"] = frame["participacion_pct"].where(
        frame["participacion_pct"] > 0,
        (frame["votes_total"] / frame["lista_nominal"].replace(0, pd.NA) * 100),
    ).fillna(0)
    # Some imported electoral files carry nullable values.  Force the derived
    # percentage to a numeric dtype before ranking it; otherwise pandas cannot
    # order it with ``nlargest`` (as occurred for the Yucatán profile).
    frame["porcentaje_referencia"] = pd.to_numeric(
        frame[party_key] / frame["numero_votos_validos"].replace(0, pd.NA) * 100,
        errors="coerce",
    ).fillna(0.0).astype(float)
    frame["votos_referencia"] = frame[party_key].round().astype(int)
    total_nominal = float(frame["lista_nominal"].sum())
    state_turnout = float(frame["votes_total"].sum() / total_nominal * 100) if total_nominal else 0.0
    frame["peso_electoral_pct"] = frame["lista_nominal"] / total_nominal * 100 if total_nominal else 0.0
    frame["brecha_participacion_pp"] = (state_turnout - frame["participacion_pct"]).clip(lower=0)

    previous_years = query(
        """SELECT DISTINCT election_year FROM territorial_election_results
           WHERE state = ? AND election_type = ? AND election_year < ? ORDER BY election_year DESC""",
        (state, election_type, election_year),
    )
    prior_year = int(previous_years[0]["election_year"]) if previous_years else None
    frame["cambio_pp"] = pd.NA
    if prior_year:
        prior_rows = decode_election_rows(query(
            """SELECT municipality, municipality_code, payload FROM territorial_election_results
               WHERE state = ? AND election_type = ? AND election_year = ?""",
            (state, election_type, prior_year),
        ))
        prior = {}
        for row in prior_rows:
            payload = row["payload"]
            valid = float(payload.get("numero_votos_validos") or 0)
            prior[municipality_match_key(row["municipality"])] = (float(payload.get(party_key) or 0) / valid * 100) if valid else None
        frame["cambio_pp"] = frame.apply(
            lambda item: item["porcentaje_referencia"] - prior.get(municipality_match_key(item["municipio"]), item["porcentaje_referencia"])
            if prior.get(municipality_match_key(item["municipio"])) is not None else pd.NA,
            axis=1,
        )

    frame["indicador_inegi"] = pd.NA
    indicator_definition = indicator_options[indicator_label]
    population_indicator_ids = {"1002000001", "1002000002", "1002000003"}
    indicator_unit = (
        "personas" if indicator_definition and str(indicator_definition["indicator_id"]) in population_indicator_ids
        else (indicator_definition["unit"] if indicator_definition else "")
    )
    is_population_indicator = bool(
        indicator_definition and str(indicator_definition["indicator_id"]) in population_indicator_ids
    )
    if indicator_definition:
        values = query(
            """SELECT municipality, municipality_code, value FROM territorial_indicators
               WHERE state = ? AND indicator_id = ?""",
            (state, indicator_definition["indicator_id"]),
        )
        by_code = {str(row["municipality_code"]).zfill(3): float(row["value"]) for row in values if row["value"] is not None}
        # Some electoral source files use an internal municipality identifier
        # rather than INEGI's Cvegeo.  Join by municipality name first (the
        # published label is stable here) and retain the code only as fallback.
        by_name = {municipality_match_key(row["municipality"]): float(row["value"]) for row in values if row["value"] is not None}
        frame["indicador_inegi"] = frame.apply(
            lambda item: by_name.get(
                municipality_match_key(item["municipio"]),
                by_code.get(str(item["clave_municipio"]).zfill(3)),
            ),
            axis=1,
        )

    def normalized(series: pd.Series) -> pd.Series:
        numeric = pd.to_numeric(series, errors="coerce").fillna(0)
        maximum = float(numeric.max())
        return numeric / maximum * 100 if maximum else numeric

    # Reproducible aggregate index: volume, recoverable participation and
    # historical reference support.  It is a planning aid, not a forecast.
    frame["indice_oportunidad"] = (
        normalized(frame["lista_nominal"]) * 0.45
        + normalized(frame["brecha_participacion_pp"]) * 0.30
        + normalized(frame["porcentaje_referencia"]) * 0.25
    ).round(1)
    # The score remains 0–100, while the traffic-light is relative to the
    # territory being compared.  This guarantees that "Alta" means the
    # upper opportunity group in the selected state, rather than requiring
    # an arbitrary universal threshold that may leave the map without highs.
    high_cut = float(frame["indice_oportunidad"].quantile(0.75))
    medium_cut = float(frame["indice_oportunidad"].quantile(0.45))
    frame["prioridad"] = pd.Series("Baja", index=frame.index)
    frame.loc[frame["indice_oportunidad"] >= medium_cut, "prioridad"] = "Media"
    frame.loc[frame["indice_oportunidad"] >= high_cut, "prioridad"] = "Alta"
    frame["lectura"] = frame.apply(
        lambda item: "Movilizar participación" if item["brecha_participacion_pp"] >= 5 and item["porcentaje_referencia"] >= frame["porcentaje_referencia"].median()
        else "Consolidar presencia" if item["porcentaje_referencia"] >= frame["porcentaje_referencia"].median()
        else "Revisar competitividad", axis=1,
    )
    frame = frame.sort_values(["indice_oportunidad", "lista_nominal"], ascending=False).reset_index(drop=True)

    stats = st.columns(4)
    stats[0].metric("Municipios analizados", len(frame))
    stats[1].metric("Lista nominal agregada", f"{int(total_nominal):,}")
    stats[2].metric("Participación estatal", f"{state_turnout:.1f}%")
    stats[3].metric("Prioridad alta", int((frame["prioridad"] == "Alta").sum()))
    st.caption(
        "Índice de oportunidad: 45% peso electoral, 30% brecha de participación y 25% presencia histórica de la opción seleccionada. "
        "La prioridad Alta corresponde al grupo superior de municipios comparados. No estima ni determina el voto individual."
    )

    metric_column = {
        "Índice de oportunidad": "indice_oportunidad",
        "Peso electoral": "peso_electoral_pct",
        "Participación baja": "brecha_participacion_pp",
        f"% {party_label}": "porcentaje_referencia",
        "Indicador INEGI": "indicador_inegi",
    }[map_metric]
    metric_presentation = {
        "Índice de oportunidad": ("Índice de oportunidad", "/100"),
        "Peso electoral": ("Peso electoral", "% de la lista nominal estatal"),
        "Participación baja": ("Brecha de participación", "puntos porcentuales bajo el promedio estatal"),
        f"% {party_label}": (f"Votación histórica · {party_label}", "% de votos válidos"),
        "Indicador INEGI": (
            indicator_definition["indicator_name"] if indicator_definition else "Indicador INEGI",
            indicator_unit,
        ),
    }
    tooltip_metric_label, tooltip_metric_unit = metric_presentation[map_metric]
    geojson, geometry_source = load_municipal_context(state=state)
    if not geojson:
        st.warning("No se encontró cartografía municipal para el estado seleccionado.")
        return
    by_municipality = {municipality_match_key(row["municipio"]): row for _, row in frame.iterrows()}
    enriched = json.loads(json.dumps(geojson))
    for feature in enriched.get("features", []):
        props = feature.setdefault("properties", {})
        municipality = props.get("municipio", props.get("nom_agem", props.get("NOMGEO", "")))
        row = by_municipality.get(municipality_match_key(municipality))
        props["municipio"] = municipality
        props["valor_mapa"] = float(row[metric_column]) if row is not None and pd.notna(row[metric_column]) else None
        props["indice"] = float(row["indice_oportunidad"]) if row is not None else None
        props["prioridad"] = str(row["prioridad"]) if row is not None else "Sin información"
        props["participacion"] = round(float(row["participacion_pct"]), 1) if row is not None else None
        props["opcion_pct"] = round(float(row["porcentaje_referencia"]), 1) if row is not None else None
        tooltip_value = props["valor_mapa"]
        props["metrica_titulo"] = tooltip_metric_label
        props["metrica_valor"] = (
            f"{tooltip_value:,.0f} {tooltip_metric_unit}" if tooltip_value is not None and is_population_indicator
            else f"{tooltip_value:,.1f} {tooltip_metric_unit}" if tooltip_value is not None
            else "Sin dato disponible"
        )
    # GeoJSON properties live below ``feature.properties`` in deck.gl.  To
    # avoid a browser-dependent property accessor (which produced black
    # polygons in some Streamlit/pydeck versions), render four explicit
    # color bands with constant RGBA values.  Every polygon remains pickable.
    values = pd.to_numeric(
        pd.Series([feature.get("properties", {}).get("valor_mapa") for feature in enriched.get("features", [])]),
        errors="coerce",
    )
    valid_values = values.dropna()
    breaks = list(valid_values.quantile([0.25, 0.50, 0.75])) if not valid_values.empty else [0, 0, 0]
    palette = [(219, 234, 254, 210), (147, 197, 253, 210), (59, 130, 246, 215), (12, 74, 110, 220)]
    color_groups = [[] for _ in palette]
    missing_group = []
    for feature in enriched.get("features", []):
        value = pd.to_numeric(pd.Series([feature.get("properties", {}).get("valor_mapa")]), errors="coerce").iloc[0]
        if pd.isna(value):
            missing_group.append(feature)
        elif value <= breaks[0]:
            color_groups[0].append(feature)
        elif value <= breaks[1]:
            color_groups[1].append(feature)
        elif value <= breaks[2]:
            color_groups[2].append(feature)
        else:
            color_groups[3].append(feature)
    map_layers = [
        pdk.Layer(
            "GeoJsonLayer", id=f"opportunity-map-{index}",
            data={"type": "FeatureCollection", "features": group}, opacity=0.80,
            stroked=True, filled=True, get_fill_color=list(palette[index]), get_line_color=[15, 23, 42, 140],
            line_width_min_pixels=1, pickable=True,
        )
        for index, group in enumerate(color_groups) if group
    ]
    if missing_group:
        map_layers.append(pdk.Layer(
            "GeoJsonLayer", id="opportunity-map-sin-dato",
            data={"type": "FeatureCollection", "features": missing_group}, opacity=0.40,
            stroked=True, filled=True, get_fill_color=[203, 213, 225, 150], get_line_color=[100, 116, 139, 130],
            line_width_min_pixels=1, pickable=True,
        ))
    municipality_options = list(frame["municipio"])
    municipality_set = set(municipality_options)
    pending_municipality = st.session_state.pop("opportunity_municipality_pending", None)
    if pending_municipality in municipality_set:
        st.session_state["opportunity_selected_municipality"] = pending_municipality
        st.session_state["opportunity_municipality_control"] = pending_municipality
    if st.session_state.get("opportunity_selected_municipality") not in municipality_set:
        st.session_state["opportunity_selected_municipality"] = municipality_options[0]
    if st.session_state.get("opportunity_municipality_control") not in municipality_set:
        st.session_state["opportunity_municipality_control"] = st.session_state["opportunity_selected_municipality"]

    def sync_opportunity_municipality() -> None:
        st.session_state["opportunity_selected_municipality"] = st.session_state["opportunity_municipality_control"]

    st.selectbox(
        "Municipio activo", municipality_options, key="opportunity_municipality_control",
        on_change=sync_opportunity_municipality,
        help="Este selector y el mapa siempre muestran el mismo municipio.",
    )
    selected_municipality = st.session_state["opportunity_selected_municipality"]
    selected = frame.loc[frame["municipio"] == selected_municipality].iloc[0]
    selected_features = [
        feature for feature in enriched.get("features", [])
        if municipality_match_key(feature.get("properties", {}).get("municipio")) == municipality_match_key(selected_municipality)
    ]
    if selected_features:
        map_layers.append(pdk.Layer(
            "GeoJsonLayer", id="opportunity-map-selected",
            data={"type": "FeatureCollection", "features": selected_features},
            stroked=True, filled=False, get_line_color=[245, 158, 11, 255],
            line_width_min_pixels=4, pickable=False,
        ))
    map_column, ficha_column = st.columns([1.55, 1], gap="large")
    with map_column:
        st.markdown("### Mapa y ficha de oportunidad")
        st.caption("Mapa municipal")
        map_event = st.pydeck_chart(
            pdk.Deck(
                map_style="light", initial_view_state=pdk.ViewState(**contextual_view(enriched)),
                layers=map_layers,
                tooltip={"html": "<b>{municipio}</b><hr style='margin:5px 0;border-color:#475569'/><b>{metrica_titulo}</b>: {metrica_valor}<br/>Prioridad relativa: {prioridad}<br/>Participación histórica: {participacion}%<br/>Votación de la opción: {opcion_pct}%<br/><span style='color:#bae6fd'>Haz clic para abrir la ficha lateral.</span>", "style": {"backgroundColor": "#0f172a", "color": "white", "fontSize": "12px"}},
            ), use_container_width=True, height=520, on_select="rerun", selection_mode="single-object",
            key=f"opportunity_map_{state}_{election_type}_{election_year}_{party_key}_{metric_column}",
        )
        st.caption("Haz clic en un municipio para actualizar la ficha lateral.")
    selected_objects = [
        item for values in map_event.selection.objects.values() for item in values
    ]
    if selected_objects:
        selected_properties = selected_objects[-1].get("properties", {}) or selected_objects[-1].get("object", {}).get("properties", {})
        clicked = selected_properties.get("municipio")
        if clicked and municipality_match_key(clicked) in by_municipality:
            clicked_municipality = by_municipality[municipality_match_key(clicked)]["municipio"]
            if clicked_municipality != selected_municipality:
                st.session_state["opportunity_municipality_pending"] = clicked_municipality
                st.rerun()
    action = {
        "Movilizar participación": "Priorizar organización, contacto territorial y seguimiento de participación; existe presencia histórica y una brecha de asistencia por recuperar.",
        "Consolidar presencia": "Mantener presencia territorial y documentar necesidades locales para conservar la base histórica y su capacidad de movilización.",
        "Revisar competitividad": "Revisar la competencia, los temas ciudadanos y la cobertura operativa antes de asignar recursos adicionales.",
    }[selected["lectura"]]
    with ficha_column:
        st.markdown("### Ficha de oportunidad")
        st.markdown("#### " + str(selected["municipio"]))
        st.success(f"**Acción sugerida · {selected['lectura']}:** {action}")
        ficha_top, ficha_bottom = st.columns(2)
        ficha_top.metric("Prioridad", selected["prioridad"])
        ficha_bottom.metric("Índice", f"{selected['indice_oportunidad']:.1f}/100")
        ficha_top.metric("Lista nominal", f"{int(selected['lista_nominal']):,}")
        ficha_bottom.metric("Participación", f"{selected['participacion_pct']:.1f}%", f"{selected['brecha_participacion_pp']:.1f} pp bajo el promedio")
        ficha_top.metric(f"% {party_label}", f"{selected['porcentaje_referencia']:.1f}%", f"{selected['cambio_pp']:+.1f} pp" if pd.notna(selected["cambio_pp"]) else None)
        ficha_bottom.metric(f"Votos {party_label}", f"{int(selected['votos_referencia']):,}")
        if indicator_definition and pd.notna(selected["indicador_inegi"]):
            indicator_average = pd.to_numeric(frame["indicador_inegi"], errors="coerce").dropna().mean()
            indicator_delta = float(selected["indicador_inegi"]) - float(indicator_average) if pd.notna(indicator_average) else None
            indicator_value = (
                f"{selected['indicador_inegi']:,.0f} {indicator_unit}"
                if is_population_indicator else f"{selected['indicador_inegi']:,.1f} {indicator_unit}"
            )
            indicator_delta_label = (
                f"{indicator_delta:+,.0f} vs. promedio municipal" if is_population_indicator
                else f"{indicator_delta:+,.1f} vs. promedio municipal"
            ) if indicator_delta is not None else None
            st.markdown("##### Contexto INEGI seleccionado")
            st.metric(
                indicator_definition["indicator_name"],
                indicator_value,
                indicator_delta_label,
            )
            st.caption(
                "Fuente: INEGI, Censo de Población y Vivienda 2020. Este indicador aporta contexto territorial; no explica por sí mismo el comportamiento electoral."
            )
        st.caption("El mapa muestra valores agregados; la ficha explica el municipio seleccionado.")

    st.divider()
    st.markdown("### Cruce electoral + INEGI")
    st.caption(
        "Esta es la consulta directa del cruce: cada fila une el resultado electoral municipal con el indicador INEGI seleccionado "
        "mediante estado y clave/nombre oficial de municipio. Sirve para comparar territorios, no para perfilar personas."
    )
    if not indicator_definition:
        st.info(
            "Selecciona un valor en **Contexto INEGI** para activar el cruce. Por ejemplo: población, acceso a internet, "
            "agua entubada, drenaje, escolaridad o salud."
        )
    else:
        cross_left, cross_right = st.columns([1, 1.45], gap="large")
        with cross_left:
            st.markdown(f"#### Lectura integrada · {selected['municipio']}")
            st.metric("Peso electoral", f"{selected['peso_electoral_pct']:.1f}% de la lista nominal estatal")
            st.metric(
                indicator_definition["indicator_name"],
                (
                    f"{selected['indicador_inegi']:,.0f} {indicator_unit}"
                    if is_population_indicator else f"{selected['indicador_inegi']:,.1f} {indicator_unit}"
                ) if pd.notna(selected["indicador_inegi"]) else "Sin dato",
            )
            if pd.notna(selected["indicador_inegi"]):
                indicator_median = pd.to_numeric(frame["indicador_inegi"], errors="coerce").dropna().median()
                context_position = "por encima" if selected["indicador_inegi"] >= indicator_median else "por debajo"
                st.write(
                    f"El municipio reúne **{selected['peso_electoral_pct']:.1f}%** de la lista nominal estatal; "
                    f"su valor de {indicator_definition['indicator_name'].lower()} está **{context_position}** de la mediana municipal. "
                    f"La participación histórica fue **{selected['participacion_pct']:.1f}%** y {party_label} obtuvo "
                    f"**{selected['porcentaje_referencia']:.1f}%** de los votos válidos."
                )
        with cross_right:
            st.markdown("#### Comparativo municipal")
            cross_frame = frame[[
                "municipio", "lista_nominal", "participacion_pct", "votos_referencia",
                "porcentaje_referencia", "indicador_inegi", "indice_oportunidad", "prioridad",
            ]].rename(columns={
                "municipio": "Municipio",
                "lista_nominal": "Lista nominal",
                "participacion_pct": "Participación (%)",
                "votos_referencia": f"Votos {party_label}",
                "porcentaje_referencia": f"% {party_label}",
                "indicador_inegi": indicator_definition["indicator_name"],
                "indice_oportunidad": "Índice de oportunidad",
                "prioridad": "Prioridad",
            }).sort_values("Índice de oportunidad", ascending=False)
            st.dataframe(
                cross_frame,
                use_container_width=True,
                hide_index=True,
                height=340,
                column_config={
                    "Lista nominal": st.column_config.NumberColumn(format="%,d"),
                    "Participación (%)": st.column_config.NumberColumn(format="%.1f%%"),
                    f"Votos {party_label}": st.column_config.NumberColumn(format="%,d"),
                    f"% {party_label}": st.column_config.NumberColumn(format="%.1f%%"),
                    indicator_definition["indicator_name"]: st.column_config.NumberColumn(
                        format="%,d" if is_population_indicator else "%.1f"
                    ),
                    "Índice de oportunidad": st.column_config.NumberColumn(format="%.1f"),
                },
            )
        st.caption(
            "Lectura sugerida: primero compara peso electoral y participación; después interpreta el indicador INEGI como "
            "contexto del territorio. El indicador no prueba una causa del resultado ni identifica preferencias individuales."
        )
    st.markdown("### Resultados del análisis")
    st.caption(
        f"Lecturas automáticas para revisar la posición territorial de {party_label}. "
        "Son evidencia agregada para análisis; no son una proyección electoral."
    )
    total_reference_votes = int(frame["votos_referencia"].sum())
    top_ten_votes = int(frame.nlargest(10, "votos_referencia")["votos_referencia"].sum())
    top_ten_concentration = top_ten_votes / total_reference_votes * 100 if total_reference_votes else 0.0
    analysis_metrics = st.columns(4)
    analysis_metrics[0].metric(f"Votos {party_label}", f"{total_reference_votes:,}")
    analysis_metrics[1].metric("Participación estatal", f"{state_turnout:.1f}%")
    analysis_metrics[2].metric("Concentración en 10 municipios", f"{top_ten_concentration:.1f}%")
    analysis_metrics[3].metric("Municipios de prioridad alta", int((frame["prioridad"] == "Alta").sum()))

    volume, strength, opportunity = st.columns(3, gap="large")
    with volume:
        st.markdown("#### Mayor volumen de votos")
        st.caption("Municipios que más votos absolutos aportan a la opción seleccionada.")
        st.dataframe(
            frame.nlargest(5, "votos_referencia")[["municipio", "votos_referencia", "porcentaje_referencia"]].rename(columns={
                "municipio": "Municipio", "votos_referencia": "Votos", "porcentaje_referencia": "% votos válidos",
            }),
            use_container_width=True, hide_index=True,
        )
    with strength:
        st.markdown("#### Mayor fortaleza porcentual")
        st.caption("Municipios con mayor proporción de votos válidos para la opción.")
        st.dataframe(
            frame.nlargest(5, "porcentaje_referencia")[["municipio", "porcentaje_referencia", "votos_referencia"]].rename(columns={
                "municipio": "Municipio", "porcentaje_referencia": "% votos válidos", "votos_referencia": "Votos",
            }),
            use_container_width=True, hide_index=True,
        )
    with opportunity:
        st.markdown("#### Prioridad de revisión")
        st.caption("Territorios que combinan peso electoral, brecha de participación y presencia histórica.")
        st.dataframe(
            frame.nlargest(5, "indice_oportunidad")[["municipio", "prioridad", "indice_oportunidad", "lectura"]].rename(columns={
                "municipio": "Municipio", "prioridad": "Prioridad", "indice_oportunidad": "Índice", "lectura": "Lectura",
            }),
            use_container_width=True, hide_index=True,
        )
    st.info(
        f"**Lectura para el analista:** los 10 municipios con mayor volumen concentran {top_ten_concentration:.1f}% "
        f"de los votos de {party_label}. Compare esta concentración con la fortaleza porcentual y la prioridad de oportunidad "
        "antes de definir dónde profundizar la revisión territorial."
    )

    ranking_columns = ["municipio", "prioridad", "indice_oportunidad", "lista_nominal", "participacion_pct", "brecha_participacion_pp", "votos_referencia", "porcentaje_referencia", "cambio_pp", "lectura"]
    st.markdown("### Ranking de municipios")
    st.dataframe(
        frame[ranking_columns].head(15).rename(columns={
            "municipio": "Municipio", "prioridad": "Prioridad", "indice_oportunidad": "Índice", "lista_nominal": "Lista nominal",
            "participacion_pct": "Participación %", "brecha_participacion_pp": "Brecha participación (pp)", "votos_referencia": f"Votos {party_label}",
            "porcentaje_referencia": f"% {party_label}", "cambio_pp": f"Cambio vs. {prior_year} (pp)" if prior_year else "Cambio histórico", "lectura": "Lectura sugerida",
        }), use_container_width=True, hide_index=True,
    )
    st.caption(f"Fuente electoral: {election_type} {election_year}. Cartografía: {geometry_source}. Los valores INEGI se muestran como contexto municipal, no como causalidad electoral.")


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
    target_rows = query(
        """
        SELECT municipality, historical_reference_votes, target_votes, vote_gap, target_percentage
        FROM territorial_vote_targets
        WHERE profile_id = ? AND state = ? AND territorial_level = 'Municipio'
        ORDER BY updated_at DESC, id DESC
        """,
        (profile_id, selected_state),
    )
    # Los catálogos pueden conservar o quitar acentos (Juárez/Juarez). La
    # ficha debe encontrar la misma meta territorial en ambos casos.
    target = next(
        (
            row for row in target_rows
            if municipality_match_key(row["municipality"]) == municipality_match_key(priority["municipality"])
        ),
        None,
    )
    proposed_focus = current["strategic_focus"] if current else "Presencia y coordinación territorial"
    proposed_tactics = current["tactics"] if current else (
        "Definir responsables de cobertura municipal; realizar escucha documentada; "
        "organizar actividades informativas y revisar resultados con evidencia de campo."
    )
    proposed_measure = current["success_measure"] if current and current["success_measure"] else (
        "Cobertura de actividades, responsables asignados y evidencias registradas."
    )
    st.markdown("### Ficha de estrategia territorial")
    with st.container(border=True):
        head, status_card = st.columns([3, 1])
        head.markdown(f"#### {priority['municipality']}")
        head.caption("Siete elementos para pasar de la prioridad a la ejecución territorial.")
        status_card.metric("Prioridad", priority["priority_level"], f"Índice {priority['priority_index']:.1f}/100")
        st.markdown("**1. Meta territorial**")
        if target:
            target_cards = st.columns(3)
            target_cards[0].metric("Voto histórico", f"{int(target['historical_reference_votes']):,}")
            target_cards[1].metric("Meta territorial", f"{int(target['target_votes']):,}")
            target_cards[2].metric("Aporte requerido", f"{int(target['vote_gap']):,}")
        else:
            st.caption("No hay una meta municipal cargada todavía; la estrategia puede registrarse y completarse después.")
        ficha_left, ficha_right = st.columns(2)
        with ficha_left:
            st.markdown("**2. Diagnóstico**")
            st.write(priority["rationale"])
            st.markdown("**3. Línea estratégica**")
            st.write(proposed_focus)
            st.markdown("**4. Objetivo territorial**")
            st.write(current["objective"] if current else default_objective)
        with ficha_right:
            st.markdown("**5. Tácticas de trabajo**")
            st.write(proposed_tactics)
            st.markdown("**6. Indicadores de seguimiento**")
            st.write(proposed_measure)
            st.markdown("**7. Regla de ajuste**")
            st.write(
                "La coordinación revisa cobertura, evidencias y mediciones agregadas; "
                "si hay rezago, ajusta responsables, actividades o prioridad territorial."
            )
        st.caption(
            "La ficha usa datos agregados del territorio. No estima ni atribuye preferencias individuales. "
            "Guarda la estrategia para validarla y crear después su plan de acción."
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
        success_measure = st.text_area(
            "Cómo se medirá el avance", value=current["success_measure"] if current and current["success_measure"] else proposed_measure,
            height=130,
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
    initialize_staff()
    st.subheader("Planes de acción")
    st.button("Actualizar actividades y recepciones")
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
        territory_columns = st.columns(2)
        district = territory_columns[0].text_input("Distrito (opcional)", placeholder="Ejemplo: 09")
        electoral_section = territory_columns[1].text_input("Sección electoral (opcional)", placeholder="Ejemplo: 0474")
        submitted = st.form_submit_button("Agregar actividad", type="primary")
    if submitted:
        if not activity_name.strip():
            st.error("Escribe el nombre de la actividad antes de agregarla.")
        else:
            execute(
                """
                INSERT INTO territorial_action_plans
                (strategy_id, profile_id, state, municipality, district, electoral_section, activity_name,
                 activity_description, responsible, due_date, priority_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (strategy["id"], profile_id, selected_state, strategy["municipality"], district.strip() or None,
                 electoral_section.strip() or None, activity_name.strip(), activity_description.strip() or None,
                 responsible.strip() or None, str(due_date), priority_level),
            )
            st.success("Actividad agregada al plan de acción.")
            st.rerun()

    actions = query(
        """
        SELECT t.id, t.activity_name, t.activity_description, t.district, t.electoral_section, t.responsible,
               t.due_date, t.priority_level, t.status, t.evidence_note, t.completed_at,
               w.name AS trabajador_telegram, a.received_at AS recepcion_telegram_utc
        FROM territorial_action_plans t
        LEFT JOIN field_task_assignments a ON a.task_id = t.id
        LEFT JOIN field_workers w ON w.id = a.worker_id
        WHERE t.strategy_id = ?
        ORDER BY CASE t.priority_level WHEN 'Alta' THEN 1 WHEN 'Media' THEN 2 ELSE 3 END, t.due_date, t.id
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
    action_lookup = {f"#{row['id']} · {row['activity_name']} · {row['due_date'] or 'sin fecha'}": row for row in actions}
    selected_action_label = st.selectbox("Actualizar una actividad", list(action_lookup), key=f"update_action_{strategy['id']}")
    selected_action = action_lookup[selected_action_label]
    render_task_assignment(selected_action)
    render_task_reports(selected_action['id'])
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


def render_pmd_tracking() -> None:
    """Turn a municipal development plan into traceable territorial follow-up."""
    st.title("Seguimiento del PMD")
    st.caption(
        "Convierte el Plan Municipal de Desarrollo en un tablero de ejes, metas, avances, evidencia y percepción territorial. "
        "Los datos se distinguen como oficiales, reportados o pendientes de validación."
    )
    options = profile_options()
    if not options:
        st.info("Primero crea o selecciona un perfil para vincular un PMD.")
        return
    chosen_profile = st.selectbox("Perfil", list(options), key="pmd_profile")
    profile_id = options[chosen_profile]
    states = profile_states(profile_id)
    if not states:
        st.info("Asigna un territorio al perfil antes de configurar el PMD.")
        return
    selected_state = st.selectbox("Estado", states, key="pmd_state")
    municipal_rows = query(
        """SELECT DISTINCT municipality FROM territories
           WHERE state = ? AND territory_type = 'Municipio' AND TRIM(COALESCE(municipality, '')) <> ''
           ORDER BY municipality""",
        (selected_state,),
    )
    municipalities = [row["municipality"] for row in municipal_rows]
    if not municipalities:
        st.info("Aún no existe un catálogo municipal para este estado.")
        return
    default_municipality = "Mérida" if selected_state == "Yucatán" and "Mérida" in municipalities else municipalities[0]
    selected_municipality = st.selectbox(
        "Municipio", municipalities, index=municipalities.index(default_municipality), key="pmd_municipality"
    )
    plans = query(
        """SELECT * FROM development_plans
           WHERE profile_id=? AND state=? AND municipality=? ORDER BY updated_at DESC, id DESC""",
        (profile_id, selected_state, selected_municipality),
    )
    if not plans:
        st.info(
            "Aún no hay un PMD configurado para este perfil y municipio. Crea la ficha inicial; "
            "después incorpora los ejes y metas exactamente como aparezcan en el documento oficial."
        )
        with st.form("create_pmd_plan"):
            title = st.text_input("Nombre del plan", value=f"Plan Municipal de Desarrollo de {selected_municipality}")
            period = st.text_input("Periodo", value="2024-2027")
            source_url = st.text_input("Liga oficial del PMD (opcional)")
            notes = st.text_area("Nota de configuración", value="Pendiente de homologar ejes, metas e indicadores con el documento oficial.")
            if st.form_submit_button("Crear ficha del PMD", type="primary"):
                if not title.strip():
                    st.error("Escribe el nombre del plan.")
                else:
                    execute(
                        """INSERT INTO development_plans
                           (profile_id, state, municipality, title, period, source_url, notes)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (profile_id, selected_state, selected_municipality, title.strip(), period.strip() or None,
                         source_url.strip() or None, notes.strip() or None),
                    )
                    st.success("Ficha del PMD creada. Ahora puedes cargar sus ejes y metas.")
                    st.rerun()
        return

    plan_options = {f"{row['title']} · {row['period'] or 'sin periodo'}": row for row in plans}
    selected_plan = plan_options[st.selectbox("Plan configurado", list(plan_options), key="pmd_plan")]
    axes = query("SELECT * FROM development_plan_axes WHERE plan_id=? ORDER BY sort_order, name", (selected_plan["id"],))
    targets = query(
        """SELECT t.*, a.name AS axis_name FROM development_plan_targets t
           JOIN development_plan_axes a ON a.id=t.axis_id WHERE a.plan_id=? ORDER BY a.sort_order, t.name""",
        (selected_plan["id"],),
    )
    progress = query(
        """SELECT p.*, t.name AS target_name, a.name AS axis_name FROM development_plan_progress p
           JOIN development_plan_targets t ON t.id=p.target_id
           JOIN development_plan_axes a ON a.id=t.axis_id
           WHERE a.plan_id=? ORDER BY p.period DESC, a.sort_order, t.name""",
        (selected_plan["id"],),
    )
    reported_results = query(
        """SELECT r.*, a.name AS axis_name FROM development_plan_reported_results r
           LEFT JOIN development_plan_axes a ON a.id=r.axis_id
           WHERE r.plan_id=? ORDER BY r.period DESC, a.sort_order, r.title""",
        (selected_plan["id"],),
    )
    poa_plans = query(
        """SELECT * FROM operational_annual_plans
           WHERE profile_id=? AND state=? AND municipality=? ORDER BY year DESC, id DESC""",
        (profile_id, selected_state, selected_municipality),
    )
    funding_snapshots = query(
        """SELECT * FROM municipal_funding_snapshots
           WHERE profile_id=? AND state=? AND municipality=?
           ORDER BY fiscal_year DESC, cutoff_period DESC, source_name""",
        (profile_id, selected_state, selected_municipality),
    )
    financial_closures = query(
        """SELECT * FROM municipal_financial_closures
           WHERE profile_id=? AND state=? AND municipality=?
           ORDER BY fiscal_year DESC""",
        (profile_id, selected_state, selected_municipality),
    )
    cards = st.columns(6)
    cards[0].metric("Ejes", len(axes))
    cards[1].metric("Metas e indicadores", len(targets))
    cards[2].metric("POA anuales", len(poa_plans))
    cards[3].metric("Resultados oficiales publicados", len(reported_results))
    cards[4].metric("Avances numéricos registrados", len(progress))
    cards[5].metric("Avances con evidencia", sum(1 for row in progress if row["evidence_url"] or row["evidence_note"]))
    st.info(
        f"**Estatus:** {selected_plan['official_status']}. "
        "No se considera una meta como oficial hasta registrar su fuente o documento de respaldo."
    )
    if financial_closures:
        closure = financial_closures[0]
        income_progress = (
            (closure["collected_income"] / closure["approved_income_budget"] * 100)
            if closure["collected_income"] and closure["approved_income_budget"] else None
        )
        st.markdown(f"#### Cierre financiero {closure['fiscal_year']} · Mérida")
        st.caption(
            "Información anual publicada. El avance mostrado es recaudación frente a la Ley de Ingresos aprobada; "
            "el gasto se presenta como registro contable, no como devengado o pagado."
        )
        closure_cards = st.columns(5)
        closure_cards[0].metric("Ingreso aprobado", f"${closure['approved_income_budget']:,.0f}")
        closure_cards[1].metric("Ingreso recaudado", f"${closure['collected_income']:,.0f}")
        closure_cards[2].metric("Avance de recaudación", f"{income_progress:,.1f}%" if income_progress else "No disponible")
        closure_cards[3].metric("Gasto contable anual", f"${closure['accounting_expenses']:,.0f}")
        closure_cards[4].metric("Gasto de funcionamiento", f"${closure['operating_expenses']:,.0f}")
        with st.expander("Ver composición del cierre financiero", expanded=False):
            closure_breakdown = pd.DataFrame([{
                "Ingresos de gestión": closure["income_management"],
                "Impuestos": closure["taxes"],
                "Participaciones, aportaciones y convenios": closure["transfers_and_contributions"],
                "Servicios personales": closure["personnel_expenses"],
                "Gasto contable anual": closure["accounting_expenses"],
            }])
            st.dataframe(
                closure_breakdown.style.format("${:,.2f}"),
                use_container_width=True,
                hide_index=True,
            )
            st.link_button("Consultar fuente oficial de ingresos", closure["source_url"])
            if closure["notes"]:
                st.caption(closure["notes"])
    tabs = st.tabs([
        "1. Ejes", "2. Metas e indicadores", "3. POA anual", "4. Resultados publicados",
        "5. Avances y evidencia", "6. Lectura territorial"
    ])
    with tabs[0]:
        if axes:
            st.dataframe(pd.DataFrame([{
                "Orden": row["sort_order"], "Eje": row["name"], "Descripción": row["description"], "Estatus": row["status"]
            } for row in axes]), use_container_width=True, hide_index=True)
        else:
            st.caption("No hay ejes registrados. Cárgalos desde la estructura oficial del PMD.")
        with st.expander("Agregar eje de seguimiento"):
            with st.form(f"pmd_axis_{selected_plan['id']}", clear_on_submit=True):
                axis_name = st.text_input("Nombre del eje")
                axis_description = st.text_area("Descripción")
                axis_order = st.number_input("Orden", min_value=1, value=len(axes) + 1, step=1)
                axis_status = st.selectbox("Estatus", ["Por homologar a documento oficial", "Oficial documentado", "En seguimiento"])
                if st.form_submit_button("Guardar eje"):
                    if not axis_name.strip():
                        st.error("Escribe el nombre del eje.")
                    else:
                        execute(
                            """INSERT INTO development_plan_axes (plan_id, name, description, sort_order, status)
                               VALUES (?, ?, ?, ?, ?) ON CONFLICT(plan_id, name) DO UPDATE SET
                               description=excluded.description, sort_order=excluded.sort_order, status=excluded.status,
                               updated_at=CURRENT_TIMESTAMP""",
                            (selected_plan["id"], axis_name.strip(), axis_description.strip() or None, int(axis_order), axis_status),
                        )
                        st.success("Eje guardado.")
                        st.rerun()
    with tabs[1]:
        if targets:
            st.dataframe(pd.DataFrame([{
                "Eje": row["axis_name"], "Meta o indicador": row["name"], "Línea base": row["baseline_value"],
                "Meta": row["target_value"], "Actual": row["current_value"], "Unidad": row["unit"],
                "Frecuencia": row["frequency"], "Estatus": row["status"]
            } for row in targets]), use_container_width=True, hide_index=True)
        else:
            st.caption("Todavía no hay metas. Registra únicamente las que tengan fuente oficial identificable.")
        if axes:
            axis_options = {row["name"]: row for row in axes}
            with st.expander("Agregar meta o indicador"):
                with st.form(f"pmd_target_{selected_plan['id']}", clear_on_submit=True):
                    axis_label = st.selectbox("Eje", list(axis_options))
                    target_name = st.text_input("Meta o indicador")
                    target_columns = st.columns(3)
                    baseline = target_columns[0].text_input("Línea base (opcional)")
                    target_value = target_columns[1].text_input("Meta (opcional)")
                    unit = target_columns[2].text_input("Unidad", placeholder="personas, %, obras, días")
                    frequency = st.selectbox("Frecuencia de seguimiento", ["Mensual", "Trimestral", "Semestral", "Anual", "Por proyecto"])
                    territory_scope = st.text_input("Cobertura territorial", value=selected_municipality)
                    source_url = st.text_input("Liga de la fuente oficial")
                    target_notes = st.text_area("Nota metodológica")
                    if st.form_submit_button("Guardar meta o indicador"):
                        def optional_number(value: str):
                            try:
                                return float(value.replace(",", "")) if value.strip() else None
                            except ValueError:
                                return None
                        if not target_name.strip():
                            st.error("Escribe el nombre de la meta o indicador.")
                        elif (baseline.strip() and optional_number(baseline) is None) or (target_value.strip() and optional_number(target_value) is None):
                            st.error("La línea base y la meta deben ser números cuando se capturen.")
                        else:
                            execute(
                                """INSERT INTO development_plan_targets
                                   (axis_id, name, baseline_value, target_value, unit, frequency, territory_scope, status, source_url, notes)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(axis_id, name) DO UPDATE SET
                                   baseline_value=excluded.baseline_value, target_value=excluded.target_value, unit=excluded.unit,
                                   frequency=excluded.frequency, territory_scope=excluded.territory_scope, status=excluded.status,
                                   source_url=excluded.source_url, notes=excluded.notes, updated_at=CURRENT_TIMESTAMP""",
                                (axis_options[axis_label]["id"], target_name.strip(), optional_number(baseline), optional_number(target_value),
                                 unit.strip() or None, frequency, territory_scope.strip() or None,
                                 "Oficial documentado" if source_url.strip() else "Pendiente de fuente oficial",
                                 source_url.strip() or None, target_notes.strip() or None),
                            )
                            st.success("Meta guardada.")
                            st.rerun()
    with tabs[2]:
        st.markdown("#### Programa Operativo Anual")
        st.caption(
            "El POA convierte el PMD en ejecución anual: programa, dependencia responsable, meta anual, presupuesto y avance. "
            "No se infieren partidas o porcentajes cuando la fuente oficial no los publica."
        )
        if poa_plans:
            poa_options = {f"{row['title']} · {row['year']}": row for row in poa_plans}
            selected_poa = poa_options[st.selectbox("POA cargado", list(poa_options), key="pmd_poa")]
            poa_programs = query(
                """SELECT op.*, a.name AS axis_name FROM operational_annual_programs op
                   LEFT JOIN development_plan_axes a ON a.id=op.axis_id
                   WHERE op.poa_id=? ORDER BY a.sort_order, op.name""",
                (selected_poa["id"],),
            )
            programmed_detail_total = sum(row["allocated_budget"] or 0 for row in poa_programs)
            poa_cards = st.columns(4)
            poa_cards[0].metric(
                "Total anual del POA",
                f"${selected_poa['total_budget']:,.0f}" if selected_poa["total_budget"] else "Pendiente de publicación",
            )
            poa_cards[1].metric(
                "Programado en componentes cargados",
                f"${programmed_detail_total:,.0f}" if programmed_detail_total else "Sin componentes con monto",
            )
            poa_cards[2].metric("Programas cargados", len(poa_programs))
            poa_cards[3].metric("Estatus", selected_poa["status"])
            if not selected_poa["total_budget"] and programmed_detail_total:
                st.caption(
                    "El monto de componentes cargados corresponde a fuentes identificadas (por ahora, FORTAMUN); "
                    "no equivale al presupuesto total anual del POA municipal."
                )
            if selected_poa["source_url"]:
                st.link_button("Consultar fuente oficial del POA", selected_poa["source_url"])
            if selected_poa["notes"]:
                st.info(selected_poa["notes"])
            if poa_programs:
                funding_summary = pd.DataFrame([{
                    "Fuente": row["funding_source"] or "Sin identificar",
                    "Presupuesto programado": row["allocated_budget"] or 0,
                    "Programas": 1,
                } for row in poa_programs]).groupby("Fuente", as_index=False).agg(
                    {"Presupuesto programado": "sum", "Programas": "sum"}
                )
                st.markdown("##### Recursos programados por fuente")
                st.dataframe(funding_summary, use_container_width=True, hide_index=True)
                st.dataframe(pd.DataFrame([{
                    "Eje PMD": row["axis_name"] or "Por vincular", "Programa o componente": row["name"],
                    "Responsable": row["responsible_unit"], "Meta anual": row["annual_goal"], "Unidad": row["goal_unit"],
                    "Fuente": row["funding_source"], "Presupuesto asignado": row["allocated_budget"], "Ejercido": row["exercised_budget"],
                    "Avance %": row["execution_pct"], "Estatus": row["status"],
                } for row in poa_programs]), use_container_width=True, hide_index=True)
            else:
                if selected_poa["year"] == 2025 and selected_municipality == "Mérida":
                    st.markdown("##### Avance que se podrá consultar del cierre 2025")
                    st.caption(
                        "El ejercicio 2025 está identificado como cierre anual. Esta vista evita presentar porcentajes "
                        "sin respaldo: muestra exactamente qué está disponible y qué falta integrar."
                    )
                    coverage = pd.DataFrame([
                        {
                            "Información": "Estado Analítico de Ingresos",
                            "Permite ver": "Ingresos propios, participaciones, aportaciones y convenios recaudados",
                            "Estatus": "Fuente anual localizada",
                            "Para mostrar cifras": "Importar Excel oficial al 31 de diciembre de 2025",
                        },
                        {
                            "Información": "Estado Analítico de Egresos",
                            "Permite ver": "Presupuesto aprobado, modificado, devengado y pagado",
                            "Estatus": "Fuente anual localizada",
                            "Para mostrar cifras": "Importar Excel oficial al 31 de diciembre de 2025",
                        },
                        {
                            "Información": "Resultados físicos por programa",
                            "Permite ver": "Metas cumplidas, avance físico y rezagos por eje del PMD",
                            "Estatus": "Pendiente de localizar e importar reporte por programa",
                            "Para mostrar cifras": "Incorporar informe anual o fichas de resultados",
                        },
                    ])
                    st.dataframe(coverage, use_container_width=True, hide_index=True)
                    st.info(
                        "Cuando se importen los dos estados anuales, aquí aparecerán las cifras de recaudación y ejecución; "
                        "el avance físico se añadirá en cuanto exista una fuente oficial por programa."
                    )
                else:
                    st.caption("La fuente consultada confirma el POA y su alineación al PMD; falta importar su matriz detallada por programa.")
            st.markdown("##### Recursos recibidos o ministrados")
            st.caption("Importe efectivamente transferido al municipio al cierre del periodo indicado; no equivale al presupuesto ejercido.")
            if funding_snapshots:
                st.dataframe(pd.DataFrame([{
                    "Año": row["fiscal_year"], "Corte": row["cutoff_period"], "Fuente": row["source_name"],
                    "Tipo": row["source_class"], "Recibido / ministrado": row["amount_received"],
                    "Fuente oficial": row["source_url"], "Nota": row["notes"],
                } for row in funding_snapshots]), use_container_width=True, hide_index=True)
            else:
                st.caption("Aún no hay cortes de recursos ministrados cargados.")
            if axes:
                axis_options = {row["name"]: row for row in axes}
                with st.expander("Registrar programa y corte físico-financiero"):
                    with st.form(f"poa_program_{selected_poa['id']}", clear_on_submit=True):
                        program_axis = st.selectbox("Eje PMD relacionado", list(axis_options))
                        program_name = st.text_input("Programa o componente operativo")
                        program_unit = st.text_input("Dependencia responsable")
                        program_columns = st.columns(3)
                        annual_goal = program_columns[0].text_input("Meta anual")
                        goal_unit = program_columns[1].text_input("Unidad de la meta", placeholder="acciones, personas, obras")
                        funding_source = program_columns[2].text_input("Ramo o fuente", placeholder="Ramo 33 · FORTAMUN")
                        allocated_budget = st.text_input("Presupuesto aprobado")
                        cut_columns = st.columns(3)
                        exercised_budget = cut_columns[0].text_input("Presupuesto devengado o pagado")
                        execution_pct = cut_columns[1].text_input("Avance financiero %")
                        program_status = cut_columns[2].selectbox(
                            "Estatus del corte", ["Pendiente de avance", "Reportado", "Validado"]
                        )
                        program_source = st.text_input("Liga oficial del POA o informe financiero")
                        program_notes = st.text_area("Periodo de corte y nota metodológica")
                        if st.form_submit_button("Guardar programa y corte"):
                            def optional_number(value: str):
                                try:
                                    return float(value.replace(",", "")) if value.strip() else None
                                except ValueError:
                                    return None
                            numeric_inputs = [optional_number(v) for v in (annual_goal, allocated_budget, exercised_budget, execution_pct)]
                            if not program_name.strip() or not program_source.strip():
                                st.error("Indica el programa y su fuente oficial.")
                            elif any(raw.strip() and value is None for raw, value in zip(
                                (annual_goal, allocated_budget, exercised_budget, execution_pct), numeric_inputs
                            )):
                                st.error("Las metas, presupuestos y porcentajes deben ser números cuando se capturen.")
                            else:
                                execute(
                                    """INSERT INTO operational_annual_programs
                                       (poa_id, axis_id, name, responsible_unit, annual_goal, goal_unit, funding_source,
                                        allocated_budget, exercised_budget, execution_pct, status, source_url, notes)
                                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                       ON CONFLICT(poa_id, name) DO UPDATE SET
                                         axis_id=excluded.axis_id, responsible_unit=excluded.responsible_unit,
                                         annual_goal=excluded.annual_goal, goal_unit=excluded.goal_unit,
                                         funding_source=excluded.funding_source, allocated_budget=excluded.allocated_budget, exercised_budget=excluded.exercised_budget,
                                         execution_pct=excluded.execution_pct, status=excluded.status,
                                         source_url=excluded.source_url, notes=excluded.notes, updated_at=CURRENT_TIMESTAMP""",
                                    (selected_poa["id"], axis_options[program_axis]["id"], program_name.strip(), program_unit.strip() or None,
                                     *numeric_inputs[:1], goal_unit.strip() or None, funding_source.strip() or None, *numeric_inputs[1:], program_status,
                                     program_source.strip(), program_notes.strip() or None),
                                )
                                st.success("Programa y corte guardados.")
                                st.rerun()
        else:
            st.caption("No hay POA anual cargado para este municipio.")
        with st.expander("Registrar POA anual"):
            with st.form(f"poa_plan_{selected_plan['id']}", clear_on_submit=True):
                poa_title = st.text_input("Nombre del POA", value=f"Programa Operativo Anual de {selected_municipality}")
                poa_year = st.number_input("Año", min_value=2020, max_value=2035, value=2026, step=1)
                poa_budget = st.text_input("Presupuesto total (opcional)")
                poa_source = st.text_input("Liga oficial del POA")
                poa_notes = st.text_area("Nota de fuente o alcance")
                if st.form_submit_button("Guardar POA"):
                    try:
                        budget_value = float(poa_budget.replace(",", "")) if poa_budget.strip() else None
                    except ValueError:
                        budget_value = None
                    if not poa_title.strip() or not poa_source.strip():
                        st.error("Indica el nombre y la liga oficial del POA.")
                    elif poa_budget.strip() and budget_value is None:
                        st.error("El presupuesto debe ser numérico cuando se capture.")
                    else:
                        execute(
                            """INSERT INTO operational_annual_plans
                               (profile_id, state, municipality, title, year, total_budget, status, source_url, notes)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                               ON CONFLICT(profile_id, state, municipality, year, title) DO UPDATE SET
                                 total_budget=excluded.total_budget, status=excluded.status, source_url=excluded.source_url,
                                 notes=excluded.notes, updated_at=CURRENT_TIMESTAMP""",
                            (profile_id, selected_state, selected_municipality, poa_title.strip(), int(poa_year), budget_value,
                             "Oficial documentado" if poa_source.strip() else "Pendiente de fuente oficial", poa_source.strip(), poa_notes.strip() or None),
                        )
                        st.success("POA anual guardado.")
                        st.rerun()
    with tabs[3]:
        st.markdown("#### Resultados publicados por el Ayuntamiento")
        st.caption(
            "Son hechos o cifras reportados oficialmente. No equivalen por sí solos al porcentaje de cumplimiento de una meta del PMD; "
            "ese porcentaje solo se muestra cuando la fuente publica la medición comparable."
        )
        if reported_results:
            result_frame = pd.DataFrame([{
                "Periodo": row["period"], "Eje": row["axis_name"] or "Transversal",
                "Resultado publicado": row["title"], "Valor": row["reported_value"],
                "Unidad": row["unit"], "Cobertura": row["territory_scope"],
                "Estatus": row["status"], "Fuente": row["evidence_url"], "Nota": row["evidence_note"],
            } for row in reported_results])
            st.dataframe(result_frame, use_container_width=True, hide_index=True)
        else:
            st.caption("Aún no hay resultados públicos cargados para este plan.")
        if axes:
            axis_options = {row["name"]: row for row in axes}
            with st.expander("Registrar resultado publicado"):
                with st.form(f"pmd_result_{selected_plan['id']}", clear_on_submit=True):
                    result_axis = st.selectbox("Eje relacionado", ["Transversal"] + list(axis_options))
                    result_period = st.text_input("Periodo", placeholder="Segundo Informe 2026")
                    result_title = st.text_input("Resultado publicado")
                    result_columns = st.columns(3)
                    result_value = result_columns[0].text_input("Valor (opcional)")
                    result_unit = result_columns[1].text_input("Unidad", placeholder="comisarías, espacios, familias")
                    result_scope = result_columns[2].text_input("Cobertura", value=selected_municipality)
                    result_url = st.text_input("Liga de la publicación oficial")
                    result_note = st.text_area("Qué informa la fuente y cómo debe interpretarse")
                    if st.form_submit_button("Guardar resultado publicado"):
                        try:
                            numeric_result = float(result_value.replace(",", "")) if result_value.strip() else None
                        except ValueError:
                            numeric_result = None
                        if not result_period.strip() or not result_title.strip() or not result_url.strip():
                            st.error("Indica periodo, resultado y liga oficial.")
                        elif result_value.strip() and numeric_result is None:
                            st.error("El valor debe ser numérico cuando se capture.")
                        else:
                            execute(
                                """INSERT INTO development_plan_reported_results
                                   (plan_id, axis_id, period, title, reported_value, unit, territory_scope, evidence_url, evidence_note)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                   ON CONFLICT(plan_id, period, title) DO UPDATE SET
                                     axis_id=excluded.axis_id, reported_value=excluded.reported_value, unit=excluded.unit,
                                     territory_scope=excluded.territory_scope, evidence_url=excluded.evidence_url,
                                     evidence_note=excluded.evidence_note, updated_at=CURRENT_TIMESTAMP""",
                                (selected_plan["id"], axis_options[result_axis]["id"] if result_axis != "Transversal" else None,
                                 result_period.strip(), result_title.strip(), numeric_result, result_unit.strip() or None,
                                 result_scope.strip() or None, result_url.strip(), result_note.strip() or None),
                            )
                            st.success("Resultado oficial publicado guardado.")
                            st.rerun()
    with tabs[4]:
        if progress:
            st.dataframe(pd.DataFrame([{
                "Periodo": row["period"], "Eje": row["axis_name"], "Meta": row["target_name"], "Territorio": row["territory_name"],
                "Avance físico": row["physical_value"], "Avance financiero": row["financial_amount"], "Avance %": row["progress_pct"],
                "Estatus": row["status"], "Evidencia": row["evidence_note"]
            } for row in progress]), use_container_width=True, hide_index=True)
        else:
            st.caption("No hay avances registrados. El primer avance debe incluir periodo, territorio y evidencia.")
        if targets:
            target_options = {f"{row['axis_name']} · {row['name']}": row for row in targets}
            with st.expander("Registrar avance"):
                with st.form(f"pmd_progress_{selected_plan['id']}", clear_on_submit=True):
                    target_label = st.selectbox("Meta o indicador", list(target_options))
                    progress_columns = st.columns(3)
                    report_period = progress_columns[0].text_input("Periodo", placeholder="2026-T3")
                    territory_name = progress_columns[1].text_input("Zona, colonia o comisaría", value=selected_municipality)
                    report_status = progress_columns[2].selectbox("Estatus", ["Reportado", "Validado", "Con observaciones"])
                    physical_value = st.text_input("Avance físico (opcional)")
                    financial_amount = st.text_input("Avance financiero (opcional)")
                    progress_pct = st.text_input("Porcentaje de avance (opcional)")
                    evidence_url = st.text_input("Liga de evidencia")
                    evidence_note = st.text_area("Evidencia o nota de avance")
                    perception_note = st.text_area("Percepción ciudadana o hallazgo territorial")
                    if st.form_submit_button("Guardar avance"):
                        def optional_number(value: str):
                            try:
                                return float(value.replace(",", "")) if value.strip() else None
                            except ValueError:
                                return None
                        numeric_values = [optional_number(value) for value in (physical_value, financial_amount, progress_pct)]
                        if not report_period.strip():
                            st.error("Escribe el periodo del avance.")
                        elif any(raw.strip() and parsed is None for raw, parsed in zip((physical_value, financial_amount, progress_pct), numeric_values)):
                            st.error("Los campos de avance deben ser numéricos cuando se capturen.")
                        else:
                            execute(
                                """INSERT INTO development_plan_progress
                                   (target_id, period, territory_name, physical_value, financial_amount, progress_pct, status, evidence_url, evidence_note, perception_note)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(target_id, period, territory_name) DO UPDATE SET
                                   physical_value=excluded.physical_value, financial_amount=excluded.financial_amount,
                                   progress_pct=excluded.progress_pct, status=excluded.status, evidence_url=excluded.evidence_url,
                                   evidence_note=excluded.evidence_note, perception_note=excluded.perception_note, updated_at=CURRENT_TIMESTAMP""",
                                (target_options[target_label]["id"], report_period.strip(), territory_name.strip() or None, *numeric_values,
                                 report_status, evidence_url.strip() or None, evidence_note.strip() or None, perception_note.strip() or None),
                            )
                            st.success("Avance guardado.")
                            st.rerun()
    with tabs[5]:
        st.markdown("#### Cómo se usa territorialmente")
        st.write(
            "Selecciona una meta, registra el avance por colonia, zona o comisaría y añade la evidencia. "
            "Después compara ese avance con los mensajes ciudadanos, la escucha digital y las recorridas de campo."
        )
        st.markdown(
            "**Lectura recomendada:** una meta con avance reportado pero sin evidencia o con quejas recurrentes "
            "debe pasar a revisión; una meta validada y bien percibida puede respaldar la narrativa de gestión."
        )


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


@st.cache_data(show_spinner=False)
def extract_dictamen_sections(file_path: str) -> list[dict]:
    """Obtiene los capítulos numerados de un PDF de dictamen para lectura interna."""
    reader = PdfReader(file_path)
    pages = [page.extract_text() or "" for page in reader.pages]
    document_text = "\f".join(pages)
    pattern = re.compile(r"(?m)^(\d{1,2})\.\s+([^\n]+)$")
    matches = []
    seen_numbers = set()
    for match in pattern.finditer(document_text):
        number = int(match.group(1))
        title = match.group(2).strip()
        # Los dictámenes usan capítulos numerados. Evitamos duplicar líneas de
        # tablas que eventualmente puedan iniciar igual que un capítulo.
        if number < 1 or number > 20 or number in seen_numbers or len(title) < 5:
            continue
        seen_numbers.add(number)
        matches.append((match, number, title))

    sections = []
    for index, (match, number, title) in enumerate(matches):
        end = matches[index + 1][0].start() if index + 1 < len(matches) else len(document_text)
        content = document_text[match.end():end].replace("\f", "\n").strip()
        sections.append({
            "number": number,
            "title": title,
            "page": document_text[:match.start()].count("\f") + 1,
            "content": content,
        })
    return sections


@st.cache_data(show_spinner=False)
def render_dictamen_pages(file_path: str, first_page: int, last_page: int) -> list[bytes]:
    """Renderiza las páginas originales para conservar el diseño del dictamen."""
    document = pymupdf.open(file_path)
    try:
        pages = []
        for page_number in range(first_page - 1, min(last_page, len(document))):
            page = document.load_page(page_number)
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.65, 1.65), alpha=False)
            pages.append(pixmap.tobytes("png"))
        return pages
    finally:
        document.close()


def render_dictamen_reader() -> None:
    """Navegación de lectura por capítulos de los dictámenes PDF cargados."""
    st.markdown(
        """
        <section class="dictamen-reader-hero">
          <small>EXPEDIENTE DE CANDIDATURA · LECTURA DOCUMENTAL</small>
          <h2>Recorrido del dictamen</h2>
          <p>Selecciona un capítulo y consulta la página original, sin perder su formato, tablas ni diseño.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    documents = query(
        """
        SELECT d.id, d.title, d.file_path, d.imported_at, p.name AS profile_name
        FROM reference_documents d
        JOIN profiles p ON p.id = d.profile_id
        WHERE d.document_type = 'Dictamen de viabilidad'
        ORDER BY p.name, d.imported_at DESC
        """
    )
    pdf_documents = [
        row for row in documents
        if row["file_path"] and Path(row["file_path"]).suffix.lower() == ".pdf" and Path(row["file_path"]).exists()
    ]
    if not pdf_documents:
        st.info("Aún no hay dictámenes PDF cargados para recorrer por secciones.")
        return

    labels = {
        f"{row['profile_name']} · {row['title']}": row
        for row in pdf_documents
    }
    selected_label = st.selectbox("Dictamen", list(labels), key="dictamen_reader_document")
    document = labels[selected_label]
    with st.spinner("Organizando capítulos del dictamen..."):
        sections = extract_dictamen_sections(document["file_path"])
    if not sections:
        st.warning("No fue posible identificar capítulos numerados en este PDF.")
        return

    left, right = st.columns([0.9, 2.55], gap="large")
    with left:
        st.metric("Secciones disponibles", len(sections))
        st.caption(f"Perfil: {document['profile_name']}")
        st.markdown("##### Índice del dictamen")
        section_options = {
            f"{item['number']:02}. {item['title']} · p. {item['page']}": item
            for item in sections
        }
        selected_section_label = st.radio(
            "Capítulos",
            list(section_options),
            key=f"dictamen_reader_section_{document['id']}",
            label_visibility="collapsed",
        )
        with open(document["file_path"], "rb") as source_file:
            st.download_button(
                "Descargar dictamen PDF",
                data=source_file.read(),
                file_name=Path(document["file_path"]).name,
                mime="application/pdf",
                key=f"download_dictamen_{document['id']}",
            )

    selected_section = section_options[selected_section_label]
    section_index = sections.index(selected_section)
    next_page = sections[section_index + 1]["page"] - 1 if section_index + 1 < len(sections) else 0
    if next_page < selected_section["page"]:
        next_page = selected_section["page"]
    if not next_page:
        with pymupdf.open(document["file_path"]) as pdf_document:
            next_page = len(pdf_document)
    page_images = render_dictamen_pages(document["file_path"], selected_section["page"], next_page)
    with right:
        st.markdown(f"### {selected_section['number']}. {selected_section['title']}")
        page_caption = f"página {selected_section['page']}" if next_page == selected_section["page"] else f"páginas {selected_section['page']} a {next_page}"
        st.markdown(
            f'<div class="dictamen-reading-note">Vista del documento original · {page_caption}. Usa el índice para avanzar por los capítulos.</div>',
            unsafe_allow_html=True,
        )
        for page_position, image in enumerate(page_images, start=selected_section["page"]):
            st.image(image, caption=f"{document['profile_name']} · Dictamen · página {page_position}", use_container_width=True)


def render_viability_opinion() -> None:
    """Build a traceable viability brief from locally stored evidence."""
    st.subheader("Dictamen de viabilidad")
    st.caption(
        "Expediente de lectura integral. Resume la evidencia disponible; no predice resultados electorales "
        "ni sustituye las decisiones políticas o jurídicas."
    )
    profile_rows = query(
        """
        SELECT p.id, p.name, p.actor_type, COUNT(pub.id) AS publicaciones
        FROM profiles p
        LEFT JOIN publications pub ON pub.profile_id = p.id
        WHERE p.active = 1
        GROUP BY p.id, p.name, p.actor_type
        ORDER BY publicaciones DESC, p.name
        """
    )
    if not profile_rows:
        st.info("Primero registra un perfil para abrir su expediente de viabilidad.")
        return
    profile_labels = {
        f"{row['name']} · {row['actor_type']}": row for row in profile_rows
    }
    selected_label = st.selectbox("Perfil del dictamen", list(profile_labels), key="viability_profile")
    profile = profile_labels[selected_label]
    profile_id = profile["id"]
    states = profile_states(profile_id)
    state_options = ["Todos los estados", *states] if states else ["Todos los estados"]
    selected_state = st.selectbox("Territorio de lectura", state_options, key="viability_state")

    positions = query(
        """
        SELECT office, condition, party_or_coalition, starts_at, ends_at, is_current
        FROM profile_positions WHERE profile_id = ?
        ORDER BY is_current DESC, starts_at DESC
        """,
        (profile_id,),
    )
    sources = query("SELECT COUNT(*) AS total FROM sources WHERE profile_id = ? AND active = 1", (profile_id,))[0]["total"]
    publications = query("SELECT COUNT(*) AS total FROM publications WHERE profile_id = ?", (profile_id,))[0]["total"]
    analysed = query(
        "SELECT COUNT(*) AS total FROM analyses a JOIN publications p ON p.id = a.publication_id WHERE p.profile_id = ?",
        (profile_id,),
    )[0]["total"]
    territories = query("SELECT COUNT(*) AS total FROM profile_territories WHERE profile_id = ?", (profile_id,))[0]["total"]
    state_filter = "" if selected_state == "Todos los estados" else " AND pt.state = ?"
    territory_params = (profile_id,) if selected_state == "Todos los estados" else (profile_id, selected_state)
    linked = query(
        f"""
        SELECT COUNT(DISTINCT p.id) AS total, COUNT(DISTINCT pt.municipality) AS municipios
        FROM publications p JOIN publication_territories pt ON pt.publication_id = p.id
        WHERE p.profile_id = ? {state_filter}
        """,
        territory_params,
    )[0]
    election_filter = "" if selected_state == "Todos los estados" else " WHERE state = ?"
    election_params = () if selected_state == "Todos los estados" else (selected_state,)
    election_rows = query(f"SELECT COUNT(*) AS total, COUNT(DISTINCT municipality) AS municipios FROM territorial_election_results{election_filter}", election_params)[0]
    election_payload_rows = query(
        f"SELECT election_year, payload FROM territorial_election_results{election_filter}", election_params
    )
    mc_by_year: dict[int, float] = {}
    total_votes_by_year: dict[int, float] = {}
    valid_votes_by_year: dict[int, float] = {}
    for result_row in election_payload_rows:
        try:
            result_payload = json.loads(result_row["payload"])
        except (TypeError, ValueError, json.JSONDecodeError):
            result_payload = {}
        year = int(result_row["election_year"])
        mc_by_year[year] = mc_by_year.get(year, 0.0) + float(result_payload.get("votes_mc") or 0)
        total_votes_by_year[year] = total_votes_by_year.get(year, 0.0) + float(result_payload.get("votes_total") or 0)
        valid_votes_by_year[year] = valid_votes_by_year.get(year, 0.0) + float(result_payload.get("numero_votos_validos") or 0)
    latest_election_year = max(mc_by_year) if mc_by_year else None
    mc_vote_floor = mc_by_year.get(latest_election_year, 0.0) if latest_election_year else 0.0
    mc_vote_share = (mc_vote_floor / total_votes_by_year[latest_election_year] * 100) if latest_election_year and total_votes_by_year.get(latest_election_year) else 0.0
    valid_vote_reference = valid_votes_by_year.get(latest_election_year, 0.0) if latest_election_year else 0.0
    competitive_vote_goal = round(valid_vote_reference * 0.35)
    close_win_vote_goal = round(valid_vote_reference * 0.38)
    robust_win_vote_goal = round(valid_vote_reference * 0.40)
    indicator_filter = "" if selected_state == "Todos los estados" else " WHERE state = ?"
    indicator_rows = query(f"SELECT COUNT(*) AS total, COUNT(DISTINCT municipality) AS municipios FROM territorial_indicators{indicator_filter}", election_params)[0]
    sentiment = query(
        """
        SELECT
          SUM(CASE WHEN a.sentiment = 'Positivo' THEN 1 ELSE 0 END) AS positivas,
          SUM(CASE WHEN a.sentiment = 'Negativo' THEN 1 ELSE 0 END) AS negativas,
          SUM(CASE WHEN a.urgency IN ('Alta', 'Crítica') THEN 1 ELSE 0 END) AS urgentes
        FROM analyses a JOIN publications p ON p.id = a.publication_id
        WHERE p.profile_id = ?
        """,
        (profile_id,),
    )[0]
    action_summary = query(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN tap.status IN ('Pendiente', 'En curso') THEN 1 ELSE 0 END) AS activas
        FROM territorial_action_plans tap
        JOIN territorial_strategies ts ON ts.id = tap.strategy_id
        WHERE ts.profile_id = ?
        """,
        (profile_id,),
    )[0]
    strategy_total = query(
        "SELECT COUNT(*) AS total FROM territorial_strategies WHERE profile_id = ?",
        (profile_id,),
    )[0]["total"]
    completed_actions = query(
        """
        SELECT COUNT(*) AS total FROM territorial_action_plans tap
        JOIN territorial_strategies ts ON ts.id = tap.strategy_id
        WHERE ts.profile_id = ? AND tap.status = 'Completada'
        """,
        (profile_id,),
    )[0]["total"]
    competitors = query(
        "SELECT name, party_or_coalition, condition, territory, positioning_note, source_url, updated_at FROM viability_competitors WHERE profile_id = ? ORDER BY updated_at DESC",
        (profile_id,),
    )
    surveys = query(
        "SELECT name, pollster, territory, fieldwork_date, sample_size, profile_result_pct, source_url, notes FROM viability_surveys WHERE profile_id = ? ORDER BY fieldwork_date DESC, id DESC",
        (profile_id,),
    )
    structure_records = query(
        "SELECT state, municipality, district, electoral_section, locality, responsible, coverage_status, evidence_note FROM viability_structure_records WHERE profile_id = ? ORDER BY state, municipality, district, electoral_section",
        (profile_id,),
    )
    verified_structure = any(
        row["coverage_status"] in {"Registrada", "Activa"} for row in structure_records
    )
    coalition_scenarios = query(
        "SELECT scenario_name, parties, scope, status, notes, source_url FROM viability_coalition_scenarios WHERE profile_id = ? ORDER BY updated_at DESC",
        (profile_id,),
    )
    resources = query(
        "SELECT category, availability_status, amount_note, source_url, notes FROM viability_resource_records WHERE profile_id = ? ORDER BY updated_at DESC",
        (profile_id,),
    )
    formal_conclusion = query(
        "SELECT assessment_status, strengths, risks, conditions, next_step FROM viability_conclusions WHERE profile_id = ?",
        (profile_id,),
    )
    formal_conclusion = formal_conclusion[0] if formal_conclusion else None
    dictamen_documents = query(
        """
        SELECT id, title, file_path, imported_at
        FROM reference_documents
        WHERE profile_id = ? AND document_type = 'Dictamen de viabilidad'
        ORDER BY imported_at DESC
        """,
        (profile_id,),
    )
    stored_variable_assessments = query(
        "SELECT variable_code, status, evidence_note, source_url, metric_label, target_value, actual_value, metric_unit, updated_at FROM viability_variable_assessments WHERE profile_id = ?",
        (profile_id,),
    )
    assessment_by_code = {row["variable_code"]: row for row in stored_variable_assessments}

    # Las 20 variables hacen visible qué parte del dictamen está respaldada y
    # qué información sigue pendiente. Una variable puede nutrirse de los
    # módulos existentes, sin duplicar datos ni inferir información ausente.
    viability_variables = [
        ("perfil", "1. Perfil del aspirante", bool(positions), "Cargo, condición, partido o coalición y periodo."),
        ("eleccion", "2. Elección objetivo", bool(positions), "Proceso y cargo para el que se evalúa la viabilidad."),
        ("territorio", "3. Territorio de cobertura", bool(territories), "Estado, distrito, municipio, sección o localidad asociados."),
        ("electoral", "4. Antecedente electoral", bool(election_rows["total"]), "Resultados electorales cargados para el territorio."),
        ("sociodemografico", "5. Contexto sociodemográfico", bool(indicator_rows["total"]), "Indicadores territoriales disponibles de INEGI."),
        ("fuentes", "6. Fuentes verificables", bool(sources), "Fuentes activas con trazabilidad."),
        ("comunicacion", "7. Evidencia de comunicación", bool(publications), "Noticias, publicaciones y documentos vinculados al perfil."),
        ("sentimiento", "8. Sentimiento y conversación", bool(analysed), "Análisis disponible sobre menciones y conversación pública."),
        ("temas", "9. Temas ciudadanos", bool(analysed), "Temas, necesidades y urgencias identificados en la evidencia."),
        ("posicionamiento", "10. Posicionamiento e imagen", bool(analysed or surveys), "Señales de percepción pública o estudios registrados."),
        ("competencia", "11. Competencia", bool(competitors), "Competidores o referentes comparables documentados."),
        ("encuestas", "12. Encuestas y mediciones", bool(surveys), "Estudios con fecha, metodología, muestra y fuente."),
        ("estructura", "13. Estructura territorial", verified_structure, "Cobertura, responsables y evidencia por territorio."),
        ("organizacion", "14. Organización operativa", bool(verified_structure or action_summary["total"]), "Capacidad de coordinación y operación comprobable."),
        ("coaliciones", "15. Escenarios de coalición", bool(coalition_scenarios), "Hipótesis o definiciones formales de alianzas."),
        ("recursos", "16. Recursos y capacidad", bool(resources), "Equipo, logística, comunicación o recursos documentados."),
        ("estrategia", "17. Estrategia territorial", bool(action_summary["total"]), "Líneas de acción vinculadas al perfil y territorio."),
        ("plan_accion", "18. Plan de acción", bool(action_summary["total"]), "Actividades y responsables registrados."),
        ("seguimiento", "19. Seguimiento y alertas", bool(action_summary["activas"] or sentiment["urgentes"]), "Acciones activas o alertas que requieren seguimiento."),
        ("conclusion", "20. Conclusión de viabilidad", bool(formal_conclusion), "Dictamen formal con fortalezas, riesgos y condiciones."),
    ]
    viability_variables = [
        (code, name, complete or assessment_by_code.get(code, {}).get("status") in {"Documentada", "Validada"}, description)
        for code, name, complete, description in viability_variables
    ]
    coverage_points = sum(1 for _, _, complete, _ in viability_variables if complete)
    coverage_pct = round(coverage_points / len(viability_variables) * 100)
    election_years = query(
        f"SELECT COUNT(DISTINCT election_year) AS total FROM territorial_election_results{election_filter}", election_params
    )[0]["total"]
    distinct_topics = query(
        """
        SELECT COUNT(DISTINCT NULLIF(TRIM(a.topic), '')) AS total
        FROM analyses a JOIN publications p ON p.id = a.publication_id
        WHERE p.profile_id = ?
        """,
        (profile_id,),
    )[0]["total"]
    responsible_count = sum(1 for row in structure_records if (row["responsible"] or "").strip())
    goal_defaults = {
        "perfil": ("Expediente de perfil completo", 1, 1, "expediente"),
        "eleccion": ("Elección objetivo definida", 1 if positions else 0, 1, "elección"),
        "territorio": ("Municipios de cobertura definidos", len(structure_records), max(len(structure_records), 1), "municipios"),
        "electoral": ("Procesos electorales comparables", election_years, 2, "elecciones"),
        "sociodemografico": ("Municipios con indicadores", int(indicator_rows["municipios"] or 0), max(int(election_rows["municipios"] or 0), 1), "municipios"),
        "fuentes": ("Fuentes activas", int(sources or 0), 10, "fuentes"),
        "comunicacion": ("Registros de comunicación analizados", int(publications or 0), 100, "registros"),
        "sentimiento": ("Registros con sentimiento analizado", int(analysed or 0), max(int(publications or 0), 1), "registros"),
        "temas": ("Temas ciudadanos identificados", int(distinct_topics or 0), 8, "temas"),
        "posicionamiento": ("Mediciones de posicionamiento", len(surveys), 3, "mediciones"),
        "competencia": ("Competidores documentados", len(competitors), 4, "perfiles"),
        "encuestas": ("Encuestas con ficha técnica", len(surveys), 3, "estudios"),
        "estructura": ("Municipios con responsable confirmado", responsible_count, max(len(structure_records), 1), "municipios"),
        "organizacion": ("Niveles operativos habilitados", 1 if responsible_count else 0, 5, "niveles"),
        "coaliciones": ("Escenarios de coalición evaluados", len(coalition_scenarios), 3, "escenarios"),
        "recursos": ("Categorías de capacidad documentadas", len(resources), 5, "categorías"),
        "estrategia": ("Estrategias territoriales registradas", int(strategy_total or 0), max(len(structure_records), 1), "estrategias"),
        "plan_accion": ("Actividades completadas", int(completed_actions or 0), 100, "actividades"),
        "seguimiento": ("Actividades activas con seguimiento", int(action_summary["activas"] or 0), 100, "actividades"),
        "conclusion": ("Dictamen formal aprobado", 1 if formal_conclusion else 0, 1, "dictamen"),
    }
    goal_rows = []
    for code, name, _, description in viability_variables:
        stored = assessment_by_code.get(code, {})
        default_label, automatic_actual, default_target, default_unit = goal_defaults[code]
        actual = stored.get("actual_value")
        target = stored.get("target_value")
        actual = float(automatic_actual if actual is None else actual)
        target = float(default_target if target is None else target)
        progress = min(actual / target * 100, 100) if target > 0 else 0
        goal_rows.append({
            "code": code, "Variable": name, "Indicador": stored.get("metric_label") or default_label,
            "Actual": actual, "Meta": target, "Unidad": stored.get("metric_unit") or default_unit,
            "Avance": progress, "Alcance": description,
        })
    goal_progress_pct = round(sum(row["Avance"] for row in goal_rows) / len(goal_rows))
    coverage_label = "Sólida" if coverage_pct >= 75 else "En desarrollo" if coverage_pct >= 45 else "Inicial"
    metric_a, metric_b, metric_c, metric_d, metric_e = st.columns(5)
    metric_a.metric("Avance de metas", f"{goal_progress_pct}%", "Promedio de 20 medidores")
    metric_b.metric("Registros y análisis", f"{int(publications or 0):,} / {int(analysed or 0):,}")
    metric_c.metric("Municipios con evidencia", int(linked["municipios"] or 0))
    metric_d.metric("Alertas de atención", int(sentiment["urgentes"] or 0))
    metric_e.metric("Evidencia disponible", f"{coverage_points}/20", coverage_label)

    st.markdown("### Resumen del perfil")
    if positions:
        position = positions[0]
        position_parts = [position["office"], position["condition"], position["party_or_coalition"]]
        st.info(" · ".join(part for part in position_parts if part) or "Sin cargo o condición registrados.")
    else:
        st.warning("Registra cargo, condición y partido o coalición en el perfil para completar el expediente.")

    tabs = st.tabs([
        "Conclusión", "20 variables", "Electoral y territorial", "Posicionamiento", "Competencia", "Encuestas",
        "Estructura territorial", "Escenarios y coaliciones", "Recursos", "Organización", "Riesgos y pendientes"
    ])
    with tabs[0]:
        st.markdown("#### Conclusión de viabilidad basada en evidencia")
        st.write(
            f"El expediente de **{profile['name']}** tiene una cobertura **{coverage_label.lower()}**: "
            f"{int(sources or 0)} fuentes activas, {int(publications or 0):,} registros, "
            f"{int(election_rows['municipios'] or 0)} municipios con resultado electoral cargado y "
            f"{int(indicator_rows['municipios'] or 0)} municipios con indicadores disponibles."
        )
        st.caption("La conclusión cambia conforme se agregan fuentes, resultados, indicadores, encuestas y evidencias de campo.")
        if dictamen_documents:
            st.markdown("#### Dictámenes incorporados")
            for document in dictamen_documents:
                document_path = Path(document["file_path"])
                if document_path.exists():
                    st.download_button(
                        f"Descargar: {document['title']}",
                        data=document_path.read_bytes(),
                        file_name=document_path.name,
                        mime="application/pdf" if document_path.suffix.casefold() == ".pdf" else "text/html",
                        key=f"viability_document_{document['id']}",
                    )
                else:
                    st.warning(f"No se encuentra el documento integrado: {document_path.name}")
        st.markdown("#### Conclusión formal del dictamen")
        with st.form(f"conclusion_form_{profile_id}"):
            conclusion_statuses = ["En elaboración", "Viable con evidencia actual", "Viable con condiciones", "Requiere fortalecimiento", "Información insuficiente"]
            current_status = formal_conclusion["assessment_status"] if formal_conclusion else "En elaboración"
            conclusion_status = st.selectbox(
                "Estatus del dictamen", conclusion_statuses,
                index=conclusion_statuses.index(current_status) if current_status in conclusion_statuses else 0,
            )
            conclusion_strengths = st.text_area("Fortalezas verificables", value=(formal_conclusion["strengths"] or "") if formal_conclusion else "")
            conclusion_risks = st.text_area("Riesgos y condiciones", value=(formal_conclusion["risks"] or "") if formal_conclusion else "")
            conclusion_conditions = st.text_area("Condiciones para avanzar", value=(formal_conclusion["conditions"] or "") if formal_conclusion else "")
            conclusion_next = st.text_area("Siguiente paso de validación", value=(formal_conclusion["next_step"] or "") if formal_conclusion else "")
            if st.form_submit_button("Guardar conclusión formal"):
                execute(
                    """
                    INSERT INTO viability_conclusions (profile_id, assessment_status, strengths, risks, conditions, next_step, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(profile_id) DO UPDATE SET
                      assessment_status = excluded.assessment_status, strengths = excluded.strengths,
                      risks = excluded.risks, conditions = excluded.conditions,
                      next_step = excluded.next_step, updated_at = CURRENT_TIMESTAMP
                    """,
                    (profile_id, conclusion_status, conclusion_strengths.strip(), conclusion_risks.strip(), conclusion_conditions.strip(), conclusion_next.strip()),
                )
                st.rerun()
    with tabs[1]:
        st.markdown("#### Metas y medidores del dictamen")
        st.caption("El avance compara el valor actual contra la meta definida para cada perfil. Las metas son editables; la evidencia sigue disponible como respaldo, pero no sustituye una meta operativa.")
        metric_table = pd.DataFrame(goal_rows).drop(columns=["code", "Alcance"])
        metric_table["Avance"] = metric_table["Avance"].map(lambda value: f"{value:.0f}%")
        st.dataframe(metric_table, use_container_width=True, hide_index=True)
        st.markdown("#### Configurar meta o medidor")
        st.caption("Ajusta la meta de acuerdo con el tamaño del territorio, etapa de campaña y objetivo del perfil.")
        variable_options = {name: code for code, name, _, _ in viability_variables}
        with st.form(f"variable_assessment_form_{profile_id}"):
            selected_variable_name = st.selectbox("Variable", list(variable_options))
            selected_variable_code = variable_options[selected_variable_name]
            current_assessment = assessment_by_code.get(selected_variable_code, {})
            selected_goal = next(row for row in goal_rows if row["code"] == selected_variable_code)
            variable_statuses = ["Pendiente", "En revisión", "Documentada", "Validada", "No aplica"]
            current_variable_status = current_assessment.get("status", "Pendiente")
            variable_status = st.selectbox(
                "Estatus de validación", variable_statuses,
                index=variable_statuses.index(current_variable_status) if current_variable_status in variable_statuses else 0,
            )
            variable_evidence = st.text_area("Nota de evidencia", value=current_assessment.get("evidence_note", ""))
            variable_source = st.text_input("Liga de fuente o documento", value=current_assessment.get("source_url", ""))
            metric_left, metric_center, metric_right = st.columns(3)
            metric_label = metric_left.text_input("Nombre del medidor", value=selected_goal["Indicador"])
            metric_actual = metric_center.number_input("Valor actual", min_value=0.0, value=float(selected_goal["Actual"]), step=1.0)
            metric_target = metric_right.number_input("Meta", min_value=0.0, value=float(selected_goal["Meta"]), step=1.0)
            metric_unit = st.text_input("Unidad", value=selected_goal["Unidad"])
            if st.form_submit_button("Guardar validación de variable"):
                execute(
                    """
                    INSERT INTO viability_variable_assessments (profile_id, variable_code, status, evidence_note, source_url, metric_label, actual_value, target_value, metric_unit, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(profile_id, variable_code) DO UPDATE SET
                      status = excluded.status, evidence_note = excluded.evidence_note,
                      source_url = excluded.source_url, metric_label = excluded.metric_label,
                      actual_value = excluded.actual_value, target_value = excluded.target_value,
                      metric_unit = excluded.metric_unit, updated_at = CURRENT_TIMESTAMP
                    """,
                    (profile_id, selected_variable_code, variable_status, variable_evidence.strip(), variable_source.strip(), metric_label.strip(), float(metric_actual), float(metric_target), metric_unit.strip()),
                )
                st.rerun()
    with tabs[2]:
        first, second, third, fourth = st.columns(4)
        first.metric("Municipios electorales", int(election_rows["municipios"] or 0))
        second.metric("Registros electorales", int(election_rows["total"] or 0))
        third.metric("Municipios con INEGI", int(indicator_rows["municipios"] or 0))
        fourth.metric("Piso partidista MC", f"{int(mc_vote_floor):,}", f"{mc_vote_share:.1f}% del voto emitido ({latest_election_year})" if latest_election_year else "Sin dato")
        if latest_election_year:
            st.caption(
                "El piso partidista es la votación municipal histórica de Movimiento Ciudadano. "
                "Es una referencia de base, no una estimación ni un piso personal del perfil."
            )
            st.markdown("#### Modelo de meta de votos")
            goal_a, goal_b, goal_c = st.columns(3)
            goal_a.metric("Competir con posibilidad de ganar", f"{competitive_vote_goal:,}", "35% de votos válidos")
            goal_b.metric("Meta para contienda cerrada", f"{close_win_vote_goal:,}", "38% de votos válidos")
            goal_c.metric("Meta robusta", f"{robust_win_vote_goal:,}", "40% de votos válidos")
            st.caption(
                f"Escenario de tres bloques competitivos, usando {int(valid_vote_reference):,} votos válidos municipales de {latest_election_year} como referencia. "
                "Son metas de planeación, no pronósticos electorales."
            )
        st.write("Consulta el detalle comparativo en **Dominio territorial**, **Visor territorial** y **Visor electoral**.")
    with tabs[3]:
        first, second, third = st.columns(3)
        first.metric("Positivas", int(sentiment["positivas"] or 0))
        second.metric("Negativas", int(sentiment["negativas"] or 0))
        third.metric("Atención alta o crítica", int(sentiment["urgentes"] or 0))
        st.write("La bandeja de evidencia permite abrir la fuente original; los enfoques de análisis ayudan a separar noticia, opinión, necesidad y relación con el perfil.")
    with tabs[4]:
        st.markdown("#### Competidores y referentes comparables")
        st.caption("Registra solo información pública o autorizada, junto con su fuente de respaldo.")
        if competitors:
            st.dataframe(pd.DataFrame(competitors), use_container_width=True, hide_index=True)
        else:
            st.info("No hay competidores o referentes cargados para este dictamen.")
        with st.form(f"competitor_form_{profile_id}", clear_on_submit=True):
            first, second, third = st.columns(3)
            competitor_name = first.text_input("Nombre")
            competitor_party = second.text_input("Partido o coalición")
            competitor_condition = third.text_input("Condición o cargo")
            competitor_territory = st.text_input("Territorio de referencia")
            competitor_note = st.text_area("Lectura comparativa y evidencia")
            competitor_url = st.text_input("Liga de fuente pública")
            if st.form_submit_button("Agregar competidor o referente"):
                if not competitor_name.strip():
                    st.error("Escribe el nombre del competidor o referente.")
                else:
                    execute(
                        "INSERT INTO viability_competitors (profile_id, name, party_or_coalition, condition, territory, positioning_note, source_url) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (profile_id, competitor_name.strip(), competitor_party.strip(), competitor_condition.strip(), competitor_territory.strip(), competitor_note.strip(), competitor_url.strip()),
                    )
                    st.rerun()
    with tabs[5]:
        st.markdown("#### Encuestas formales y ejercicios de campo")
        st.caption("Captura metodología, fecha, muestra y fuente para distinguir una encuesta verificable de una referencia sin sustento.")
        if surveys:
            st.dataframe(pd.DataFrame(surveys), use_container_width=True, hide_index=True)
        else:
            st.info("No hay encuestas o ejercicios de campo cargados para este perfil.")
        with st.form(f"survey_form_{profile_id}", clear_on_submit=True):
            first, second, third = st.columns(3)
            survey_name = first.text_input("Nombre del estudio")
            survey_pollster = second.text_input("Casa encuestadora o responsable")
            survey_territory = third.text_input("Territorio")
            fourth, fifth, sixth = st.columns(3)
            survey_date = fourth.text_input("Fecha de levantamiento")
            survey_sample = fifth.number_input("Tamaño de muestra", min_value=0, step=1)
            survey_result = sixth.number_input("Resultado del perfil (%)", min_value=0.0, max_value=100.0, step=0.1)
            survey_methodology = st.text_area("Metodología y notas")
            survey_url = st.text_input("Liga de fuente o documento")
            if st.form_submit_button("Agregar encuesta o ejercicio"):
                if not survey_name.strip():
                    st.error("Escribe el nombre del estudio o ejercicio.")
                else:
                    execute(
                        "INSERT INTO viability_surveys (profile_id, name, pollster, territory, fieldwork_date, sample_size, methodology, profile_result_pct, source_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (profile_id, survey_name.strip(), survey_pollster.strip(), survey_territory.strip(), survey_date.strip(), int(survey_sample) or None, survey_methodology.strip(), float(survey_result) if survey_result else None, survey_url.strip()),
                    )
                    st.rerun()
    with tabs[6]:
        st.markdown("#### Estructura territorial comprobable")
        st.caption("Registra cobertura y responsables por territorio. No se utilizan perfiles individuales de electores.")
        if structure_records:
            st.dataframe(pd.DataFrame(structure_records), use_container_width=True, hide_index=True)
        else:
            st.info("No hay registros de estructura territorial para este perfil.")
        with st.form(f"structure_form_{profile_id}", clear_on_submit=True):
            first, second, third = st.columns(3)
            structure_state = first.text_input("Estado", value=selected_state if selected_state != "Todos los estados" else "")
            structure_municipality = second.text_input("Municipio")
            structure_district = third.text_input("Distrito")
            fourth, fifth, sixth = st.columns(3)
            structure_section = fourth.text_input("Sección electoral")
            structure_locality = fifth.text_input("Localidad")
            structure_responsible = sixth.text_input("Responsable")
            structure_status = st.selectbox("Estatus de cobertura", ["Planeada", "Por validar", "Registrada", "Activa", "Incompleta"], key=f"structure_status_{profile_id}")
            structure_evidence = st.text_area("Evidencia o nota de verificación")
            if st.form_submit_button("Agregar registro de estructura"):
                execute(
                    "INSERT INTO viability_structure_records (profile_id, state, municipality, district, electoral_section, locality, responsible, coverage_status, evidence_note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (profile_id, structure_state.strip(), structure_municipality.strip(), structure_district.strip(), structure_section.strip(), structure_locality.strip(), structure_responsible.strip(), structure_status, structure_evidence.strip()),
                )
                st.rerun()
    with tabs[7]:
        st.markdown("#### Escenarios de viabilidad y coalición")
        if coalition_scenarios:
            st.dataframe(pd.DataFrame(coalition_scenarios), use_container_width=True, hide_index=True)
        else:
            st.info("No hay escenarios de coalición cargados. Regístralos como hipótesis hasta que exista una definición formal.")
        with st.form(f"coalition_form_{profile_id}", clear_on_submit=True):
            coalition_name = st.text_input("Nombre del escenario")
            coalition_parties = st.text_input("Partidos o coalición")
            coalition_scope = st.text_input("Alcance territorial o electoral")
            coalition_status = st.selectbox("Estatus", ["Hipótesis", "En análisis", "Confirmado", "Descartado"], key=f"coalition_status_{profile_id}")
            coalition_notes = st.text_area("Supuestos, alcance y observaciones")
            coalition_url = st.text_input("Liga de fuente pública")
            if st.form_submit_button("Agregar escenario de coalición"):
                if not coalition_name.strip():
                    st.error("Escribe un nombre para el escenario.")
                else:
                    execute(
                        "INSERT INTO viability_coalition_scenarios (profile_id, scenario_name, parties, scope, status, notes, source_url) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (profile_id, coalition_name.strip(), coalition_parties.strip(), coalition_scope.strip(), coalition_status, coalition_notes.strip(), coalition_url.strip()),
                    )
                    st.rerun()
    with tabs[8]:
        st.markdown("#### Recursos y capacidad operativa")
        st.caption("Registra disponibilidad y respaldo documental; evita guardar credenciales, datos bancarios o información personal sensible.")
        if resources:
            st.dataframe(pd.DataFrame(resources), use_container_width=True, hide_index=True)
        else:
            st.info("No hay registros de recursos o capacidad operativa para este perfil.")
        with st.form(f"resource_form_{profile_id}", clear_on_submit=True):
            resource_category = st.selectbox("Categoría", ["Equipo", "Logística", "Comunicación", "Capacitación", "Financiamiento autorizado", "Otra"], key=f"resource_category_{profile_id}")
            resource_status = st.selectbox("Disponibilidad", ["Por validar", "Disponible", "Parcial", "No disponible"], key=f"resource_status_{profile_id}")
            resource_amount = st.text_input("Monto o referencia agregada, si aplica")
            resource_notes = st.text_area("Evidencia, limitaciones o notas")
            resource_url = st.text_input("Liga de fuente o documento")
            if st.form_submit_button("Agregar recurso o capacidad"):
                execute(
                    "INSERT INTO viability_resource_records (profile_id, category, availability_status, amount_note, source_url, notes) VALUES (?, ?, ?, ?, ?, ?)",
                    (profile_id, resource_category, resource_status, resource_amount.strip(), resource_url.strip(), resource_notes.strip()),
                )
                st.rerun()
    with tabs[9]:
        first, second, third = st.columns(3)
        first.metric("Territorios asignados", int(territories or 0))
        second.metric("Acciones registradas", int(action_summary["total"] or 0))
        third.metric("Acciones activas", int(action_summary["activas"] or 0))
        st.write("Los módulos de Estrategia territorial, Planes de acción, CRM y Seguimiento de campo convierten hallazgos en trabajo verificable.")
    with tabs[10]:
        missing = []
        if not int(sources or 0): missing.append("fuentes activas")
        if not int(publications or 0): missing.append("registros de evidencia")
        if not int(election_rows["total"] or 0): missing.append("resultados electorales")
        if not int(indicator_rows["total"] or 0): missing.append("indicadores INEGI")
        if not int(territories or 0): missing.append("territorios asignados")
        if not int(action_summary["total"] or 0): missing.append("acciones de seguimiento")
        if not competitors: missing.append("competidores o referentes")
        if not surveys: missing.append("encuestas o ejercicios de campo")
        if not structure_records: missing.append("estructura territorial comprobable")
        if not coalition_scenarios: missing.append("escenarios de coalición")
        if not resources: missing.append("recursos y capacidad operativa")
        if not formal_conclusion: missing.append("conclusión formal")
        if missing:
            st.warning("Falta integrar: " + ", ".join(missing) + ".")
        else:
            st.success("El expediente tiene evidencia en todos los bloques básicos. Revisa la calidad y actualidad de cada fuente antes de emitir una versión formal.")
        st.caption("Los riesgos se documentan con fuentes verificables y se revisan periódicamente; el módulo no construye perfiles individuales de electores.")


if "active_page" not in st.session_state:
    st.session_state["active_page"] = "Inicio"
if not st.session_state.get("navigation_groups_v18"):
    for widget_key in NAVIGATION_WIDGET_KEYS:
        st.session_state.pop(widget_key, None)
    st.session_state["navigation_groups_v18"] = True
    if st.session_state.get("active_page") == "Codex":
        st.session_state["active_page"] = "Inicio"


with st.sidebar:
    st.markdown(
        """
        <div class="pulso-kicker">INTELIGENCIA ELECTORAL</div>
        <div class="pulso-title">Go2Win<br><span style="font-size:.68em;font-weight:600;letter-spacing:.04em">Tablero de mando electoral</span></div>
        <div class="pulso-subtitle">Evidencia, dictamen, territorio, estrategia y seguimiento.</div>
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
    st.caption("1 · EXPEDIENTE DE CANDIDATURA")
    st.caption("Perfil, elección y dictamen de viabilidad.")
    st.radio(
        "Perfil y dictamen",
        list(PROFILE_NAVIGATION),
        index=None,
        key="profile_navigation",
        label_visibility="collapsed",
        on_change=select_navigation,
        args=("profile_navigation", PROFILE_NAVIGATION),
    )
    st.divider()
    st.caption("2 · VISORES GIS")
    st.caption("Explora cartografía, resultados e indicadores sin modificar la operación.")
    st.radio(
        "Visores GIS",
        list(GIS_NAVIGATION),
        index=None,
        key="gis_navigation",
        label_visibility="collapsed",
        on_change=select_navigation,
        args=("gis_navigation", GIS_NAVIGATION),
    )
    st.divider()
    st.caption("3 · ENTENDER EL TERRITORIO")
    st.caption("Consulta el mercado, diagnostica condiciones y localiza oportunidades.")
    st.radio(
        "Análisis y priorización",
        list(DIAGNOSTIC_NAVIGATION),
        index=None,
        key="diagnostic_navigation",
        label_visibility="collapsed",
        on_change=select_navigation,
        args=("diagnostic_navigation", DIAGNOSTIC_NAVIGATION),
    )
    st.divider()
    st.caption("4 · ESCENARIO Y METAS")
    st.caption("Define la hipótesis electoral y distribuye la meta a todo el territorio.")
    st.radio(
        "Escenario y metas",
        list(DECISION_NAVIGATION),
        index=None,
        key="decision_navigation",
        label_visibility="collapsed",
        on_change=select_navigation,
        args=("decision_navigation", DECISION_NAVIGATION),
    )
    st.divider()
    st.caption("5 · PRIORIZACIÓN, ESTRATEGIA Y OPERACIÓN")
    st.caption("Ordena dónde actuar primero, define el rumbo y da seguimiento a la ejecución.")
    st.radio(
        "Priorización, estrategia y operación",
        list(EXECUTION_NAVIGATION),
        index=None,
        key="execution_navigation",
        label_visibility="collapsed",
        on_change=select_navigation,
        args=("execution_navigation", EXECUTION_NAVIGATION),
    )
    st.divider()
    st.caption("7 · ESCUCHA Y EVIDENCIA")
    st.caption("Obtén, analiza, vincula y revisa la información que respalda decisiones.")
    st.radio(
        "Módulos de evidencia",
        list(EVIDENCE_NAVIGATION),
        index=None,
        key="evidence_navigation",
        label_visibility="collapsed",
        on_change=select_navigation,
        args=("evidence_navigation", EVIDENCE_NAVIGATION),
    )
    st.divider()
    st.caption("8 · CONFIGURACIÓN Y APOYO")
    st.radio(
        "Configuración y apoyo",
        list(SETTINGS_NAVIGATION),
        index=None,
        key="settings_navigation",
        label_visibility="collapsed",
        on_change=select_navigation,
        args=("settings_navigation", SETTINGS_NAVIGATION),
    )
    st.divider()
    st.caption("Flujo: expediente → análisis → escenarios y metas → estrategia → seguimiento.")
    st.caption("Los datos se conservan en esta computadora.")

page = st.session_state["active_page"]

if page not in {"Dominio territorial", "Territorio", "Electoral", "Visor electoral", "INEGI", "Diagnóstico regional del PED", "Perfil territorial", "Dictamen de viabilidad", "Recorrido del dictamen"}:
    st.title(page if page != "Inicio" else "Go2Win · Tablero de mando electoral")
    st.caption("Etapa 1 local: datos y análisis en tu computadora, sin costo de infraestructura.")

if page == "Personal y Telegram":
    render_field_staff()

elif page == "Escenarios electorales":
    render_electoral_scenarios()

elif page == "Mapa de estrategia y operación":
    render_strategy_operation_map()

elif page == "Metas y control territorial":
    render_territorial_goals()

elif page == "Planes de acción":
    render_action_plans()

elif page == "Estrategia territorial":
    render_territorial_strategy()

elif page == "Priorización territorial":
    render_territorial_prioritization()

elif page == "Mapa de oportunidad electoral":
    render_electoral_opportunity_map()

elif page == "Cruce INEGI + INE":
    render_inegi_ine_cross_analysis()

elif page == "Mercado electoral":
    render_electoral_market()

elif page == "Diagnóstico territorial":
    render_territorial_diagnosis()

elif page == "Tablero Electoral":
    render_electoral_dashboard()

elif page == "Dictamen de viabilidad":
    render_viability_opinion()

elif page == "Recorrido del dictamen":
    render_dictamen_reader()

elif page == "Inicio":
    st.subheader("Objetivo del proyecto")
    st.markdown(
        "Gobernar o construir una propuesta pública exige entender dos cosas al mismo tiempo: "
        "qué ocurre en el territorio y qué está expresando la ciudadanía."
    )
    st.markdown(
        "**Go2Win** integra ambas lecturas en una plataforma local, "
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

elif page == "Orden de cargas":
    st.subheader("Orden de cargas en Go2Win")
    st.caption("Secuencia recomendada para crear un caso de campaña sin mezclar información ni anticipar decisiones.")
    st.info("Regla de operación: primero información y evidencia; después análisis; luego estrategia; al final operación y seguimiento.")
    load_steps = [
        ("1. Crear el perfil", "Registrar nombre, tipo, cargo objetivo, condición, partido o coalición."),
        ("2. Asociar el territorio", "Asignar estado y después municipios, distritos o secciones que correspondan a la cobertura."),
        ("3. Cargar información territorial base", "Incorporar cartografía, resultados electorales históricos, lista nominal, participación, votos e indicadores INEGI."),
        ("4. Cargar el expediente", "Agregar dictámenes, documentos, encuestas, competidores, escenarios y estructura conocida."),
        ("5. Configurar escucha y evidencia", "Registrar fuentes autorizadas, obtener publicaciones y conservar el enlace al contenido original."),
        ("6. Completar las 20 variables de viabilidad", "Documentar evidencia, fuente, fecha de corte y estatus antes de asignar puntajes."),
        ("7. Construir escenarios electorales", "Definir participación esperada, votos necesarios, competidores, coaliciones y escenarios de decisión."),
        ("8. Definir diagnóstico y estrategia territorial", "Priorizar territorios para defender, crecer, persuadir o recuperar con base en datos agregados."),
        ("9. Crear metas y planes de acción", "Convertir la estrategia en metas, responsables y actividades; después se conectará con el CRM territorial."),
    ]
    for title, description in load_steps:
        st.markdown(
            f"<div class='electoral-kpi'><div class='electoral-kpi-label'>{title}</div>"
            f"<div class='electoral-kpi-note'>{description}</div></div>",
            unsafe_allow_html=True,
        )

elif page == "Tableros y reportes":
    st.subheader("Tablero de evidencia y seguimiento")
    st.caption(
        "Corte ejecutivo de la información disponible. Cada indicador conserva su vínculo con fuentes, "
        "territorio y análisis; no representa una predicción electoral."
    )
    dashboard_profiles = query(
        """
        SELECT p.id, p.name, COUNT(pub.id) AS publicaciones
        FROM profiles p
        LEFT JOIN publications pub ON pub.profile_id = p.id
        WHERE p.active = 1
        GROUP BY p.id, p.name
        ORDER BY publicaciones DESC, p.name
        """
    )
    if not dashboard_profiles:
        st.info("Registra un perfil para comenzar a construir su tablero de mando.")
        st.stop()
    dashboard_options = {
        f"{row['name']} · {int(row['publicaciones'] or 0):,} registros": row["id"]
        for row in dashboard_profiles
    }
    selected_dashboard_label = st.selectbox(
        "Perfil del tablero", list(dashboard_options), key="dashboard_profile"
    )
    dashboard_profile_id = dashboard_options[selected_dashboard_label]

    summary = query(
        """
        SELECT
            COUNT(DISTINCT p.id) AS publicaciones,
            COUNT(DISTINCT a.id) AS analizadas,
            COUNT(DISTINCT s.id) AS fuentes,
            SUM(CASE WHEN a.sentiment = 'Positivo' THEN 1 ELSE 0 END) AS positivas,
            SUM(CASE WHEN a.sentiment = 'Negativo' THEN 1 ELSE 0 END) AS negativas,
            SUM(CASE WHEN a.sentiment = 'Neutral' THEN 1 ELSE 0 END) AS neutras,
            SUM(CASE WHEN a.urgency IN ('Alta', 'Crítica') THEN 1 ELSE 0 END) AS urgentes
        FROM publications p
        LEFT JOIN analyses a ON a.publication_id = p.id
        LEFT JOIN sources s ON s.id = p.source_id
        WHERE p.profile_id = ?
        """,
        (dashboard_profile_id,),
    )[0]
    territorial_summary = query(
        """
        SELECT COUNT(DISTINCT municipality) AS municipios
        FROM publication_territories pt
        JOIN publications p ON p.id = pt.publication_id
        WHERE p.profile_id = ? AND municipality IS NOT NULL
        """,
        (dashboard_profile_id,),
    )[0]
    actions_summary = query(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN tap.status = 'Concluida' THEN 1 ELSE 0 END) AS concluidas,
               SUM(CASE WHEN tap.status IN ('Pendiente', 'En curso') THEN 1 ELSE 0 END) AS activas
        FROM territorial_action_plans tap
        JOIN territorial_strategies ts ON ts.id = tap.strategy_id
        WHERE ts.profile_id = ?
        """,
        (dashboard_profile_id,),
    )[0]

    top_metrics = st.columns(5)
    top_metrics[0].metric("Registros", f"{int(summary['publicaciones'] or 0):,}")
    top_metrics[1].metric("Analizados", f"{int(summary['analizadas'] or 0):,}")
    top_metrics[2].metric("Fuentes", int(summary['fuentes'] or 0))
    top_metrics[3].metric("Municipios vinculados", int(territorial_summary['municipios'] or 0))
    top_metrics[4].metric("Atención alta o crítica", int(summary['urgentes'] or 0))

    st.markdown("### Lectura ejecutiva")
    left_panel, right_panel = st.columns([1.05, 1])
    with left_panel:
        st.markdown("#### Percepción pública")
        sentiment_frame = pd.DataFrame([
            {"Sentimiento": "Positivas", "Registros": int(summary["positivas"] or 0)},
            {"Sentimiento": "Negativas", "Registros": int(summary["negativas"] or 0)},
            {"Sentimiento": "Neutras", "Registros": int(summary["neutras"] or 0)},
        ])
        st.bar_chart(sentiment_frame.set_index("Sentimiento"), height=260)
        balance = int(summary["positivas"] or 0) - int(summary["negativas"] or 0)
        st.caption(f"Balance de sentimiento: {balance:+,} registros positivos menos negativos.")
    with right_panel:
        st.markdown("#### Operación territorial")
        operation_metrics = st.columns(2)
        operation_metrics[0].metric("Acciones activas", int(actions_summary["activas"] or 0))
        operation_metrics[1].metric("Acciones concluidas", int(actions_summary["concluidas"] or 0))
        operation_metrics[0].metric("Total de acciones", int(actions_summary["total"] or 0))
        operation_metrics[1].metric("Cobertura municipal", int(territorial_summary["municipios"] or 0))
        st.info(
            "El tablero reúne escucha, análisis y operación. Las acciones aparecen cuando se registran "
            "planes territoriales para este perfil."
        )

    topic_rows = query(
        """
        SELECT COALESCE(NULLIF(TRIM(a.topic), ''), 'Sin tema') AS tema, COUNT(*) AS registros
        FROM analyses a
        JOIN publications p ON p.id = a.publication_id
        WHERE p.profile_id = ?
        GROUP BY tema
        ORDER BY registros DESC, tema
        LIMIT 8
        """,
        (dashboard_profile_id,),
    )
    source_rows = query(
        """
        SELECT s.name AS fuente, s.source_type AS tipo, COUNT(p.id) AS registros
        FROM publications p
        JOIN sources s ON s.id = p.source_id
        WHERE p.profile_id = ?
        GROUP BY s.id, s.name, s.source_type
        ORDER BY registros DESC, fuente
        LIMIT 8
        """,
        (dashboard_profile_id,),
    )
    detail_left, detail_right = st.columns(2)
    with detail_left:
        st.markdown("#### Temas con mayor presencia")
        if topic_rows:
            topic_frame = pd.DataFrame(topic_rows)
            st.bar_chart(topic_frame.set_index("tema")[["registros"]], horizontal=True, height=300)
        else:
            st.caption("Aún no hay análisis temático disponible para este perfil.")
    with detail_right:
        st.markdown("#### Fuentes con información")
        if source_rows:
            source_frame = pd.DataFrame(source_rows).rename(columns={"fuente": "Fuente", "tipo": "Tipo", "registros": "Registros"})
            st.dataframe(source_frame, use_container_width=True, hide_index=True)
        else:
            st.caption("Aún no hay fuentes con registros para este perfil.")

    municipality_rows = query(
        """
        SELECT pt.municipality AS municipio, COUNT(DISTINCT p.id) AS registros,
               SUM(CASE WHEN a.urgency IN ('Alta', 'Crítica') THEN 1 ELSE 0 END) AS urgentes
        FROM publication_territories pt
        JOIN publications p ON p.id = pt.publication_id
        LEFT JOIN analyses a ON a.publication_id = p.id
        WHERE p.profile_id = ? AND pt.municipality IS NOT NULL
        GROUP BY pt.municipality
        ORDER BY urgentes DESC, registros DESC, municipio
        LIMIT 10
        """,
        (dashboard_profile_id,),
    )
    st.markdown("#### Territorios que requieren revisión")
    if municipality_rows:
        municipality_frame = pd.DataFrame(municipality_rows).rename(columns={
            "municipio": "Municipio", "registros": "Registros vinculados", "urgentes": "Atención alta o crítica"
        })
        st.dataframe(municipality_frame, use_container_width=True, hide_index=True)
    else:
        st.caption("No hay publicaciones vinculadas explícitamente a municipios para este perfil.")

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

elif page == "Seguimiento del PMD":
    render_pmd_tracking()

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
        "en Fuentes y actualización conforme construyamos cada conector."
    )

elif page == "Fuentes y actualización":
    st.subheader("Fuentes y actualización")
    st.caption(
        "Aquí se actualiza la información pública de un perfil. Después se revisa en Bandeja de registros; "
        "el análisis se realiza en los módulos de diagnóstico y estrategia."
    )
    options = profile_options()
    if not options:
        st.info("Primero crea un perfil y registra sus fuentes.")
        st.stop()

    chosen = st.selectbox("Perfil a monitorear", list(options))
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
    col1.metric("Medios configurados", len(registered_media))
    col2.metric("Feeds RSS activos", len(rss_sources))
    col3.metric("Otros canales", len(all_sources) - len(registered_media) - len(rss_sources))
    col4.metric("Registros capturados", existing)

    st.markdown("### 1. Fuentes del perfil")
    st.caption("Estas son las fuentes que se consultarán al presionar Actualizar. Agrega o ajusta fuentes antes de iniciar una consulta.")

    if all_sources:
        st.dataframe(pd.DataFrame(all_sources), use_container_width=True, hide_index=True)
    else:
        st.warning("Este perfil no tiene fuentes activas. Registra primero un medio, un RSS, una cuenta X o una fuente institucional.")

    with st.expander("Ajustar palabras clave para filtrar resultados"):
        st.caption(
            "La plataforma conserva sólo notas relacionadas con estas palabras. Incluye nombre completo, alias públicos, "
            "cargo y variantes útiles."
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
            )
            save_keywords = st.form_submit_button("Guardar palabras clave")
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
                    st.success(f"Palabras clave actualizadas: {len(keywords)}.")
                    st.rerun()

    st.markdown("### 2. Actualizar información")
    st.caption("Elige el canal que deseas actualizar. La plataforma no realiza consultas automáticas.")
    media_button, rss_button = st.columns(2)
    if media_button.button("Actualizar noticias de medios", type="primary", disabled=not registered_media):
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

    if rss_sources:
        if rss_button.button("Actualizar feeds RSS"):
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
    elif rss_button.button("Buscar y activar feeds RSS", disabled=not registered_media):
        with st.spinner("Buscando feeds RSS publicados por los medios configurados..."):
            discovery = discover_rss(profile_id)
        st.success(f"Se activaron {discovery['added']} feeds nuevos. Actualiza la pantalla para consultarlos.")
        if discovery["errors"]:
            st.warning("Algunos sitios no respondieron:\n\n- " + "\n- ".join(discovery["errors"]))
        st.rerun()

    x_default_query = (
        '("Maru Campos" OR "María Eugenia Campos") lang:es -is:retweet'
        if "María Eugenia Campos" in chosen
        else '("Cecilia Patrón" OR "Cecilia Patron" OR "@CeciliaPatronL") lang:es -is:retweet'
        if "Cecilia" in chosen
        else '("Felifer" OR "Felipe Fernando Macías" OR "Felipe Macías" OR "@FeliFerMacias" OR from:FeliFerMacias) lang:es -is:retweet'
        if "Felipe Fernando Macías" in chosen
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
            "Actualizar conversación pública en X",
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

    institutional_button = st.columns(1)[0]
    if institutional_button.button(
        "Actualizar fuentes institucionales",
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

    with st.expander("Administrar feeds RSS"):
        action_left, action_right = st.columns(2)
        if action_left.button("Buscar feeds en los medios configurados", disabled=not registered_media):
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
        if rss_sources:
            st.dataframe(pd.DataFrame(rss_sources), use_container_width=True, hide_index=True)

    st.markdown("### 3. Resultado de las actualizaciones")
    st.caption("Al terminar una actualización, revisa los registros en Bandeja de registros para clasificarlos y vincularlos al territorio.")
    if latest_runs:
        st.dataframe(pd.DataFrame(latest_runs), use_container_width=True, hide_index=True)
    else:
        st.caption("Aún no se ha ejecutado ninguna obtención para este perfil.")

elif page == "Dominio territorial":
    render_domain_header("Dominio territorial")
    render_domain_scroll_nav([
        ("Configuración", "configuracion-gis"),
        ("Resumen estatal", "ficha-estatal"),
        ("Mapa", "mapa-gis"),
        ("Ficha municipal", "ficha-municipal"),
        ("Volver arriba", "dominio-territorial"),
    ])
    st.markdown('<div id="configuracion-gis" class="scroll-anchor"></div>', unsafe_allow_html=True)
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
    # El visor inicia con una ficha estatal para que la consulta no dependa de
    # seleccionar un municipio. Los resultados se agregan exclusivamente a
    # partir de las filas municipales ya cargadas en la plataforma.
    state_election_payload: dict[str, float] = {}
    for election_row in viewer_election_data:
        for field, value in election_row["payload"].items():
            try:
                state_election_payload[field] = state_election_payload.get(field, 0.0) + float(value or 0)
            except (TypeError, ValueError):
                continue
    state_population_row = query(
        """SELECT SUM(value) AS population, COUNT(DISTINCT municipality_code) AS coverage
           FROM territorial_indicators
           WHERE state = ? AND indicator_id = '1002000001'""",
        (viewer_state,),
    )
    state_population = float(state_population_row[0]["population"] or 0) if state_population_row else 0.0
    state_population_coverage = int(state_population_row[0]["coverage"] or 0) if state_population_row else 0
    state_indicator_catalog = query(
        """SELECT indicator_name AS Indicador, period AS Periodo, COUNT(DISTINCT municipality_code) AS Cobertura
           FROM territorial_indicators
           WHERE state = ?
           GROUP BY indicator_id, indicator_name, period
           ORDER BY indicator_name, period DESC""",
        (viewer_state,),
    )
    state_nominal = float(state_election_payload.get("lista_nominal") or 0)
    state_votes_total = float(state_election_payload.get("votes_total") or 0)
    state_turnout = state_votes_total / state_nominal * 100 if state_nominal else 0.0
    st.markdown('<div id="ficha-estatal" class="scroll-anchor"></div>', unsafe_allow_html=True)
    st.markdown('<div class="domain-section">0. Consulta la información del estado</div>', unsafe_allow_html=True)
    state_a, state_b, state_c, state_d = st.columns(4)
    state_a.metric("Estado", viewer_state)
    state_b.metric("Municipios", len(viewer_names))
    state_c.metric(
        "Población total",
        f"{state_population:,.0f}" if state_population else "No disponible",
        f"INEGI · {state_population_coverage} municipios" if state_population_coverage else None,
    )
    state_d.metric(
        "Participación electoral",
        f"{state_turnout:.1f}%" if state_nominal else "No disponible",
        f"{viewer_election_type} {viewer_election_year}" if viewer_election_year else None,
    )
    state_territorial_tab, state_electoral_tab, state_inegi_tab = st.tabs([
        "Resumen territorial", "Resultados electorales estatales", "Indicadores INEGI cargados",
    ])
    with state_territorial_tab:
        state_summary_a, state_summary_b, state_summary_c = st.columns(3)
        state_summary_a.metric("Lista nominal agregada", f"{state_nominal:,.0f}" if state_nominal else "No disponible")
        state_summary_b.metric("Votos totales agregados", f"{state_votes_total:,.0f}" if state_votes_total else "No disponible")
        state_summary_c.metric("Municipios con resultado", len(viewer_election_data))
        st.caption(
            "El resumen estatal agrega la información municipal disponible. Selecciona después un municipio para abrir sus fichas territorial, electoral e INEGI."
        )
    with state_electoral_tab:
        if state_election_payload:
            st.markdown(f"#### {viewer_election_type} {viewer_election_year} · resultado agregado")
            render_electoral_breakdown(state_election_payload)
        else:
            st.info("No hay resultados municipales cargados para construir el agregado estatal.")
    with state_inegi_tab:
        if state_indicator_catalog:
            st.dataframe(pd.DataFrame(state_indicator_catalog), use_container_width=True, hide_index=True)
            st.caption("La cobertura indica en cuántos municipios está disponible cada indicador. Los porcentajes se consultan por municipio, no se suman a nivel estatal.")
        else:
            st.info("No hay indicadores INEGI cargados para este estado.")
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
    st.markdown('<div id="mapa-gis" class="scroll-anchor"></div>', unsafe_allow_html=True)
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
    st.markdown('<div id="ficha-municipal" class="scroll-anchor"></div>', unsafe_allow_html=True)
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
    if page == "Visor electoral":
        render_domain_scroll_nav([
            ("Configuración", "configuracion-electoral"),
            ("Rutas", "rutas-electorales"),
            ("Ficha", "ficha-electoral"),
            ("Mapa", "mapa-electoral"),
            ("Arriba", "visor-electoral"),
        ])
        st.markdown('<div id="configuracion-electoral" class="scroll-anchor"></div>', unsafe_allow_html=True)
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

    if page == "Visor electoral":
        st.markdown('<div id="rutas-electorales" class="scroll-anchor"></div>', unsafe_allow_html=True)
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
        # Algunas importaciones históricas de secciones no incluían la clave
        # municipal. Agrupamos por nombre normalizado y conservamos la clave
        # válida que aparezca en cualquiera de sus secciones; de lo contrario
        # el mismo municipio se duplicaba y la ficha INEGI quedaba vacía.
        aggregate: dict[str, dict] = {}
        for row in district_sections:
            key = municipality_match_key(row["Municipio"])
            bucket = aggregate.setdefault(key, {
                "Municipio": row["Municipio"], "Clave municipio": row["Clave municipio"],
                "Secciones con resultado": 0, "payload": {},
            })
            if not str(bucket["Clave municipio"] or "").strip("0") and str(row["Clave municipio"] or "").strip("0"):
                bucket["Clave municipio"] = row["Clave municipio"]
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
            # Respaldo para cargas históricas sin clave municipal: el nombre
            # también existe en el catálogo INEGI y permite recuperar la ficha.
            if not stored_inegi:
                stored_inegi = query(
                    """
                    SELECT indicator_name AS Indicador, value AS Valor, unit AS Unidad, period AS Periodo
                    FROM territorial_indicators
                    WHERE state = ? AND lower(municipality) = lower(?)
                    ORDER BY indicator_name, period DESC
                    """,
                    (context_state, ficha_municipality),
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
            if section_payload.get("ieeq_descripcion_territorial"):
                st.markdown("**Contexto territorial oficial de la sección**")
                st.write(section_payload["ieeq_descripcion_territorial"])
                current_roll, current_list = st.columns(2)
                current_roll.metric(
                    "Padrón electoral publicado",
                    f"{float(section_payload.get('ieeq_padron_electoral_actual') or 0):,.0f}",
                )
                current_list.metric(
                    "Lista nominal publicada",
                    f"{float(section_payload.get('ieeq_lista_nominal_actual') or 0):,.0f}",
                )
                if section_payload.get("ieeq_plano_seccional"):
                    st.link_button(
                        "Abrir plano oficial de la sección",
                        section_payload["ieeq_plano_seccional"],
                    )
        st.markdown("### 4. Mapa seccional")
        map_column = st.container()
        ficha_column = st.empty()
        with map_column:
            section_geojson, section_source = load_electoral_sections_context(context_state)
            if section_geojson is None:
                if context_state == "Querétaro":
                    st.info(
                        "La ficha ya incorpora el catálogo oficial del IEEQ para 1,007 secciones "
                        "(contexto territorial, padrón, lista nominal y plano individual). "
                        "El polígono vectorial de cada sección sigue pendiente de una fuente geográfica oficial reutilizable; "
                        "no se dibuja una aproximación."
                    )
                else:
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
        district_metric_options = [
            "Participación electoral (%)", "Lista nominal", "Votos totales", "Votos opción más votada",
        ]
        available_district_metrics = [
            metric for metric in district_metric_options
            if pd.to_numeric(district_frame[metric], errors="coerce").notna().any()
        ]
        if not available_district_metrics:
            st.warning("La elección seleccionada no contiene métricas distritales utilizables.")
            st.stop()
        district_metric = st.radio(
            "Tema distrital",
            available_district_metrics,
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
            recognized_districts = sum(
                bool(feature.get("properties", {}).get("clave_distrito"))
                for feature in enriched_district_geojson.get("features", [])
            )
            if page == "Visor electoral":
                st.markdown('<div id="ficha-electoral" class="scroll-anchor"></div>', unsafe_allow_html=True)
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
            district_participation_top = pd.to_numeric(
                district_payload.get("participacion_pct"), errors="coerce"
            )
            district_average_top = pd.to_numeric(
                district_frame["Participación electoral (%)"], errors="coerce"
            ).mean()
            with st.container(border=True):
                ficha_a, ficha_b, ficha_c, ficha_d = st.columns(4)
                nominal_top = pd.to_numeric(district_payload.get("lista_nominal"), errors="coerce")
                ficha_a.metric("Lista nominal", f"{float(nominal_top):,.0f}" if pd.notna(nominal_top) else "No disponible")
                ficha_b.metric("Votos totales", f"{float(district_payload.get('votes_total') or 0):,.0f}")
                ficha_c.metric(
                    "Participación",
                    f"{float(district_participation_top):.1f}%" if pd.notna(district_participation_top) else "No disponible",
                    f"{float(district_participation_top - district_average_top):+.1f} pp vs. promedio estatal"
                    if pd.notna(district_participation_top) and pd.notna(district_average_top) else None,
                )
                ficha_d.metric("Cabecera", chosen_district_row_top["Cabecera distrital"])
                render_electoral_breakdown(district_payload)
            if page == "Visor electoral":
                st.markdown('<div id="mapa-electoral" class="scroll-anchor"></div>', unsafe_allow_html=True)
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
                elif recognized_districts:
                    st.info(
                        f"Se reconocieron {recognized_districts} distritos, pero la métrica “{district_metric}” "
                        "no está disponible para la elección elegida. Selecciona otra métrica."
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
                district_participation = pd.to_numeric(
                    chosen_district_row["Participación electoral (%)"], errors="coerce"
                )
                district_average = participation_values.mean()
                st.caption(f"Cabecera distrital: {chosen_district_row['Cabecera distrital']}")
                nominal_value = pd.to_numeric(chosen_district_row["Lista nominal"], errors="coerce")
                st.metric("Lista nominal", f"{int(nominal_value):,}" if pd.notna(nominal_value) else "No disponible")
                st.metric("Votos totales", f"{int(chosen_district_row['Votos totales']):,}")
                st.metric(
                    "Participación",
                    f"{float(district_participation):.1f}%" if pd.notna(district_participation) else "No disponible",
                    f"{float(district_participation - district_average):+.1f} pp vs. promedio estatal"
                    if pd.notna(district_participation) and pd.notna(district_average) else None,
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
        municipal_detail = municipal_detail[
            municipal_detail["municipio"].map(municipality_match_key) == municipality_match_key(municipality_filter)
        ]
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
    if municipality_filter != "Todos los municipios" and not municipal_detail.empty:
        detail = municipal_detail.iloc[0]
        excluded_fields = {"clave_municipio", "geometry", "geom", "id"}
        vertical_fields = [
            column for column in municipal_detail.columns
            if column not in excluded_fields and pd.notna(detail.get(column))
            and str(detail.get(column)).strip() not in {"", "nan", "None"}
        ]
        st.markdown(f"#### Ficha municipal · {detail.get('municipio', municipality_filter)}")
        st.caption("Consulta los indicadores uno debajo de otro; la ficha corresponde al municipio seleccionado.")
        with st.container(border=True):
            for column in vertical_fields:
                if column == "municipio":
                    continue
                label = str(column).replace("_", " ").capitalize()
                value = detail.get(column)
                label_column, value_column = st.columns([1, 1.35])
                label_column.markdown(f"**{label}**")
                if column == "plan municipal de desarrollo" and str(value).startswith("http"):
                    value_column.markdown(f"[Consultar documento]({value})")
                else:
                    numeric_value = pd.to_numeric(value, errors="coerce")
                    if pd.notna(numeric_value) and not isinstance(value, bool):
                        suffix = "%" if "%" in label else ""
                        formatted = (
                            f"{float(numeric_value):,.1f}{suffix}"
                            if suffix else f"{float(numeric_value):,.0f}"
                        )
                        value_column.write(formatted)
                    else:
                        value_column.write(str(value))
                st.divider()
    else:
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
    st.caption("Los lugares detectados por IA son propuestas de lectura. La vinculación municipal se valida contra el catálogo y la mención explícita en el texto, sin otra consulta de IA.")
    territory_results = query(
        """SELECT p.id AS mensaje, p.title AS titulo, ar.topic AS lugares_detectados,
                  ar.explanation AS explicacion,
                  (SELECT GROUP_CONCAT(pt.municipality, ', ') FROM publication_territories pt
                   WHERE pt.publication_id=p.id AND pt.state=?) AS municipios_vinculados,
                  p.url AS enlace
           FROM publications p JOIN analysis_results ar ON ar.publication_id=p.id
           JOIN analysis_approaches ap ON ap.id=ar.approach_id
           WHERE p.profile_id=? AND ap.name='Territorial' ORDER BY p.id DESC""",
        (linking_state, linking_profile_id),
    )
    if territory_results:
        st.markdown("#### Lugares detectados y vínculos municipales")
        st.dataframe(pd.DataFrame(territory_results), hide_index=True, width="stretch",
                     column_config={"enlace": st.column_config.LinkColumn("Original", display_text="Abrir")})

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
    from services.analysis_view import render_analysis

    render_analysis(profile_options())

elif page == "Prompts y consultas IA":
    st.subheader("Prompts y consultas IA")
    st.info("Consulta opcional con costo de API. Cada ejecución hace una nueva solicitud. Leer el historial no consulta IA ni genera ese costo.")
    st.caption(
        "Pregunta sobre mensajes y sus análisis guardados. No obtiene datos nuevos ni reemplaza análisis existentes."
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
    unified_history = query(
        """SELECT p.id AS mensaje, p.title AS titulo, ap.name AS enfoque,
                  ar.sentiment AS sentimiento, ar.topic AS tema, ar.explanation AS explicacion,
                  ar.method AS metodo, ar.model AS modelo, ar.analyzed_at AS fecha, p.url AS enlace
           FROM analysis_results ar JOIN publications p ON p.id=ar.publication_id
           JOIN analysis_approaches ap ON ap.id=ar.approach_id
           WHERE p.profile_id=? ORDER BY ar.analyzed_at DESC, p.id DESC""", (profile_id,))
    st.caption("Consulta local sin costo de IA. Los análisis completos se conservan; al ampliar una clasificación básica se guarda su versión anterior.")
    unified_versions = query(
        """SELECT v.publication_id AS mensaje, ap.name AS enfoque, v.replaced_at AS reemplazado,
                  v.previous_result AS resultado_anterior
           FROM analysis_result_versions v JOIN publications p ON p.id=v.publication_id
           JOIN analysis_approaches ap ON ap.id=v.approach_id
           WHERE p.profile_id=? ORDER BY v.id DESC""", (profile_id,))
    if unified_versions:
        with st.expander("Versiones anteriores de los enfoques"):
            version_display = []
            for version in unified_versions:
                previous = json.loads(version["resultado_anterior"])
                version_display.append({
                    "Mensaje": version["mensaje"], "Enfoque": version["enfoque"],
                    "Reemplazado": version["reemplazado"], "Sentimiento anterior": previous.get("sentiment"),
                    "Tema anterior": previous.get("topic"), "Explicación anterior": previous.get("explanation"),
                    "Método anterior": previous.get("method"), "Modelo anterior": previous.get("model"),
                })
            st.dataframe(pd.DataFrame(version_display), hide_index=True, width="stretch")
    if unified_history:
        st.markdown("#### Análisis por mensaje y enfoque")
        st.dataframe(pd.DataFrame(unified_history), hide_index=True, width="stretch",
                     column_config={"enlace": st.column_config.LinkColumn("Original", display_text="Abrir")})
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
        st.markdown("#### Clasificación original conservada")
        st.dataframe(pd.DataFrame(current_results), use_container_width=True, hide_index=True)
    if history_rows:
        st.markdown("#### Clasificaciones anteriores")
        st.dataframe(pd.DataFrame(history_rows), use_container_width=True, hide_index=True)
    if not current_results and not history_rows and not unified_history:
        st.info("Todavía no hay resultados ni versiones anteriores para este perfil.")

elif page == "Manual de usuario":
    st.subheader("Manual de usuario")
    manual_path = Path(__file__).resolve().with_name("MANUAL_USUARIO.md")
    st.markdown(manual_path.read_text(encoding="utf-8"))

else:
    st.subheader("Manual técnico")
    technical_manual_path = Path(__file__).resolve().with_name("MANUAL_TECNICO.md")
    st.markdown(technical_manual_path.read_text(encoding="utf-8"))
