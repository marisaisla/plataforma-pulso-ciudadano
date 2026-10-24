-- Extensión de procedencia heredada. No escribe en public ni altera sus tablas.
BEGIN;
ALTER TABLE electoral_history.geographies ALTER COLUMN valid_on DROP NOT NULL;
ALTER TABLE electoral_history.elections ALTER COLUMN election_date DROP NOT NULL;
ALTER TABLE electoral_history.elections ADD COLUMN IF NOT EXISTS legacy_election_year INTEGER;
ALTER TABLE electoral_history.elections ADD COLUMN IF NOT EXISTS legacy_note TEXT;
ALTER TABLE electoral_history.elections DROP CONSTRAINT IF EXISTS elections_process_check;
ALTER TABLE electoral_history.elections ADD CONSTRAINT elections_process_check CHECK(process IN ('ordinary','extraordinary','unknown'));
ALTER TABLE electoral_history.elections DROP CONSTRAINT IF EXISTS elections_principle_check;
ALTER TABLE electoral_history.elections ADD CONSTRAINT elections_principle_check CHECK(principle IN ('MR','RP','NA','unknown'));
ALTER TABLE electoral_history.imports DROP CONSTRAINT IF EXISTS imports_vote_basis_check;
ALTER TABLE electoral_history.imports ADD CONSTRAINT imports_vote_basis_check CHECK(vote_basis IN ('party','candidacy','ballot_combination','legacy_reported'));
CREATE TABLE IF NOT EXISTS electoral_history.legacy_runs (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 snapshot_sha256 TEXT NOT NULL UNIQUE, snapshot_path TEXT NOT NULL,
 created_by BIGINT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 report JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS electoral_history.legacy_records (
 run_id BIGINT NOT NULL REFERENCES electoral_history.legacy_runs(id),
 source_table TEXT NOT NULL, source_id BIGINT NOT NULL,
 row_sha256 TEXT NOT NULL, original_row JSONB NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('normalized','pending')),
 issues JSONB NOT NULL, import_id BIGINT REFERENCES electoral_history.imports(id),
 unit_code TEXT, PRIMARY KEY(run_id,source_table,source_id)
);
CREATE INDEX IF NOT EXISTS legacy_records_import_idx ON electoral_history.legacy_records(import_id,unit_code);
CREATE INDEX IF NOT EXISTS legacy_records_pending_idx ON electoral_history.legacy_records(run_id,status,source_table,source_id);
-- Las cargas pendientes de acreditación nunca entran a la vista de hechos oficiales.
CREATE OR REPLACE VIEW electoral_history.fact_votes AS
 SELECT v.import_id,i.election_id,e.election_date,e.jurisdiction,e.office,e.principle,e.process,
 i.geography_id,g.version AS geography_version,i.level,i.vote_basis,
 v.unit_code,u.name AS unit_name,u.entity_code,u.municipality_code,
 u.federal_district_code,u.local_district_code,v.option_code,v.option_name,v.votes,
 i.source,i.content_sha256,i.created_at
 FROM electoral_history.votes v
 JOIN electoral_history.imports i ON i.id=v.import_id
 JOIN electoral_history.elections e ON e.id=i.election_id
 JOIN electoral_history.geographies g ON g.id=i.geography_id
 JOIN electoral_history.units u ON u.geography_id=i.geography_id AND u.level=i.level AND u.code=v.unit_code
 WHERE i.vote_basis <> 'legacy_reported' AND i.source->>'stage' <> 'legacy_snapshot';
COMMIT;
