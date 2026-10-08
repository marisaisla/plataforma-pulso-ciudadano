-- Ejecutar con psql -U postgres -d go2win_desarrollo -W -f este_archivo.
-- Las contrasenas se solicitan de forma interactiva, nunca se guardan aqui.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL client_encoding='UTF8';
SET LOCAL password_encryption='scram-sha-256';
DO $$ BEGIN
  IF current_database() <> 'go2win_desarrollo' THEN
    RAISE EXCEPTION 'Conectate a go2win_desarrollo';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='go2win_owner') THEN
    RAISE EXCEPTION 'Falta el rol compartido go2win_owner';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='go2win_mau') THEN
    RAISE EXCEPTION 'go2win_mau ya existe; no se modifico su cuenta';
  END IF;
END $$;
CREATE ROLE go2win_mau LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE;
GRANT go2win_owner TO go2win_mau;
ALTER ROLE go2win_mau IN DATABASE go2win_desarrollo SET search_path=public;
ALTER DEFAULT PRIVILEGES FOR ROLE go2win_mau IN SCHEMA public
  GRANT ALL ON TABLES TO go2win_owner;
ALTER DEFAULT PRIVILEGES FOR ROLE go2win_mau IN SCHEMA public
  GRANT ALL ON SEQUENCES TO go2win_owner;
\echo Introduce la nueva contrasena de Mau dos veces. No se mostrara en pantalla.
\password go2win_mau
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_authid WHERE rolname='go2win_mau' AND rolpassword IS NOT NULL) THEN
    RAISE EXCEPTION 'No se definio una contrasena; se cancela la creacion';
  END IF;
END $$;
COMMIT;
SELECT rolname, rolcanlogin, pg_has_role('go2win_mau','go2win_owner','MEMBER') AS miembro_desarrollo
FROM pg_roles WHERE rolname='go2win_mau';
\echo Cuenta creada. Para nuevas tablas de propiedad compartida usa SET ROLE go2win_owner.
\echo El acceso desde otra computadora requiere autorizar su IP en pg_hba.conf y el firewall.
