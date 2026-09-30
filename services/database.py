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

            CREATE TABLE IF NOT EXISTS analysis_result_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                publication_id INTEGER NOT NULL,
                approach_id INTEGER NOT NULL,
                previous_result TEXT NOT NULL,
                replaced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (publication_id) REFERENCES publications(id) ON DELETE CASCADE
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

            CREATE TABLE IF NOT EXISTS development_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                state TEXT NOT NULL,
                municipality TEXT NOT NULL,
                title TEXT NOT NULL,
                period TEXT,
                official_status TEXT NOT NULL DEFAULT 'Por homologar a documento oficial',
                source_url TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(profile_id, state, municipality, title),
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS development_plan_axes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                sort_order INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Por homologar a documento oficial',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(plan_id, name),
                FOREIGN KEY (plan_id) REFERENCES development_plans(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS development_plan_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                axis_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                baseline_value REAL,
                target_value REAL,
                current_value REAL,
                unit TEXT,
                frequency TEXT,
                territory_scope TEXT,
                status TEXT NOT NULL DEFAULT 'Pendiente de fuente oficial',
                source_url TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(axis_id, name),
                FOREIGN KEY (axis_id) REFERENCES development_plan_axes(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS development_plan_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_id INTEGER NOT NULL,
                period TEXT NOT NULL,
                territory_name TEXT,
                physical_value REAL,
                financial_amount REAL,
                progress_pct REAL,
                status TEXT NOT NULL DEFAULT 'Reportado',
                evidence_url TEXT,
                evidence_note TEXT,
                perception_note TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(target_id, period, territory_name),
                FOREIGN KEY (target_id) REFERENCES development_plan_targets(id) ON DELETE CASCADE
            );

            -- A government report may describe a verified result without publishing the
            -- denominator required to calculate progress against a PMD indicator.  Keep
            -- those results separate from numeric progress so that a reported action is
            -- never mistaken for completion of a formal target.
            CREATE TABLE IF NOT EXISTS development_plan_reported_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id INTEGER NOT NULL,
                axis_id INTEGER,
                period TEXT NOT NULL,
                title TEXT NOT NULL,
                reported_value REAL,
                unit TEXT,
                territory_scope TEXT,
                status TEXT NOT NULL DEFAULT 'Resultado oficial reportado',
                evidence_url TEXT NOT NULL,
                evidence_note TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(plan_id, period, title),
                FOREIGN KEY (plan_id) REFERENCES development_plans(id) ON DELETE CASCADE,
                FOREIGN KEY (axis_id) REFERENCES development_plan_axes(id) ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS idx_development_plan_profile
                ON development_plans(profile_id, state, municipality);
            CREATE INDEX IF NOT EXISTS idx_development_target_axis
                ON development_plan_targets(axis_id);
            CREATE INDEX IF NOT EXISTS idx_development_result_plan
                ON development_plan_reported_results(plan_id, period);

            CREATE TABLE IF NOT EXISTS operational_annual_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                state TEXT NOT NULL,
                municipality TEXT NOT NULL,
                title TEXT NOT NULL,
                year INTEGER NOT NULL,
                total_budget REAL,
                status TEXT NOT NULL DEFAULT 'Pendiente de fuente oficial',
                source_url TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(profile_id, state, municipality, year, title),
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS operational_annual_programs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                poa_id INTEGER NOT NULL,
                axis_id INTEGER,
                name TEXT NOT NULL,
                responsible_unit TEXT,
                annual_goal REAL,
                goal_unit TEXT,
                funding_source TEXT,
                allocated_budget REAL,
                exercised_budget REAL,
                execution_pct REAL,
                status TEXT NOT NULL DEFAULT 'Pendiente de avance',
                source_url TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(poa_id, name),
                FOREIGN KEY (poa_id) REFERENCES operational_annual_plans(id) ON DELETE CASCADE,
                FOREIGN KEY (axis_id) REFERENCES development_plan_axes(id) ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS idx_operational_plan_profile
                ON operational_annual_plans(profile_id, state, municipality, year);
            CREATE INDEX IF NOT EXISTS idx_operational_program_poa
                ON operational_annual_programs(poa_id);

            CREATE TABLE IF NOT EXISTS municipal_funding_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                state TEXT NOT NULL,
                municipality TEXT NOT NULL,
                fiscal_year INTEGER NOT NULL,
                cutoff_period TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_class TEXT NOT NULL,
                amount_received REAL NOT NULL,
                source_url TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(profile_id, municipality, fiscal_year, cutoff_period, source_name),
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_funding_snapshot_profile
                ON municipal_funding_snapshots(profile_id, state, municipality, fiscal_year, cutoff_period);

            CREATE TABLE IF NOT EXISTS municipal_financial_closures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                state TEXT NOT NULL,
                municipality TEXT NOT NULL,
                fiscal_year INTEGER NOT NULL,
                approved_income_budget REAL,
                collected_income REAL,
                income_management REAL,
                taxes REAL,
                transfers_and_contributions REAL,
                accounting_expenses REAL,
                operating_expenses REAL,
                personnel_expenses REAL,
                source_url TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(profile_id, municipality, fiscal_year),
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_financial_closure_profile
                ON municipal_financial_closures(profile_id, state, municipality, fiscal_year);

            CREATE TABLE IF NOT EXISTS territorial_vote_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                state TEXT NOT NULL,
                election_year INTEGER NOT NULL,
                territorial_level TEXT NOT NULL,
                district TEXT NOT NULL DEFAULT '',
                municipality TEXT NOT NULL DEFAULT '',
                electoral_section TEXT NOT NULL DEFAULT '',
                scenario_id INTEGER,
                reference_option TEXT NOT NULL,
                historical_valid_votes INTEGER NOT NULL DEFAULT 0,
                historical_reference_votes INTEGER NOT NULL DEFAULT 0,
                target_percentage REAL NOT NULL,
                target_votes INTEGER NOT NULL DEFAULT 0,
                vote_gap INTEGER NOT NULL DEFAULT 0,
                classification TEXT NOT NULL DEFAULT 'Crecimiento',
                responsible TEXT,
                coverage_status TEXT NOT NULL DEFAULT 'Sin asignar',
                evidence_note TEXT,
                status TEXT NOT NULL DEFAULT 'Propuesta',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(profile_id, state, election_year, territorial_level, district, municipality,
                       electoral_section, reference_option),
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                FOREIGN KEY (scenario_id) REFERENCES electoral_scenarios(id) ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS idx_vote_targets_profile_territory
                ON territorial_vote_targets(profile_id, state, election_year, territorial_level, district, municipality);

            CREATE TABLE IF NOT EXISTS electoral_scenarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                state TEXT NOT NULL,
                election_year INTEGER NOT NULL,
                name TEXT NOT NULL,
                target_percentage REAL NOT NULL,
                participation_assumption REAL,
                competition_context TEXT,
                coalition_context TEXT,
                rationale TEXT,
                status TEXT NOT NULL DEFAULT 'Borrador',
                active INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(profile_id, state, election_year, name),
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS viability_competitors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                party_or_coalition TEXT,
                condition TEXT,
                territory TEXT,
                positioning_note TEXT,
                source_url TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS viability_surveys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                pollster TEXT,
                territory TEXT,
                fieldwork_date TEXT,
                sample_size INTEGER,
                methodology TEXT,
                profile_result_pct REAL,
                source_url TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS viability_structure_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                state TEXT,
                municipality TEXT,
                district TEXT,
                electoral_section TEXT,
                locality TEXT,
                responsible TEXT,
                coverage_status TEXT NOT NULL DEFAULT 'Por validar',
                evidence_note TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS viability_coalition_scenarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                scenario_name TEXT NOT NULL,
                parties TEXT,
                scope TEXT,
                status TEXT NOT NULL DEFAULT 'Hipótesis',
                notes TEXT,
                source_url TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS viability_resource_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                availability_status TEXT NOT NULL DEFAULT 'Por validar',
                amount_note TEXT,
                source_url TEXT,
                notes TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS viability_conclusions (
                profile_id INTEGER PRIMARY KEY,
                assessment_status TEXT NOT NULL DEFAULT 'En elaboración',
                strengths TEXT,
                risks TEXT,
                conditions TEXT,
                next_step TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS viability_variable_assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                variable_code TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pendiente',
                evidence_note TEXT,
                source_url TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(profile_id, variable_code),
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS viability_electoral_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                variable_code TEXT NOT NULL,
                score REAL NOT NULL CHECK(score >= 0 AND score <= 100),
                notes TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(profile_id, variable_code),
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS viability_electoral_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                variable_code TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pendiente',
                evidence_note TEXT,
                source_label TEXT,
                source_url TEXT,
                reference_date TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(profile_id, variable_code),
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );
            """
        )
        # Migración segura para bases creadas antes de agregar la liga de origen.
        reference_columns = {row[1] for row in conn.execute("PRAGMA table_info(reference_documents)")}
        if "source_url" not in reference_columns:
            conn.execute("ALTER TABLE reference_documents ADD COLUMN source_url TEXT")
        variable_assessment_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(viability_variable_assessments)")
        }
        variable_assessment_additions = {
            "metric_label": "TEXT",
            "target_value": "REAL",
            "actual_value": "REAL",
            "metric_unit": "TEXT",
        }
        for column, definition in variable_assessment_additions.items():
            if column not in variable_assessment_columns:
                conn.execute(
                    f"ALTER TABLE viability_variable_assessments ADD COLUMN {column} {definition}"
                )
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

        action_plan_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(territorial_action_plans)").fetchall()
        }
        action_plan_additions = {
            "district": "TEXT",
            "electoral_section": "TEXT",
        }
        for column, definition in action_plan_additions.items():
            if column not in action_plan_columns:
                conn.execute(f"ALTER TABLE territorial_action_plans ADD COLUMN {column} {definition}")

        target_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(territorial_vote_targets)").fetchall()
        }
        if "scenario_id" not in target_columns:
            conn.execute("ALTER TABLE territorial_vote_targets ADD COLUMN scenario_id INTEGER")

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

        operational_program_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(operational_annual_programs)").fetchall()
        }
        if "funding_source" not in operational_program_columns:
            conn.execute("ALTER TABLE operational_annual_programs ADD COLUMN funding_source TEXT")

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
