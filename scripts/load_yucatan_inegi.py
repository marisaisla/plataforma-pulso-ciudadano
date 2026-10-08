"""Load the validated municipal INEGI indicators for all 106 municipalities of Yucatán."""

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
import sys

from services.inegi import CORE_INDICATORS, collect_municipal_indicator
from services.settings import get_setting


ROOT = Path(__file__).resolve().parents[1]
MAP = storage_path("data") / "yucatan_municipios_inegi.geojson"
STATE = "Yucatán"


def main() -> None:
    token = get_setting("INEGI_INDICATORS_TOKEN")
    if not token:
        raise RuntimeError("No hay token privado de INEGI configurado.")
    features = json.loads(MAP.read_text(encoding="utf-8")).get("features", [])
    stored, errors = 0, []
    requested = set(sys.argv[1:])
    indicator_ids = [indicator_id for indicator_id in dict.fromkeys(CORE_INDICATORS.values()) if not requested or indicator_id in requested]
    with connection() as conn:
        for indicator_id in indicator_ids:
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
        total = conn.execute("SELECT COUNT(*) FROM territorial_indicators WHERE state=?", (STATE,)).fetchone()[0]
        municipalities = conn.execute("SELECT COUNT(DISTINCT municipality_code) FROM territorial_indicators WHERE state=?", (STATE,)).fetchone()[0]
        conn.execute("UPDATE territories SET notes=? WHERE territory_type='Estado' AND state=?", (
            f"Base territorial: 106 municipios y resultados oficiales IEPAC 2021 y 2024. Indicadores INEGI: {total} registros en {municipalities} municipios. Pendiente: cartografía distrital y ficha seccional.", STATE))
        conn.commit()
    print(json.dumps({"guardados": stored, "municipios": municipalities, "indicadores": total, "errores": len(errors)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
