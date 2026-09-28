"""Incorpora el dictamen de Cecilia Patrón Laviada al expediente Go2Win."""

from __future__ import annotations

import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "pulso_ciudadano_local.db"
DOCUMENT = ROOT / "data" / "reference_documents" / "Dictamen_Viabilidad_Electoral_Cecilia_Patron_Laviada_Merida_2027.pdf"
PROFILE_NAME = "Cecilia Anunciación Patrón Laviada"
STATE = "Yucatán"

DOCUMENT_VARIABLES = {
    "perfil": ("Documentada", "Presidenta municipal de Mérida 2024-2027; previamente diputada federal en las legislaturas LXIV y LXV.", "Expediente de perfil", 1, 1, "expediente"),
    "eleccion": ("Documentada", "Ruta de elección consecutiva a la Presidencia Municipal de Mérida en 2027, sujeta a requisitos y plazos aplicables.", "Elección objetivo definida", 1, 1, "elección"),
    "territorio": ("Documentada", "Seis zonas funcionales: norte consolidado, centro, poniente-Caucel, sur-suroriente, oriente y comisarías.", "Zonas prioritarias", 6, 6, "zonas"),
    "electoral": ("Documentada", "Elección municipal 2024: 258,489 votos para PAN-PRI-Nueva Alianza frente a 205,395 para Morena-PT-PVEM.", "Elección municipal comparable", 1, 1, "elección"),
    "sociodemografico": ("Documentada", "Indicadores INEGI municipales disponibles para Mérida dentro de la base territorial de Yucatán.", "Municipio con indicadores", 1, 1, "municipio"),
    "fuentes": ("Documentada", "Dictamen respaldado por IEPAC, INEGI, Ayuntamiento de Mérida y mediciones públicas citadas.", "Fuentes documentales", 4, 4, "fuentes"),
    "comunicacion": ("En revisión", "El dictamen propone convertir cada logro en problema, acción, cobertura, resultado y siguiente meta; falta monitoreo trazable de publicaciones.", "Sistema de comunicación", 0, 1, "sistema"),
    "sentimiento": ("Pendiente", "Aún no hay una muestra procesada de conversación pública, sentimiento y posibles cuentas no auténticas.", "Registros analizados", 0, 100, "registros"),
    "temas": ("Documentada", "Agua, movilidad, calles y drenaje, seguridad, orden urbano, economía familiar y medio ambiente.", "Agenda prioritaria", 7, 7, "temas"),
    "posicionamiento": ("Documentada", "Aprobación reportada entre 59.4% y 64.5%; debe distinguirse de intención de voto.", "Mediciones de aprobación", 3, 3, "mediciones"),
    "competencia": ("Documentada", "Rivales observados: Rommel Pacheco, Jessica Saidén, Verónica Camino, Óscar Brito y Javier Osante.", "Perfiles competitivos", 5, 5, "perfiles"),
    "encuestas": ("Documentada", "LaEncuesta.mx, MetaMetrics y Demoscopia Digital, con metodologías por verificar antes de compararlas.", "Estudios citados", 3, 3, "estudios"),
    "estructura": ("Documentada", "Incumbencia municipal, estructura partidista y presencia territorial; requiere auditoría por zona y responsable.", "Zonas con ruta estratégica", 6, 6, "zonas"),
    "organizacion": ("En revisión", "Falta acreditar responsables, cobertura, movilización y evidencias operativas por zona funcional.", "Zonas con responsable validado", 0, 6, "zonas"),
    "coaliciones": ("En revisión", "PAN-PRI-Nueva Alianza fue la coalición ganadora en 2024; la configuración formal de 2027 permanece abierta.", "Escenarios de coalición", 1, 3, "escenarios"),
    "recursos": ("En revisión", "Los logros de gestión son activos potenciales; falta documentar recursos, logística y controles de cumplimiento.", "Capacidades documentadas", 1, 5, "categorías"),
    "estrategia": ("Documentada", "Continuidad que corrige y llega parejo: proteger servicios, ampliar la coalición social y diferenciar la agenda por zona.", "Rutas territoriales", 6, 6, "zonas"),
    "plan_accion": ("En revisión", "El dictamen define prioridades y pruebas necesarias, pero faltan actividades calendarizadas, responsables y metas operativas.", "Actividades calendarizadas", 0, 100, "actividades"),
    "seguimiento": ("En revisión", "Propone monitorear aprobación, servicios, cobertura territorial y riesgos; falta tablero operativo con corte periódico.", "Indicadores en seguimiento", 0, 7, "indicadores"),
    "conclusion": ("Documentada", "Viabilidad global alta y condicionada: 84/100, con ventaja inicial no irreversible.", "Índice del dictamen", 84, 100, "puntos"),
}

