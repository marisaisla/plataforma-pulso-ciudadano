"""Carga al tablero la estructura oficial publicada del PMD de Mérida 2024-2027.

Extrae exclusivamente ejes e indicadores, con su línea base y escenario meta 2027,
desde las cédulas semestrales publicadas por el Ayuntamiento. No convierte los
escenarios meta en avances reales: éstos quedan vacíos hasta contar con evidencia.
"""

from __future__ import annotations

import sys as _storage_sys
from pathlib import Path as _StoragePath
_storage_sys.path.insert(0, str(_StoragePath(__file__).resolve().parents[1]))
from services.storage import storage_path


import re
import unicodedata
from difflib import get_close_matches
from pathlib import Path

from pypdf import PdfReader

from services.database import execute, initialize_database, query


PROFILE_NAME = "Cecilia Anunciación Patrón Laviada"
PLAN_TITLE = "Plan Municipal de Desarrollo de Mérida 2024-2027"
PMD_URL = "https://merida.gob.mx/pmd/"
PDF_FOLDER = storage_path("data/reference_documents/merida_pmd")

AXIS_ORDER = {
    "Inclusión, bienestar y desarrollo social": 1,
    "Prosperidad y empleo": 2,
    "Medio ambiente y bienestar animal": 3,
    "Seguridad y buen gobierno": 4,
    "Servicios públicos": 5,
    "Desarrollo ordenado": 6,
}


def clean(value: str) -> str:
    return " ".join(value.replace("\n", " ").split()).strip()


def normalize(value: str) -> str:
    # Algunas fuentes PDF expresan caracteres acentuados de modo inconsistente.
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return value.replace("  ", " ").strip()


def decimal(value: str) -> float | None:
    candidate = value.replace(",", "").replace("%", "").strip()
    try:
        return float(candidate)
    except ValueError:
        return None


def extract_indicators(pdf_path: Path) -> list[dict[str, object]]:
    text = "\n".join((page.extract_text() or "") for page in PdfReader(str(pdf_path)).pages)
    # Each official cédula repeats this stable data structure for every indicator.
    block_pattern = re.compile(
        r"Eje:\s*(.*?)\s*Tema:\s*(.*?)\s*Objetivo:\s*(.*?)\s*Tipo de algoritmo:.*?"
        r"Indicador:\s*(.*?)\s*Periodicidad:\s*(.*?)\s*Descripción:.*?"
        r"L[í�]nea base Meta 2027\s*\n.*?\n([^\n]+)",
        re.S,
    )
    records: list[dict[str, object]] = []
    for match in block_pattern.finditer(text):
        axis = clean(match.group(1))
        objective = clean(match.group(3))
        indicator = clean(match.group(4))
        frequency = clean(match.group(5))
        figures_line = clean(match.group(6))
        # First number is official baseline; second-to-last is the middle "escenario meta".
        numbers = re.findall(r"-?\d[\d,]*(?:\.\d+)?%?", figures_line)
        if len(numbers) < 4:
            baseline = None
            target = None
        else:
            baseline = decimal(numbers[0])
            target = decimal(numbers[-2])
        unit_match = re.search(r"^\s*[^\s]+\s+(.+?)\s+\d{4}\s+", figures_line)
        unit = clean(unit_match.group(1)) if unit_match else None
        records.append(
            {
                "axis": axis,
                "objective": objective,
                "name": indicator,
                "frequency": frequency,
                "baseline": baseline,
                "target": target,
                "unit": unit,
            }
        )
    return records


