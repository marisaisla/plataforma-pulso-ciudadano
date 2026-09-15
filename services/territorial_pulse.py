"""Vinculación territorial conservadora para publicaciones locales.

Solo guarda un municipio cuando su nombre aparece literalmente en el título o
texto. No deduce domicilio, sección electoral ni intención de una persona.
"""

from __future__ import annotations

import re
import unicodedata

from services.database import connection


EXPLICIT_METHOD = "Municipio escrito en el texto"


def normalize(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.casefold().split())


def municipality_mentions(text: str, municipality_names: list[str]) -> list[str]:
    """Return each municipality name explicitly written in the publication."""
    normalized_text = normalize(text)
    matches: list[str] = []
    for municipality in municipality_names:
        normalized_name = normalize(municipality)
        if not normalized_name:
            continue
        pattern = rf"(?<![a-z0-9]){re.escape(normalized_name)}(?![a-z0-9])"
        if re.search(pattern, normalized_text):
            matches.append(municipality)
    return matches


def rebuild_explicit_municipality_links(
    profile_id: int, state: str, municipality_names: list[str]
) -> dict[str, int]:
    """Refresh automatic explicit-name links while preserving all source text."""
    names = sorted(set(name.strip() for name in municipality_names if str(name).strip()), key=len, reverse=True)
    with connection() as conn:
        publications = conn.execute(
            """
            SELECT id, COALESCE(title, '') AS title, COALESCE(text, '') AS text
            FROM publications WHERE profile_id = ?
            """,
            (profile_id,),
        ).fetchall()
        conn.execute(
            """
            DELETE FROM publication_territories
            WHERE state = ? AND match_method = ?
              AND publication_id IN (SELECT id FROM publications WHERE profile_id = ?)
            """,
            (state, EXPLICIT_METHOD, profile_id),
        )
        links = 0
        for publication in publications:
            text = f"{publication['title']}\n{publication['text']}"
            for municipality in municipality_mentions(text, names):
                conn.execute(
                    """
                    INSERT OR IGNORE INTO publication_territories
                    (publication_id, state, municipality, match_method, confidence)
                    VALUES (?, ?, ?, ?, 'Explícita')
                    """,
                    (publication["id"], state, municipality, EXPLICIT_METHOD),
                )
                links += 1
    return {"publications_reviewed": len(publications), "links_created": links}


def municipal_pulse_summary(profile_id: int, state: str) -> list[dict]:
    """Aggregate only linked publications; sentiment remains null when unanalyzed."""
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT pt.municipality,
                   COUNT(DISTINCT p.id) AS publications,
                   SUM(CASE WHEN a.sentiment = 'Positivo' THEN 1 ELSE 0 END) AS positive,
                   SUM(CASE WHEN a.sentiment = 'Negativo' THEN 1 ELSE 0 END) AS negative,
                   SUM(CASE WHEN a.sentiment = 'Neutro' THEN 1 ELSE 0 END) AS neutral,
                   SUM(CASE WHEN a.urgency IN ('Alta', 'Crítica') THEN 1 ELSE 0 END) AS high_urgency
            FROM publication_territories pt
            JOIN publications p ON p.id = pt.publication_id
            LEFT JOIN analyses a ON a.publication_id = p.id
            WHERE p.profile_id = ? AND pt.state = ? AND pt.municipality IS NOT NULL
            GROUP BY pt.municipality
            ORDER BY publications DESC, pt.municipality
            """,
            (profile_id, state),
        ).fetchall()
    return [dict(row) for row in rows]
