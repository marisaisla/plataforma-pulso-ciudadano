-- Fase 1. Migración aditiva; ejecutar explícitamente, nunca al arrancar la API.
BEGIN;
CREATE SCHEMA IF NOT EXISTS electoral_history;
CREATE TABLE IF NOT EXISTS electoral_history.geographies (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 version TEXT NOT NULL UNIQUE, valid_on DATE NOT NULL,
 source JSONB NOT NULL, content_sha256 TEXT NOT NULL, csv_content TEXT NOT NULL,
 created_by BIGINT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS electoral_history.units (
 geography_id BIGINT NOT NULL REFERENCES electoral_history.geographies(id),
 level TEXT NOT NULL CHECK(level IN ('entity','municipality','federal_district','local_district','section')),
 code TEXT NOT NULL, name TEXT NOT NULL, entity_code TEXT NOT NULL,
 municipality_code TEXT, federal_district_code TEXT, local_district_code TEXT,
 PRIMARY KEY (geography_id,level,code)
);
CREATE INDEX IF NOT EXISTS history_units_entity_idx ON electoral_history.units(geography_id,entity_code,level,code);
CREATE TABLE IF NOT EXISTS electoral_history.elections (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 code TEXT NOT NULL UNIQUE, name TEXT NOT NULL, election_date DATE NOT NULL,
 jurisdiction TEXT NOT NULL CHECK(jurisdiction IN ('federal','local')),
 office TEXT NOT NULL, principle TEXT NOT NULL CHECK(principle IN ('MR','RP','NA')),
 process TEXT NOT NULL CHECK(process IN ('ordinary','extraordinary')),
 entity_code TEXT, created_by BIGINT NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 CHECK(jurisdiction <> 'local' OR entity_code IS NOT NULL)
);
CREATE TABLE IF NOT EXISTS electoral_history.imports (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 election_id BIGINT NOT NULL REFERENCES electoral_history.elections(id),
 geography_id BIGINT NOT NULL REFERENCES electoral_history.geographies(id),
 level TEXT NOT NULL CHECK(level IN ('entity','municipality','federal_district','local_district','section')),
 vote_basis TEXT NOT NULL CHECK(vote_basis IN ('party','candidacy','ballot_combination')),
 source JSONB NOT NULL, content_sha256 TEXT NOT NULL, fingerprint TEXT NOT NULL UNIQUE,
 csv_content TEXT NOT NULL, supersedes_id BIGINT REFERENCES electoral_history.imports(id),
 coverage_note TEXT NOT NULL, created_by BIGINT NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS electoral_history.results (
 import_id BIGINT NOT NULL REFERENCES electoral_history.imports(id),
 unit_code TEXT NOT NULL, nominal_list BIGINT CHECK(nominal_list>=0),
 total_votes BIGINT CHECK(total_votes>=0), null_votes BIGINT CHECK(null_votes>=0),
 unregistered_votes BIGINT CHECK(unregistered_votes>=0),
 PRIMARY KEY(import_id,unit_code)
);
CREATE TABLE IF NOT EXISTS electoral_history.votes (
 import_id BIGINT NOT NULL, unit_code TEXT NOT NULL,
 option_code TEXT NOT NULL, option_name TEXT NOT NULL, votes BIGINT CHECK(votes>=0),
 PRIMARY KEY(import_id,unit_code,option_code),
 FOREIGN KEY(import_id,unit_code) REFERENCES electoral_history.results(import_id,unit_code)
);
-- Grano: lote + unidad + opción. No sumar entre lotes/niveles/bases sin conciliación.
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
