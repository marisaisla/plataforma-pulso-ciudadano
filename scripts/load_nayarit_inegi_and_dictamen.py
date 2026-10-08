"""Load Nayarit INEGI indicators and structure Geraldine Ponce's dictamen."""
from __future__ import annotations

import sys as _storage_sys
from pathlib import Path as _StoragePath
_storage_sys.path.insert(0, str(_StoragePath(__file__).resolve().parents[1]))
from services.storage import storage_path


import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.database import connection

from services.inegi import CORE_INDICATORS, collect_municipal_indicator
from services.settings import get_setting

ROOT = Path(__file__).resolve().parents[1]
GEOJSON = storage_path("data") / "nayarit_municipios_2025.geojson"
PROFILE_ID = 7
DICTAMEN_PATH = storage_path("data") / "reference_documents" / "Dictamen_Viabilidad_Electoral_Maria_Geraldine_Ponce_Mendez_Nayarit_2027.pdf"

VARIABLES = {
    "perfil": ("Documentada", "Presidenta municipal de Tepic 2024-2027; previamente diputada federal y titular del ayuntamiento iniciado en 2021.", "Trayectoria política documentada", 1, 1, "perfil"),
    "eleccion": ("Documentada", "Posible candidatura a la Gubernatura de Nayarit en el proceso electoral de 2027.", "Elección objetivo definida", 1, 1, "elección"),
    "territorio": ("Documentada", "Cobertura estatal con prioridad en Tepic, Bahía de Banderas, costa, norte, sur y sierra.", "Zonas estratégicas identificadas", 9, 9, "zonas"),
    "electoral": ("Documentada", "Morena parte como primera fuerza; se integraron resultados oficiales municipales, distritales y seccionales 2024.", "Municipios con resultado electoral", 20, 20, "municipios"),
    "sociodemografico": ("Documentada", "Indicadores municipales oficiales descargados mediante el Banco de Indicadores del INEGI.", "Municipios con indicadores INEGI", 20, 20, "municipios"),
    "fuentes": ("En revisión", "El dictamen enumera referencias públicas; falta registrarlas individualmente como fuentes activas de seguimiento.", "Fuentes activas", 0, 10, "fuentes"),
    "comunicacion": ("En revisión", "Existe evidencia pública de gestión y posicionamiento, pero aún no se ha incorporado una colección trazable de publicaciones.", "Registros de comunicación", 0, 100, "registros"),
    "sentimiento": ("En revisión", "El dictamen identifica riesgos reputacionales y escrutinio de gestión; falta análisis sistemático de conversación pública.", "Registros analizados", 0, 100, "registros"),
    "temas": ("Documentada", "Agenda prioritaria: seguridad, agua, turismo y vivienda, campo y pesca, salud y conectividad, pueblos originarios y transparencia.", "Temas prioritarios", 7, 7, "temas"),
    "posicionamiento": ("Documentada", "Las mediciones publicadas ubican a Ponce en el grupo puntero, con resultados divergentes entre 17.6% y 38.4%.", "Mediciones consideradas", 7, 7, "mediciones"),
    "competencia": ("Documentada", "Rivales internos principales: Héctor Santana y Jasmín Bugarín; se consideran además María Elizabeth López, Pavel Jarero y fuerzas opositoras.", "Referentes competitivos", 6, 6, "perfiles/fuerzas"),
    "encuestas": ("Documentada", "Se documentan Rubrum, FactoMétrica, GobernArte, CE Research, Massive Caller, Alius y Cripeso; no procede un promedio simple.", "Encuestas documentadas", 7, 7, "estudios"),
    "estructura": ("En revisión", "Tepic constituye la base territorial principal; la cobertura operativa fuera de la capital todavía debe acreditarse.", "Zonas con cobertura validada", 1, 9, "zonas"),
    "organizacion": ("En revisión", "La reelección acredita capacidad política en Tepic, pero falta documentar responsables y coordinación a escala estatal.", "Niveles operativos validados", 1, 5, "niveles"),
    "coaliciones": ("Documentada", "Se evaluaron coalición Morena-PT-PVEM unida, competencia interna con Santana y un escenario de PVEM impulsando a Bugarín.", "Escenarios de coalición", 3, 3, "escenarios"),
    "recursos": ("En revisión", "La gestión municipal es un activo, pero equipo, logística, comunicación y recursos financieros requieren evidencia específica.", "Categorías de capacidad", 1, 5, "categorías"),
    "estrategia": ("Documentada", "Ruta de expansión estatal: defender Tepic, crecer en Bahía de Banderas, costa, norte y sierra y construir agenda temática verificable.", "Fases estratégicas definidas", 4, 4, "fases"),
    "plan_accion": ("Documentada", "Ruta de 120 días: línea base, diagnóstico territorial, agenda estatal costeada y pruebas de competitividad y respuesta.", "Fases con producto verificable", 4, 4, "fases"),
    "seguimiento": ("Documentada", "Tablero propuesto con seguimiento quincenal, mensual, semanal y continuo de preferencia, gestión, territorio, coalición y cumplimiento.", "Variables de seguimiento", 8, 8, "variables"),
    "conclusion": ("Documentada", "Viabilidad electoral alta condicionada, 79/100: favorable en elección general si obtiene la nominación y preserva una coalición funcional.", "Calificación global", 79, 100, "puntos"),
}