def main() -> None:
    initialize_database()
    profiles = query("SELECT id FROM profiles WHERE name = ?", (PROFILE_NAME,))
    if not profiles:
        raise RuntimeError(f"No se encontró el perfil: {PROFILE_NAME}")
    profile_id = profiles[0]["id"]

    execute(
        """
        UPDATE development_plans
        SET source_url=?, official_status='Oficial documentado',
            notes='Ejes, línea base y escenario meta cargados desde el PMD y las cédulas de indicadores publicadas por el Ayuntamiento de Mérida.',
            updated_at=CURRENT_TIMESTAMP
        WHERE profile_id=? AND state='Yucatán' AND municipality='Mérida' AND title=?
        """,
        (PMD_URL, profile_id, PLAN_TITLE),
    )
    plan_rows = query(
        "SELECT id FROM development_plans WHERE profile_id=? AND state='Yucatán' AND municipality='Mérida' AND title=?",
        (profile_id, PLAN_TITLE),
    )
    if not plan_rows:
        raise RuntimeError("Primero ejecuta seed_merida_pmd.py para crear la ficha inicial.")
    plan_id = plan_rows[0]["id"]

    records: list[dict[str, object]] = []
    for file_index in range(1, 7):
        file_path = PDF_FOLDER / f"eje{file_index}_1semestre.pdf"
        if not file_path.exists():
            raise FileNotFoundError(file_path)
        records.extend(extract_indicators(file_path))

    # Normalize official labels to the expected six ejes, preserving source wording in descriptions.
    axis_labels: dict[str, str] = {}
    for item in records:
        axis_raw = str(item["axis"])
        normalized = normalize(axis_raw)
        canonical_labels = {normalize(name).lower(): name for name in AXIS_ORDER}
        for canonical in AXIS_ORDER:
            if normalize(canonical).lower() == normalized.lower():
                axis_labels[axis_raw] = canonical
                break
        else:
            match = get_close_matches(normalized.lower(), canonical_labels, n=1, cutoff=0.72)
            if not match:
                raise RuntimeError(f"Eje no reconocido en el PDF: {axis_raw}")
            axis_labels[axis_raw] = canonical_labels[match[0]]

    for axis_name, order in AXIS_ORDER.items():
        execute(
            """
            INSERT INTO development_plan_axes (plan_id, name, description, sort_order, status)
            VALUES (?, ?, ?, ?, 'Oficial documentado')
            ON CONFLICT(plan_id, name) DO UPDATE SET
                description=excluded.description, sort_order=excluded.sort_order,
                status='Oficial documentado', updated_at=CURRENT_TIMESTAMP
            """,
            (plan_id, axis_name, "Eje oficial del Plan Municipal de Desarrollo de Mérida 2024-2027.", order),
        )

    axes = {row["name"]: row["id"] for row in query("SELECT id, name FROM development_plan_axes WHERE plan_id=?", (plan_id,))}
    imported = 0
    for item in records:
        canonical_axis = axis_labels[str(item["axis"])]
        axis_id = axes[canonical_axis]
        source_url = f"{PMD_URL}content/documents/indicadores/eje{AXIS_ORDER[canonical_axis]}_1semestre.pdf"
        execute(
            """
            INSERT INTO development_plan_targets
              (axis_id, name, baseline_value, target_value, unit, frequency, territory_scope, status, source_url, notes)
            VALUES (?, ?, ?, ?, ?, ?, 'Mérida', 'Oficial documentado', ?, ?)
            ON CONFLICT(axis_id, name) DO UPDATE SET
              baseline_value=excluded.baseline_value, target_value=excluded.target_value,
              unit=excluded.unit, frequency=excluded.frequency, territory_scope=excluded.territory_scope,
              status='Oficial documentado', source_url=excluded.source_url, notes=excluded.notes,
              updated_at=CURRENT_TIMESTAMP
            """,
            (
                axis_id, item["name"], item["baseline"], item["target"], item["unit"], item["frequency"], source_url,
                f"Objetivo oficial: {item['objective']}. Meta: escenario meta 2027 de la cédula publicada.",
            ),
        )
        imported += 1

    # Remove only the six provisional names created before the official source was available.
    provisional = [
        "Servicios urbanos, calles y drenaje pluvial", "Agua y comisarías", "Movilidad y orden urbano",
        "Seguridad y convivencia", "Bienestar, mujeres y economía familiar", "Medio ambiente y espacio público",
    ]
    for name in provisional:
        execute("DELETE FROM development_plan_axes WHERE plan_id=? AND name=?", (plan_id, name))

    print(f"PMD oficial importado: {len(AXIS_ORDER)} ejes y {imported} indicadores.")


if __name__ == "__main__":
    main()
