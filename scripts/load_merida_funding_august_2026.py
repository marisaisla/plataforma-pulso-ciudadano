"""Carga transferencias oficiales ministradas a Mérida, acumuladas a agosto de 2026.

Los datos provienen de la consulta estatal de Participaciones a Municipios para
Mérida, ejercicio 2026, acumulado enero-agosto. Son recursos recibidos/ministrados;
no son gasto devengado o pagado.
"""

from services.database import execute, initialize_database, query


PROFILE_NAME = "Cecilia Anunciación Patrón Laviada"
SOURCE_URL = "https://srvshyweb.yucatan.gob.mx/cgi-bin/wspd_cgi.sh/WService%3Dwspartmun/sh_conpar.r"
CUTOFF = "Enero-agosto 2026"

SOURCES = [
    ("Ramo 28 · Participaciones federales y estatales", "Participaciones de libre disposición", 1520975601.36,
     "Subtotal de participaciones informado por el Estado para Mérida; incluye los componentes federales y estatales ministrados."),
    ("Ramo 33 · FAISMUN", "Aportación federal etiquetada", 224866328.00,
     "Fondo de Infraestructura Social Municipal ministrado; su aplicación está etiquetada a infraestructura social."),
    ("Ramo 33 · FORTAMUN", "Aportación federal etiquetada", 708927400.00,
     "Monto ministrado a agosto. Es distinto del programa anual FORTAMUN de $1,063,391,199 cargado como presupuesto programado."),
]


def main() -> None:
    initialize_database()
    profile = query("SELECT id FROM profiles WHERE name=?", (PROFILE_NAME,))
    if not profile:
        raise RuntimeError(f"No existe el perfil {PROFILE_NAME!r}")
    profile_id = profile[0]["id"]
    for name, kind, amount, note in SOURCES:
        execute(
            """INSERT INTO municipal_funding_snapshots
               (profile_id, state, municipality, fiscal_year, cutoff_period, source_name, source_class,
                amount_received, source_url, notes)
               VALUES (?, 'Yucatán', 'Mérida', 2026, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(profile_id, municipality, fiscal_year, cutoff_period, source_name) DO UPDATE SET
                 source_class=excluded.source_class, amount_received=excluded.amount_received,
                 source_url=excluded.source_url, notes=excluded.notes, updated_at=CURRENT_TIMESTAMP""",
            (profile_id, CUTOFF, name, kind, amount, SOURCE_URL, note),
        )
    print(f"Fuentes cargadas: {len(SOURCES)}; total ${sum(row[2] for row in SOURCES):,.2f}")


if __name__ == "__main__":
    main()
