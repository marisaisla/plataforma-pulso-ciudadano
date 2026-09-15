"""Base SQLite local de la primera etapa de Plataforma Pulso Ciudadano."""

from __future__ import annotations

import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "data" / "pulso_ciudadano_local.db"


def connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database() -> None:
    with connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                actor_type TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS profile_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                office TEXT NOT NULL,
                condition TEXT NOT NULL,
                starts_at TEXT,
                ends_at TEXT,
                party_or_coalition TEXT,
                is_current INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS territories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                territory_type TEXT NOT NULL,
                state TEXT NOT NULL,
                municipality TEXT,
                district TEXT,
                electoral_section TEXT,
                locality TEXT,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS profile_territories (
                profile_id INTEGER NOT NULL,
                territory_id INTEGER NOT NULL,
                relationship_type TEXT NOT NULL DEFAULT 'cobertura',
                PRIMARY KEY (profile_id, territory_id),
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                FOREIGN KEY (territory_id) REFERENCES territories(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                source_type TEXT NOT NULL,
                name TEXT NOT NULL,
                account_or_url TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS profile_keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                keyword TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                UNIQUE(profile_id, keyword),
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS reference_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                state TEXT,
                title TEXT NOT NULL,
                document_type TEXT NOT NULL DEFAULT 'Documento de referencia',
                file_path TEXT NOT NULL,
                source_url TEXT,
                notes TEXT,
                imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(profile_id, file_path),
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS import_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_application TEXT NOT NULL,
                source_database TEXT NOT NULL,
                imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                imported_records INTEGER NOT NULL DEFAULT 0,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS publications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                source_id INTEGER NOT NULL,
                external_id TEXT NOT NULL,
                title TEXT,
                text TEXT,
                url TEXT,
                published_at TEXT,
                collected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE,
                UNIQUE(profile_id, source_id, external_id)
            );

            CREATE TABLE IF NOT EXISTS publication_territories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                publication_id INTEGER NOT NULL,
                state TEXT NOT NULL,
                municipality TEXT,
                district TEXT,
                electoral_section TEXT,
                match_method TEXT NOT NULL,
                confidence TEXT NOT NULL DEFAULT 'Explícita',
                matched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(publication_id, state, municipality, district, electoral_section, match_method),
                FOREIGN KEY (publication_id) REFERENCES publications(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_publication_territories_state_municipality
                ON publication_territories(state, municipality);

            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                publication_id INTEGER NOT NULL UNIQUE,
                sentiment TEXT NOT NULL,
                sentiment_score INTEGER NOT NULL DEFAULT 0,
                topic TEXT NOT NULL,
                urgency TEXT NOT NULL,
                method TEXT NOT NULL,
                analyzed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (publication_id) REFERENCES publications(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS analysis_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                publication_id INTEGER NOT NULL,
                sentiment TEXT NOT NULL,
                sentiment_score INTEGER NOT NULL DEFAULT 0,
                topic TEXT NOT NULL,
                urgency TEXT NOT NULL,
                method TEXT NOT NULL,
                content_type TEXT,
                relation_to_profile TEXT,
                explanation TEXT,
                model TEXT,
                replaced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (publication_id) REFERENCES publications(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS analysis_approaches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS analysis_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                publication_id INTEGER NOT NULL,
                approach_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'Analizado',
                sentiment TEXT,
                content_type TEXT,
                topic TEXT,
                urgency TEXT,
                relation_to_profile TEXT,
                explanation TEXT,
                method TEXT NOT NULL,
                model TEXT,
                analyzed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(publication_id, approach_id),
                FOREIGN KEY (publication_id) REFERENCES publications(id) ON DELETE CASCADE,
                FOREIGN KEY (approach_id) REFERENCES analysis_approaches(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS prompt_catalog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL,
                prompt_text TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS prompt_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                prompt_catalog_id INTEGER,
                prompt_text TEXT NOT NULL,
                source_filter TEXT,
                date_from TEXT,
                date_to TEXT,
                publication_ids TEXT NOT NULL,
                records_sent INTEGER NOT NULL,
                model TEXT,
                status TEXT NOT NULL DEFAULT 'Completada',
                error TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                FOREIGN KEY (prompt_catalog_id) REFERENCES prompt_catalog(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS prompt_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt_run_id INTEGER NOT NULL UNIQUE,
                response_text TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (prompt_run_id) REFERENCES prompt_runs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS territorial_indicators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state TEXT NOT NULL,
                municipality_code TEXT NOT NULL,
                municipality TEXT NOT NULL,
                indicator_id TEXT NOT NULL,
                indicator_name TEXT NOT NULL,
                unit TEXT,
                value REAL,
                period TEXT,
                source TEXT NOT NULL DEFAULT 'INEGI Banco de Indicadores',
                retrieved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(state, municipality_code, indicator_id, period)
            );

            CREATE TABLE IF NOT EXISTS territorial_election_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state TEXT NOT NULL,
                municipality_code TEXT,
                municipality TEXT NOT NULL,
                election_type TEXT NOT NULL DEFAULT 'Ayuntamientos',
                election_year INTEGER NOT NULL,
                payload TEXT NOT NULL,
                source TEXT NOT NULL,
                imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(state, municipality, election_type, election_year)
            );

            CREATE TABLE IF NOT EXISTS territorial_district_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state TEXT NOT NULL,
                district_code TEXT NOT NULL,
                district_name TEXT NOT NULL,
                election_type TEXT NOT NULL DEFAULT 'Diputaciones locales',
                election_year INTEGER NOT NULL,
                payload TEXT NOT NULL,
                source TEXT,
                imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(state, district_code, election_type, election_year)
            );
            CREATE TABLE IF NOT EXISTS territorial_section_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state TEXT NOT NULL,
                district_code TEXT NOT NULL,
                section_code TEXT NOT NULL,
                municipality_code TEXT,
                municipality TEXT,
                election_type TEXT NOT NULL DEFAULT 'Diputaciones locales',
                election_year INTEGER NOT NULL,
                payload TEXT NOT NULL,
                source TEXT,
                imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(state, district_code, section_code, election_type, election_year)
            );

            CREATE TABLE IF NOT EXISTS territorial_priorities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                state TEXT NOT NULL,
                municipality TEXT NOT NULL,
                election_year INTEGER NOT NULL DEFAULT 2024,
                party_or_coalition TEXT,
                priority_level TEXT NOT NULL,
                priority_index REAL NOT NULL,
                rationale TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Propuesta',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(profile_id, state, municipality, election_year, party_or_coalition),
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS territorial_strategies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                state TEXT NOT NULL,
                municipality TEXT NOT NULL,
                party_or_coalition TEXT,
                priority_id INTEGER,
                strategic_focus TEXT NOT NULL,
                objective TEXT NOT NULL,
                tactics TEXT NOT NULL,
                success_measure TEXT,
                status TEXT NOT NULL DEFAULT 'Borrador',
                starts_at TEXT,
                ends_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(profile_id, state, municipality, party_or_coalition),
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                FOREIGN KEY (priority_id) REFERENCES territorial_priorities(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS territorial_action_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id INTEGER NOT NULL,
                profile_id INTEGER NOT NULL,
                state TEXT NOT NULL,
                municipality TEXT NOT NULL,
                activity_name TEXT NOT NULL,
                activity_description TEXT,
                responsible TEXT,
                due_date TEXT,
                priority_level TEXT NOT NULL DEFAULT 'Media',
                status TEXT NOT NULL DEFAULT 'Pendiente',
                evidence_note TEXT,
                completed_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (strategy_id) REFERENCES territorial_strategies(id) ON DELETE CASCADE,
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );
            """
        )
        # Migración segura para bases creadas antes de agregar la liga de origen.
        reference_columns = {row[1] for row in conn.execute("PRAGMA table_info(reference_documents)")}
        if "source_url" not in reference_columns:
            conn.execute("ALTER TABLE reference_documents ADD COLUMN source_url TEXT")
        existing_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(import_runs)").fetchall()
        }
        additions = {
            "profile_id": "INTEGER",
            "source_type": "TEXT",
            "status": "TEXT",
            "duplicates": "INTEGER NOT NULL DEFAULT 0",
            "details": "TEXT",
        }
        for column, definition in additions.items():
            if column not in existing_columns:
                conn.execute(f"ALTER TABLE import_runs ADD COLUMN {column} {definition}")

        analysis_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(analyses)").fetchall()
        }
        analysis_additions = {
            "content_type": "TEXT",
            "relation_to_profile": "TEXT",
            "explanation": "TEXT",
            "model": "TEXT",
        }
        for column, definition in analysis_additions.items():
            if column not in analysis_columns:
                conn.execute(f"ALTER TABLE analyses ADD COLUMN {column} {definition}")

        # Cada perfil inicia con su nombre como criterio mínimo de relevancia.
        # El usuario puede añadir alias y variantes desde la pantalla de obtención.
        conn.execute(
            """
            INSERT OR IGNORE INTO profile_keywords (profile_id, keyword)
            SELECT id, name FROM profiles
            WHERE TRIM(name) <> ''
            """
        )

        approaches = [
            ("Perfil político", "Tono y relación de un mensaje con la persona o perfil seleccionado."),
            ("Necesidades ciudadanas", "Problema, solicitud, prioridad y posible autoridad responsable."),
            ("Gobierno en funciones", "Servicios, resultados, obras, fallas y responsabilidad institucional."),
            ("Medios digitales", "Distingue noticia, opinión, comunicado y cobertura temática."),
            ("Territorial", "Identifica el territorio mencionado y el contexto geográfico del mensaje."),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO analysis_approaches (name, description) VALUES (?, ?)",
            approaches,
        )
        prompt_templates = [
            (
                "Resumen de percepción pública",
                "Resume tono, temas y mensajes relevantes sobre el perfil.",
                "Elabora un resumen ejecutivo de la percepción pública observada. "
                "Separa hechos informativos, opiniones, apoyos y críticas. Cita los números de fuente que respaldan cada hallazgo.",
            ),
            (
                "Temas críticos y alertas",
                "Detecta críticas, acusaciones, riesgos de reputación y asuntos que merecen seguimiento.",
                "Identifica los temas críticos o alertas. Distingue entre hechos reportados, opiniones, ataques y acusaciones no verificadas. "
                "No afirmes que una acusación es verdadera. Cita los números de fuente.",
            ),
            (
                "Necesidades ciudadanas",
                "Identifica problemas, quejas y solicitudes públicas, sin atribuir ubicación si no se menciona.",
                "Extrae necesidades ciudadanas, quejas o solicitudes. Agrúpalas por tema y urgencia. "
                "Indica municipio o localidad solo si está escrito expresamente en el mensaje. Cita los números de fuente.",
            ),
            (
                "Cobertura de medios",
                "Distingue cobertura informativa, opinión, comunicado y conversación pública.",
                "Clasifica la cobertura en noticia, opinión, comunicado, denuncia o conversación. "
                "Resume cuál es el encuadre predominante y cita los números de fuente.",
            ),
            (
                "Comparativo del periodo",
                "Compara tendencias internas del conjunto seleccionado, sin establecer causalidad.",
                "Describe los cambios de tema y tono dentro del periodo seleccionado. "
                "No infieras causalidad ni generalices más allá de los mensajes proporcionados. Cita los números de fuente.",
            ),
            (
                "Mensajes favorables y atributos destacados",
                "Identifica apoyos y los atributos, acciones o resultados que se reconocen.",
                "Identifica los mensajes favorables y explica qué atributo, acción o resultado se destaca. "
                "Distingue apoyo ciudadano, cobertura informativa e institucional. Cita los números de fuente.",
            ),
            (
                "Agenda pública del perfil",
                "Ordena los asuntos públicos relacionados con el perfil por presencia y tono.",
                "Enumera los temas públicos asociados al perfil, ordenados por presencia en la muestra. "
                "Para cada tema indica el tono predominante y cita los números de fuente.",
            ),
            (
                "Gobierno, servicios y resultados",
                "Busca menciones de obras, programas, servicios, fallas y resultados de gobierno.",
                "Identifica menciones de seguridad, servicios, obras, salud, educación o economía vinculadas al gobierno. "
                "Separa resultados reportados de quejas u opiniones. Cita los números de fuente.",
            ),
            (
                "Municipios y asuntos territoriales",
                "Extrae territorios mencionados y el asunto asociado, solo cuando estén explícitos.",
                "Identifica municipios, localidades, distritos o secciones expresamente escritos. "
                "Para cada territorio resume el asunto mencionado. No infieras ubicación. Cita los números de fuente.",
            ),
            (
                "Relación con Marco Bonilla y sucesión",
                "Resume cobertura y conversación sobre la relación entre Maru Campos, Marco Bonilla y sucesión.",
                "Resume únicamente los mensajes que mencionan la relación entre Maru Campos y Marco Bonilla o la sucesión. "
                "Distingue hechos informativos, interpretaciones y opiniones. Cita los números de fuente.",
            ),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO prompt_catalog (name, description, prompt_text) VALUES (?, ?, ?)",
            prompt_templates,
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO analysis_results
            (publication_id, approach_id, sentiment, content_type, topic, urgency,
             relation_to_profile, explanation, method, model, analyzed_at)
            SELECT a.publication_id, ap.id, a.sentiment, a.content_type, a.topic, a.urgency,
                   a.relation_to_profile, a.explanation, a.method, a.model, a.analyzed_at
            FROM analyses a
            JOIN analysis_approaches ap ON ap.name = 'Perfil político'
            """
        )


def query(sql: str, parameters: tuple = ()) -> list[dict]:
    with connection() as conn:
        return [dict(row) for row in conn.execute(sql, parameters).fetchall()]


def execute(sql: str, parameters: tuple = ()) -> None:
    with connection() as conn:
        conn.execute(sql, parameters)


def record_obtainment_run(profile_id: int, source_type: str, result: dict) -> None:
    errors = result.get("errors", [])
    execute(
        """
        INSERT INTO import_runs
        (source_application, source_database, imported_records, profile_id, source_type, status, duplicates, details)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "Plataforma Pulso Ciudadano",
            "Obtención manual",
            result.get("new_publications", 0),
            profile_id,
            source_type,
            "Con errores" if errors else "Correcta",
            result.get("duplicates", 0),
            "\n".join(errors),
        ),
    )
