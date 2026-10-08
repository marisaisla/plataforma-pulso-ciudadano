"""Carga los resultados municipales, distritales y por sección de Querétaro 2021.

Fuente primaria: Instituto Electoral del Estado de Querétaro (IEEQ), archivo
oficial de resultados de ayuntamientos. La cartografía territorial de la
plataforma permanece identificada como Marco Geográfico Electoral del INE.
"""

from __future__ import annotations

import sys as _storage_sys
from pathlib import Path as _StoragePath
_storage_sys.path.insert(0, str(_StoragePath(__file__).resolve().parents[1]))
from services.storage import storage_path


import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.database import connection
import unicodedata

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILE = storage_path("data") / "raw" / "queretaro_2021_ayuntamiento.xlsx"
SOURCE_URL = "https://ieeq.mx/contenido/elecciones/2020_2021/resultados/2021_Ayuntamiento.xlsx"
STATE = "Querétaro"
YEAR = 2021
ELECTION = "Ayuntamientos"

VOTE_COLUMNS = {
    "PAN": "votes_pan",
    "PRI": "votes_pri",
    "PRD": "votes_prd",
    "MC": "votes_mc",
    "PVEM": "votes_pvem",
    "MORENA": "votes_morena",
    "PT": "votes_pt",
    "QI": "votes_qi",
    "PES": "votes_pes",
    "RSP": "votes_rsp",
    "FM": "votes_fm",
    "PAN_QI": "votes_pan_qi",
    "PRI_PVEM": "votes_pri_pvem",
    "PVEM_PT": "votes_pvem_pt",
    "PAN_PRD_QI": "votes_pan_prd_qi",
    "PAN_PRD": "votes_pan_prd",
    "PRD_QI": "votes_prd_qi",
    "PT_QI": "votes_pt_qi",
}


def number(value: object) -> float:
    value = pd.to_numeric(value, errors="coerce")
    return 0.0 if pd.isna(value) else float(value)


def canonical_municipality(value: object, catalog: dict[str, str]) -> str:
    """Use the name already registered in territories, preserving its accents."""
    raw = str(value).strip()
    key = "".join(char for char in unicodedata.normalize("NFD", raw.upper()) if unicodedata.category(char) != "Mn")
    return catalog.get(key, raw.title())


def payload_from_row(row: pd.Series) -> dict[str, float | str | None]:
    payload: dict[str, float | str | None] = {
        destination: number(row.get(source)) for source, destination in VOTE_COLUMNS.items()
    }
    payload["numero_votos_validos"] = number(row.get("NUM_VOTOS_VALIDOS"))
    payload["votes_no_reg"] = number(row.get("NUM_VOTOS_CAN_NREG"))
    payload["votes_nulos"] = number(row.get("NUM_VOTOS_NULOS"))
    payload["votes_total"] = number(row.get("TOTAL_VOTOS"))
    payload["lista_nominal"] = number(row.get("LISTA_NOMINAL"))
    payload["participacion_pct"] = (
        round(100 * payload["votes_total"] / payload["lista_nominal"], 2)
        if payload["lista_nominal"] else None
    )
    vote_keys = [key for key in payload if key.startswith("votes_") and key not in {"votes_total", "votes_no_reg", "votes_nulos"}]
    winner = max(vote_keys, key=lambda key: float(payload[key] or 0))
    payload["opcion_mayor_votacion"] = winner
    payload["votos_opcion_mayor"] = payload[winner]
    return payload


def aggregate_payload(payloads: list[dict[str, float | str | None]]) -> dict[str, float | str | None]:
    summed: dict[str, float | str | None] = {}
    keys = {key for item in payloads for key in item if key not in {"participacion_pct", "opcion_mayor_votacion", "votos_opcion_mayor"}}
    for key in keys:
        values = [item.get(key) for item in payloads]
        if any(value is not None for value in values):
            summed[key] = sum(float(value or 0) for value in values)
        else:
            summed[key] = None
    if summed.get("lista_nominal"):
        summed["participacion_pct"] = round(100 * float(summed["votes_total"] or 0) / float(summed["lista_nominal"]), 2)
    else:
        summed["participacion_pct"] = None
    vote_keys = [key for key in summed if key.startswith("votes_") and key not in {"votes_total", "votes_no_reg", "votes_nulos"}]
    winner = max(vote_keys, key=lambda key: float(summed[key] or 0))
    summed["opcion_mayor_votacion"] = winner
    summed["votos_opcion_mayor"] = summed[winner]
    return summed


