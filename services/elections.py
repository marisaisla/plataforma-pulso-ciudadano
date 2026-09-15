"""Importación local de resultados electorales municipales verificables."""

from __future__ import annotations

import io
import json
import unicodedata

import pandas as pd
import requests


TEMPLATE_COLUMNS = [
    "cve_mun", "municipio", "lista_nominal", "participacion_pct", "votes_total",
    "votes_nulos", "ganador_candidatura", "segundo_lugar", "votos_ganador",
    "margen_votos", "votes_pan", "votes_pri", "votes_prd", "votes_morena",
    "votes_pt", "votes_pvem", "votes_mc", "votes_mxrep", "votes_pueblo",
]

SONORA_2024_RESULTS_URL = (
    "https://ieesonora.org.mx/elecciones2024/resultados/basedatos/"
    "TABLA_DE_RESULTADOS_GLOBAL_2024.xlsx"
)
SONORA_2024_LOCAL_DEPUTIES_URL = (
    "https://ieesonora.org.mx/elecciones2024/resultados/basedatos/"
    "TABLA_DE_RESULTADOS_DIPUTADO_2024.xlsx"
)

_SONORA_COLUMNS = {
    "PARTIDO_ACCION_NACIONAL": "votes_pan",
    "PARTIDO_REVOLUCIONARIO_INSTITUCIONAL": "votes_pri",
    "PARTIDO_DE_LA_REVOLUCION_DEMOCRATICA": "votes_prd",
    "PARTIDO_VERDE_ECOLOGISTA_DE_MEXICO": "votes_pvem",
    "PARTIDO_DEL_TRABAJO": "votes_pt",
    "MOVIMIENTO_CIUDADANO": "votes_mc",
    "MORENA": "votes_morena",
    "PARTIDO_NUEVA_ALIANZA": "votes_nueva_alianza",
    "PARTIDO_ENCUENTRO_SOLIDARIO_SONORA": "votes_encuentro_solidario_sonora",
    "PARTIDO_SONORENSE": "votes_partido_sonorense",
    "COALICION_PAN_PRI_PRD": "votes_coalicion_pan_pri_prd",
    "COALICION_PAN_PRI": "votes_coalicion_pan_pri",
    "COALICION_PAN_PRD": "votes_coalicion_pan_prd",
    "COALICION_PRI_PRD": "votes_coalicion_pri_prd",
    "CANDIDATURA_COMUN_SIGAMOS_HACIENDO_HISTORIA": "votes_sigamos_haciendo_historia",
    "CANDIDATURA_COMUN_FURZA_Y_CORAZON_POR_SONORA": "votes_fuerza_y_corazon_sonora",
    "AMIGOS_DE_BAES": "votes_amigos_de_baes",
    "ETCHOJOA_INDEPENDIENTE": "votes_etchojoa_independiente",
    "MAGDALENA_SOMOS_TODOS": "votes_magdalena_somos_todos",
    "PROGRESA_Y_EVOLUCIONA_SANTA_ANA": "votes_progresa_santa_ana",
    "CAMPESINOS_DE_LA_LLAVE_DEL_DESIERTO": "votes_campesinos_llave_desierto",
    "NACOZARI_SOMOS_TODOS": "votes_nacozari_somos_todos",
}

_ALIASES = {
    "municipio": "municipio", "nombre_municipio": "municipio", "municipality": "municipio",
    "cve_mun": "cve_mun", "clave_municipio": "cve_mun", "municipio_id": "cve_mun",
    "lista_nominal": "lista_nominal", "participacion_pct": "participacion_pct",
    "participacion": "participacion_pct", "votos_total": "votes_total", "total_votos": "votes_total",
    "votes_total": "votes_total", "votos_nulos": "votes_nulos", "votes_nulos": "votes_nulos",
    "ganador": "ganador_candidatura", "ganador_candidatura": "ganador_candidatura",
    "segundo_lugar": "segundo_lugar", "votos_ganador": "votos_ganador",
    "margen_votos": "margen_votos", "votos_pan": "votes_pan", "votes_pan": "votes_pan",
    "votos_pri": "votes_pri", "votes_pri": "votes_pri", "votos_prd": "votes_prd",
    "votes_prd": "votes_prd", "votos_morena": "votes_morena", "votes_morena": "votes_morena",
    "votos_pt": "votes_pt", "votes_pt": "votes_pt", "votos_pvem": "votes_pvem",
    "votes_pvem": "votes_pvem", "votos_mc": "votes_mc", "votes_mc": "votes_mc",
    "votos_mxrep": "votes_mxrep", "votes_mxrep": "votes_mxrep",
    "votos_pueblo": "votes_pueblo", "votes_pueblo": "votes_pueblo",
}


