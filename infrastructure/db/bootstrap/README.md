# DB-000 bootstrap harness

This directory owns only the one-shot Phase-1 PostgreSQL role/schema/grant bootstrap and its isolated integration harness. It does not create extensions, Alembic state, domain enums, application tables or seed data.

Run the clean integration gate from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File infrastructure/db/bootstrap/run-integration.ps1
```

The runner generates process-local test passwords when values are absent, validates the Compose model without printing resolved configuration, bootstraps twice, runs the grant matrix checks and removes the isolated database volume. Real passwords and the bootstrap admin DSN must never be committed or printed.

