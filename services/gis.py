"""Utilidades para el módulo GIS de gobierno de Pulso Ciudadano.

El módulo no modifica los datos electorales de origen. Únicamente aprovecha
la geometría municipal y los indicadores públicos ya integrados para mostrar
contexto territorial de gobierno.
"""

from __future__ import annotations

import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path

import pandas as pd
import requests


APP_DIR = Path(__file__).resolve().parents[1]
SOURCE_DATASET = Path(
    r"C:\Users\jorge\Documents\Codex\2026-08-17\me\outputs"
    r"\gis-resultados-diputados-locales\chihuahua_municipios_resultados_2024.geojson"
)
LOCAL_DATASET = APP_DIR / "data" / "chihuahua_municipios_contexto.geojson"
REMOTE_STATE_LAYERS = {
    "Sonora": "https://raw.githubusercontent.com/MacWilliXD/INEGI-geojson/main/"
    "geojson_descargas/AGEM_26.geojson",
    # Marco municipal INEGI: clave de entidad 15, 125 municipios. Esta capa
    # es la base territorial para perfiles y para unir indicadores por Cvegeo.
    "Estado de México": "https://raw.githubusercontent.com/MacWilliXD/INEGI-geojson/main/"
    "geojson_descargas/AGEM_15.geojson",
}
STATE_NAME_ALIASES = {
    "Estado de Mexico": "Estado de México",
    "Edomex": "Estado de México",
    "Edo. Méx.": "Estado de México",
}
LOCAL_DISTRICT_DATASETS = {
    "Estado de México": APP_DIR / "data" / "edomex_distritos_locales_2025.geojson",
}
LOCAL_SECTION_DATASETS = {
    "Estado de México": APP_DIR / "data" / "edomex_secciones_electorales_2025.geojson",
}
SONORA_LOCAL_DISTRICTS_KML_URL = (
    "https://www.ieesonora.org.mx/documentos/estadistica_cartografia/"
    "2024_pcartograficos2/KML/DL_2022.kml"
)
SONORA_ELECTORAL_SECTIONS_KML_URL = (
    "https://www.ieesonora.org.mx/documentos/estadistica_cartografia/"
    "2024_pcartograficos2/KML/SECCION_DTTO_LOCAL_2024.kml"
)

