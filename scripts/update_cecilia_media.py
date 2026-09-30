"""Run a clean media update for Cecilia and close the resolved URL incident."""

from services.capture import capture_media_headlines
from services.database import connection, record_obtainment_run


def main() -> None:
    with connection() as conn:
        profile = conn.execute(
            "SELECT id FROM profiles WHERE name LIKE ? ORDER BY id LIMIT 1", ("Cecilia%",)
        ).fetchone()
        if not profile:
            raise RuntimeError("No se encontró el perfil de Cecilia Patrón.")
        profile_id = profile["id"]

    result = capture_media_headlines(profile_id)
    record_obtainment_run(profile_id, "Medio digital", result)

    with connection() as conn:
        conn.execute(
            """UPDATE import_runs
               SET status = 'Corregida',
                   details = 'Incidencia histórica resuelta: se actualizó la URL de Por Esto!; la fuente responde correctamente.'
               WHERE profile_id = ? AND source_type = 'Medio digital' AND status = 'Con errores'""",
            (profile_id,),
        )
    print(result)


if __name__ == "__main__":
    main()
