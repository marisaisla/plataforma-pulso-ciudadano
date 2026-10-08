"""Load official IEPAC local-election results for Yucatán (2021 and 2024)."""

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
RAW = storage_path("data") / "raw" / "yucatan"
MUNICIPAL_MAP = storage_path("data") / "yucatan_municipios_inegi.geojson"
STATE = "Yucatán"
SOURCE = "https://www.iepac.mx/micrositios/resultados-electorales"

SOURCES = [
    (2021, "Ayuntamientos", RAW / "YUCATAN AYU_EXT" / "2021_SEE_AYUN_YUC_SEC.xlsx"),
    (2021, "Diputaciones locales", RAW / "YUCATAN DIP_MR" / "2021_SEE_DIP_LOC_MR_YUC_SEC.csv"),
    (2024, "Ayuntamientos", RAW / "RESULTADOS AYUNTAMIENTOS" / "2024_AYUNTAMIENTO_SECCION.csv"),
    (2024, "Diputaciones locales", RAW / "RESULTADOS DIPUTACIONES LOC" / "2024_DIPUTADOS_SECCION.csv"),
]

VOTE_COLUMNS = {
    "PAN": "votes_pan", "PRI": "votes_pri", "PRD": "votes_prd", "PVEM": "votes_pvem",
    "PT": "votes_pt", "MC": "votes_mc", "MORENA": "votes_morena", "NAY": "votes_nay",
    "PES": "votes_pes", "RSP": "votes_rsp", "FXM": "votes_fxm", "CAND_IND1": "votes_independent",
    "PAN_PRI_PRD_NAY": "votes_pan_pri_prd_nay", "PAN_PRI_PRD": "votes_pan_pri_prd",
    "PAN_PRI_NAY": "votes_pan_pri_nay", "PAN_PRD_NAY": "votes_pan_prd_nay",
    "PRI_PRD_NAY": "votes_pri_prd_nay", "PAN_PRI": "votes_pan_pri",
    "PAN_PRD": "votes_pan_prd", "PAN_NAY": "votes_pan_nay", "PRI_PRD": "votes_pri_prd",
    "PRI_NAY": "votes_pri_nay", "PRD_NAY": "votes_prd_nay", "PRD_NAY_2": "votes_prd_nay_2",
    "PVEM_PT_MORENA": "votes_pvem_pt_morena", "PVEM_PT": "votes_pvem_pt",
    "PVEM_MORENA": "votes_pvem_morena", "PT_MORENA": "votes_pt_morena",
}


def normalize(value: object) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFD", str(value).strip().upper())
        if unicodedata.category(char) != "Mn"
    )


def number(value: object) -> float:
    parsed = pd.to_numeric(value, errors="coerce")
    return 0.0 if pd.isna(parsed) else float(parsed)