BASE_MODEL = {
    "previous_election": (90, "Resultado electoral previo: ventaja comprobada en Mérida 2024."),
    "approval_knowledge": (88, "Aprobación y conocimiento: posición favorable en mediciones públicas de 2026."),
    "structure_nomination": (91, "Estructura y nominación: incumbencia y control de red partidista."),
    "management_results": (80, "Gestión y resultados: activos visibles con escrutinio alto."),
    "territorial_coverage": (77, "Cobertura territorial: existen brechas entre zonas de la ciudad."),
    "coalition_alliances": (74, "Coalición y alianzas: configuración 2027 todavía abierta."),
    "political_context": (75, "Entorno político: el gobierno estatal de Morena eleva la competencia."),
    "reputational_risk": (91, "Control de riesgo reputacional: sin ruptura dominante, con prevención necesaria."),
}

COMPETITORS = [
    ("Rommel Pacheco Marrufo", "Morena", "Rival observado", "Mérida", "Principal rival observado; su riesgo aumenta con una coalición Morena-PT-PVEM cohesionada."),
    ("Jessica Saidén Quiroz", "Morena", "Rival observado", "Mérida", "Estructura política y crecimiento en mediciones internas; depende de nominación y transferencia."),
    ("Verónica Camino Farjat", "Morena", "Rival observado", "Mérida", "Experiencia y reconocimiento; requeriría recuperar voto urbano y articular redes."),
    ("Óscar Brito Zapata", "Morena", "Rival observado", "Mérida", "Trayectoria partidista; tendría que ampliar conocimiento y operación territorial."),
    ("Javier Osante Solís", "Movimiento Ciudadano", "Rival observado", "Mérida", "Puede captar voto joven o de rechazo y alterar el margen de la contienda."),
]

SURVEYS = [
    ("Aprobación de gestión - marzo 2026", "LaEncuesta.mx", "Mérida", "marzo 2026", 64.5),
    ("Aprobación de gestión - agosto 2026", "MetaMetrics", "Mérida", "agosto 2026", 64.1),
    ("Aprobación de gestión - agosto 2026", "Demoscopia Digital", "Mérida", "agosto 2026", 59.4),
]


