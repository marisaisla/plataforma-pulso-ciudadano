"""Hace visible el cierre POA 2025 de Mérida sin atribuirle cifras no verificadas.

La Tesorería municipal publica la Cuenta Pública Anual y los estados analíticos
de ingresos y egresos de 2025. El monto y desglose se mantienen pendientes
hasta extraer los archivos oficiales de la publicación.
"""

from services.database import execute, initialize_database, query


PROFILE_NAME = "Cecilia Anunciación Patrón Laviada"
SOURCE_URL = "https://merida.gob.mx/finanzas/conac.php"


def main() -> None:
    initialize_database()
    profile = query("SELECT id FROM profiles WHERE name=?", (PROFILE_NAME,))
    if not profile:
        raise RuntimeError(f"No existe el perfil {PROFILE_NAME!r}")

    execute(
        """INSERT INTO operational_annual_plans
           (profile_id, state, municipality, title, year, status, source_url, notes)
           VALUES (?, 'Yucatán', 'Mérida', 'Cierre anual del POA de Mérida', 2025, ?, ?, ?)
           ON CONFLICT(profile_id, state, municipality, year, title) DO UPDATE SET
             status=excluded.status, source_url=excluded.source_url, notes=excluded.notes,
             updated_at=CURRENT_TIMESTAMP""",
        (
            profile[0]["id"],
            "Fuentes anuales localizadas; cifras pendientes de importación",
            SOURCE_URL,
            "Disponible en la Tesorería: Cuenta Pública Anual 2025, Estado Analítico de Ingresos "
            "y Estado Analítico del Ejercicio del Presupuesto de Egresos al 31 de diciembre de 2025. "
            "Pendiente: extraer los importes y el desglose por programa desde los archivos oficiales. "
            "No se muestran montos hasta contar con esos documentos.",
        ),
    )
    print("Cierre POA 2025 registrado como pendiente de importación.")


if __name__ == "__main__":
    main()
