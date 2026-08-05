\set ON_ERROR_STOP on
\set QUIET on

DO $assertions$
DECLARE
    role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'support_owner', 'commerce_owner', 'support_app', 'commerce_app'
    ]
    LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM pg_roles AS candidate
            WHERE candidate.rolname = role_name
              AND rolcanlogin
              AND NOT rolsuper
              AND NOT rolcreatedb
              AND NOT rolcreaterole
              AND NOT rolinherit
              AND NOT rolreplication
              AND NOT rolbypassrls
        ) THEN
            RAISE EXCEPTION 'DB-000 role attributes are invalid for %', role_name;
        END IF;
    END LOOP;

    IF (SELECT nspowner::regrole::text FROM pg_namespace WHERE nspname = 'support')
        IS DISTINCT FROM 'support_owner' THEN
        RAISE EXCEPTION 'support schema owner is invalid';
    END IF;
    IF (SELECT nspowner::regrole::text FROM pg_namespace WHERE nspname = 'commerce')
        IS DISTINCT FROM 'commerce_owner' THEN
        RAISE EXCEPTION 'commerce schema owner is invalid';
    END IF;

    IF NOT has_schema_privilege('support_app', 'support', 'USAGE')
       OR has_schema_privilege('support_app', 'support', 'CREATE')
       OR has_schema_privilege('support_app', 'commerce', 'USAGE')
       OR has_schema_privilege('support_app', 'commerce', 'CREATE') THEN
        RAISE EXCEPTION 'support_app schema grant matrix is invalid';
    END IF;
    IF NOT has_schema_privilege('commerce_app', 'commerce', 'USAGE')
       OR has_schema_privilege('commerce_app', 'commerce', 'CREATE')
       OR has_schema_privilege('commerce_app', 'support', 'USAGE')
       OR has_schema_privilege('commerce_app', 'support', 'CREATE') THEN
        RAISE EXCEPTION 'commerce_app schema grant matrix is invalid';
    END IF;
    IF has_schema_privilege('support_owner', 'commerce', 'USAGE')
       OR has_schema_privilege('commerce_owner', 'support', 'USAGE') THEN
        RAISE EXCEPTION 'owner roles have cross-schema access';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM pg_namespace AS namespace
        CROSS JOIN LATERAL aclexplode(namespace.nspacl) AS privilege
        WHERE namespace.nspname IN ('support', 'commerce')
          AND privilege.grantee = 0
          AND privilege.privilege_type IN ('USAGE', 'CREATE')
    ) THEN
        RAISE EXCEPTION 'PUBLIC has application-schema access';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_auth_members AS membership
        JOIN pg_roles AS granted ON granted.oid = membership.roleid
        JOIN pg_roles AS member ON member.oid = membership.member
        WHERE granted.rolname IN ('support_owner', 'commerce_owner', 'support_app', 'commerce_app')
           OR member.rolname IN ('support_owner', 'commerce_owner', 'support_app', 'commerce_app')
    ) THEN
        RAISE EXCEPTION 'DB-000 roles must not share role membership';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_class AS relation
        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname IN ('support', 'commerce')
          AND relation.relkind IN ('r', 'p', 'S', 'v', 'm', 'f')
    ) THEN
        RAISE EXCEPTION 'Phase-1 catalog contains an application relation';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM pg_type AS type
        JOIN pg_namespace AS namespace ON namespace.oid = type.typnamespace
        WHERE namespace.nspname IN ('support', 'commerce')
          AND type.typtype = 'e'
    ) THEN
        RAISE EXCEPTION 'Phase-1 catalog contains a domain enum';
    END IF;
END
$assertions$;
