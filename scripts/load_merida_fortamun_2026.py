"""Carga la programación oficial FORTAMUN 2026 de Mérida al POA local.

Los importes son costos programados al inicio del ejercicio, no gasto ejercido.
Por ello el avance financiero queda vacío hasta importar un estado presupuestario
con aprobado, modificado, devengado o pagado.
"""

from services.database import execute, initialize_database, query


PROFILE_NAME = "Cecilia Anunciación Patrón Laviada"
SOURCE_URL = "https://merida.gob.mx/finanzas/content/conac/2026/fortamun_2026.pdf"
FUND = "Ramo 33 · FORTAMUN 2026"


# name, programmed cost, PMD axis, annual target, target unit, responsible unit
PROGRAMS = [
    ("Prevención social del delito y participación ciudadana", 53350, "Seguridad y buen gobierno", 10000, "personas", "Policía Municipal"),
    ("Prevención y atención de la violencia familiar y de género", 344188, "Seguridad y buen gobierno", 400, "personas", "Policía Municipal"),
    ("Policía educativa y comunitaria", 679639, "Seguridad y buen gobierno", 10000, "personas", "Policía Municipal"),
    ("Profesionalización y certificación del personal de la Policía Municipal", 1540000, "Seguridad y buen gobierno", None, None, "Policía Municipal"),
    ("Servicio médico policial", 30000, "Seguridad y buen gobierno", None, None, "Policía Municipal"),
    ("Operación de la Unidad de Asuntos Internos de la Policía", 34199, "Seguridad y buen gobierno", None, None, "Policía Municipal"),
    ("Administración eficiente de la Subdirección Operativa de la Policía Municipal", 177484, "Seguridad y buen gobierno", None, None, "Policía Municipal"),
    ("Seguridad ciudadana y proximidad social", 15409424, "Seguridad y buen gobierno", 235000, "personas", "Policía Municipal"),
    ("Operación de servicios viales y acciones de proximidad social", 6172640, "Seguridad y buen gobierno", None, None, "Policía Municipal"),
    ("Centro de Comando y Control", 1341538, "Seguridad y buen gobierno", None, None, "Policía Municipal"),
    ("Sistema Individual de Retiro y Jubilación Municipal SIRJUM", 338767, "Seguridad y buen gobierno", None, None, "Ayuntamiento de Mérida"),
    ("Administración eficiente del despacho de la Policía Municipal", 82876582, "Seguridad y buen gobierno", None, None, "Policía Municipal"),
    ("Gestión eficiente de los servicios administrativos generales y operativos de la Policía Municipal", 28603281, "Seguridad y buen gobierno", None, None, "Policía Municipal"),
    ("Mantenimiento del alumbrado público del sector poniente", 167891577, "Servicios públicos", None, None, "Dirección de Servicios Públicos"),
    ("Administración del servicio de energía eléctrica para el alumbrado público", 117496948, "Servicios públicos", None, None, "Dirección de Servicios Públicos"),
    ("Mantenimiento del alumbrado público del sector oriente", 135585625, "Servicios públicos", None, None, "Dirección de Servicios Públicos"),
    ("Administración eficiente de la Dirección de Servicios Públicos", 62169826, "Servicios públicos", None, None, "Dirección de Servicios Públicos"),
    ("Mantenimiento de calles", 53515128, "Servicios públicos", 131252, "m² de bacheo", "Dirección de Obras Públicas"),
    ("Construcción y mantenimiento de la infraestructura urbana", 479925, "Desarrollo ordenado", 3.05, "km de guarniciones, banquetas y pozos", "Dirección de Obras Públicas"),
    ("Rehabilitación, modernización y repavimentación de vialidades", 34831708, "Desarrollo ordenado", 10.5, "km de vialidades", "Dirección de Obras Públicas"),
    ("Mantenimiento a sistemas de bombeo de agua potable en comisarías", 9040166, "Servicios públicos", None, None, "Dirección de Obras Públicas"),
    ("Operatividad y control administrativo de la Dirección de Obras Públicas", 42948376, "Desarrollo ordenado", 333, "vehículos y/o maquinaria", "Dirección de Obras Públicas"),
    ("Mantenimiento y conservación del edificio de Obras Públicas", 92446, "Desarrollo ordenado", 1, "edificio", "Dirección de Obras Públicas"),
    ("Cambio y mantenimiento del alumbrado en canchas, campos y espacios deportivos", 19904000, "Servicios públicos", None, None, "Dirección de Servicios Públicos"),
    ("Servicio de recolección de residuos sólidos urbanos Mérida Ciudad Sustentable", 281834382, "Servicios públicos", None, None, "Dirección de Servicios Públicos"),
]


def main() -> None:
    initialize_database()
    profile = query("SELECT id FROM profiles WHERE name=?", (PROFILE_NAME,))
    if not profile:
        raise RuntimeError(f"No existe el perfil {PROFILE_NAME!r}")
    profile_id = profile[0]["id"]
    poa = query(
        """SELECT id FROM operational_annual_plans
           WHERE profile_id=? AND state='Yucatán' AND municipality='Mérida' AND year=2026
             AND title='Programa Operativo Anual de Mérida'""",
        (profile_id,),
    )
    if not poa:
        raise RuntimeError("Primero ejecuta load_merida_poa_2026.py")
    poa_id = poa[0]["id"]
    axes = {row["name"]: row["id"] for row in query(
        """SELECT a.id, a.name FROM development_plan_axes a
           JOIN development_plans p ON p.id=a.plan_id
           WHERE p.profile_id=? AND p.state='Yucatán' AND p.municipality='Mérida'""",
        (profile_id,),
    )}
    for name, cost, axis, target, unit, responsible in PROGRAMS:
        execute(
            """INSERT INTO operational_annual_programs
               (poa_id, axis_id, name, responsible_unit, annual_goal, goal_unit, funding_source,
                allocated_budget, exercised_budget, execution_pct, status, source_url, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?)
               ON CONFLICT(poa_id, name) DO UPDATE SET
                 axis_id=excluded.axis_id, responsible_unit=excluded.responsible_unit, annual_goal=excluded.annual_goal,
                 goal_unit=excluded.goal_unit, funding_source=excluded.funding_source,
                 allocated_budget=excluded.allocated_budget, status=excluded.status, source_url=excluded.source_url,
                 notes=excluded.notes, updated_at=CURRENT_TIMESTAMP""",
            (poa_id, axes[axis], name, responsible, target, unit, FUND, cost,
             "Programado oficial; avance financiero pendiente de corte de ejecución", SOURCE_URL,
             "Costo y, cuando aplica, meta transcritos del formato FORTAMUN 2026. No representa gasto devengado o pagado."),
        )
    total = sum(row[1] for row in PROGRAMS)
    if total != 1063391199:
        raise RuntimeError(f"La suma importada ({total}) no coincide con el total oficial FORTAMUN.")
    print(f"FORTAMUN importado: {len(PROGRAMS)} acciones; ${total:,.2f}")


if __name__ == "__main__":
    main()
