"""Alinea el modelo ampliado de Marco Bonilla con el dictamen base de 2026.

El dictamen conserva su índice original de 78/100 (15 variables).  Go2Win
mantiene un índice ampliado de 20 variables, explícitamente preliminar.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


DB = Path(__file__).resolve().parents[1] / "data" / "pulso_ciudadano_local.db"
PROFILE_ID = 4


def main() -> None:
    with sqlite3.connect(DB) as conn:
        conn.execute(
            """UPDATE viability_electoral_scores
               SET score=?, notes=?, updated_at=CURRENT_TIMESTAMP
               WHERE profile_id=? AND variable_code='mobilization'""",
            (
                68,
                "Comunicación digital: 68/100. El dictamen indica que debe ampliar alcance en el norte; no representa capacidad de movilización territorial.",
                PROFILE_ID,
            ),
        )
        conn.execute(
            """UPDATE viability_electoral_evidence
               SET evidence_note=?, updated_at=CURRENT_TIMESTAMP
               WHERE profile_id=? AND variable_code='mobilization'""",
            (
                "El dictamen base califica la comunicación digital en 68/100 y recomienda ampliar alcance en el norte. Se conserva como evidencia documental, no como registro de movilización.",
                PROFILE_ID,
            ),
        )
        conn.execute(
            """UPDATE viability_conclusions
               SET assessment_status=?, conditions=?, next_step=?, updated_at=CURRENT_TIMESTAMP
               WHERE profile_id=?""",
            (
                "Dictamen base: 78/100 · Modelo Go2Win ampliado: preliminar",
                "El dictamen base conserva 78/100 con 15 variables. El modelo ampliado de 20 variables debe leerse por separado hasta validar tracking comparable, rival, indecisos, voto útil y estructura auditada.",
                "Actualizar mediciones comparables, auditar estructura territorial y recalibrar el índice ampliado sin alterar el dictamen base.",
                PROFILE_ID,
            ),
        )
        conn.commit()
    print("Modelo de Marco Bonilla recalibrado.")


if __name__ == "__main__":
    main()
