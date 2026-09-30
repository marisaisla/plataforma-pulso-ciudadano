"""Configura el expediente inicial de Felipe Fernando \"Felifer\" Macías en Go2Win.

La carga distingue entre hechos documentados y elementos que todavía requieren
un dictamen, tracking o validación; no califica la viabilidad ni presupone una
candidatura formal para 2027.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "pulso_ciudadano_local.db"
PROFILE_NAME = "Felipe Fernando Macías Olvera"
STATE = "Querétaro"

OFFICIAL_ROLE_SOURCE = (
    "https://municipiodequeretaro.gob.mx/municipio/repositorios/gacetas-2024-2027/Gaceta-No.38.pdf"
)
LEGISLATIVE_PROFILE_SOURCE = (
    "https://sil.gobernacion.gob.mx/Librerias/pp_PerfilLegislador.php?Referencia=9226104"
)
CONTEXT_2027_SOURCE = (
    "https://elpais.com/mexico/2026-09-19/defensores-de-la-patria-el-pan-copia-la-estrategia-de-morena-en-un-intento-de-mantener-el-pulso-de-2027.html"
)

ASSESSMENTS = {
    "perfil": (
        "Documentada",
        "Presidente Municipal de Querétaro para el periodo 2024-2027; trayectoria legislativa pública disponible.",
        OFFICIAL_ROLE_SOURCE,
        "Fuentes de perfil verificadas",
        2,
        2,
        "fuentes",
    ),
    "eleccion": (
        "En revisión",
        "El proceso de selección del PAN y las candidaturas para la gubernatura de 2027 no están definidos formalmente.",
        CONTEXT_2027_SOURCE,
        "Definición formal de candidatura",
        0,
        1,
        "definición",
    ),
    "territorio": (
        "Documentada",
        "Go2Win ya cuenta con la base territorial estatal de Querétaro: 18 municipios, distritos, secciones e indicadores municipales.",
        None,
        "Cobertura territorial disponible",
        1,
        1,
        "estado",
    ),
    "electoral": (
        "Documentada",
        "La plataforma contiene resultados electorales históricos para Querétaro; falta convertirlos en una lectura específica del perfil.",
        None,
        "Base electoral territorial",
        1,
        1,
        "base",
    ),
    "sociodemografico": (
        "Documentada",
        "Hay indicadores INEGI municipales cargados para cruzar el análisis electoral con condiciones demográficas y sociales.",
        None,
        "Indicadores territoriales",
        1,
        1,
        "base",
    ),
    "fuentes": (
        "Documentada",
        "Se integraron fuentes oficiales para el cargo vigente, trayectoria pública y contexto político publicado.",
        OFFICIAL_ROLE_SOURCE,
        "Fuentes iniciales",
        3,
        3,
        "fuentes",
    ),
    "posicionamiento": ("Pendiente", "Requiere estudios comparables de conocimiento, opinión e intención de voto con ficha técnica.", None, "Estudios comparables", 0, 1, "estudio"),
    "competencia": ("En revisión", "Santiago Nieto ha sido mencionado públicamente como perfil de Morena; las candidaturas y alianzas siguen abiertas.", CONTEXT_2027_SOURCE, "Perfiles documentados", 1, 1, "perfil"),
    "encuestas": ("Pendiente", "No se carga ningún porcentaje sin ficha técnica, fecha de levantamiento, universo y fuente verificable.", None, "Encuestas verificadas", 0, 1, "estudio"),
    "estructura": ("Pendiente", "Falta auditoría de responsables, cobertura y capacidad operativa por municipio y sección.", None, "Cobertura validada", 0, 100, "%"),
    "organizacion": ("Pendiente", "Falta registrar responsables, actividades, evidencias y seguimiento territorial.", None, "Registros operativos", 0, 1, "sistema"),
    "coaliciones": ("En revisión", "La definición de alianzas y método de selección corresponde a los partidos; no se asume una coalición para 2027.", CONTEXT_2027_SOURCE, "Escenarios confirmados", 0, 1, "escenario"),
    "recursos": ("Pendiente", "No hay presupuesto, logística ni capacidades operativas documentadas en el expediente.", None, "Capacidades documentadas", 0, 1, "expediente"),
    "comunicacion": ("Pendiente", "Falta incorporar fuentes oficiales, medios y conversación digital para medir agenda, alcance y riesgo.", None, "Monitoreo activo", 0, 1, "sistema"),
    "sentimiento": ("Pendiente", "No existe aún una muestra procesada de conversación digital o medios para este perfil.", None, "Registros procesados", 0, 100, "registros"),
    "temas": ("Pendiente", "La agenda territorial debe derivarse de evidencia ciudadana, resultados de gestión y medición de prioridades.", None, "Agenda validada", 0, 1, "agenda"),
    "estrategia": ("Pendiente", "Sólo se construirá después de validar escenario, objetivo, estructura y prioridades territoriales.", None, "Estrategia validada", 0, 1, "estrategia"),
    "plan_accion": ("Pendiente", "Faltan metas, responsables, calendario y evidencia de ejecución.", None, "Plan operativo", 0, 1, "plan"),
    "seguimiento": ("Pendiente", "Falta definir corte, indicadores, fuentes y responsables de seguimiento.", None, "Tablero de seguimiento", 0, 1, "tablero"),
    "conclusion": ("Pendiente", "No hay dictamen de viabilidad ni calificación cargada; se requiere evidencia para emitirlo.", None, "Dictamen concluido", 0, 1, "dictamen"),
}


def main() -> None:
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        profile = conn.execute("SELECT id FROM profiles WHERE name=?", (PROFILE_NAME,)).fetchone()
        if profile:
            profile_id = int(profile["id"])
            conn.execute(
                "UPDATE profiles SET active=1, notes=? WHERE id=?",
                ("Expediente inicial de Felipe Fernando \"Felifer\" Macías para Querétaro. La posible postulación de 2027 está por definir; los puntajes de viabilidad permanecen sin calificar.", profile_id),
            )
        else:
            cursor = conn.execute(
                "INSERT INTO profiles (name, actor_type, active, notes) VALUES (?, 'Persona', 1, ?)",
                (PROFILE_NAME, "Expediente inicial de Felipe Fernando \"Felifer\" Macías para Querétaro. La posible postulación de 2027 está por definir; los puntajes de viabilidad permanecen sin calificar."),
            )
            profile_id = int(cursor.lastrowid)

        state = conn.execute(
            "SELECT id FROM territories WHERE territory_type='Estado' AND state=?", (STATE,)
        ).fetchone()
        municipality = conn.execute(
            "SELECT id FROM territories WHERE territory_type='Municipio' AND state=? AND municipality='Querétaro'", (STATE,)
        ).fetchone()
        if not state or not municipality:
            raise RuntimeError("No se encontró la base territorial estatal o municipal de Querétaro.")
        conn.execute(
            "INSERT OR REPLACE INTO profile_territories (profile_id, territory_id, relationship_type) VALUES (?, ?, 'cobertura')",
            (profile_id, state["id"]),
        )
        conn.execute(
            "INSERT OR REPLACE INTO profile_territories (profile_id, territory_id, relationship_type) VALUES (?, ?, 'representación')",
            (profile_id, municipality["id"]),
        )

        conn.execute("DELETE FROM profile_positions WHERE profile_id=?", (profile_id,))
        conn.executemany(
            """INSERT INTO profile_positions
               (profile_id, office, condition, starts_at, ends_at, party_or_coalition, is_current)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                (profile_id, "Presidente Municipal de Querétaro · periodo 2024-2027", "En funciones", "2024", "2027", "PAN", 1),
                (profile_id, "Gubernatura de Querétaro", "Perfil mencionado para 2027; candidatura no formalizada", "2027", None, "PAN", 0),
            ],
        )

        conn.execute("DELETE FROM sources WHERE profile_id=?", (profile_id,))
        conn.executemany(
            "INSERT INTO sources (profile_id, source_type, name, account_or_url, active) VALUES (?, ?, ?, ?, 1)",
            [
                (profile_id, "Fuente oficial", "Municipio de Querétaro · Gaceta 2024-2027", OFFICIAL_ROLE_SOURCE),
                (profile_id, "Fuente oficial", "Sistema de Información Legislativa · perfil público", LEGISLATIVE_PROFILE_SOURCE),
                (profile_id, "Prensa de contexto", "El País · proceso político Querétaro 2027", CONTEXT_2027_SOURCE),
            ],
        )
        conn.execute("DELETE FROM profile_keywords WHERE profile_id=?", (profile_id,))
        conn.executemany(
            "INSERT INTO profile_keywords (profile_id, keyword, active) VALUES (?, ?, 1)",
            [(profile_id, value) for value in ("Felipe Fernando Macías", "Felifer Macías", "Felifer", "Felipe Macías")],
        )

        for code, (status, note, source, label, actual, target, unit) in ASSESSMENTS.items():
            conn.execute(
                """INSERT INTO viability_variable_assessments
                   (profile_id, variable_code, status, evidence_note, source_url, metric_label, actual_value, target_value, metric_unit, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(profile_id, variable_code) DO UPDATE SET
                     status=excluded.status, evidence_note=excluded.evidence_note, source_url=excluded.source_url,
                     metric_label=excluded.metric_label, actual_value=excluded.actual_value,
                     target_value=excluded.target_value, metric_unit=excluded.metric_unit, updated_at=CURRENT_TIMESTAMP""",
                (profile_id, code, status, note, source, label, actual, target, unit),
            )

        conn.execute("DELETE FROM viability_competitors WHERE profile_id=?", (profile_id,))
        conn.execute(
            """INSERT INTO viability_competitors
               (profile_id, name, party_or_coalition, condition, territory, positioning_note, source_url)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (profile_id, "Santiago Nieto Castillo", "Morena", "Perfil mencionado públicamente", "Querétaro", "Perfil de Morena referido en la conversación pública rumbo a 2027; candidatura y coalición por confirmar.", CONTEXT_2027_SOURCE),
        )

        conn.execute(
            """INSERT INTO viability_conclusions
               (profile_id, assessment_status, strengths, risks, conditions, next_step, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(profile_id) DO UPDATE SET assessment_status=excluded.assessment_status,
                 strengths=excluded.strengths, risks=excluded.risks, conditions=excluded.conditions,
                 next_step=excluded.next_step, updated_at=CURRENT_TIMESTAMP""",
            (
                profile_id,
                "Expediente inicial · sin calificación de viabilidad",
                "Cargo municipal vigente, representación en la capital y base territorial-electoral estatal ya disponible en Go2Win.",
                "La candidatura, alianzas, preferencia electoral, estructura territorial y evaluación comparativa aún requieren evidencia verificable.",
                "No se debe interpretar este expediente como una candidatura formal, pronóstico ni dictamen terminado.",
                "Incorporar un dictamen de viabilidad y tracking con ficha técnica; después evaluar las 20 variables sin usar valores estimados.",
            ),
        )
        conn.commit()

    print(f"Perfil configurado: {PROFILE_NAME} (id {profile_id})")


if __name__ == "__main__":
    main()