ELECTORAL_MODEL = {
    "vote_intent": (79, "Competitiva en la interna; las mediciones publicadas oscilan entre 17.6% y 38.4%."),
    "name_recognition": (82, "Alta visibilidad derivada de la presidencia municipal de Tepic y experiencia federal."),
    "favorable_opinion": (75, "Perfil visible y competitivo; requiere medición homogénea de positivos, negativos y rechazo."),
    "territorial_structure": (70, "Base sólida en Tepic; la cobertura fuera de la capital todavía debe acreditarse."),
    "party_brand": (92, "Morena aparece como primera fuerza en todas las mediciones partidistas consideradas."),
    "brand_transfer": (90, "Potencial alto de transferencia, condicionado a nominación, coalición y unidad regional."),
    "electoral_experience": (88, "Reelección municipal, mandato ejecutivo previo y elección como diputada federal."),
    "institutional_position": (82, "Cargo ejecutivo vigente en la capital del estado y exposición institucional relevante."),
    "internal_unity": (64, "Competencia abierta con Santana y Bugarín; la unidad Morena-PT-PVEM es decisiva."),
    "nomination_probability": (72, "Nominación abierta: Ponce lidera algunas mediciones y aparece rezagada en otras."),
    "party_vote_history": (92, "Ventaja estructural de Morena y antecedente estatal ganador en 2021."),
    "mobilization": (85, "La reelección y el gobierno de Tepic aportan base operativa; falta validación estatal completa."),
    "strategic_territories": (75, "Nueve zonas prioritarias definidas con agenda diferenciada."),
    "urban_segments": (92, "Tepic y el corredor con Xalisco constituyen el núcleo urbano más favorable."),
    "undecided_voters": (75, "Existe espacio de crecimiento, pero debe medirse con preguntas y muestras comparables."),
    "useful_vote": (80, "Si encabeza la coalición gobernante puede concentrar voto frente a una oposición fragmentada."),
    "main_rival": (65, "Héctor Santana es el rival interno principal observado y domina varias mediciones."),
    "opposition_fragmentation": (80, "Movimiento Ciudadano aparece como segunda fuerza; PAN y PRI mantienen alianzas inciertas."),
    "reputational_risk": (62, "La gestión municipal concentra escrutinio en agua, seguridad, obra, contratación y servicios."),
    "growth_potential": (84, "Potencial alto si convierte gestión municipal en visión estatal y expande presencia regional."),
}


def load_inegi(conn) -> tuple[int, list[str]]:
    token = get_setting("INEGI_INDICATORS_TOKEN")
    if not token:
        raise RuntimeError("No hay token de Banco de Indicadores INEGI configurado.")
    features = json.loads(GEOJSON.read_text(encoding="utf-8"))["features"]
    stored = 0
    errors: list[str] = []
    for indicator_id in dict.fromkeys(CORE_INDICATORS.values()):
        rows, indicator_errors, _ = collect_municipal_indicator("Nayarit", features, indicator_id, token)
        errors.extend(indicator_errors)
        for row in rows:
            conn.execute(
                """INSERT INTO territorial_indicators
                (state, municipality_code, municipality, indicator_id, indicator_name, unit, value, period)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(state, municipality_code, indicator_id, period) DO UPDATE SET
                municipality=excluded.municipality, indicator_name=excluded.indicator_name,
                unit=excluded.unit, value=excluded.value, retrieved_at=CURRENT_TIMESTAMP""",
                (row["state"], row["municipality_code"], row["municipality"], row["indicator_id"],
                 row["indicator_name"], row["unit"], row["value"], row["period"]),
            )
            stored += 1
        conn.commit()
    return stored, errors


