"""Registra el POA 2026 de Mérida sin inventar su desglose por programa.

La publicación oficial confirma su aprobación y su alineación con los seis ejes del
PMD. La matriz detallada de programas, metas y presupuesto por unidad permanece
pendiente de importación desde el PDF oficial del POA.
"""

from services.database import execute, initialize_database, query


PROFILE_NAME = "Cecilia Anunciación Patrón Laviada"
POA_SOURCE_URL = "https://www.merida.gob.mx/copladem/programacion.php"


def main() -> None:
    initialize_database()
    profile = query("SELECT id FROM profiles WHERE name=?", (PROFILE_NAME,))
    if not profile:
        raise RuntimeError(f"No existe el perfil {PROFILE_NAME!r}")
    execute(
        """INSERT INTO operational_annual_plans
           (profile_id, state, municipality, title, year, status, source_url, notes)
           VALUES (?, 'Yucatán', 'Mérida', 'Programa Operativo Anual de Mérida', 2026, ?, ?, ?)
           ON CONFLICT(profile_id, state, municipality, year, title) DO UPDATE SET
             status=excluded.status, source_url=excluded.source_url, notes=excluded.notes,
             updated_at=CURRENT_TIMESTAMP""",
        (
            profile[0]["id"],
            "Oficial aprobado; matriz detallada pendiente de importación",
            POA_SOURCE_URL,
            "El Ayuntamiento publica el POA 2026 y sus programas presupuestarios. La fuente oficial confirma que se articula con los seis ejes del PMD. "
            "El último corte presupuestario listado por la Tesorería corresponde a agosto de 2026; falta extraer la matriz por categoría programática para cargar aprobado, devengado y pagado. "
            "El monto global comunicado supera $6,300 millones; no se captura como presupuesto exacto hasta verificarlo en el PDF oficial del POA.",
        ),
    )
    print("POA 2026 de Mérida registrado.")


if __name__ == "__main__":
    main()
