"""Vincula el dictamen preliminar de Felipe Fernando Macías a su expediente Go2Win."""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.database import connection


ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "output" / "pdf" / "Dictamen_Viabilidad_Electoral_Felipe_Fernando_Macias_Queretaro_2027.pdf"
PROFILE = "Felipe Fernando Macías Olvera"
EL_PAIS = "https://elpais.com/mexico/2026-09-19/defensores-de-la-patria-el-pan-copia-la-estrategia-de-morena-en-un-intento-de-mantener-el-pulso-de-2027.html"
IEEQ = "https://ieeq.mx/comunicacion/boletines/3094"
CE_RESEARCH = "https://ceonline.com.mx/wp-content/uploads/2026/03/11-Destino-27-QUERETARO-2-Marzo-2026.pdf"
METAMETRICS = "https://metametrics.org/rumbo-a-las-elecciones-2027-en-queretaro-4-de-septiembre-2026/"
POLIGRAMA = "https://www.publimetro.com.mx/queretaro/2026/09/16/felifer-macias-encabeza-preferencias-en-queretaro-poligrama/"


def main() -> None:
    if not PDF.exists():
        raise FileNotFoundError(f"No se encontró el PDF: {PDF}")
    with connection() as conn:
        row = conn.execute("SELECT id FROM profiles WHERE name=?", (PROFILE,)).fetchone()
        if not row:
            raise RuntimeError("Primero ejecuta configure_felifer_macias_queretaro.py")
        profile_id = int(row["id"])
        conn.execute(
            "DELETE FROM reference_documents WHERE profile_id=? AND document_type='Dictamen de viabilidad'",
            (profile_id,),
        )
        conn.execute(
            """INSERT INTO reference_documents
               (profile_id, state, title, document_type, file_path, source_url, notes)
               VALUES (?, 'Querétaro', ?, 'Dictamen de viabilidad', ?, ?, ?)""",
            (
                profile_id,
                "Dictamen de viabilidad electoral - Felipe Fernando Macías - Querétaro 2027",
                str(PDF),
                IEEQ,
                "Corte al 27 de septiembre de 2026. Índice actualizado con encuestas públicas documentadas; no equivale a pronóstico ni candidatura formal.",
            ),
        )

        conn.execute("DELETE FROM viability_competitors WHERE profile_id=?", (profile_id,))
        conn.executemany(
            """INSERT INTO viability_competitors
               (profile_id, name, party_or_coalition, condition, territory, positioning_note, source_url)
               VALUES (?, ?, ?, ?, 'Querétaro', ?, ?)""",
            [
                (profile_id, "Luis Bernardo Nava Guerrero", "PAN", "Perfil de competencia interna", "Referido públicamente en la definición panista; sin candidatura formal en este expediente.", EL_PAIS),
                (profile_id, "Agustín Dorantes Lámbarri", "PAN", "Perfil de competencia interna", "Referido públicamente en la definición panista; sin candidatura formal en este expediente.", EL_PAIS),
                (profile_id, "Santiago Nieto Castillo", "Morena", "Perfil de competencia observado", "Perfil mencionado para Morena rumbo a 2027; candidatura y coalición deben validarse periódicamente.", EL_PAIS),
            ],
        )

        conn.execute("DELETE FROM viability_surveys WHERE profile_id=?", (profile_id,))
        conn.executemany(
            """INSERT INTO viability_surveys
               (profile_id, name, pollster, territory, fieldwork_date, sample_size, methodology, profile_result_pct, source_url, notes)
               VALUES (?, ?, ?, 'Querétaro', ?, ?, ?, ?, ?, ?)""",
            [
                (profile_id, "Interna PAN y careo estatal", "CE Research", "2026-03-01", 400,
                 "400 entrevistas con operadora robotizada a teléfono fijo; ±4.9 pp; 95% de confianza.", 39.0, CE_RESEARCH,
                 "Interna PAN: Macías 39%. Careo sin alianza PAN-MC: Macías 30% frente a Santiago Nieto 39%. Medición temprana."),
                (profile_id, "Interna PAN", "MetaMetrics", "2026-09-01", 1500,
                 "1,500 entrevistas digitales efectivas; muestreo aleatorio estratificado; ±3.4 pp; 95% de confianza.", 26.9, METAMETRICS,
                 "Macías 26.9%; Luis Nava 27.1%; Dorantes 16.8%. Trabajo de campo del 1 al 4 de septiembre."),
                (profile_id, "Careo gubernatura", "Poligrama", "2026-09-09", 1000,
                 "1,000 encuestas telefónicas estatales; ±3.10 pp; 95% de confianza.", 44.9, POLIGRAMA,
                 "Macías 44.9% frente a Santiago Nieto 29.9%. Fotografía de un solo día."),
                (profile_id, "Interna PAN", "Poligrama", "2026-09-09", 1000,
                 "1,000 encuestas telefónicas estatales; ±3.10 pp; 95% de confianza.", 27.8, POLIGRAMA,
                 "Macías 27.8%; Luis Nava 20.0%; Dorantes 14.1%; ninguno 29.5%."),
            ],
        )

        evidence = [
            ("institutional_position", "Documentada", "Presidencia municipal de Querétaro 2024-2027 documentada en fuente oficial.", "Municipio de Querétaro / IEEQ", IEEQ, "2024-06-08"),
            ("electoral_experience", "Documentada", "El IEEQ declaró la validez de la elección municipal 2024 para la candidatura encabezada por Felipe Fernando Macías.", "IEEQ", IEEQ, "2024-06-08"),
            ("nomination_probability", "En revisión", "Proceso interno del PAN abierto; Macías, Luis Nava y Agustín Dorantes son perfiles referidos públicamente.", "El País", EL_PAIS, "2026-09-19"),
            ("main_rival", "En revisión", "Santiago Nieto es un perfil mencionado públicamente para Morena; se requiere validar postulación y alianza.", "El País", EL_PAIS, "2026-09-19"),
            ("vote_intent", "Documentada", "Tres fuentes públicas con ficha técnica ubican a Macías como perfil competitivo del PAN. Los resultados varían por fecha, pregunta y modo; no se promedian ni constituyen pronóstico.", "CE Research / MetaMetrics / Poligrama", METAMETRICS, "2026-09-09"),
        ]
        for code, status, note, label, url, date in evidence:
            conn.execute(
                """INSERT INTO viability_electoral_evidence
                   (profile_id, variable_code, status, evidence_note, source_label, source_url, reference_date, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(profile_id, variable_code) DO UPDATE SET
                       status=excluded.status, evidence_note=excluded.evidence_note, source_label=excluded.source_label,
                       source_url=excluded.source_url, reference_date=excluded.reference_date, updated_at=CURRENT_TIMESTAMP""",
                (profile_id, code, status, note, label, url, date),
            )
        conn.execute(
            """INSERT INTO viability_conclusions
               (profile_id, assessment_status, strengths, risks, conditions, next_step, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(profile_id) DO UPDATE SET
                   assessment_status=excluded.assessment_status, strengths=excluded.strengths,
                   risks=excluded.risks, conditions=excluded.conditions,
                   next_step=excluded.next_step, updated_at=CURRENT_TIMESTAMP""",
            (
                profile_id,
                "66/100 · Viable con condiciones",
                "Presidencia municipal de la capital, victoria PAN-PRI-PRD en 2024, trayectoria pública, base territorial estatal y posicionamiento documentado en fuentes públicas.",
                "Resultados de encuesta heterogéneos, estructura territorial sin auditoría, definición interna y coalición formal pendientes; la base de la capital no se transfiere automáticamente al estado.",
                "El índice incorpora cuatro registros de tres fuentes públicas, analizados por separado. No es promedio de encuestas, pronóstico ni candidatura formal.",
                "Levantar tracking homogéneo, definir método partidista, auditar cobertura y actualizar las ocho variables del índice.",
            ),
        )
        conn.commit()
    print(f"Dictamen vinculado al perfil {profile_id}")


if __name__ == "__main__":
    main()