GOVERNMENT_INDICATORS = {
    "Población total": ("inegi_poblacion_total", "habitantes"),
    "Población · 18 años y más": ("inegi_poblacion_18ymas", "habitantes"),
    "Población · 18 a 24 años": ("inegi_poblacion_18a24", "habitantes"),
    "Condiciones sociales · Escolaridad promedio": ("inegi_escolaridad_promedio", "años"),
    "Condiciones sociales · PEA": ("inegi_pea_pct", "%"),
    "Condiciones sociales · Ocupación": ("inegi_ocupacion_pct", "%"),
    "Condiciones sociales · Afiliación a servicios de salud": ("inegi_afiliacion_salud_pct", "%"),
    "Condiciones sociales · Discapacidad": ("inegi_discapacidad_pct", "%"),
    "Condiciones sociales · Lengua indígena": ("inegi_lengua_indigena_pct", "%"),
    "Vivienda y conectividad · Acceso a internet": ("inegi_internet_pct", "%"),
    "Vivienda y conectividad · Agua entubada": ("inegi_agua_entubada_pct", "%"),
    "Vivienda y conectividad · Drenaje": ("inegi_drenaje_pct", "%"),
    "Participación electoral · Lista nominal": ("lista_nominal", "personas"),
    "Participación electoral · Participación": ("participacion_pct", "%"),
    "Resultados electorales · Votos totales": ("votes_total", "votos"),
    "Resultados electorales · Votos nulos": ("votes_nulos", "votos"),
    "Resultados electorales · Votos candidatura JDCH": ("votes_jdch", "votos"),
    "Resultados electorales · Votos candidatura SHH": ("votes_shh", "votos"),
    "Resultados electorales · Votos PVEM": ("votes_pvem", "votos"),
    "Resultados electorales · Votos MC": ("votes_mc", "votos"),
    "Resultados electorales · Votos México Republicano": ("votes_mxrep", "votos"),
    "Resultados electorales · Votos Pueblo": ("votes_pueblo", "votos"),
    "Resultados electorales · Votos PAN": ("votes_pan", "votos"),
    "Resultados electorales · Votos PRI": ("votes_pri", "votos"),
    "Resultados electorales · Votos PRD": ("votes_prd", "votos"),
    "Resultados electorales · Votos PT": ("votes_pt", "votos"),
    "Resultados electorales · Votos Morena": ("votes_morena", "votos"),
    "Resultados electorales · Votos Nueva Alianza": ("votes_nueva_alianza", "votos"),
    "Resultados electorales · Votos Encuentro Solidario Sonora": ("votes_encuentro_solidario_sonora", "votos"),
    "Resultados electorales · Votos Partido Sonorense": ("votes_partido_sonorense", "votos"),
    "Resultados electorales · Votos coalición PAN-PRI-PRD": ("votes_coalicion_pan_pri_prd", "votos"),
    "Resultados electorales · Votos coalición PAN-PRI": ("votes_coalicion_pan_pri", "votos"),
    "Resultados electorales · Votos coalición PAN-PRD": ("votes_coalicion_pan_prd", "votos"),
    "Resultados electorales · Votos candidatura común Sigamos Haciendo Historia": ("votes_sigamos_haciendo_historia", "votos"),
    "Resultados electorales · Votos candidatura común Fuerza y Corazón por Sonora": ("votes_fuerza_y_corazon_sonora", "votos"),
    "Resultados electorales · Votos candidatura independiente Amigos de Baes": ("votes_amigos_de_baes", "votos"),
    "Resultados electorales · Votos candidatura independiente Etchojoa": ("votes_etchojoa_independiente", "votos"),
    "Resultados electorales · Votos candidatura independiente Magdalena Somos Todos": ("votes_magdalena_somos_todos", "votos"),
    "Resultados electorales · Votos candidatura independiente Progresa Santa Ana": ("votes_progresa_santa_ana", "votos"),
    "Resultados electorales · Votos candidatura independiente Nacozari Somos Todos": ("votes_nacozari_somos_todos", "votos"),
    "Resultados electorales · Votos de candidatura ganadora": ("votos_ganador", "votos"),
    "Resultados electorales · Margen de votos": ("margen_votos", "votos"),
    "Gestión municipal · Participaciones Ramo 28": ("ramo28_2025_pesos", "MXN"),
}

LAYER_INDICATOR_GROUPS = {
    "Población": ["Población total", "Población · 18 años y más", "Población · 18 a 24 años"],
    "Condiciones sociales": [
        "Condiciones sociales · Escolaridad promedio", "Condiciones sociales · PEA",
        "Condiciones sociales · Ocupación", "Condiciones sociales · Afiliación a servicios de salud",
        "Condiciones sociales · Discapacidad", "Condiciones sociales · Lengua indígena",
    ],
    "Vivienda y conectividad": [
        "Vivienda y conectividad · Acceso a internet", "Vivienda y conectividad · Agua entubada",
        "Vivienda y conectividad · Drenaje",
    ],
    "Participación electoral": [
        "Participación electoral · Lista nominal", "Participación electoral · Participación",
    ],
    "Resultados electorales": [label for label in GOVERNMENT_INDICATORS if label.startswith("Resultados electorales ·")],
    "Gestión municipal": ["Gestión municipal · Participaciones Ramo 28"],
}

