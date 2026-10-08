-- Aplicar una vez al PostgreSQL compartido antes de reiniciar Go2Win y el bot.
BEGIN;
CREATE TABLE IF NOT EXISTS field_report_photos (
    report_id BIGINT PRIMARY KEY REFERENCES field_reports(id),
    file_id TEXT NOT NULL,
    file_unique_id TEXT NOT NULL,
    content_base64 TEXT NOT NULL
);
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='go2win_owner') THEN
        ALTER TABLE field_report_photos OWNER TO go2win_owner;
    END IF;
END $$;
COMMIT;
