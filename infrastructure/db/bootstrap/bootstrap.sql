\set ON_ERROR_STOP on
\set QUIET on

DO $db000$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'support_owner') THEN
        CREATE ROLE support_owner LOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'commerce_owner') THEN
        CREATE ROLE commerce_owner LOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'support_app') THEN
        CREATE ROLE support_app LOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'commerce_app') THEN
        CREATE ROLE commerce_app LOGIN;
    END IF;
END
$db000$;

ALTER ROLE support_owner
    WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
ALTER ROLE commerce_owner
    WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
ALTER ROLE support_app
    WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
ALTER ROLE commerce_app
    WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;

\getenv support_owner_password SUPPORT_OWNER_PASSWORD
\getenv commerce_owner_password COMMERCE_OWNER_PASSWORD
\getenv support_app_password SUPPORT_APP_PASSWORD
\getenv commerce_app_password COMMERCE_APP_PASSWORD
SELECT format('ALTER ROLE support_owner PASSWORD %L', :'support_owner_password') \gexec
SELECT format('ALTER ROLE commerce_owner PASSWORD %L', :'commerce_owner_password') \gexec
SELECT format('ALTER ROLE support_app PASSWORD %L', :'support_app_password') \gexec
SELECT format('ALTER ROLE commerce_app PASSWORD %L', :'commerce_app_password') \gexec
\unset support_owner_password
\unset commerce_owner_password
\unset support_app_password
\unset commerce_app_password

SELECT format('REVOKE %I FROM %I', granted.rolname, member.rolname)
FROM pg_auth_members AS membership
JOIN pg_roles AS granted ON granted.oid = membership.roleid
JOIN pg_roles AS member ON member.oid = membership.member
WHERE member.rolname IN ('support_owner', 'commerce_owner', 'support_app', 'commerce_app')
\gexec

SELECT format('REVOKE %I FROM %I', granted.rolname, member.rolname)
FROM pg_auth_members AS membership
JOIN pg_roles AS granted ON granted.oid = membership.roleid
JOIN pg_roles AS member ON member.oid = membership.member
WHERE granted.rolname IN ('support_owner', 'commerce_owner', 'support_app', 'commerce_app')
\gexec

CREATE SCHEMA IF NOT EXISTS support AUTHORIZATION support_owner;
ALTER SCHEMA support OWNER TO support_owner;
CREATE SCHEMA IF NOT EXISTS commerce AUTHORIZATION commerce_owner;
ALTER SCHEMA commerce OWNER TO commerce_owner;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA support FROM PUBLIC;
REVOKE ALL ON SCHEMA commerce FROM PUBLIC;

REVOKE ALL ON SCHEMA support FROM support_app, commerce_owner, commerce_app;
REVOKE ALL ON SCHEMA commerce FROM commerce_app, support_owner, support_app;
GRANT USAGE ON SCHEMA support TO support_app;
GRANT USAGE ON SCHEMA commerce TO commerce_app;

ALTER DEFAULT PRIVILEGES FOR ROLE support_owner IN SCHEMA support
    REVOKE ALL ON TABLES FROM PUBLIC, support_app, commerce_owner, commerce_app;
ALTER DEFAULT PRIVILEGES FOR ROLE support_owner IN SCHEMA support
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO support_app;
ALTER DEFAULT PRIVILEGES FOR ROLE support_owner IN SCHEMA support
    REVOKE ALL ON SEQUENCES FROM PUBLIC, support_app, commerce_owner, commerce_app;
ALTER DEFAULT PRIVILEGES FOR ROLE support_owner IN SCHEMA support
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO support_app;
ALTER DEFAULT PRIVILEGES FOR ROLE support_owner IN SCHEMA support
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC, support_app, commerce_owner, commerce_app;
ALTER DEFAULT PRIVILEGES FOR ROLE support_owner IN SCHEMA support
    REVOKE USAGE ON TYPES FROM PUBLIC, support_app, commerce_owner, commerce_app;
ALTER DEFAULT PRIVILEGES FOR ROLE support_owner IN SCHEMA support
    GRANT USAGE ON TYPES TO support_app;

ALTER DEFAULT PRIVILEGES FOR ROLE commerce_owner IN SCHEMA commerce
    REVOKE ALL ON TABLES FROM PUBLIC, commerce_app, support_owner, support_app;
ALTER DEFAULT PRIVILEGES FOR ROLE commerce_owner IN SCHEMA commerce
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO commerce_app;
ALTER DEFAULT PRIVILEGES FOR ROLE commerce_owner IN SCHEMA commerce
    REVOKE ALL ON SEQUENCES FROM PUBLIC, commerce_app, support_owner, support_app;
ALTER DEFAULT PRIVILEGES FOR ROLE commerce_owner IN SCHEMA commerce
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO commerce_app;
ALTER DEFAULT PRIVILEGES FOR ROLE commerce_owner IN SCHEMA commerce
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC, commerce_app, support_owner, support_app;
ALTER DEFAULT PRIVILEGES FOR ROLE commerce_owner IN SCHEMA commerce
    REVOKE USAGE ON TYPES FROM PUBLIC, commerce_app, support_owner, support_app;
ALTER DEFAULT PRIVILEGES FOR ROLE commerce_owner IN SCHEMA commerce
    GRANT USAGE ON TYPES TO commerce_app;

