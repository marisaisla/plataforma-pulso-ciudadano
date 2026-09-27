"""Load the 2021 Nayarit governor result and dictamen competitors/polls."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "pulso_ciudadano_local.db"
BOOK = ROOT / "data" / "nayarit_fuentes_oficiales" / "IEEN_Nayarit_2021_Gubernatura.xlsx"
SOURCE_URL = "https://ieenayarit.org/PDF/elecciones/2021/Gob21.xlsx"
PROFILE_ID = 7

MUNICIPAL_CODES = {
    "Acaponeta":"001","Ahuacatlan":"002","Amatlan de Canas":"003","Compostela":"004",
    "Huajicori":"005","Ixtlan del Rio":"006","Jala":"007","Xalisco":"008","Del Nayar":"009",
    "Rosamorada":"010","Ruiz":"011","San Blas":"012","San Pedro Lagunillas":"013",
    "Santa Maria del Oro":"014","Santiago Ixcuintla":"015","Tecuala":"016","Tepic":"017",
    "Tuxpan":"018","La Yesca":"019","Bahia de Banderas":"020",
}

COMPETITORS = [
    ("Héctor Santana", "Morena", "Aspirante interno", "Bahía de Banderas", "Principal rival interno observado; cuenta con estructura municipal y liderazgo en varias mediciones."),
    ("Jasmín Bugarín", "PVEM", "Aspirante de coalición", "Nayarit", "Presencia estatal y liderazgo en la medición de Alius; puede modificar la negociación de género y alianza."),
    ("María Elizabeth López", "Morena", "Aspirante interna", "Nayarit", "Estructura partidista y presencia institucional; menor liderazgo en las mediciones citadas."),
    ("Pavel Jarero", "Morena", "Referente interno", "Nayarit", "Trayectoria legislativa y partidista; puede influir en la unidad y estructura interna."),
    ("Movimiento Ciudadano", "Movimiento Ciudadano", "Principal fuerza opositora", "Nayarit", "Segunda fuerza en varios estudios; candidatura y estructura aún por definir."),
    ("PAN / PRI", "PAN-PRI", "Bloque opositor potencial", "Nayarit", "Marcas y liderazgos regionales con alianzas todavía inciertas."),
]

POLLS = [
    ("Nayarit 2027 · interna Morena", "Rubrum", "Nayarit", "2026-09-03", 800, "Llamadas automatizadas; no combinar con estudios de método distinto.", 38.4, "Ponce 38.4%; Héctor Santana 20.6%."),
    ("Nayarit 2027 · interna Morena", "FactoMétrica", "Nayarit", "2026-09-14", None, "Medición pública; ficha metodológica pendiente de incorporar al expediente.", 31.1, "Ponce 31.1%; Héctor Santana 22.1%."),
    ("Nayarit 2027 · interna Morena", "GobernArte", "Nayarit", "2026-09-07", 500, "Levantamiento del 3 al 7 de septiembre de 2026.", 22.9, "Ponce 22.9%; Héctor Santana 35.7%."),
    ("Nayarit 2027 · interna Morena", "CE Research", "Nayarit", "2026-08", None, "Seguimiento publicado por C&E Research; ficha completa pendiente.", 24.7, "Ponce 24.7%; Héctor Santana 33.7%."),
    ("Nayarit 2027 · interna Morena", "Massive Caller", "Nayarit", "2026-05-14", 1000, "Mil entrevistas; error referido de ±3.4 puntos porcentuales.", 24.3, "Ponce 24.3%; Héctor Santana 35.7%."),
    ("Nayarit 2027 · escenario de coalición", "Alius / Polls.mx", "Nayarit", "2026-09", None, "Escenario de coalición distinto; no comparable directamente con la interna de Morena.", 17.6, "Ponce 17.6%; Jasmín Bugarín 42.1%."),
    ("Nayarit 2027 · interna Morena", "Cripeso", "Nayarit", "2026-09", None, "Seguridad y corrupción aparecen entre los problemas dominantes.", 19.37, "Ponce 19.37%; Héctor Santana en primer lugar."),
]


def clean_name(value: object) -> str:
    text = str(value).strip()
    starts = {
        "ahuacatl":"Ahuacatlan", "amatl":"Amatlan de Canas", "bah":"Bahia de Banderas",
        "ixtl":"Ixtlan del Rio", "santa mar":"Santa Maria del Oro",
    }
    folded = text.casefold()
    for prefix, result in starts.items():
        if folded.startswith(prefix):
            return result
    return text


def number(value: object) -> float:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return 0.0 if pd.isna(parsed) else float(parsed)


def load_election(conn: sqlite3.Connection) -> int:
    frame = pd.read_excel(BOOK, sheet_name="Concentrado", header=5).dropna(how="all")
    count = 0
    for _, row in frame.iterrows():
        municipality = clean_name(row.iloc[0])
        if municipality not in MUNICIPAL_CODES or municipality == "La Yesca":
            continue
        payload = {
            "votes_mc": number(row.get("MC")),
            "votes_viva": number(row.get("VIVA")),
            "votes_mln": number(row.get("MLN")),
            "votes_pes": number(row.get("PES")),
            "votes_rsp": number(row.get("RSP")),
            "votes_fxm": number(row.get("FXM")),
            "votes_pan_pri_prd": number(row.get("PAN-PRI-PRD")),
            "votes_pt_pvem_morena_nan": number(row.get("PT-PVEM-MORENA-NAN")),
            "votes_no_reg": number(row.get("Candidaturas no registradas")),
            "votes_nulos": number(row.get("Votos nulos")),
        }
        payload["numero_votos_validos"] = sum(v for k,v in payload.items() if k not in {"votes_nulos","votes_no_reg"})
        payload["votes_total"] = payload["numero_votos_validos"] + payload["votes_no_reg"] + payload["votes_nulos"]
        options = {k:v for k,v in payload.items() if k not in {"votes_nulos","votes_no_reg","votes_total","numero_votos_validos"}}
        winner = max(options, key=options.get)
        payload.update(opcion_mayor_votacion=winner, votos_opcion_mayor=options[winner])
        conn.execute(
            """INSERT INTO territorial_election_results
            (state, municipality_code, municipality, election_type, election_year, payload, source)
            VALUES ('Nayarit', ?, ?, 'Gubernatura', 2021, ?, ?)
            ON CONFLICT(state, municipality, election_type, election_year) DO UPDATE SET
            municipality_code=excluded.municipality_code, payload=excluded.payload,
            source=excluded.source, imported_at=CURRENT_TIMESTAMP""",
            (MUNICIPAL_CODES[municipality], municipality, json.dumps(payload, ensure_ascii=False), SOURCE_URL),
        )
        count += 1
    return count


def load_competitors(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM viability_competitors WHERE profile_id=?", (PROFILE_ID,))
    conn.executemany(
        """INSERT INTO viability_competitors
        (profile_id,name,party_or_coalition,condition,territory,positioning_note,source_url)
        VALUES (?,?,?,?,?,?,NULL)""",
        [(PROFILE_ID, *row) for row in COMPETITORS],
    )
    return len(COMPETITORS)


def load_polls(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM viability_surveys WHERE profile_id=?", (PROFILE_ID,))
    conn.executemany(
        """INSERT INTO viability_surveys
        (profile_id,name,pollster,territory,fieldwork_date,sample_size,methodology,
         profile_result_pct,source_url,notes)
        VALUES (?,?,?,?,?,?,?,?,NULL,?)""",
        [(PROFILE_ID, *row) for row in POLLS],
    )
    return len(POLLS)


def main() -> None:
    with sqlite3.connect(DB) as conn:
        result = {
            "municipios_gubernatura_2021": load_election(conn),
            "competidores": load_competitors(conn),
            "encuestas": load_polls(conn),
        }
        conn.commit()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
