"""Create a local GeoJSON layer of Querétaro's 15 local districts.

The INE public cartography service returns the current district polygon for a
selected section.  We use one section with official 2024 IEEQ results for each
local district, validate the response, and retain the local-district polygon.
"""

from __future__ import annotations

import sys as _storage_sys
from pathlib import Path as _StoragePath
_storage_sys.path.insert(0, str(_StoragePath(__file__).resolve().parents[1]))
from services.storage import storage_path


import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = storage_path("data") / "queretaro_distritos_locales_ine.geojson"
API = "https://cartografia.ine.mx/sige8/api/getConoceTuNuevoDistrito"


def fetch_json(url: str):
    with urlopen(url, timeout=30) as response:
        return json.load(response)


def main() -> None:
    # Representative sections verified against the INE public cartography
    # service, one for each of Querétaro's 15 current local districts.
    representative_sections = {
        "001": "350", "002": "300", "003": "750", "004": "275",
        "005": "400", "006": "450", "007": "516", "008": "100",
        "009": "001", "010": "600", "011": "900", "012": "650",
        "013": "200", "014": "076", "015": "250",
    }
    districts: dict[str, dict] = {}
    for expected_district, section_code in representative_sections.items():
        params = urlencode({"entidad": 22, "seccion": int(section_code)})
        collections = fetch_json(f"{API}?{params}")
        local = next(
            (
                collection
                for collection in collections
                if collection.get("features")
                and collection["features"][0].get("properties", {}).get("distrito_l") is not None
            ),
            None,
        )
        if not local or not local.get("features"):
            raise RuntimeError(f"No local district geometry returned for section {section_code}.")

        feature = local["features"][0]
        returned_district = str(feature["properties"]["distrito_l"]).zfill(3)
        if returned_district != expected_district:
            raise RuntimeError(
                f"Section {section_code} returned district {returned_district}; expected {expected_district}."
            )
        feature["properties"] = {
            "state": "Querétaro",
            "distrito_local": returned_district,
            "distrito": returned_district,
            "source": "INE Cartografía Electoral",
            "source_section": section_code,
        }
        districts[returned_district] = feature
        print(f"District {returned_district} recovered from section {section_code}.")

    features = [districts[key] for key in sorted(districts, key=int)]
    if len(features) != 15:
        raise RuntimeError(f"Expected 15 local districts, received {len(features)}.")

    OUTPUT_PATH.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Created {OUTPUT_PATH} with {len(features)} local district polygons.")


if __name__ == "__main__":
    main()
