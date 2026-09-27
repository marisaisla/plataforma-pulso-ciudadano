"""Convierte la cartografía publicada por el IEPAC a capas locales de Go2Win.

La fuente es el mapa de Distritación Local 2022 del IEPAC.  Se conservan sus
geometrías y atributos de identificación; los resultados electorales se unen
en tiempo de consulta desde la base local.
"""

from __future__ import annotations

import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "raw" / "iepac_yucatan_distritos.kml"
SECTIONS_OUTPUT = ROOT / "data" / "yucatan_secciones_electorales_iepac.geojson"
DISTRICTS_OUTPUT = ROOT / "data" / "yucatan_distritos_locales_iepac.geojson"
SOURCE = "IEPAC · Distritación Local 2022"


def normalized(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.upper().split())


def html_value(description: str, label: str) -> str:
    match = re.search(rf"{label}:\s*([^<]+)", description, flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def geometry(placemark: ET.Element) -> dict | None:
    polygons: list[list[list[list[float]]]] = []
    for polygon in placemark.findall(".//{*}Polygon"):
        coordinate_text = polygon.findtext(".//{*}outerBoundaryIs/{*}LinearRing/{*}coordinates")
        if not coordinate_text:
            continue
        ring = []
        for coordinate in coordinate_text.split():
            values = coordinate.split(",")
            if len(values) < 2:
                continue
            try:
                ring.append([float(values[0]), float(values[1])])
            except ValueError:
                continue
        if len(ring) >= 4:
            polygons.append([ring])
    if not polygons:
        return None
    if len(polygons) == 1:
        return {"type": "Polygon", "coordinates": polygons[0]}
    return {"type": "MultiPolygon", "coordinates": polygons}


def main() -> None:
    root = ET.parse(INPUT).getroot()
    folders = {
        folder.findtext("{*}name", default="").strip(): folder
        for folder in root.findall(".//{*}Folder")
    }

    municipality_codes: dict[str, str] = {}
    for placemark in folders["Municipios"].findall("{*}Placemark"):
        municipality = placemark.findtext("{*}name", default="").strip()
        code = html_value(placemark.findtext("{*}description", default=""), "MUNICIPIO")
        if municipality and code:
            municipality_codes[normalized(municipality)] = code.zfill(3)

    section_features = []
    for placemark in folders["Secciones Electorales"].findall("{*}Placemark"):
        section = placemark.findtext("{*}name", default="").strip()
        description = placemark.findtext("{*}description", default="")
        district = html_value(description, "DISTRITO LOCAL")
        municipality = html_value(description, "MUNICIPIO")
        shape = geometry(placemark)
        try:
            section_code = str(int(float(section))).zfill(4)
        except ValueError:
            continue
        if not shape or not district:
            continue
        section_features.append({
            "type": "Feature",
            "properties": {
                "state": "Yucatán",
                "seccion": section_code,
                "distrito_local": district.zfill(2),
                "municipio": municipality.title(),
                "municipio_electoral": municipality_codes.get(normalized(municipality), ""),
                "fuente_geometria": SOURCE,
            },
            "geometry": shape,
        })

    district_features = []
    for placemark in folders["Distritos Electorales Locales"].findall("{*}Placemark"):
        name = placemark.findtext("{*}name", default="").strip()
        description = placemark.findtext("{*}description", default="")
        code = html_value(description, "descripci.n") or "".join(re.findall(r"\d+", name))
        shape = geometry(placemark)
        if not shape or not code:
            continue
        district_features.append({
            "type": "Feature",
            "properties": {
                "state": "Yucatán",
                "distrito_local": code.zfill(2),
                "distrito": f"Distrito Electoral Local {code.zfill(2)}",
                "cabecera_distrital": html_value(description, "CABECERA DISTRITAL").title(),
                "fuente_geometria": SOURCE,
            },
            "geometry": shape,
        })

    SECTIONS_OUTPUT.write_text(
        json.dumps({"type": "FeatureCollection", "features": section_features}, ensure_ascii=False),
        encoding="utf-8",
    )
    DISTRICTS_OUTPUT.write_text(
        json.dumps({"type": "FeatureCollection", "features": district_features}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Secciones: {len(section_features)} -> {SECTIONS_OUTPUT.name}")
    print(f"Distritos: {len(district_features)} -> {DISTRICTS_OUTPUT.name}")


if __name__ == "__main__":
    main()
