"""Incorpora evidencia oficial PbR-SED y el avance agregado del PMD de Merida.

La matriz del cuarto trimestre define programas, MIR, responsables y medios de
verificacion. No publica valores ejercidos o metas alcanzadas por indicador, por
lo que se registra como estructura SED y no como avance fisico-financiero.
El 42.5% del PMD se carga aparte como avance agregado reportado en el Primer
Informe de Trabajo; no se distribuye artificialmente entre los 72 indicadores.
"""

from pathlib import Path

from services.database import execute, initialize_database, query


PROFILE_NAME = "Cecilia Anunciación Patrón Laviada"
PLAN_TITLE = "Plan Municipal de Desarrollo de Mérida 2024-2027"
STATE = "Yucatán"
MUNICIPALITY = "Mérida"
SED_URL = "https://www.merida.gob.mx/copladem/content/documents/monitoreo/2024-2027/matrizIndicadoresDesemp2025-4toTri.pdf"
REPORT_URL = "https://www.merida.gob.mx/municipio/portal/gobierno/informes/2024-2027/1erInforme/1erInforme.pdf"
SED_FILE = Path("data/reference_documents/merida_sed_2025_4t.pdf")
REPORT_FILE = Path("data/reference_documents/merida_primer_informe_2025.pdf")


def main() -> None:
    initialize_database()
    profile = query("SELECT id FROM profiles WHERE name=?", (PROFILE_NAME,))
    if not profile:
        raise RuntimeError(f"No existe el perfil {PROFILE_NAME!r}")
    profile_id = profile[0]["id"]
    plan = query(
        """SELECT id FROM development_plans
           WHERE profile_id=? AND state=? AND municipality=? AND title=?""",
        (profile_id, STATE, MUNICIPALITY, PLAN_TITLE),
    )
    if not plan:
        raise RuntimeError("Primero debe cargarse el PMD oficial de Mérida.")
    plan_id = plan[0]["id"]
    axis = query(
        "SELECT id FROM development_plan_axes WHERE plan_id=? AND name='Seguridad y buen gobierno'",
        (plan_id,),
    )
    if not axis:
        raise RuntimeError("No se encontró el eje Seguridad y buen gobierno.")
    axis_id = axis[0]["id"]

    for title, document_type, file_path, source_url, notes in [
        (
            "Matriz de Indicadores de Desempeño PbR-SED 2025 - cuarto trimestre",
            "Matriz PbR-SED",
            SED_FILE,
            SED_URL,
            "Matriz oficial de programas, indicadores, responsables, medios de verificación y alineación al PMD. Define el diseño de seguimiento; no sustituye los avances físico-financieros.",
        ),
        (
            "Primer Informe de Trabajo 2024-2025 - Ayuntamiento de Mérida",
            "Informe de gobierno",
            REPORT_FILE,
            REPORT_URL,
            "Informe oficial que reporta el avance agregado del PMD y resultados de gestión. Los resultados sin denominador se conservan separados de las metas formales.",
        ),
    ]:
        if not file_path.exists():
            raise FileNotFoundError(file_path)
        execute(
            """INSERT INTO reference_documents
               (profile_id, state, title, document_type, file_path, source_url, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(profile_id, file_path) DO UPDATE SET
                 title=excluded.title, document_type=excluded.document_type,
                 source_url=excluded.source_url, notes=excluded.notes,
                 imported_at=CURRENT_TIMESTAMP""",
            (profile_id, STATE, title, document_type, str(file_path), source_url, notes),
        )

    target_name = "Avance agregado en el cumplimiento del Plan Municipal de Desarrollo"
    execute(
        """INSERT INTO development_plan_targets
           (axis_id, name, baseline_value, target_value, current_value, unit, frequency,
            territory_scope, status, source_url, notes)
           VALUES (?, ?, NULL, 100, 42.5, 'Porcentaje', 'Anual', 'Mérida',
                   'Resultado oficial reportado', ?, ?)
           ON CONFLICT(axis_id, name) DO UPDATE SET
             target_value=excluded.target_value, current_value=excluded.current_value,
             unit=excluded.unit, frequency=excluded.frequency, territory_scope=excluded.territory_scope,
             status=excluded.status, source_url=excluded.source_url, notes=excluded.notes,
             updated_at=CURRENT_TIMESTAMP""",
        (
            axis_id,
            target_name,
            REPORT_URL,
            "El Primer Informe reporta 42.5% de avance en el cumplimiento del PMD. Es una cifra agregada de la administración; no se asigna a cada eje ni a cada indicador sin su cédula de cálculo.",
        ),
    )
    target = query(
        "SELECT id FROM development_plan_targets WHERE axis_id=? AND name=?",
        (axis_id, target_name),
    )
    target_id = target[0]["id"]
    execute(
        """INSERT INTO development_plan_progress
           (target_id, period, territory_name, physical_value, financial_amount, progress_pct,
            status, evidence_url, evidence_note, perception_note)
           VALUES (?, 'Primer Informe de Trabajo 2024-2025', 'Mérida', 42.5, NULL, 42.5,
                   'Resultado oficial reportado', ?, ?, NULL)
           ON CONFLICT(target_id, period, territory_name) DO UPDATE SET
             physical_value=excluded.physical_value, financial_amount=excluded.financial_amount,
             progress_pct=excluded.progress_pct, status=excluded.status,
             evidence_url=excluded.evidence_url, evidence_note=excluded.evidence_note,
             updated_at=CURRENT_TIMESTAMP""",
        (
            target_id,
            REPORT_URL,
            "Fuente oficial: el Primer Informe presenta 42.5% de avance en el cumplimiento del PMD. No equivale a avance financiero ni a porcentaje individual por programa.",
        ),
    )
    execute(
        """INSERT INTO development_plan_reported_results
           (plan_id, axis_id, period, title, reported_value, unit, territory_scope,
            status, evidence_url, evidence_note)
           VALUES (?, ?, 'Primer Informe de Trabajo 2024-2025',
                   'Seguimiento trimestral del gasto programado', 100, 'Porcentaje', 'Mérida',
                   'Resultado oficial reportado', ?, ?)
           ON CONFLICT(plan_id, period, title) DO UPDATE SET
             axis_id=excluded.axis_id, reported_value=excluded.reported_value, unit=excluded.unit,
             territory_scope=excluded.territory_scope, status=excluded.status,
             evidence_url=excluded.evidence_url, evidence_note=excluded.evidence_note,
             updated_at=CURRENT_TIMESTAMP""",
        (
            plan_id,
            axis_id,
            REPORT_URL,
            "El informe reporta seguimiento trimestral al 100% del gasto programado. Es un indicador de seguimiento administrativo; no prueba el cumplimiento físico de todos los programas.",
        ),
    )
    print("PbR-SED 2025 y avance agregado del PMD incorporados.")


if __name__ == "__main__":
    main()
