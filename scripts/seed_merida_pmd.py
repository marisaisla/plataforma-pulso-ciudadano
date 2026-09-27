"""Crea una estructura inicial, no oficial, para seguimiento del PMD de Mérida.

Los ejes quedan expresamente marcados para homologación con el documento oficial.
No se cargan metas numéricas ni avances sin fuente verificable.
"""

from services.database import execute, initialize_database, query


PROFILE_NAME = "Cecilia Anunciación Patrón Laviada"
PLAN_TITLE = "Plan Municipal de Desarrollo de Mérida 2024-2027"
INITIAL_AXES = [
    ("Servicios urbanos, calles y drenaje pluvial", 1),
    ("Agua y comisarías", 2),
    ("Movilidad y orden urbano", 3),
    ("Seguridad y convivencia", 4),
    ("Bienestar, mujeres y economía familiar", 5),
    ("Medio ambiente y espacio público", 6),
]


def main() -> None:
    initialize_database()
    profile = query("SELECT id FROM profiles WHERE name = ?", (PROFILE_NAME,))
    if not profile:
        raise RuntimeError(f"No se encontró el perfil: {PROFILE_NAME}")
    profile_id = profile[0]["id"]

    execute(
        """
        INSERT INTO development_plans (
            profile_id, state, municipality, title, period, official_status, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(profile_id, state, municipality, title) DO UPDATE SET
            period = excluded.period,
            official_status = excluded.official_status,
            notes = excluded.notes,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            profile_id,
            "Yucatán",
            "Mérida",
            PLAN_TITLE,
            "2024-2027",
            "Por homologar a documento oficial",
            (
                "Estructura inicial derivada de temas de gestión citados en el dictamen. "
                "Debe contrastarse con el PMD oficial antes de marcar ejes, metas, indicadores "
                "o avances como oficiales."
            ),
        ),
    )
    plan = query(
        """
        SELECT id FROM development_plans
        WHERE profile_id = ? AND state = ? AND municipality = ? AND title = ?
        """,
        (profile_id, "Yucatán", "Mérida", PLAN_TITLE),
    )[0]
    for axis_name, sort_order in INITIAL_AXES:
        execute(
            """
            INSERT INTO development_plan_axes (plan_id, name, description, sort_order, status)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(plan_id, name) DO UPDATE SET
                sort_order = excluded.sort_order,
                status = excluded.status,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                plan["id"],
                axis_name,
                "Eje inicial de seguimiento; pendiente de homologación con el documento oficial.",
                sort_order,
                "Por homologar a documento oficial",
            ),
        )

    print(f"PMD inicial preparado para {PROFILE_NAME}: plan {plan['id']}, {len(INITIAL_AXES)} ejes.")


if __name__ == "__main__":
    main()
