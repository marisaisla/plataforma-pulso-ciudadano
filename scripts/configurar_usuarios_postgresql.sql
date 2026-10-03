-- Ejecutar con psql como postgres en go2win_desarrollo.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL client_encoding='UTF8';
DO $$ BEGIN
  IF current_database() <> 'go2win_desarrollo' THEN
    RAISE EXCEPTION 'Conectate a go2win_desarrollo';
  END IF;
  IF to_regclass('public.field_workers') IS NULL THEN
    RAISE EXCEPTION 'Primero completa la migracion';
  END IF;
END $$;
-- Si los nombres ya existen, se detiene sin cambiar permisos existentes.
CREATE ROLE go2win_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE ROLE go2win_marisa LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE ROLE go2win_jorge LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE;
GRANT go2win_owner TO go2win_marisa, go2win_jorge;
ALTER DATABASE go2win_desarrollo OWNER TO go2win_owner;
ALTER SCHEMA public OWNER TO go2win_owner;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
DO $$ DECLARE item record; BEGIN
  FOR item IN SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relkind IN ('r','p')
  LOOP
    EXECUTE format('ALTER TABLE public.%I OWNER TO go2win_owner', item.relname);
  END LOOP;
  FOR item IN SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relkind='S'
  LOOP
    EXECUTE format('ALTER SEQUENCE public.%I OWNER TO go2win_owner', item.relname);
  END LOOP;
END $$;
ALTER ROLE go2win_marisa IN DATABASE go2win_desarrollo SET search_path=public;
ALTER ROLE go2win_jorge IN DATABASE go2win_desarrollo SET search_path=public;
-- Tambien compartir datos de objetos creados sin SET ROLE.
ALTER DEFAULT PRIVILEGES FOR ROLE go2win_marisa IN SCHEMA public GRANT ALL ON TABLES TO go2win_owner;
ALTER DEFAULT PRIVILEGES FOR ROLE go2win_jorge IN SCHEMA public GRANT ALL ON TABLES TO go2win_owner;
ALTER DEFAULT PRIVILEGES FOR ROLE go2win_marisa IN SCHEMA public GRANT ALL ON SEQUENCES TO go2win_owner;
ALTER DEFAULT PRIVILEGES FOR ROLE go2win_jorge IN SCHEMA public GRANT ALL ON SEQUENCES TO go2win_owner;
COMMIT;
SET password_encryption='scram-sha-256';
SELECT pg_reload_conf();
\echo Define la contrasena de go2win_marisa (dos veces).
\password go2win_marisa
\echo Define la contrasena de go2win_jorge (dos veces).
\password go2win_jorge
\echo Cuentas preparadas. Para crear objetos de propiedad compartida usa SET ROLE go2win_owner.
