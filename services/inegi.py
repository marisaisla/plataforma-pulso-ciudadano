"""Consultas controladas al Banco de Indicadores del INEGI."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


BASE_URL = "https://www.inegi.org.mx/app/api/indicadores/desarrolladores/jsonxml"
STATE_CODES = {"Sonora": "26", "Chihuahua": "08"}
CORE_INDICATORS = {
    "Población · Total": "1002000001",
    "Población · Hombres": "1002000002",
    "Población · Mujeres": "1002000003",
    "Conectividad · Viviendas con Internet (%)": "6207019042",
    "Vivienda · Total de viviendas particulares habitadas": "1003000001",
    "Vivienda · Con energía eléctrica": "1003000017",
    "Vivienda · Con agua de la red pública": "1003000018",
    "Vivienda · Con drenaje": "1003000019",
    "Vivienda · Con excusado o sanitario": "1003000020",
    "Vivienda · Con lavadora": "1003000023",
    "Vivienda · Con computadora": "1003000024",
    "Seguridad · Personal de seguridad pública municipal": "6200001666",
    "Seguridad · Personal municipal: hombres": "6200001667",
    "Seguridad · Personal municipal: mujeres": "6200001668",
}

# Catálogo jerárquico de indicadores ya validados en el Banco de Indicadores.
# El primer nivel ayuda a elegir la materia pública; el segundo evita mezclar
# conceptos distintos dentro de un mismo selector.
INDICATOR_GROUPS = {
    "Población": {
        "Tamaño y composición": {
            "Población total": CORE_INDICATORS["Población · Total"],
            "Población: hombres": CORE_INDICATORS["Población · Hombres"],
            "Población: mujeres": CORE_INDICATORS["Población · Mujeres"],
        },
    },
    "Vivienda y servicios": {
        "Disponibilidad de vivienda": {
            "Total de viviendas particulares habitadas": CORE_INDICATORS[
                "Vivienda · Total de viviendas particulares habitadas"
            ],
        },
        "Servicios básicos": {
            "Viviendas con energía eléctrica": CORE_INDICATORS["Vivienda · Con energía eléctrica"],
            "Viviendas con agua de la red pública": CORE_INDICATORS["Vivienda · Con agua de la red pública"],
            "Viviendas con drenaje": CORE_INDICATORS["Vivienda · Con drenaje"],
            "Viviendas con excusado o sanitario": CORE_INDICATORS["Vivienda · Con excusado o sanitario"],
        },
        "Equipamiento del hogar": {
            "Viviendas con lavadora": CORE_INDICATORS["Vivienda · Con lavadora"],
            "Viviendas con computadora": CORE_INDICATORS["Vivienda · Con computadora"],
        },
    },
    "Conectividad": {
        "Acceso digital": {
            "Viviendas con Internet (%)": CORE_INDICATORS["Conectividad · Viviendas con Internet (%)"],
        },
    },
    "Seguridad y capacidad institucional": {
        "Personal de seguridad pública": {
            "Personal de seguridad pública municipal": CORE_INDICATORS[
                "Seguridad · Personal de seguridad pública municipal"
            ],
            "Personal municipal: hombres": CORE_INDICATORS["Seguridad · Personal municipal: hombres"],
            "Personal municipal: mujeres": CORE_INDICATORS["Seguridad · Personal municipal: mujeres"],
        },
    },
}


def search_indicator_catalog(token: str, search_text: str, limit: int = 50) -> list[dict]:
    """Search the official INEGI indicator catalogue by a human-readable term.

    The catalogue is retrieved only when the user requests a search; it is not
    loaded automatically during normal dashboard use.
    """
    term = search_text.strip().casefold()
    if len(term) < 3:
        return []
    url = f"{BASE_URL}/CL_INDICATOR/null/es/BISE/2.0/{token}?type=json"
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    matches = []
    for item in response.json().get("CODE", []):
        description = str(item.get("Description", "")).strip()
        indicator_id = str(item.get("value", "")).strip()
        if indicator_id and term in description.casefold():
            matches.append({"id": indicator_id, "name": description})
            if len(matches) >= limit:
                break
    return matches


def _metadata(indicator_id: str, token: str) -> str:
    url = f"{BASE_URL}/CL_INDICATOR/{indicator_id}/es/BISE/2.0/{token}?type=json"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    codes = response.json().get("CODE", [])
    return codes[0].get("Description", indicator_id) if codes else indicator_id


def _one_municipality(indicator_id: str, area: str, token: str) -> dict | None:
    url = f"{BASE_URL}/INDICATOR/{indicator_id}/es/{area}/true/BISE/2.0/{token}?type=json"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    series = response.json().get("Series", [])
    observations = series[0].get("OBSERVATIONS", []) if series else []
    if not observations:
        return None
    return observations[0]


def collect_municipal_indicator(
    state: str, features: list[dict], indicator_id: str, token: str
) -> tuple[list[dict], list[str], str]:
    """Retrieve a selected indicator per municipality with bounded concurrency."""
    state_code = STATE_CODES.get(state)
    if not state_code:
        return [], [f"Aún no hay clave INEGI configurada para {state}."], indicator_id
    try:
        indicator_name = _metadata(indicator_id, token)
    except requests.RequestException as error:
        return [], [f"INEGI no permitió consultar los metadatos: {error}"], indicator_id

    tasks = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        for feature in features:
            properties = feature.get("properties", {})
            municipal_code = str(properties.get("cve_agem", "")).zfill(3)
            municipality = properties.get("municipio", properties.get("nom_agem", "Sin nombre"))
            if municipal_code and municipal_code != "000":
                tasks.append((municipal_code, municipality, executor.submit(
                    _one_municipality, indicator_id, f"{state_code}{municipal_code}", token
                )))
        rows: list[dict] = []
        errors: list[str] = []
        for municipal_code, municipality, future in tasks:
            try:
                observation = future.result()
                if observation and observation.get("OBS_VALUE") is not None:
                    rows.append({
                        "state": state,
                        "municipality_code": municipal_code,
                        "municipality": municipality,
                        "indicator_id": indicator_id,
                        "indicator_name": indicator_name,
                        "unit": "",
                        "value": float(observation["OBS_VALUE"]),
                        "period": str(observation.get("TIME_PERIOD", "")),
                    })
            except (requests.RequestException, ValueError) as error:
                errors.append(f"{municipality}: {error}")
    return rows, errors, indicator_name
