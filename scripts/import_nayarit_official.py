"""Import official 2024 Nayarit cartography and election results."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd
import py7zr
import shapefile
from pyproj import CRS, Transformer

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "nayarit_fuentes_oficiales"
OUT = SRC / "ine_bgd_nayarit_diciembre_2025"
DB = ROOT / "data" / "pulso_ciudadano_local.db"
MUN_BOOK = SRC / "IEEN_Nayarit_2024_Presidencias_Sindicaturas.xlsx"
DIS_BOOK = SRC / "IEEN_Nayarit_2024_Diputaciones.xlsx"
MUN_URL = "https://ieenayarit.org/PDF/elecciones/2024/PyS24.xlsx"
DIS_URL = "https://ieenayarit.org/PDF/elecciones/2024/Dip24.xlsx"

NOM_MUN = {
    "Acaponeta":27824,"Ahuacatlan":12879,"Amatlan de Canas":10068,
    "Bahia de Banderas":139756,"Compostela":63924,"Huajicori":8752,
    "Ixtlan del Rio":23432,"Jala":14745,"Del Nayar":30831,"Rosamorada":27113,
    "Ruiz":18935,"San Blas":32005,"San Pedro Lagunillas":7118,
    "Santa Maria del Oro":20045,"Santiago Ixcuintla":74736,"Tecuala":29342,
    "Tepic":328603,"Tuxpan":23767,"Xalisco":48176,"La Yesca":8595,
}
NOM_DIS = dict(enumerate([47101,53631,49766,62332,60475,51242,42055,60248,50807,
                          60392,55197,52047,53497,48176,63924,48294,41819,49643], 1))
PARTIES = {"PAN":"votes_pan","PRI":"votes_pri","PRD":"votes_prd","PVEM":"votes_pvem",
           "PT":"votes_pt","MC":"votes_mc","MORENA":"votes_morena","NAN":"votes_nan",
           "MLN":"votes_mln","RSPN":"votes_rspn","FXMN":"votes_fxmn",
           "Candidaturas no registradas":"votes_no_reg","Votos nulos":"votes_nulos"}


def mun_name(value):
    text = str(value).strip()
    folded = text.casefold()
    if folded.startswith("ahuacatl"):
        return "Ahuacatlan"
    if folded.startswith("amatl"):
        return "Amatlan de Canas"
    if folded.startswith("bah"):
        return "Bahia de Banderas"
    if folded.startswith("ixtl"):
        return "Ixtlan del Rio"
    if folded.startswith("santa mar"):
        return "Santa Maria del Oro"
    return text


def num(value):
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return 0.0 if pd.isna(parsed) else float(parsed)


def sheet(book, name):
    return pd.read_excel(book, sheet_name=name, header=5).dropna(how="all")


def payload(row, nominal=0):
    data = {"lista_nominal": float(nominal)} if nominal else {}
    for label, key in PARTIES.items():
        if label in row.index:
            data[key] = num(row[label])
    valid = sum(v for k, v in data.items() if k.startswith("votes_") and k not in {"votes_nulos","votes_no_reg"})
    total = valid + data.get("votes_nulos", 0) + data.get("votes_no_reg", 0)
    data.update(numero_votos_validos=valid, votes_total=total)
    if nominal:
        data["participacion_pct"] = round(total / nominal * 100, 2)
    options = {k:v for k,v in data.items() if k.startswith("votes_") and k not in {"votes_nulos","votes_no_reg"}}
    if options:
        winner = max(options, key=options.get)
        data.update(opcion_mayor_votacion=winner, votos_opcion_mayor=options[winner])
    return data


def extract():
    if not any(OUT.rglob("MUNICIPIO.shp")):
        OUT.mkdir(parents=True, exist_ok=True)
        with py7zr.SevenZipFile(SRC / "INE_BGD_Nayarit_diciembre_2025.7z") as archive:
            archive.extractall(OUT)


def shape_path(name):
    paths = list(OUT.rglob(name))
    if not paths:
        raise FileNotFoundError(name)
    return paths[0]


def convert_shape(name, destination):
    path = shape_path(name)
    reader = shapefile.Reader(str(path), encoding="latin-1")
    fields = [f[0] for f in reader.fields[1:]]
    prj = path.with_suffix(".prj")
    transformer = None
    if prj.exists():
        crs = CRS.from_wkt(prj.read_text(encoding="latin-1"))
        if crs.to_epsg() != 4326:
            transformer = Transformer.from_crs(crs, 4326, always_xy=True)
    def tx(coords):
        if coords and isinstance(coords[0], (int, float)):
            return list(transformer.transform(coords[0], coords[1])) if transformer else list(coords)
        return [tx(part) for part in coords]
    features = []
    for item in reader.iterShapeRecords():
        geometry = dict(item.shape.__geo_interface__)
        geometry["coordinates"] = tx(geometry["coordinates"])
        features.append({"type":"Feature","properties":dict(zip(fields, item.record)),"geometry":geometry})
    destination.write_text(json.dumps({"type":"FeatureCollection","features":features}, ensure_ascii=False), encoding="utf-8")
    return len(features)


def load_database(conn):
    counts = {"municipios":0,"distritos":0,"secciones":0}
    for _, row in sheet(MUN_BOOK, "ConcentradoMRxPart").iterrows():
        municipality = mun_name(row.iloc[0])
        if municipality not in NOM_MUN:
            continue
        data = payload(row, NOM_MUN[municipality])
        conn.execute("""INSERT INTO territorial_election_results
          (state,municipality_code,municipality,election_type,election_year,payload,source)
          VALUES ('Nayarit','',?,'Ayuntamientos',2024,?,?)
          ON CONFLICT(state,municipality,election_type,election_year) DO UPDATE SET
          payload=excluded.payload,source=excluded.source,imported_at=CURRENT_TIMESTAMP""",
          (municipality,json.dumps(data,ensure_ascii=False),MUN_URL))
        counts["municipios"] += 1
    for _, row in sheet(DIS_BOOK, "ConcentradoMRxPart").iterrows():
        district = pd.to_numeric(pd.Series([row.iloc[0]]), errors="coerce").iloc[0]
        if pd.isna(district) or int(district) not in NOM_DIS:
            continue
        district = int(district)
        data = payload(row, NOM_DIS[district])
        conn.execute("""INSERT INTO territorial_district_results
          (state,district_code,district_name,election_type,election_year,payload,source)
          VALUES ('Nayarit',?,?,'Diputaciones locales',2024,?,?)
          ON CONFLICT(state,district_code,election_type,election_year) DO UPDATE SET
          district_name=excluded.district_name,payload=excluded.payload,source=excluded.source,imported_at=CURRENT_TIMESTAMP""",
          (str(district).zfill(2),f"Distrito local {district}",json.dumps(data,ensure_ascii=False),DIS_URL))
        counts["distritos"] += 1
    sections = {}
    for district in range(1, 19):
        for _, row in sheet(DIS_BOOK, f"D{district}").iterrows():
            section = pd.to_numeric(pd.Series([row.iloc[1]]), errors="coerce").iloc[0]
            if pd.isna(section) or int(section) <= 0:
                continue
            key = (district,str(int(section)).zfill(4),mun_name(row.iloc[0]))
            aggregate = sections.setdefault(key, {v:0.0 for v in PARTIES.values()})
            for label, mapped in PARTIES.items():
                if label in row.index:
                    aggregate[mapped] += num(row[label])
    for (district,section,municipality), data in sections.items():
        valid = sum(v for k,v in data.items() if k.startswith("votes_") and k not in {"votes_nulos","votes_no_reg"})
        total = valid + data.get("votes_nulos",0) + data.get("votes_no_reg",0)
        options = {k:v for k,v in data.items() if k.startswith("votes_") and k not in {"votes_nulos","votes_no_reg"}}
        winner = max(options,key=options.get)
        data.update(numero_votos_validos=valid,votes_total=total,opcion_mayor_votacion=winner,votos_opcion_mayor=options[winner])
        conn.execute("""INSERT INTO territorial_section_results
          (state,district_code,section_code,municipality_code,municipality,election_type,election_year,payload,source)
          VALUES ('Nayarit',?,?,'',?,'Diputaciones locales',2024,?,?)
          ON CONFLICT(state,district_code,section_code,election_type,election_year) DO UPDATE SET
          municipality=excluded.municipality,payload=excluded.payload,source=excluded.source,imported_at=CURRENT_TIMESTAMP""",
          (str(district).zfill(2),section,municipality,json.dumps(data,ensure_ascii=False),DIS_URL))
    counts["secciones"] = len(sections)
    return counts


def main():
    extract()
    geometries = {
        "municipios": convert_shape("MUNICIPIO.shp", ROOT / "data" / "nayarit_municipios_2025.geojson"),
        "distritos": convert_shape("DISTRITO_LOCAL.shp", ROOT / "data" / "nayarit_distritos_locales_2025.geojson"),
        "secciones": convert_shape("SECCION.shp", ROOT / "data" / "nayarit_secciones_electorales_2025.geojson"),
    }
    with sqlite3.connect(DB) as conn:
        results = load_database(conn)
        conn.commit()
    print(json.dumps({"geometrias":geometries,"resultados":results},ensure_ascii=False))


if __name__ == "__main__":
    main()