# Regionalización presentada en el "Diagnóstico por Regiones" del Plan Estatal
# de Desarrollo Sonora 2021-2027. Cada municipio pertenece a una sola región.
PED_SONORA_REGIONS = {
    "Región del Alto Golfo": [
        "San Luis Río Colorado", "Puerto Peñasco", "General Plutarco Elías Calles",
    ],
    "Región del Gran Desierto": [
        "Caborca", "Altar", "Sáric", "Oquitoa", "Átil", "Tubutama", "Magdalena",
        "Pitiquito", "Trincheras", "Benjamín Hill", "Santa Ana", "Carbó",
    ],
    "Región de la Frontera": ["Nogales", "Santa Cruz", "Ímuris", "Cucurpe"],
    "Región de las Cuatro Sierras": [
        "Cananea", "Naco", "Agua Prieta", "Fronteras", "Bacoachi", "Arizpe",
    ],
    "Región de los Tres Ríos": [
        "Opodepe", "Banámichi", "San Felipe de Jesús", "Huépac", "Rayón", "Aconchi",
        "San Miguel de Horcasitas", "Ures", "Baviácora", "Mazatán", "Soyopa", "Yécora",
        "Villa Pesqueira", "San Pedro de la Cueva", "Bacanora", "Sahuaripa", "Arivechi",
    ],
    "Región de la Sierra Alta": [
        "Nacozari de García", "Bavispe", "Bacerac", "Villa Hidalgo", "Huachinera",
        "Cumpas", "Huásabas", "Bacadéhuachi", "Moctezuma", "Nácori Chico", "Granados",
        "Divisaderos", "Tepache",
    ],
    "Región Capital": ["Hermosillo"],
    "Región del Puerto": ["La Colorada", "San Javier", "Guaymas", "Empalme", "Suaqui Grande", "Ónavas"],
    "Región del Río Yaqui": ["San Ignacio Río Muerto", "Bácum", "Cajeme"],
    "Región del Río Mayo": ["Rosario", "Quiriego", "Navojoa", "Etchojoa", "Benito Juárez", "Álamos", "Huatabampo"],
}

PED_REGION_COLORS = [
    [31, 119, 180, 190], [255, 127, 14, 190], [44, 160, 44, 190],
    [214, 39, 40, 190], [148, 103, 189, 190], [140, 86, 75, 190],
    [227, 119, 194, 190], [127, 127, 127, 190], [188, 189, 34, 190],
    [23, 190, 207, 190],
]

# Síntesis fiel de las fichas del Diagnóstico por Regiones del PED. No son
# resultados nuevos ni una valoración de la plataforma; son contexto para
# interpretar las capas municipales.
PED_SONORA_REGION_PROFILES = {
    "Región del Alto Golfo": {
        "vocacion": "Comercio transfronterizo, turismo sostenible y conservación ambiental.",
        "diagnostico": "Su cercanía con Arizona y California favorece el comercio; el PED destaca además el turismo sostenible asociado a las reservas del Pinacate, Gran Desierto de Altar y Alto Golfo de California.",
    },
    "Región del Gran Desierto": {
        "vocacion": "Agroexportación y generación de energía solar.",
        "diagnostico": "El Valle de Altar-Pitiquito-Caborca es identificado como un importante productor de espárrago de exportación. Sus altos niveles de radiación solar ofrecen condiciones para proyectos fotovoltaicos a gran escala.",
    },
    "Región de la Frontera": {
        "vocacion": "Industria manufacturera, comercio exterior y logística fronteriza.",
        "diagnostico": "La actividad regional se impulsa principalmente por la manufactura instalada en Nogales; el PED señala inversiones que buscan consolidar a Sonora como sede de un clúster aeroespacial de rápido crecimiento.",
    },
    "Región de las Cuatro Sierras": {
        "vocacion": "Minería, maquila, comercio y agricultura.",
        "diagnostico": "Agua Prieta concentra actividades ligadas a la industria maquiladora, comercio y agricultura; Cananea aporta una trayectoria histórica vinculada a la minería como actividad productiva principal.",
    },
    "Región de los Tres Ríos": {
        "vocacion": "Sector primario, ganadería y producción tradicional de Bacanora.",
        "diagnostico": "Agrupa municipios cercanos a afluentes de ríos importantes. La agricultura y ganadería conforman su base económica, complementada por la producción y comercialización de Bacanora.",
    },
    "Región de la Sierra Alta": {
        "vocacion": "Producción agropecuaria, minería y turismo rural.",
        "diagnostico": "El PED reconoce la producción agropecuaria de municipios como Moctezuma y la minería de Nacozari; también identifica potencial de turismo rural en torno al Río Bavispe.",
    },
    "Región Capital": {
        "vocacion": "Servicios, manufactura automotriz, agricultura y turismo local.",
        "diagnostico": "Hermosillo concentra población y funciones de capital. El diagnóstico destaca su clúster automotriz, la agricultura de la Costa de Hermosillo y el turismo de Bahía de Kino.",
    },
    "Región del Puerto": {
        "vocacion": "Logística portuaria, manufactura, actividad costera y turismo.",
        "diagnostico": "Guaymas alberga el puerto más importante del estado. El corredor Guaymas-Empalme integra manufactura, incluido el sector de dispositivos médicos, y San Carlos funciona como atractivo turístico relevante.",
    },
    "Región del Río Yaqui": {
        "vocacion": "Agricultura de valle, servicios urbanos e identidad del pueblo Yaqui.",
        "diagnostico": "Ciudad Obregón es identificada como la segunda ciudad más importante del estado por población y economía. El PED resalta la agricultura del valle y la relevancia histórica y cultural del Pueblo Yaqui.",
    },
    "Región del Río Mayo": {
        "vocacion": "Agricultura, diversidad territorial, costa, sierra y vínculo regional con Sinaloa.",
        "diagnostico": "El Valle del Mayo es presentado como un centro agrícola de importancia nacional. La región combina territorios costeros, desérticos y serranos, con conexión hacia el vecino estado de Sinaloa.",
    },
}


