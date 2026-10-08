"""Carga resultados oficiales 2024 de Querétaro para Go2Win.

El paquete publicado por el IEEQ incluye la elección de ayuntamientos y la
elección de diputaciones locales, ambas desagregadas a nivel casilla.
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
from collections import defaultdict

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = storage_path("data") / "raw" / "ieeq_2024" / "IEEQ_RESULTADOS_QRO"
AYUNTAMIENTO_FILE = RAW / "IEEQ_AYUN_QRO" / "QRO_AYUN_RESULTADOS_2024.csv"
DIPUTACION_FILE = RAW / "IEEQ_DIP_QRO" / "QRO_DIP_LOC_RESULTADOS_2024.csv"
CATALOG_FILE = storage_path("data") / "raw" / "JSON_CATALOGO.json"
SOURCE_URL = "https://ieeq.mx/contenido/elecciones/2023_2024/resultados/"
STATE = "Querétaro"
YEAR = 2024

VOTE_COLUMNS = {
    "PAN": "votes_pan", "PRI": "votes_pri", "PRD": "votes_prd", "MC": "votes_mc",
    "PVEM": "votes_pvem", "MORENA": "votes_morena", "PT": "votes_pt",
    "QS": "votes_qs", "EMC": "votes_emc", "JBLL": "votes_jbll", "RHR": "votes_rhr",
    "LDBG": "votes_ldbg", "ATV": "votes_atv", "SSP": "votes_ssp", "MRGH": "votes_mrgh",
    "SMG": "votes_smg", "PVEM-MORENA-PT": "votes_pvem_pt_morena",
    "PVEM-MORENA": "votes_pvem_morena", "PVEM-PT": "votes_pvem_pt",
    "MORENA-PT": "votes_pt_morena", "PAN-PRI-PRD": "votes_pan_pri_prd",
    "PAN-PRI": "votes_pan_pri", "PAN-PRD": "votes_pan_prd", "PRI-PRD": "votes_pri_prd",
}


def number(value: object) -> float:
    result = pd.to_numeric(value, errors="coerce")
    return 0.0 if pd.isna(result) else float(result)


def key(value: object) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFD", str(value).strip().upper())
        if unicodedata.category(char) != "Mn"
    )


def read_csv(path: Path) -> pd.DataFrame:
    # El ZIP oficial usa codificación Windows-1252, no UTF-8.
    frame = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="cp1252")
    return frame[frame["SECCION"].str.fullmatch(r"\d+")].copy()


def to_payload(row: pd.Series) -> dict[str, float | str | None]:
    data: dict[str, float | str | None] = {
        destination: number(row.get(source)) for source, destination in VOTE_COLUMNS.items()
    }
    data["votes_no_reg"] = number(row.get("NO_REGISTRADAS"))
    data["votes_nulos"] = number(row.get("NULOS"))
    data["votes_total"] = number(row.get("TOTAL_VOTOS"))
    data["numero_votos_validos"] = max(0.0, data["votes_total"] - data["votes_no_reg"] - data["votes_nulos"])
    data["lista_nominal"] = number(row.get("LISTA_NOMINAL"))
    data["participacion_pct"] = (
        round(100 * float(data["votes_total"]) / float(data["lista_nominal"]), 2)
        if data["lista_nominal"] else None
    )
    candidates = [name for name in data if name.startswith("votes_") and name not in {"votes_total", "votes_no_reg", "votes_nulos"}]
    winner = max(candidates, key=lambda name: float(data[name] or 0))
    data["opcion_mayor_votacion"] = winner
    data["votos_opcion_mayor"] = data[winner]
    return data


def aggregate(items: list[dict[str, float | str | None]]) -> dict[str, float | str | None]:
    ignored = {"participacion_pct", "opcion_mayor_votacion", "votos_opcion_mayor"}
    out: dict[str, float | str | None] = {}
    for name in {name for item in items for name in item if name not in ignored}:
        out[name] = sum(float(item.get(name) or 0) for item in items)
    out["participacion_pct"] = (
        round(100 * float(out["votes_total"]) / float(out["lista_nominal"]), 2)
        if out.get("lista_nominal") else None
    )
    candidates = [name for name in out if name.startswith("votes_") and name not in {"votes_total", "votes_no_reg", "votes_nulos"}]
    winner = max(candidates, key=lambda name: float(out[name] or 0))
    out["opcion_mayor_votacion"] = winner
    out["votos_opcion_mayor"] = out[winner]
    return out


def run() -> None:
    for required in (AYUNTAMIENTO_FILE, DIPUTACION_FILE, CATALOG_FILE):
        if not required.exists():
            raise FileNotFoundError(f"Falta archivo oficial: {required}")
    ayuntamientos = read_csv(AYUNTAMIENTO_FILE)
    diputaciones = read_csv(DIPUTACION_FILE)
    catalog_entries = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    section_catalog = {str(item["seccion"]).zfill(4): item for item in catalog_entries}

    con = connection()
    try:
        municipal_catalog = {
            key(municipality): municipality
            for (municipality,) in con.execute(
                "SELECT municipality FROM territories WHERE territory_type='Municipio' AND state=?", (STATE,)
            )
        }
        canonical = lambda value: municipal_catalog.get(key(value), str(value).title())

        con.execute("DELETE FROM territorial_election_results WHERE state=? AND election_type='Ayuntamientos' AND election_year=?", (STATE, YEAR))
        con.execute("DELETE FROM territorial_section_results WHERE state=? AND election_type='Ayuntamientos' AND election_year=?", (STATE, YEAR))
        con.execute("DELETE FROM territorial_district_results WHERE state=? AND election_type='Diputaciones locales' AND election_year=?", (STATE, YEAR))
        con.execute("DELETE FROM territorial_section_results WHERE state=? AND election_type='Diputaciones locales' AND election_year=?", (STATE, YEAR))

        municipal_payloads: dict[tuple[str, str], list[dict[str, float | str | None]]] = defaultdict(list)
        # La sección es única dentro de la entidad. Se agrupan sus casillas antes
        # de asignarle municipio y distrito mediante el catálogo geoelectoral.
        section_payloads: dict[str, list[dict[str, float | str | None]]] = defaultdict(list)
        for _, row in ayuntamientos.iterrows():
            municipality_code = str(row["ID_MUNICIPIO"]).zfill(3)
            municipality = canonical(row["MUNICIPIO"])
            section = str(row["SECCION"]).zfill(4)
            item = to_payload(row)
            municipal_payloads[(municipality_code, municipality)].append(item)
            section_payloads[section].append(item)

        for (municipality_code, municipality), items in municipal_payloads.items():
            con.execute(
                """INSERT INTO territorial_election_results
                (state, municipality_code, municipality, election_type, election_year, payload, source)
                VALUES (?, ?, ?, 'Ayuntamientos', ?, ?, ?)""",
                (STATE, municipality_code, municipality, YEAR, json.dumps(aggregate(items), ensure_ascii=False), SOURCE_URL),
            )
        for section, items in section_payloads.items():
            entry = section_catalog.get(section, {})
            district = f"{int(entry.get('id_distrito', 0)):02d}"
            municipality_code = str(entry.get("id_municipio", "")).zfill(3) if entry else None
            municipality = canonical(entry.get("nombre_municipio", "")) if entry else None
            con.execute(
                """INSERT INTO territorial_section_results
                (state, district_code, section_code, municipality_code, municipality, election_type, election_year, payload, source)
                VALUES (?, ?, ?, ?, ?, 'Ayuntamientos', ?, ?, ?)""",
                (STATE, district, section, municipality_code, municipality, YEAR,
                 json.dumps(aggregate(items), ensure_ascii=False), SOURCE_URL),
            )

        district_payloads: dict[str, list[dict[str, float | str | None]]] = defaultdict(list)
        dip_sections: dict[tuple[str, str], list[dict[str, float | str | None]]] = defaultdict(list)
        district_names: dict[str, str] = {}
        for _, row in diputaciones.iterrows():
            district = str(row["ID_DISTRITO_LOCAL"]).zfill(2)
            section = str(row["SECCION"]).zfill(4)
            item = to_payload(row)
            district_payloads[district].append(item)
            dip_sections[(district, section)].append(item)
            district_names[district] = str(row["DISTRITO_LOCAL"]).strip() or f"Distrito local {district}"
        for district, items in district_payloads.items():
            con.execute(
                """INSERT INTO territorial_district_results
                (state, district_code, district_name, election_type, election_year, payload, source)
                VALUES (?, ?, ?, 'Diputaciones locales', ?, ?, ?)""",
                (STATE, district, district_names[district], YEAR, json.dumps(aggregate(items), ensure_ascii=False), SOURCE_URL),
            )
        for (district, section), items in dip_sections.items():
            entry = section_catalog.get(section, {})
            municipality_code = str(entry.get("id_municipio", "")).zfill(3) if entry else None
            municipality = canonical(entry.get("nombre_municipio", "")) if entry else None
            con.execute(
                """INSERT INTO territorial_section_results
                (state, district_code, section_code, municipality_code, municipality, election_type, election_year, payload, source)
                VALUES (?, ?, ?, ?, ?, 'Diputaciones locales', ?, ?, ?)""",
                (STATE, district, section, municipality_code, municipality, YEAR,
                 json.dumps(aggregate(items), ensure_ascii=False), SOURCE_URL),
            )

        counts = (len(municipal_payloads), len(section_payloads), len(district_payloads), len(dip_sections))
        con.execute(
            """UPDATE territories SET notes=? WHERE territory_type='Estado' AND state=?""",
            ("Base territorial INE: 18 municipios. Resultados IEEQ: Ayuntamientos 2021 y 2024, "
             f"incluyendo {counts[2]} distritos locales y {counts[1]} secciones municipales en 2024. "
             "Pendiente: cartografía geográfica e indicadores INEGI.", STATE),
        )
        con.execute(
            """INSERT INTO import_runs
            (source_application, source_database, imported_records, notes, source_type, status, duplicates, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("Go2Win", "Resultados 2024, IEEQ", sum(counts), "Carga oficial 2024 de Querétaro sin perfil asociado.",
             "IEEQ / INE", "Completado", 0,
             f"Ayuntamientos: {counts[0]} municipios y {counts[1]} secciones. Diputaciones: {counts[2]} distritos y {counts[3]} secciones."),
        )
        con.commit()
        print(f"Ayuntamientos: {counts[0]} municipios y {counts[1]} secciones.")
        print(f"Diputaciones: {counts[2]} distritos y {counts[3]} secciones.")
    finally:
        con.close()


if __name__ == "__main__":
    run()
