"""Add official IEEQ section context to the Querétaro 2024 election records.

This supplements the loaded voting results with the public IEEQ description of
each section (neighbourhoods/locality, electoral roll and the official section
map link). It does not create geometry: the section polygons remain pending an
official vector layer.
"""

from __future__ import annotations

import html
import json
import re
import sqlite3
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "data" / "pulso_ciudadano_local.db"
URL = "https://ieeq.mx/elecciones/cartografia-electoral/Dto/{district}/"


def plain(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return " ".join(html.unescape(value).replace("\xa0", " ").split())


def number(value: str) -> int:
    return int(re.sub(r"[^0-9]", "", value) or 0)


def fetch_district(district: int) -> dict[str, dict]:
    with urlopen(URL.format(district=district), timeout=30) as response:
        page = response.read().decode("utf-8", errors="replace")
    municipality = ""
    sections: dict[str, dict] = {}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, flags=re.I | re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.I | re.S)
        values = [plain(cell) for cell in cells]
        if not values:
            continue
        # Municipality header rows have one populated cell spanning the table.
        if len(values) >= 1 and values[0] and not re.fullmatch(r"\d+", values[0]):
            nonempty = [value for value in values if value]
            if len(nonempty) == 1:
                municipality = nonempty[0].title()
            continue
        if len(values) < 9 or not re.fullmatch(r"\d+", values[0]):
            continue
        section = values[0].zfill(4)
        pdf_match = re.search(r'https?://[^"\']+\.pdf', row, flags=re.I)
        sections[section] = {
            "ieeq_municipio": municipality,
            "ieeq_descripcion_territorial": values[1],
            "ieeq_padron_electoral_actual": number(values[5]),
            "ieeq_lista_nominal_actual": number(values[9]),
            "ieeq_plano_seccional": pdf_match.group(0) if pdf_match else "",
            "ieeq_fuente_cartografica": URL.format(district=district),
        }
    return sections


def main() -> None:
    catalog: dict[str, dict] = {}
    for district in range(1, 16):
        catalog.update(fetch_district(district))
        print(f"Distrito {district:02d}: {len(catalog):,} secciones acumuladas.")

    conn = sqlite3.connect(DATABASE)
    rows = conn.execute(
        """SELECT id, section_code, payload FROM territorial_section_results
           WHERE state = 'Querétaro' AND election_year = 2024"""
    ).fetchall()
    updated = 0
    for record_id, section_code, payload_text in rows:
        context = catalog.get(str(section_code).zfill(4))
        if not context:
            continue
        payload = json.loads(payload_text)
        payload.update(context)
        conn.execute(
            "UPDATE territorial_section_results SET payload=? WHERE id=?",
            (json.dumps(payload, ensure_ascii=False), record_id),
        )
        updated += 1
    conn.commit()
    conn.close()
    print(f"Catálogo IEEQ: {len(catalog):,} secciones; registros actualizados: {updated:,}.")


if __name__ == "__main__":
    main()