def _normalized_name(value: object) -> str:
    """Normalize municipality labels for joins across public datasets."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.casefold().split())


def attach_ped_sonora_regions(geojson: dict) -> dict:
    """Attach PED 2021-2027 regional labels and categorical colors to Sonora."""
    region_by_municipality = {
        _normalized_name(municipality): (region, index + 1, PED_REGION_COLORS[index])
        for index, (region, municipalities) in enumerate(PED_SONORA_REGIONS.items())
        for municipality in municipalities
    }
    enriched = json.loads(json.dumps(geojson))
    for feature in enriched.get("features", []):
        properties = feature.setdefault("properties", {})
        municipality = properties.get("municipio", properties.get("nom_agem", properties.get("NOMGEO", "")))
        properties["municipio"] = municipality or "Sin nombre"
        region_data = region_by_municipality.get(_normalized_name(municipality))
        if region_data is None:
            properties["region_ped"] = "Sin asignación"
            properties["region_ped_numero"] = 0
            properties["region_ped_color"] = [148, 163, 184, 150]
            continue
        region, region_number, color = region_data
        properties["region_ped"] = region
        properties["region_ped_numero"] = region_number
        properties["region_ped_color"] = color
    return enriched


def dataset_path(state: str | None = None) -> Path | None:
    """Return the local copy when available, otherwise the existing GIS source."""
    if state and state.casefold() != "chihuahua":
        return None
    for candidate in (LOCAL_DATASET, SOURCE_DATASET):
        if candidate.exists():
            return candidate
    return None


@lru_cache(maxsize=8)
def _load_remote_layer(url: str) -> dict:
    response = requests.get(url, timeout=45)
    response.raise_for_status()
    return response.json()


def load_municipal_context(
    uploaded_file=None, state: str | None = None
) -> tuple[dict | None, str | None]:
    """Load a municipal GeoJSON from a user upload or the local GIS project."""
    try:
        if uploaded_file is not None:
            return json.loads(uploaded_file.getvalue().decode("utf-8")), uploaded_file.name
        path = dataset_path(state)
        if path is not None:
            return json.loads(path.read_text(encoding="utf-8")), str(path)
        canonical_state = STATE_NAME_ALIASES.get(state or "", state or "")
        remote_url = REMOTE_STATE_LAYERS.get(canonical_state)
        if remote_url:
            return _load_remote_layer(remote_url), remote_url
        return None, None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, requests.RequestException):
        return None, None


@lru_cache(maxsize=2)
def load_sonora_local_district_context() -> tuple[dict | None, str | None]:
    """Load the official IEE Sonora KML of 2022 local districts as GeoJSON.

    The IEE publishes this KML as its current cartographic product.  We only
    read its polygon geometry and official district code; electoral metrics are
    joined later from the separately published 2024 result workbook.
    """
    try:
        response = requests.get(SONORA_LOCAL_DISTRICTS_KML_URL, timeout=90)
        response.raise_for_status()
        root = ET.fromstring(response.content)
    except (requests.RequestException, ET.ParseError):
        return None, None

    features = []
    for placemark in root.findall(".//{*}Placemark"):
        name = (placemark.findtext("{*}name") or "").strip()
        description = placemark.findtext("{*}description") or ""
        district_match = re.search(
            r"DISTRITO_L.*?<font[^>]*>\s*(\d+)\s*<", description,
            flags=re.IGNORECASE | re.DOTALL,
        )
        district_code = (district_match.group(1) if district_match else name).strip()
        digits = "".join(re.findall(r"\d+", district_code))
        if not digits:
            continue
        polygons = []
        for polygon in placemark.findall(".//{*}Polygon"):
            coordinate_text = polygon.findtext(".//{*}outerBoundaryIs/{*}LinearRing/{*}coordinates")
            if not coordinate_text:
                continue
            ring = []
            for coordinate in coordinate_text.split():
                parts = coordinate.split(",")
                if len(parts) < 2:
                    continue
                try:
                    ring.append([float(parts[0]), float(parts[1])])
                except ValueError:
                    continue
            if len(ring) >= 4:
                polygons.append([ring])
        if not polygons:
            continue
        geometry = (
            {"type": "Polygon", "coordinates": polygons[0]}
            if len(polygons) == 1
            else {"type": "MultiPolygon", "coordinates": polygons}
        )
        features.append({
            "type": "Feature",
            "properties": {
                "distrito_local": digits[-2:].zfill(2),
                "fuente_geometria": "IEE Sonora · KML Distritos Locales 2022",
            },
            "geometry": geometry,
        })
    if not features:
        return None, None
    return {"type": "FeatureCollection", "features": features}, SONORA_LOCAL_DISTRICTS_KML_URL


@lru_cache(maxsize=2)
def load_sonora_electoral_sections_context() -> tuple[dict | None, str | None]:
    """Load the official IEE Sonora KML of electoral sections as GeoJSON."""
    try:
        response = requests.get(SONORA_ELECTORAL_SECTIONS_KML_URL, timeout=120)
        response.raise_for_status()
        root = ET.fromstring(response.content)
    except (requests.RequestException, ET.ParseError):
        return None, None

    def description_value(description: str, field: str) -> str:
        match = re.search(
            rf"{field}.*?<font[^>]*>\s*(\d+)\s*<", description,
            flags=re.IGNORECASE | re.DOTALL,
        )
        return match.group(1) if match else ""

    features = []
    for placemark in root.findall(".//{*}Placemark"):
        description = placemark.findtext("{*}description") or ""
        district_code = description_value(description, "DISTRITO_L")
        section_code = description_value(description, "SECCION")
        municipality_code = description_value(description, "MUNICIPIO")
        if not district_code or not section_code:
            continue
        polygons = []
        for polygon in placemark.findall(".//{*}Polygon"):
            coordinate_text = polygon.findtext(".//{*}outerBoundaryIs/{*}LinearRing/{*}coordinates")
            if not coordinate_text:
                continue
            ring = []
            for coordinate in coordinate_text.split():
                parts = coordinate.split(",")
                if len(parts) < 2:
                    continue
                try:
                    ring.append([float(parts[0]), float(parts[1])])
                except ValueError:
                    continue
            if len(ring) >= 4:
                polygons.append([ring])
        if not polygons:
            continue
        geometry = (
            {"type": "Polygon", "coordinates": polygons[0]}
            if len(polygons) == 1
            else {"type": "MultiPolygon", "coordinates": polygons}
        )
        features.append({
            "type": "Feature",
            "properties": {
                "distrito_local": district_code[-2:].zfill(2),
                "seccion": section_code.zfill(4),
                "municipio_electoral": municipality_code.zfill(3) if municipality_code else "",
                "fuente_geometria": "IEE Sonora · KML Secciones 2024",
            },
            "geometry": geometry,
        })
    if not features:
        return None, None
    return {"type": "FeatureCollection", "features": features}, SONORA_ELECTORAL_SECTIONS_KML_URL


@lru_cache(maxsize=8)
def load_local_district_context(state: str) -> tuple[dict | None, str | None]:
    """Load the verified local-district geometry for the requested state."""
    canonical_state = STATE_NAME_ALIASES.get(state, state)
    if canonical_state == "Sonora":
        return load_sonora_local_district_context()
    path = LOCAL_DISTRICT_DATASETS.get(canonical_state)
    if path is None or not path.exists():
        return None, None
    try:
        layer = json.loads(path.read_text(encoding="utf-8"))
        if len(layer.get("features", [])) == 0:
            return None, None
        return layer, str(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, None


@lru_cache(maxsize=8)
def load_electoral_sections_context(state: str) -> tuple[dict | None, str | None]:
    """Load the verified electoral-section geometry for the requested state."""
    canonical_state = STATE_NAME_ALIASES.get(state, state)
    if canonical_state == "Sonora":
        return load_sonora_electoral_sections_context()
    path = LOCAL_SECTION_DATASETS.get(canonical_state)
    if path is None or not path.exists():
        return None, None
    try:
        layer = json.loads(path.read_text(encoding="utf-8"))
        if len(layer.get("features", [])) == 0:
            return None, None
        return layer, str(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, None


def municipal_dataframe(geojson: dict) -> pd.DataFrame:
    """Extract only government-context attributes from the geographic layer."""
    rows = []
    for feature in geojson.get("features", []):
        properties = feature.get("properties", {})
        rows.append(
            {
                "clave_municipio": str(
                    properties.get("cve_agem", properties.get("cve_mun", ""))
                ).zfill(3),
                "municipio": properties.get("municipio", properties.get("nom_agem", "Sin nombre")),
                "poblacion": properties.get("inegi_poblacion_total", properties.get("pob")),
                "viviendas": properties.get("viv"),
                "población 18 años y más": properties.get("inegi_poblacion_18ymas"),
                "población 18 a 24 años": properties.get("inegi_poblacion_18a24"),
                "escolaridad promedio": properties.get("inegi_escolaridad_promedio"),
                "PEA (%)": properties.get("inegi_pea_pct"),
                "ocupación (%)": properties.get("inegi_ocupacion_pct"),
                "internet_pct": properties.get("inegi_internet_pct"),
                "agua_pct": properties.get("inegi_agua_entubada_pct"),
                "drenaje_pct": properties.get("inegi_drenaje_pct"),
                "salud_pct": properties.get("inegi_afiliacion_salud_pct"),
                "discapacidad (%)": properties.get("inegi_discapacidad_pct"),
                "lengua indígena (%)": properties.get("inegi_lengua_indigena_pct"),
                "lista nominal": properties.get("lista_nominal"),
                "participación electoral (%)": properties.get("participacion_pct"),
                "ganador electoral": properties.get("ganador_candidatura"),
                "segundo lugar electoral": properties.get("segundo_lugar"),
                "margen de votos": properties.get("margen_votos"),
                "votos totales": properties.get("votes_total"),
                "votos nulos": properties.get("votes_nulos"),
                "ramo28_pesos": properties.get("ramo28_2025_pesos"),
                "pmd_url": properties.get("pmd_url"),
                "pmd_estatus": properties.get("pmd_estatus"),
            }
        )
    return pd.DataFrame(rows)


def available_indicators(geojson: dict) -> dict[str, tuple[str, str]]:
    """Return indicators actually available in a state layer."""
    properties = [feature.get("properties", {}) for feature in geojson.get("features", [])]
    keys = {key for row in properties for key in row}
    indicators: dict[str, tuple[str, str]] = {}
    if "inegi_poblacion_total" in keys:
        indicators["Población total"] = ("inegi_poblacion_total", "habitantes")
    elif "pob" in keys:
        indicators["Población total"] = ("pob", "habitantes")
    if "viv" in keys:
        indicators["Viviendas"] = ("viv", "viviendas")
    for label, definition in GOVERNMENT_INDICATORS.items():
        if definition[0] in keys:
            indicators[label] = definition
    return indicators


def contextual_view(geojson: dict) -> dict:
    """Derive a map view from the active state's municipal geometry."""
    coordinates: list[tuple[float, float]] = []

    def collect(node):
        if not node:
            return
        if isinstance(node[0], (int, float)):
            coordinates.append((float(node[0]), float(node[1])))
            return
        for child in node:
            collect(child)

    for feature in geojson.get("features", []):
        geometry = feature.get("geometry") or {}
        collect(geometry.get("coordinates", []))
    if not coordinates:
        return {"latitude": 24.5, "longitude": -106.0, "zoom": 5.0}
    longitudes, latitudes = zip(*coordinates)
    span = max(max(longitudes) - min(longitudes), max(latitudes) - min(latitudes))
    zoom = 7.0 if span < 1 else 6.2 if span < 3 else 5.4 if span < 7 else 4.8
    return {
        "latitude": (min(latitudes) + max(latitudes)) / 2,
        "longitude": (min(longitudes) + max(longitudes)) / 2,
        "zoom": zoom,
    }