def _key(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return "_".join(text.casefold().strip().replace("-", " ").split())


def election_template_csv() -> bytes:
    """Return a UTF-8 template users may complete from official municipal results."""
    return (",".join(TEMPLATE_COLUMNS) + "\n").encode("utf-8")


def fetch_sonora_municipal_2024() -> tuple[list[dict], str]:
    """Download and aggregate the official IEE Sonora municipal 2024 workbook."""
    response = requests.get(SONORA_2024_RESULTS_URL, timeout=90)
    response.raise_for_status()
    frame = pd.read_excel(io.BytesIO(response.content), skiprows=1)
    required = {"id_municipio_local", "municipio_local", "lista_nominal", "total_votos"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"La base oficial cambió y no contiene: {', '.join(sorted(missing))}.")

    numeric_columns = ["lista_nominal", "num_votos_nulos", "num_votos_can_nreg", "numero_votos_validos", "total_votos"]
    numeric_columns.extend(column for column in _SONORA_COLUMNS if column in frame.columns)
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)

    rows = []
    grouped = frame.groupby(["id_municipio_local", "municipio_local"], dropna=False)[numeric_columns].sum()
    for (code, municipality), values in grouped.iterrows():
        if pd.isna(code) or pd.isna(municipality) or not str(municipality).strip():
            continue
        total_votes = float(values["total_votos"])
        list_size = float(values["lista_nominal"])
        payload = {
            "lista_nominal": list_size,
            "votes_total": total_votes,
            "votes_nulos": float(values["num_votos_nulos"]),
            "votes_no_reg": float(values["num_votos_can_nreg"]),
            "numero_votos_validos": float(values["numero_votos_validos"]),
            "participacion_pct": round((total_votes / list_size) * 100, 2) if list_size else None,
        }
        for official_column, local_column in _SONORA_COLUMNS.items():
            if official_column in values:
                payload[local_column] = float(values[official_column])
        rows.append({
            "municipality": str(municipality).strip().title(),
            "municipality_code": str(int(code)).zfill(3),
            "payload": payload,
        })
    return rows, SONORA_2024_RESULTS_URL


def fetch_sonora_local_district_2024() -> tuple[list[dict], str]:
    """Aggregate the official 2024 local-deputy results by Sonora district.

    The IEE workbook is published at casilla level. This keeps the official
    votes but only aggregates them to the district level; it does not infer a
    candidate name when the published columns represent parties or coalitions.
    """
    response = requests.get(
        SONORA_2024_LOCAL_DEPUTIES_URL,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=90,
    )
    response.raise_for_status()
    frame = pd.read_excel(io.BytesIO(response.content), skiprows=1)
    required = {"id_distrito_local", "cabecera_distrital_local", "lista_nominal", "total_votos"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"La base oficial cambió y no contiene: {', '.join(sorted(missing))}.")

    # Rows whose section is 0 are workbook totals; excluding them prevents
    # double counting against individual casillas.
    if "seccion" in frame.columns:
        frame = frame[pd.to_numeric(frame["seccion"], errors="coerce").fillna(0) != 0].copy()
    numeric_columns = ["lista_nominal", "num_votos_nulos", "no_registrados", "numero_votos_validos", "total_votos"]
    numeric_columns.extend(column for column in _SONORA_COLUMNS if column in frame.columns)
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)

    # Las casillas especiales no tienen lista nominal asignada; sus votos se
    # conservan en el total, pero no intervienen en la tasa de participación.
    is_special = frame.get("tipo_casilla", pd.Series("", index=frame.index)).astype(str).str.upper().eq("S")
    regular_votes = frame.loc[~is_special].groupby(
        ["id_distrito_local", "cabecera_distrital_local"], dropna=False
    )["total_votos"].sum()

    rows = []
    grouped = frame.groupby(["id_distrito_local", "cabecera_distrital_local"], dropna=False)[numeric_columns].sum()
    for (district_code, district_name), values in grouped.iterrows():
        if pd.isna(district_code) or pd.isna(district_name):
            continue
        total_votes = float(values["total_votos"])
        list_size = float(values["lista_nominal"])
        regular_total = float(regular_votes.get((district_code, district_name), 0))
        payload = {
            "lista_nominal": list_size,
            "votes_total": total_votes,
            "votes_nulos": float(values["num_votos_nulos"]),
            "votes_no_reg": float(values["no_registrados"]),
            "numero_votos_validos": float(values["numero_votos_validos"]),
            "participacion_pct": round((regular_total / list_size) * 100, 2) if list_size else None,
        }
        options = {}
        for official_column, local_column in _SONORA_COLUMNS.items():
            if official_column in values:
                vote_value = float(values[official_column])
                payload[local_column] = vote_value
                options[local_column] = vote_value
        if options:
            payload["opcion_mayor_votacion"] = max(options, key=options.get)
            payload["votos_opcion_mayor"] = options[payload["opcion_mayor_votacion"]]
        rows.append({
            "district_code": str(int(district_code)).zfill(2),
            "district_name": str(district_name).strip().title(),
            "payload": payload,
        })
    return rows, SONORA_2024_LOCAL_DEPUTIES_URL


