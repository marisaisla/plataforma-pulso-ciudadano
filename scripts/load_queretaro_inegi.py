"""Carga indicadores municipales oficiales de INEGI para Querétaro."""

from __future__ import annotations

import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.database import connection

from services.inegi import CORE_INDICATORS, collect_municipal_indicator
from services.settings import get_setting


ROOT = Path(__file__).resolve().parents[1]
STATE = "Querétaro"

# Claves geoestadísticas INEGI verificadas contra la serie municipal de población 2020.
MUNICIPALITIES = [
    ("001", "Amealco de Bonfil"), ("002", "Pinal de Amoles"), ("003", "Arroyo Seco"),
    ("004", "Cadereyta de Montes"), ("005", "Colón"), ("006", "Corregidora"),
    ("007", "Ezequiel Montes"), ("008", "Huimilpan"), ("009", "Jalpan de Serra"),
    ("010", "Landa de Matamoros"), ("011", "El Marqués"), ("012", "Pedro Escobedo"),
    ("013", "Peñamiller"), ("014", "Querétaro"), ("015", "San Joaquín"),
    ("016", "San Juan del Río"), ("017", "Tequisquiapan"), ("018", "Tolimán"),
]


def main() -> None:
    token = get_setting("INEGI_INDICATORS_TOKEN")
    if not token:
        raise RuntimeError("No hay token privado de INEGI configurado.")
    features = [
        {"properties": {"cve_agem": code, "nom_agem": municipality}}
        for code, municipality in MUNICIPALITIES
    ]
    stored = 0
    errors: list[str] = []
    with connection() as conn:
        for indicator_id in dict.fromkeys(CORE_INDICATORS.values()):
            rows, current_errors, _ = collect_municipal_indicator(STATE, features, indicator_id, token)
            errors.extend(current_errors)
            for row in rows:
                conn.execute(
                    """INSERT INTO territorial_indicators
                    (state, municipality_code, municipality, indicator_id, indicator_name, unit, value, period, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'INEGI Banco de Indicadores')
                    ON CONFLICT(state, municipality_code, indicator_id, period) DO UPDATE SET
                      municipality=excluded.municipality, indicator_name=excluded.indicator_name,
                      unit=excluded.unit, value=excluded.value, source=excluded.source,
                      retrieved_at=CURRENT_TIMESTAMP""",
                    (row["state"], row["municipality_code"], row["municipality"], row["indicator_id"],
                     row["indicator_name"], row["unit"], row["value"], row["period"]),
                )
                stored += 1
            conn.commit()
        indicators = conn.execute(
            "SELECT COUNT(*) FROM territorial_indicators WHERE state=?", (STATE,)
        ).fetchone()[0]
        municipalities = conn.execute(
            "SELECT COUNT(DISTINCT municipality_code) FROM territorial_indicators WHERE state=?", (STATE,)
        ).fetchone()[0]
        conn.execute(
            """UPDATE territories SET notes=? WHERE territory_type='Estado' AND state=?""",
            ("Base territorial INE: 18 municipios. Resultados IEEQ 2021 y 2024 cargados. "
             f"Indicadores INEGI: {indicators} registros en {municipalities} municipios. Pendiente: cartografía geográfica.", STATE),
        )
        conn.execute(
            """INSERT INTO import_runs
            (source_application, source_database, imported_records, notes, source_type, status, duplicates, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("Go2Win", "Banco de Indicadores INEGI", stored,
             "Carga de indicadores municipales oficiales para Querétaro.", "INEGI", "Completado", 0,
             f"Indicadores consultados: {len(dict.fromkeys(CORE_INDICATORS.values()))}; municipios: {municipalities}; errores: {len(errors)}."),
        )
        conn.commit()
    print(json.dumps({"guardados": stored, "municipios": municipalities, "indicadores": indicators,
                      "errores": len(errors), "muestra_errores": errors[:3]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
