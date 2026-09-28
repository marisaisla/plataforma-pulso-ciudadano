"""Carga el cierre financiero anual 2025 oficialmente publicado por Mérida.

Los ingresos y gastos proceden de los Informes Mensuales de la Hacienda
Municipal con corte enero-diciembre 2025. Los montos de gasto son contables;
no se etiquetan como devengado o pagado porque ese dato requiere el Estado
Analítico del Ejercicio del Presupuesto de Egresos.
"""

from services.database import execute, initialize_database, query


PROFILE_NAME = "Cecilia Anunciación Patrón Laviada"
INCOME_SOURCE = "https://merida.gob.mx/finanzas/content/informes_hacienda/2025/diciembre/Ingresos.htm"
EXPENSE_SOURCE = "https://merida.gob.mx/finanzas/content/informes_hacienda/2025/diciembre/Gastos.htm"


def main() -> None:
    initialize_database()
    profile = query("SELECT id FROM profiles WHERE name=?", (PROFILE_NAME,))
    if not profile:
        raise RuntimeError(f"No existe el perfil {PROFILE_NAME!r}")

    execute(
        """INSERT INTO municipal_financial_closures
           (profile_id, state, municipality, fiscal_year, approved_income_budget, collected_income,
            income_management, taxes, transfers_and_contributions, accounting_expenses,
            operating_expenses, personnel_expenses, source_url, notes)
           VALUES (?, 'Yucatán', 'Mérida', 2025, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(profile_id, municipality, fiscal_year) DO UPDATE SET
             approved_income_budget=excluded.approved_income_budget, collected_income=excluded.collected_income,
             income_management=excluded.income_management, taxes=excluded.taxes,
             transfers_and_contributions=excluded.transfers_and_contributions,
             accounting_expenses=excluded.accounting_expenses, operating_expenses=excluded.operating_expenses,
             personnel_expenses=excluded.personnel_expenses, source_url=excluded.source_url,
             notes=excluded.notes, updated_at=CURRENT_TIMESTAMP""",
        (
            profile[0]["id"],
            6188821981.00, 6369639843.98, 3101613187.30, 2620854803.94, 3141312540.48,
            5559970729.83, 4005361765.14, 1565848317.75,
            INCOME_SOURCE,
            "Fuentes: ingresos anuales y gastos contables enero-diciembre 2025. "
            f"Gasto contable: {EXPENSE_SOURCE}. El porcentaje de avance mostrado corresponde a recaudación "
            "frente a Ley de Ingresos aprobada; no equivale a gasto devengado o pagado.",
        ),
    )
    print("Cierre financiero 2025 de Mérida cargado.")


if __name__ == "__main__":
    main()
