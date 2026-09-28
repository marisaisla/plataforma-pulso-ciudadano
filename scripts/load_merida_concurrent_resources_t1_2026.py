"""Carga recursos concurrentes oficialmente publicados para Mérida.

El formato oficial del primer trimestre identifica una aportación estatal para
"5% Museos, monumentos y zonas arqueológicas 2025". No representa el total
anual de convenios ni gasto ejercido: únicamente el recurso concurrente
identificado en el reporte con corte al primer trimestre de 2026.
"""

from services.database import execute, initialize_database, query


PROFILE_NAME = "Cecilia Anunciación Patrón Laviada"
SOURCE_URL = (
    "https://merida.gob.mx/finanzas/content/conac/2026/rConcurrentes/"
    "rc_enero_marzo2026.pdf"
)


def main() -> None:
    initialize_database()
    profile = query("SELECT id FROM profiles WHERE name=?", (PROFILE_NAME,))
    if not profile:
        raise RuntimeError(f"No existe el perfil {PROFILE_NAME!r}")

    execute(
        """INSERT INTO municipal_funding_snapshots
           (profile_id, state, municipality, fiscal_year, cutoff_period, source_name, source_class,
            amount_received, source_url, notes)
           VALUES (?, 'Yucatán', 'Mérida', 2026, 'Primer trimestre 2026', ?, ?, ?, ?, ?)
           ON CONFLICT(profile_id, municipality, fiscal_year, cutoff_period, source_name) DO UPDATE SET
             source_class=excluded.source_class, amount_received=excluded.amount_received,
             source_url=excluded.source_url, notes=excluded.notes, updated_at=CURRENT_TIMESTAMP""",
        (
            profile[0]["id"],
            "5% Museos, monumentos y zonas arqueológicas 2025",
            "Recursos concurrentes estatales",
            227482.85,
            SOURCE_URL,
            "Aportación estatal reportada en el Formato de Programas con Recursos Concurrentes. "
            "Es un programa identificado al corte del primer trimestre; no equivale al total anual de convenios ni a gasto ejercido.",
        ),
    )
    print("Recurso concurrente identificado cargado: $227,482.85")


if __name__ == "__main__":
    main()