def load(path: Path) -> pd.DataFrame:
    if path.suffix.casefold() == ".xlsx":
        frame = pd.read_excel(path, dtype=str)
    else:
        for encoding in ("utf-8", "cp1252", "latin1"):
            try:
                frame = pd.read_csv(path, dtype=str, encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
    return frame[frame["SECCION"].astype(str).str.fullmatch(r"\d+")].copy()


def payload(row: pd.Series) -> dict[str, float | str | None]:
    item = {target: number(row.get(source)) for source, target in VOTE_COLUMNS.items()}
    item["votes_no_reg"] = number(row.get("NUM_VOTOS_CAN_NREG"))
    item["votes_nulos"] = number(row.get("NUM_VOTOS_NULOS"))
    item["votes_total"] = number(row.get("TOTAL_VOTOS"))
    item["numero_votos_validos"] = number(row.get("NUM_VOTOS_VALIDOS"))
    item["lista_nominal"] = number(row.get("LISTA_NOMINAL"))
    item["participacion_pct"] = round(100 * item["votes_total"] / item["lista_nominal"], 2) if item["lista_nominal"] else None
    options = [key for key in item if key.startswith("votes_") and key not in {"votes_total", "votes_no_reg", "votes_nulos"}]
    winner = max(options, key=lambda key: float(item[key] or 0))
    item["opcion_mayor_votacion"] = winner
    item["votos_opcion_mayor"] = item[winner]
    return item


def aggregate(items: list[dict]) -> dict:
    ignored = {"participacion_pct", "opcion_mayor_votacion", "votos_opcion_mayor"}
    out = {key: sum(float(item.get(key) or 0) for item in items) for key in {key for item in items for key in item if key not in ignored}}
    out["participacion_pct"] = round(100 * out["votes_total"] / out["lista_nominal"], 2) if out.get("lista_nominal") else None
    options = [key for key in out if key.startswith("votes_") and key not in {"votes_total", "votes_no_reg", "votes_nulos"}]
    winner = max(options, key=lambda key: float(out[key] or 0))
    out["opcion_mayor_votacion"] = winner
    out["votos_opcion_mayor"] = out[winner]
    return out


def main() -> None:
    municipalities = json.loads(MUNICIPAL_MAP.read_text(encoding="utf-8"))["features"]
    by_name = {normalize(feature["properties"].get("nom_agem", "")): feature["properties"] for feature in municipalities}
    with connection() as conn:
        conn.execute("DELETE FROM territorial_election_results WHERE state=?", (STATE,))
        conn.execute("DELETE FROM territorial_district_results WHERE state=?", (STATE,))
        conn.execute("DELETE FROM territorial_section_results WHERE state=?", (STATE,))
        conn.execute("DELETE FROM territories WHERE state=?", (STATE,))
        conn.execute("INSERT INTO territories (territory_type, state, municipality, notes) VALUES ('Estado', ?, '', ?)",
                     (STATE, "Base territorial en preparación con resultados oficiales IEPAC 2021 y 2024."))
        for feature in municipalities:
            props = feature["properties"]
            conn.execute("INSERT INTO territories (territory_type, state, municipality, notes) VALUES ('Municipio', ?, ?, ?)",
                         (STATE, props.get("nom_agem", ""), f"Clave INEGI: {str(props.get('cve_agem', '')).zfill(3)}"))

        summary = []
        for year, election_type, path in SOURCES:
            frame = load(path)
            municipal = defaultdict(list)
            district = defaultdict(list)
            sections = defaultdict(list)
            district_names: dict[str, str] = {}
            for _, row in frame.iterrows():
                municipality_code = str(row["ID_MUNICIPIO"]).zfill(3)
                source_name = str(row["MUNICIPIO"]).strip()
                map_props = by_name.get(normalize(source_name), {})
                municipality_name = map_props.get("nom_agem", source_name.title())
                district_code = str(row["ID_DISTRITO_LOCAL"]).zfill(2)
                section_code = str(row["SECCION"]).zfill(4)
                value = payload(row)
                municipal[(municipality_code, municipality_name)].append(value)
                sections[(district_code, section_code, municipality_code, municipality_name)].append(value)
                if election_type == "Diputaciones locales":
                    district[district_code].append(value)
                    district_names[district_code] = str(row["CABECERA_DISTRITAL_LOCAL"]).strip().title()
            for (code, name), values in municipal.items():
                conn.execute("""INSERT INTO territorial_election_results
                    (state, municipality_code, municipality, election_type, election_year, payload, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (STATE, code, name, election_type, year, json.dumps(aggregate(values), ensure_ascii=False), SOURCE))
            for (dcode, scode, mcode, mname), values in sections.items():
                conn.execute("""INSERT INTO territorial_section_results
                    (state, district_code, section_code, municipality_code, municipality, election_type, election_year, payload, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (STATE, dcode, scode, mcode, mname, election_type, year, json.dumps(aggregate(values), ensure_ascii=False), SOURCE))
            for code, values in district.items():
                conn.execute("""INSERT INTO territorial_district_results
                    (state, district_code, district_name, election_type, election_year, payload, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (STATE, code, district_names.get(code, f"Distrito {code}"), election_type, year, json.dumps(aggregate(values), ensure_ascii=False), SOURCE))
            summary.append((year, election_type, len(municipal), len(district), len(sections)))

        conn.execute("""UPDATE territories SET notes=? WHERE territory_type='Estado' AND state=?""",
                     (
                         "Base territorial completa: 106 municipios; resultados oficiales IEPAC 2021 y 2024; "
                         "14 indicadores INEGI para cada municipio; cartografía IEPAC de 21 distritos locales "
                         "y 1,122 secciones electorales.",
                         STATE,
                     ))
        conn.commit()
    for item in summary:
        print(item)


if __name__ == "__main__":
    main()