def load_variables(conn) -> int:
    source = str(DICTAMEN_PATH)
    for code, (status, note, label, actual, target, unit) in VARIABLES.items():
        conn.execute(
            """INSERT INTO viability_variable_assessments
            (profile_id, variable_code, status, evidence_note, source_url,
             metric_label, actual_value, target_value, metric_unit, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(profile_id, variable_code) DO UPDATE SET
            status=excluded.status, evidence_note=excluded.evidence_note,
            source_url=excluded.source_url, metric_label=excluded.metric_label,
            actual_value=excluded.actual_value, target_value=excluded.target_value,
            metric_unit=excluded.metric_unit, updated_at=CURRENT_TIMESTAMP""",
            (PROFILE_ID, code, status, note, source, label, actual, target, unit),
        )
    conn.execute(
        """INSERT INTO viability_conclusions
        (profile_id, assessment_status, strengths, risks, conditions, next_step, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(profile_id) DO UPDATE SET assessment_status=excluded.assessment_status,
        strengths=excluded.strengths, risks=excluded.risks, conditions=excluded.conditions,
        next_step=excluded.next_step, updated_at=CURRENT_TIMESTAMP""",
        (PROFILE_ID, "Viable con condiciones",
         "Reelección en Tepic; experiencia ejecutiva y legislativa; alta visibilidad; Morena como primera fuerza; base urbana sólida.",
         "Nominación abierta; encuestas internas contradictorias; dependencia de Tepic; cobertura estatal y resultados sectoriales por acreditar.",
         "Obtener la nominación, preservar la unidad Morena-PT-PVEM, expandir presencia regional y sostener resultados auditables en seguridad, agua y servicios.",
         "Levantar una medición independiente comparable y validar responsables, cobertura y agenda en las nueve zonas estratégicas."),
    )
    conn.commit()
    return len(VARIABLES)


def load_electoral_model(conn) -> int:
    source = str(DICTAMEN_PATH)
    for code, (score, note) in ELECTORAL_MODEL.items():
        conn.execute(
            """INSERT INTO viability_electoral_scores
            (profile_id, variable_code, score, notes, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(profile_id, variable_code) DO UPDATE SET
            score=excluded.score, notes=excluded.notes, updated_at=CURRENT_TIMESTAMP""",
            (PROFILE_ID, code, score, note),
        )
        conn.execute(
            """INSERT INTO viability_electoral_evidence
            (profile_id, variable_code, status, evidence_note, source_label,
             source_url, reference_date, updated_at)
            VALUES (?, ?, 'Documentada', ?, ?, ?, '2026-09-22', CURRENT_TIMESTAMP)
            ON CONFLICT(profile_id, variable_code) DO UPDATE SET
            status=excluded.status, evidence_note=excluded.evidence_note,
            source_label=excluded.source_label, source_url=excluded.source_url,
            reference_date=excluded.reference_date, updated_at=CURRENT_TIMESTAMP""",
            (PROFILE_ID, code, note, "Dictamen de viabilidad electoral Nayarit 2027", source),
        )
    conn.commit()
    return len(ELECTORAL_MODEL)


def main() -> None:
    with connection() as conn:
        indicator_rows, errors = load_inegi(conn)
        variable_rows = load_variables(conn)
        electoral_scores = load_electoral_model(conn)
        municipalities = conn.execute(
            "SELECT COUNT(DISTINCT municipality_code) FROM territorial_indicators WHERE state='Nayarit'"
        ).fetchone()[0]
        total_indicators = conn.execute(
            "SELECT COUNT(*) FROM territorial_indicators WHERE state='Nayarit'"
        ).fetchone()[0]
    print(json.dumps({"descargas_guardadas": indicator_rows, "municipios": municipalities,
                      "indicadores_guardados": total_indicators, "variables": variable_rows,
                      "puntajes_electorales": electoral_scores,
                      "errores": len(errors)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