def colorize_geojson(
    geojson: dict,
    property_name: str,
    low_color: tuple[int, int, int] = (219, 234, 254),
    high_color: tuple[int, int, int] = (51, 65, 85),
) -> dict:
    """Color numeric municipal values with the selected contextual palette."""
    values = [
        feature.get("properties", {}).get(property_name)
        for feature in geojson.get("features", [])
    ]
    numeric = pd.to_numeric(pd.Series(values), errors="coerce").dropna()
    if numeric.empty:
        minimum, maximum = 0.0, 1.0
    else:
        minimum, maximum = float(numeric.min()), float(numeric.max())
        if minimum == maximum:
            maximum = minimum + 1.0

    colored = json.loads(json.dumps(geojson))
    for feature in colored.get("features", []):
        properties = feature.setdefault("properties", {})
        properties["municipio"] = properties.get("municipio", properties.get("nom_agem", "Sin nombre"))
        value = pd.to_numeric(pd.Series([properties.get(property_name)]), errors="coerce").iloc[0]
        ratio = 0.0 if pd.isna(value) else max(0.0, min(1.0, (float(value) - minimum) / (maximum - minimum)))
        properties["pulso_color"] = [
            int(low_color[0] + ((high_color[0] - low_color[0]) * ratio)),
            int(low_color[1] + ((high_color[1] - low_color[1]) * ratio)),
            int(low_color[2] + ((high_color[2] - low_color[2]) * ratio)),
            185,
        ]
    return colored


