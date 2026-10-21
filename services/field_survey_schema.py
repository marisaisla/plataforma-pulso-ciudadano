"""Esquema SQLite para inicialización local; PostgreSQL usa migración explícita."""
SCHEMA = [
    '''CREATE TABLE IF NOT EXISTS field_questionnaires (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL REFERENCES territorial_action_plans(id),
        title TEXT NOT NULL, description TEXT NOT NULL, definition TEXT NOT NULL,
        mode TEXT NOT NULL CHECK(mode IN ('single','multiple')),
        status TEXT NOT NULL CHECK(status IN ('draft','published')),
        created_by INTEGER NOT NULL REFERENCES field_workers(id),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''',
    '''CREATE TABLE IF NOT EXISTS field_task_surveys (
        task_id INTEGER PRIMARY KEY REFERENCES territorial_action_plans(id),
        questionnaire_id INTEGER NOT NULL REFERENCES field_questionnaires(id),
        generation TEXT NOT NULL, target INTEGER NOT NULL CHECK(target > 0))''',
    '''CREATE TABLE IF NOT EXISTS field_survey_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL REFERENCES territorial_action_plans(id),
        questionnaire_id INTEGER NOT NULL REFERENCES field_questionnaires(id),
        worker_id INTEGER NOT NULL REFERENCES field_workers(id),
        assignment_generation TEXT NOT NULL, survey_generation TEXT NOT NULL,
        submission_key TEXT NOT NULL UNIQUE, answers TEXT NOT NULL,
        profile_id INTEGER NOT NULL REFERENCES profiles(id), state TEXT NOT NULL, municipality TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''',
    'CREATE INDEX IF NOT EXISTS field_survey_response_task_idx ON field_survey_responses(task_id, questionnaire_id)',
]


def initialize_surveys(conn):
    for sql in SCHEMA:
        conn.execute(sql)
