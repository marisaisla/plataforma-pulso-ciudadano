"""Carga resultados publicados del Segundo Informe de Mérida sin confundirlos con metas del PMD.

Fuente primaria: comunicado oficial del Ayuntamiento de Mérida, 28 de agosto de 2026.
Cada resultado se conserva como dato reportado: el informe no publica una ficha
metodológica que permita calcular el porcentaje de cumplimiento de los 72 indicadores.
"""

from services.database import execute, initialize_database, query


PROFILE_NAME = "Cecilia Anunciación Patrón Laviada"
PLAN_TITLE = "Plan Municipal de Desarrollo de Mérida 2024-2027"
PERIOD = "Segundo Informe de Trabajo 2026"
SOURCE_URL = "https://prensa.merida.gob.mx/12556/Presenta-Cecilia-Patron-ante-el-Cabildo-de-Merida-su-segundo-informe-de-gobierno/amp"


RESULTS = [
    ("Servicios públicos", "Comisarías con alumbrado LED", 47, "comisarías", "Comisarías de Mérida",
     "El informe señala que las 47 comisarías cuentan con iluminación LED. Es cobertura reportada, no porcentaje de satisfacción del servicio."),
    ("Servicios públicos", "Espacios públicos intervenidos por Mérida Enchula", 800, "espacios", "Mérida",
     "El informe reporta más de 800 parques, calles y áreas de convivencia renovados; se conserva 800 como mínimo publicado."),
    ("Inclusión, bienestar y desarrollo social", "Familias con certeza jurídica mediante fundos legales", 82, "familias", "Mérida",
     "El informe reporta la entrega de fundos legales que brindó certeza jurídica a 82 familias."),
    ("Inclusión, bienestar y desarrollo social", "Capacidad anual estimada del Centro Municipal de Autismo", 8000, "atenciones anuales estimadas", "Mérida",
     "La comunicación institucional estima entre 8,000 y 10,000 atenciones anuales; se registra el límite inferior para no sobreestimar."),
    ("Inclusión, bienestar y desarrollo social", "Personas estimadas beneficiarias del Centro Municipal de Autismo", 400, "personas", "Mérida",
     "Estimación institucional para personas autistas atendidas tras la ampliación de servicios."),
    ("Desarrollo ordenado", "Aprobación del Programa Municipal de Ordenamiento Territorial y Desarrollo Urbano", None, "hito normativo", "Mérida",
     "Resultado cualitativo: el Cabildo aprobó por unanimidad el PMOTDU. No se asigna un porcentaje de avance sin metodología comparable."),
    ("Seguridad y buen gobierno", "Puesta en marcha de MID Digital", None, "hito operativo", "Mérida",
     "Resultado cualitativo: el informe describe MID Digital como herramienta para simplificar trámites y la relación con el Ayuntamiento."),
]


def main() -> None:
    initialize_database()
    profile = query("SELECT id FROM profiles WHERE name=?", (PROFILE_NAME,))
    if not profile:
        raise RuntimeError(f"No existe el perfil {PROFILE_NAME!r}")
    plan = query(
        """SELECT id FROM development_plans
           WHERE profile_id=? AND state='Yucatán' AND municipality='Mérida' AND title=?""",
        (profile[0]["id"], PLAN_TITLE),
    )
    if not plan:
        raise RuntimeError("No existe el PMD de Mérida. Ejecuta primero la carga oficial del PMD.")
    plan_id = plan[0]["id"]
    axes = {row["name"]: row["id"] for row in query("SELECT id, name FROM development_plan_axes WHERE plan_id=?", (plan_id,))}
    for axis_name, title, value, unit, scope, note in RESULTS:
        execute(
            """INSERT INTO development_plan_reported_results
               (plan_id, axis_id, period, title, reported_value, unit, territory_scope, evidence_url, evidence_note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(plan_id, period, title) DO UPDATE SET
                 axis_id=excluded.axis_id, reported_value=excluded.reported_value, unit=excluded.unit,
                 territory_scope=excluded.territory_scope, evidence_url=excluded.evidence_url,
                 evidence_note=excluded.evidence_note, updated_at=CURRENT_TIMESTAMP""",
            (plan_id, axes[axis_name], PERIOD, title, value, unit, scope, SOURCE_URL, note),
        )
    print(f"Resultados publicados cargados: {len(RESULTS)}")


if __name__ == "__main__":
    main()
