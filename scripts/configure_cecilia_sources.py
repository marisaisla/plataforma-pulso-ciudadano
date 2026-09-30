"""Configure initial public-information sources for Cecilia Patrón's profile."""

from services.database import connection
from services.capture import discover_rss


SOURCES = (
    ("Fuente institucional", "Ayuntamiento de Mérida", "https://www.merida.gob.mx/"),
    ("Fuente institucional", "Prensa Ayuntamiento de Mérida", "https://prensa.merida.gob.mx/"),
    ("Fuente institucional", "COPLADEM Mérida", "https://www.merida.gob.mx/copladem/"),
    ("Fuente institucional", "Transparencia y Finanzas Mérida", "https://www.merida.gob.mx/finanzas/conac.php"),
    ("Medio digital", "Diario de Yucatán", "https://www.yucatan.com.mx/"),
    ("Medio digital", "Por Esto! Yucatán", "https://www.poresto.com/"),
    ("Medio digital", "La Jornada Maya", "https://www.lajornadamaya.mx/yucatan"),
    ("Medio digital", "Novedades Yucatán", "https://sipse.com/novedades-yucatan"),
    ("X", "Cecilia Patrón Laviada", "https://x.com/CeciliaPatronL"),
)

KEYWORDS = (
    "Cecilia Patrón",
    "Cecilia Patron",
    "Cecilia Anunciación Patrón Laviada",
    "Cecilia Anunciacion Patron Laviada",
    "alcaldesa de Mérida",
    "alcaldesa de Merida",
    "presidenta municipal de Mérida",
    "presidenta municipal de Merida",
    "Ayuntamiento de Mérida",
    "Ayuntamiento de Merida",
)


def main() -> None:
    with connection() as conn:
        row = conn.execute(
            "SELECT id FROM profiles WHERE name LIKE ? ORDER BY id LIMIT 1",
            ("Cecilia%",),
        ).fetchone()
        if not row:
            raise RuntimeError("No se encontró el perfil de Cecilia Patrón.")
        profile_id = row["id"]
        for source_type, name, url in SOURCES:
            exists = conn.execute(
                "SELECT id FROM sources WHERE profile_id = ? AND name = ?",
                (profile_id, name),
            ).fetchone()
            if exists:
                conn.execute("UPDATE sources SET source_type = ?, account_or_url = ?, active = 1 WHERE id = ?", (source_type, url, exists["id"]))
            else:
                conn.execute(
                    "INSERT INTO sources (profile_id, source_type, name, account_or_url, active) VALUES (?, ?, ?, ?, 1)",
                    (profile_id, source_type, name, url),
                )
        conn.execute("DELETE FROM profile_keywords WHERE profile_id = ?", (profile_id,))
        conn.executemany(
            "INSERT INTO profile_keywords (profile_id, keyword, active) VALUES (?, ?, 1)",
            [(profile_id, keyword) for keyword in KEYWORDS],
        )
    discovery = discover_rss(profile_id)
    print(
        f"Configuradas {len(SOURCES)} fuentes y {len(KEYWORDS)} palabras clave para Cecilia Patrón. "
        f"Feeds RSS detectados: {discovery['added']} nuevos, {discovery['existing']} existentes."
    )


if __name__ == "__main__":
    main()