def attach_indicator_values(geojson: dict, rows: list[dict], property_name: str) -> dict:
    """Attach stored INEGI values to the municipal geometry for map rendering."""
    values_by_code = {str(row["municipality_code"]).zfill(3): row["value"] for row in rows}
    enriched = json.loads(json.dumps(geojson))
    for feature in enriched.get("features", []):
        properties = feature.setdefault("properties", {})
        code = str(properties.get("cve_agem", "")).zfill(3)
        properties[property_name] = values_by_code.get(code)
    return enriched


def attach_municipal_pulse(geojson: dict, rows: list[dict]) -> dict:
    """Attach an already aggregated local pulse to municipal geometries by name."""
    def normalized(value: object) -> str:
        text = unicodedata.normalize("NFKD", str(value or ""))
        text = "".join(char for char in text if not unicodedata.combining(char))
        return " ".join(text.casefold().split())

    by_name = {normalized(row.get("municipality")): row for row in rows}
    enriched = json.loads(json.dumps(geojson))
    for feature in enriched.get("features", []):
        properties = feature.setdefault("properties", {})
        municipality = properties.get("municipio", properties.get("nom_agem", ""))
        summary = by_name.get(normalized(municipality))
        if summary:
            properties.update({f"pulso_{key}": value for key, value in summary.items() if key != "municipality"})
    return enriched