def main() -> None:
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        existing = conn.execute("SELECT id FROM profiles WHERE name=?", (PROFILE_NAME,)).fetchone()
        if existing:
            profile_id = int(existing["id"])
            conn.execute("UPDATE profiles SET active=1, notes=? WHERE id=?", ("Perfil incorporado desde dictamen de viabilidad electoral de Mérida 2027.", profile_id))
        else:
            cursor = conn.execute(
                "INSERT INTO profiles (name, actor_type, active, notes) VALUES (?, 'Persona', 1, ?)",
                (PROFILE_NAME, "Perfil incorporado desde dictamen de viabilidad electoral de Mérida 2027."),
            )
            profile_id = int(cursor.lastrowid)

        state_territory = conn.execute("SELECT id FROM territories WHERE territory_type='Estado' AND state=?", (STATE,)).fetchone()
        merida_territory = conn.execute("SELECT id FROM territories WHERE territory_type='Municipio' AND state=? AND municipality='Mérida'", (STATE,)).fetchone()
        if not state_territory or not merida_territory:
            raise RuntimeError("No se encontró la base territorial de Yucatán o el municipio de Mérida.")
        conn.execute("INSERT OR REPLACE INTO profile_territories (profile_id, territory_id, relationship_type) VALUES (?, ?, 'cobertura')", (profile_id, state_territory["id"]))
        conn.execute("INSERT OR REPLACE INTO profile_territories (profile_id, territory_id, relationship_type) VALUES (?, ?, 'representación')", (profile_id, merida_territory["id"]))

        conn.execute("DELETE FROM profile_positions WHERE profile_id=?", (profile_id,))
        conn.executemany(
            """INSERT INTO profile_positions (profile_id, office, condition, starts_at, ends_at, party_or_coalition, is_current)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                (profile_id, "Presidenta Municipal de Mérida - periodo 2024-2027", "En funciones", "2024", "2027", "PAN", 1),
                (profile_id, "Presidencia Municipal de Mérida", "Posible candidata a elección consecutiva", "2027", None, "PAN o coalición original", 1),
            ],
        )

        conn.execute("DELETE FROM reference_documents WHERE profile_id=? AND document_type='Dictamen de viabilidad'", (profile_id,))
        conn.execute(
            """INSERT INTO reference_documents (profile_id, state, title, document_type, file_path, notes)
               VALUES (?, ?, ?, 'Dictamen de viabilidad', ?, ?)""",
            (profile_id, STATE, "Dictamen de Viabilidad Electoral - Cecilia Patrón Laviada - Mérida 2027", str(DOCUMENT),
             "Documento de análisis estratégico con corte al 25 de septiembre de 2026. Sus indicadores y escenarios requieren actualización periódica."),
        )

        for code, (status, note, label, actual, target, unit) in DOCUMENT_VARIABLES.items():
            conn.execute(
                """INSERT INTO viability_variable_assessments
                   (profile_id, variable_code, status, evidence_note, source_url, metric_label, actual_value, target_value, metric_unit, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(profile_id, variable_code) DO UPDATE SET
                   status=excluded.status, evidence_note=excluded.evidence_note, source_url=excluded.source_url,
                   metric_label=excluded.metric_label, actual_value=excluded.actual_value,
                   target_value=excluded.target_value, metric_unit=excluded.metric_unit, updated_at=CURRENT_TIMESTAMP""",
                (profile_id, code, status, note, str(DOCUMENT), label, actual, target, unit),
            )

        for code, (score, note) in BASE_MODEL.items():
            conn.execute(
                """INSERT INTO viability_electoral_scores (profile_id, variable_code, score, notes, updated_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(profile_id, variable_code) DO UPDATE SET score=excluded.score, notes=excluded.notes, updated_at=CURRENT_TIMESTAMP""",
                (profile_id, code, score, note),
            )
            conn.execute(
                """INSERT INTO viability_electoral_evidence
                   (profile_id, variable_code, status, evidence_note, source_label, source_url, reference_date, updated_at)
                   VALUES (?, ?, 'Documentada', ?, ?, ?, '2026-09-25', CURRENT_TIMESTAMP)
                   ON CONFLICT(profile_id, variable_code) DO UPDATE SET status=excluded.status, evidence_note=excluded.evidence_note,
                   source_label=excluded.source_label, source_url=excluded.source_url, reference_date=excluded.reference_date, updated_at=CURRENT_TIMESTAMP""",
                (profile_id, code, note, "Dictamen de Viabilidad Electoral - Cecilia Patrón Laviada - Mérida 2027", str(DOCUMENT)),
            )

        conn.execute("DELETE FROM viability_competitors WHERE profile_id=?", (profile_id,))
        conn.executemany(
            """INSERT INTO viability_competitors (profile_id, name, party_or_coalition, condition, territory, positioning_note)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [(profile_id, *row) for row in COMPETITORS],
        )
        conn.execute("DELETE FROM viability_surveys WHERE profile_id=?", (profile_id,))
        conn.executemany(
            """INSERT INTO viability_surveys (profile_id, name, pollster, territory, fieldwork_date, profile_result_pct, methodology, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [(profile_id, name, pollster, territory, fieldwork, value,
              "Medición pública de aprobación; ficha técnica y comparabilidad por validar.",
              "La aprobación no equivale a intención de voto.") for name, pollster, territory, fieldwork, value in SURVEYS],
        )
        conn.execute(
            """INSERT INTO viability_conclusions (profile_id, assessment_status, strengths, risks, conditions, next_step, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(profile_id) DO UPDATE SET assessment_status=excluded.assessment_status,
               strengths=excluded.strengths, risks=excluded.risks, conditions=excluded.conditions,
               next_step=excluded.next_step, updated_at=CURRENT_TIMESTAMP""",
            (profile_id, "Alta, condicionada - 84/100", "Victoria comprobada en 2024, incumbencia municipal, aprobación pública, reconocimiento y marca PAN competitiva en Mérida.",
             "Desgaste de gestión, brechas de servicios entre zonas, rival único de Morena, crisis de agua, movilidad, seguridad o ruptura interna.",
             "Transformar aprobación en preferencia, sostener resultados verificables de gobierno, ampliar apoyo en sur, poniente y comisarías y definir coalición.",
             "Levantar tracking comparable por zona, auditar responsables territoriales y convertir agenda de servicios en metas semanales."),
        )
        conn.commit()

    print(f"Perfil {profile_id} cargado: {PROFILE_NAME}")


if __name__ == "__main__":
    main()