def run() -> None:
    if not SOURCE_FILE.exists():
        raise FileNotFoundError(f"No se encontró el archivo oficial: {SOURCE_FILE}")

    municipalities = pd.read_excel(SOURCE_FILE, sheet_name="Municipio", header=1)
    sections = pd.read_excel(SOURCE_FILE, sheet_name="Sección", header=1)
    municipalities.columns = [str(column).strip() for column in municipalities.columns]
    sections.columns = [str(column).strip() for column in sections.columns]
    municipalities = municipalities.dropna(subset=["ID_MUNICIPIO", "MUNICIPIO"])
    sections = sections.dropna(subset=["ID_DISTRITO_LOCAL", "ID_MUNICIPIO", "MUNICIPIO", "SECCION"])

    con = connection()
    try:
        catalog = {}
        for (municipality,) in con.execute(
            "SELECT municipality FROM territories WHERE territory_type='Municipio' AND state=?", (STATE,)
        ):
            key = "".join(char for char in unicodedata.normalize("NFD", municipality.upper()) if unicodedata.category(char) != "Mn")
            catalog[key] = municipality
        con.execute("DELETE FROM territorial_election_results WHERE state=? AND election_type=? AND election_year=?", (STATE, ELECTION, YEAR))
        con.execute("DELETE FROM territorial_district_results WHERE state=? AND election_type=? AND election_year=?", (STATE, ELECTION, YEAR))
        con.execute("DELETE FROM territorial_section_results WHERE state=? AND election_type=? AND election_year=?", (STATE, ELECTION, YEAR))

        for _, row in municipalities.iterrows():
            con.execute(
                """INSERT INTO territorial_election_results
                (state, municipality_code, municipality, election_type, election_year, payload, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (STATE, f"{int(number(row['ID_MUNICIPIO'])):03d}", canonical_municipality(row["MUNICIPIO"], catalog), ELECTION, YEAR,
                 json.dumps(payload_from_row(row), ensure_ascii=False), SOURCE_URL),
            )

        section_rows: list[tuple[str, str, str, str, dict[str, float | str | None]]] = []
        for _, row in sections.iterrows():
            district = f"{int(number(row['ID_DISTRITO_LOCAL'])):02d}"
            municipality_code = f"{int(number(row['ID_MUNICIPIO'])):03d}"
            municipality = canonical_municipality(row["MUNICIPIO"], catalog)
            section = f"{int(number(row['SECCION'])):04d}"
            payload = payload_from_row(row)
            section_rows.append((district, municipality_code, municipality, section, payload))
            con.execute(
                """INSERT INTO territorial_section_results
                (state, district_code, section_code, municipality_code, municipality, election_type, election_year, payload, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (STATE, district, section, municipality_code, municipality, ELECTION, YEAR,
                 json.dumps(payload, ensure_ascii=False), SOURCE_URL),
            )

        districts: dict[str, list[dict[str, float | str | None]]] = {}
        for district, _, _, _, payload in section_rows:
            districts.setdefault(district, []).append(payload)
        for district, payloads in districts.items():
            con.execute(
                """INSERT INTO territorial_district_results
                (state, district_code, district_name, election_type, election_year, payload, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (STATE, district, f"Distrito local {district}", ELECTION, YEAR,
                 json.dumps(aggregate_payload(payloads), ensure_ascii=False), SOURCE_URL),
            )

        con.execute(
            """UPDATE territories SET notes=?
            WHERE territory_type='Estado' AND state=?""",
            ("Base territorial INE: 18 municipios. Resultados IEEQ 2021 cargados: 18 municipios, 15 distritos locales y "
             f"{len(section_rows):,} secciones. Pendiente: cartografía geográfica, resultados 2024 e indicadores INEGI.", STATE),
        )
        con.execute(
            """INSERT INTO import_runs
            (source_application, source_database, imported_records, notes, source_type, status, duplicates, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("Go2Win", "Resultados de Ayuntamientos 2021, IEEQ", 18 + len(districts) + len(section_rows),
             "Carga histórica oficial de Querétaro sin perfil asociado.", "IEEQ / INE", "Completado", 0,
             f"18 municipios; {len(districts)} distritos locales; {len(section_rows)} secciones. Marco territorial: INE."),
        )
        con.commit()
        print(f"Importados: {len(municipalities)} municipios, {len(districts)} distritos, {len(section_rows)} secciones.")
    finally:
        con.close()


if __name__ == "__main__":
    run()