def attach_election_results(geojson: dict, rows: list[dict]) -> dict:
    """Attach locally imported municipal election values to the active layer."""
    def normalized(value: object) -> str:
        text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
        return " ".join(text.casefold().split())

    by_code = {str(row.get("municipality_code", "")).zfill(3): row["payload"] for row in rows if row.get("municipality_code")}
    by_name = {normalized(row.get("municipality", "")): row["payload"] for row in rows}
    enriched = json.loads(json.dumps(geojson))
    for feature in enriched.get("features", []):
        properties = feature.setdefault("properties", {})
        code = str(properties.get("cve_agem", properties.get("cve_mun", ""))).zfill(3)
        name = normalized(properties.get("municipio", properties.get("nom_agem", "")))
        properties.update(by_code.get(code, by_name.get(name, {})))
    return enriched


def attach_district_results(geojson: dict, rows: list[dict]) -> dict:
    """Join local-district results to an official district GeoJSON.

    INE/OPLE files use different field names across releases.  The join accepts
    common district-code fields, preserves the original attributes, and leaves
    an unmatched polygon visibly without a result instead of guessing it.
    """
    by_code = {str(row["district_code"]).zfill(2): row for row in rows}
    enriched = json.loads(json.dumps(geojson))

    def code_from(properties: dict) -> str:
        preferred = {
            "distrito", "distrito_local", "cve_distrito", "cve_dist",
            "dist_loc", "distritol", "cve_distritol", "distrito_l",
        }
        for key, value in properties.items():
            normalized_key = "_".join(
                unicodedata.normalize("NFKD", str(key)).encode("ascii", "ignore")
                .decode().casefold().replace("-", " ").split()
            )
            if normalized_key not in preferred or value is None:
                continue
            digits = "".join(re.findall(r"\d+", str(value)))
            if digits:
                return digits[-2:].zfill(2)
        return ""

    for feature in enriched.get("features", []):
        properties = feature.setdefault("properties", {})
        district_code = code_from(properties)
        result = by_code.get(district_code)
        if result is None:
            properties["distrito"] = properties.get("distrito", f"Distrito sin identificar")
            properties["municipio"] = properties["distrito"]
            continue
        properties["distrito"] = f"{district_code} · {result['district_name']}"
        # colorize_geojson uses the generic territorial label "municipio";
        # keeping an alias lets the same renderer work for district polygons.
        properties["municipio"] = properties["distrito"]
        properties["clave_distrito"] = district_code
        properties.update(result["payload"])
    return enriched


def attach_section_results(geojson: dict, rows: list[dict]) -> dict:
    """Join published local-deputy section results to official IEE polygons."""
    by_key = {
        (str(row["district_code"]).zfill(2), str(row["section_code"]).zfill(4)): row
        for row in rows
    }
    enriched = json.loads(json.dumps(geojson))
    for feature in enriched.get("features", []):
        properties = feature.setdefault("properties", {})
        district = str(properties.get("distrito_local", "")).zfill(2)
        section = str(properties.get("seccion", "")).zfill(4)
        properties["seccion_etiqueta"] = f"Sección {section} · Distrito {district}"
        properties["municipio"] = properties["seccion_etiqueta"]
        result = by_key.get((district, section))
        if result is None:
            continue
        properties.update(result["payload"])
        if result.get("municipality"):
            properties["municipio_resultado"] = result["municipality"]
    return enriched
