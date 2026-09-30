"""Configura fuentes públicas de Felifer y ejecuta una actualización inicial."""

import json

from services.capture import capture_media_headlines, capture_rss, discover_rss
from services.database import connection, record_obtainment_run


SOURCES = (
    ("Fuente institucional", "Municipio de Querétaro · Noticias de Felifer", "https://municipiodequeretaro.gob.mx/etiquetas/felifer-macias/"),
    ("Medio digital", "El Universal Querétaro", "https://www.eluniversalqueretaro.mx/"),
    ("Medio digital", "Plaza de Armas Querétaro", "https://plazadearmas.com.mx/"),
    ("Medio digital", "CódigoQro", "https://codigoqro.mx/"),
    ("X", "Felipe Fernando Macías · Felifer", "https://x.com/FeliFerMacias"),
)
KEYWORDS = ("Felifer", "Felifer Macías", "Felipe Fernando Macías", "Felipe Fernando Macías Olvera", "Felipe Macías", "FeliFerMacias")


def main():
    with connection() as conn:
        profile = conn.execute("SELECT id FROM profiles WHERE name = ?", ("Felipe Fernando Macías Olvera",)).fetchone()
        if profile is None:
            raise RuntimeError("No se encontró el perfil de Felifer.")
        profile_id = profile["id"]
        for kind, name, url in SOURCES:
            existing = conn.execute("SELECT id FROM sources WHERE profile_id = ? AND account_or_url = ? AND source_type = ?", (profile_id, url, kind)).fetchone()
            if existing:
                conn.execute("UPDATE sources SET name = ?, active = 1 WHERE id = ?", (name, existing["id"]))
            else:
                conn.execute("INSERT INTO sources (profile_id, source_type, name, account_or_url) VALUES (?, ?, ?, ?)", (profile_id, kind, name, url))
        conn.executemany("INSERT INTO profile_keywords (profile_id, keyword, active) VALUES (?, ?, 1) ON CONFLICT(profile_id, keyword) DO UPDATE SET active = 1", [(profile_id, keyword) for keyword in KEYWORDS])
    print(json.dumps({"discovery": discover_rss(profile_id)}, ensure_ascii=True), flush=True)
    for kind in ("Medio digital", "Fuente institucional", "RSS"):
        result = capture_rss(profile_id) if kind == "RSS" else capture_media_headlines(profile_id, kind)
        record_obtainment_run(profile_id, kind, result)
        print(json.dumps({kind: result}, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