def fetch_sonora_local_sections_2024() -> tuple[list[dict], str]:
    """Aggregate the IEE Sonora 2024 deputy workbook by local district and section."""
    response = requests.get(
        SONORA_2024_LOCAL_DEPUTIES_URL,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=90,
    )
    response.raise_for_status()
    frame = pd.read_excel(io.BytesIO(response.content), skiprows=1)
    required = {
        "id_distrito_local", "id_municipio_local", "municipio_local", "seccion",
        "lista_nominal", "total_votos",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"La base oficial cambió y no contiene: {', '.join(sorted(missing))}.")

    frame["seccion"] = pd.to_numeric(frame["seccion"], errors="coerce").fillna(0)
    # La sección 0 contiene totales publicados en el libro, no una sección real.
    frame = frame[frame["seccion"] != 0].copy()
    numeric_columns = ["lista_nominal", "num_votos_nulos", "no_registrados", "numero_votos_validos", "total_votos"]
    numeric_columns.extend(column for column in _SONORA_COLUMNS if column in frame.columns)
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)

    group_columns = ["id_distrito_local", "id_municipio_local", "municipio_local", "seccion"]
    is_special = frame.get("tipo_casilla", pd.Series("", index=frame.index)).astype(str).str.upper().eq("S")
    regular_votes = frame.loc[~is_special].groupby(group_columns, dropna=False)["total_votos"].sum()
    grouped = frame.groupby(group_columns, dropna=False)[numeric_columns].sum()
    rows = []
    for (district, municipality_code, municipality, section), values in grouped.iterrows():
        if pd.isna(district) or pd.isna(section):
            continue
        total_votes = float(values["total_votos"])
        list_size = float(values["lista_nominal"])
        regular_total = float(regular_votes.get((district, municipality_code, municipality, section), 0))
        payload = {
            "lista_nominal": list_size,
            "votes_total": total_votes,
            "votes_nulos": float(values["num_votos_nulos"]),
            "votes_no_reg": float(values["no_registrados"]),
            "numero_votos_validos": float(values["numero_votos_validos"]),
            "participacion_pct": round((regular_total / list_size) * 100, 2) if list_size else None,
        }
        options = {}
        for official_column, local_column in _SONORA_COLUMNS.items():
            if official_column in values:
                vote_value = float(values[official_column])
                payload[local_column] = vote_value
                options[local_column] = vote_value
        if options:
            payload["opcion_mayor_votacion"] = max(options, key=options.get)
            payload["votos_opcion_mayor"] = options[payload["opcion_mayor_votacion"]]
        rows.append({
            "district_code": str(int(district)).zfill(2),
            "section_code": str(int(section)).zfill(4),
            "municipality_code": str(int(municipality_code)).zfill(3) if not pd.isna(municipality_code) else "",
            "municipality": str(municipality).strip().title() if not pd.isna(municipality) else "",
            "payload": payload,
        })
    return rows, SONORA_2024_LOCAL_DEPUTIES_URL


def parse_municipal_results(file_bytes: bytes) -> tuple[list[dict], list[str]]:
    """Parse a municipal CSV and preserve only recognised, non-empty fields."""
    frame = None
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            frame = pd.read_csv(io.BytesIO(file_bytes), encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
    if frame is None:
        return [], ["No fue posible leer el CSV. Guárdalo como UTF-8 o Latin-1."]

    renamed = {column: _ALIASES.get(_key(column), _key(column)) for column in frame.columns}
    frame = frame.rename(columns=renamed)
    if "municipio" not in frame.columns:
        return [], ["El archivo debe incluir la columna municipio (o nombre_municipio)."]

    rows, errors = [], []
    for index, item in frame.iterrows():
        municipality = str(item.get("municipio", "")).strip()
        if not municipality or municipality.casefold() == "nan":
            continue
        payload = {}
        for column in TEMPLATE_COLUMNS:
            if column in {"municipio", "cve_mun"} or column not in frame.columns:
                continue
            value = item[column]
            if pd.isna(value) or str(value).strip() == "":
                continue
            if column in {"ganador_candidatura", "segundo_lugar"}:
                payload[column] = str(value).strip()
            else:
                number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
                if pd.isna(number):
                    errors.append(f"Fila {index + 2}: {column} no es numérico y se omitió.")
                else:
                    payload[column] = float(number)
        if not payload:
            errors.append(f"Fila {index + 2}: {municipality} no contiene indicadores utilizables.")
            continue
        code = str(item.get("cve_mun", "")).strip().replace(".0", "")
        rows.append({"municipality": municipality, "municipality_code": code.zfill(3) if code else "", "payload": payload})
    return rows, errors


def decode_election_rows(rows) -> list[dict]:
    """Decode rows returned by SQLite into dictionaries ready for a GeoJSON join."""
    decoded = []
    for row in rows:
        try:
            payload = json.loads(row["payload"])
        except (TypeError, json.JSONDecodeError):
            continue
        decoded.append({
            "municipality": row["municipality"],
            "municipality_code": row["municipality_code"] or "",
            "payload": payload,
        })
    return decoded
