# SupportPilot Phase 1 infrastructure

This directory implements only the `INF-001` foundation topology. It contains no domain
table, enum, seed, business API, queue, or Redis service.

## Ownership boundaries

- `db-bootstrap` uses the PostgreSQL bootstrap credential to create extensions and reuse
  the DB-000 role/schema bootstrap.
- `migrate-support` receives only `SUPPORT_MIGRATION_DATABASE_URL` for `support_owner`.
- `migrate-commerce` receives only `COMMERCE_MIGRATION_DATABASE_URL` for `commerce_owner`.
- `backend` receives only the `support_app` runtime DSN.
- `mock-commerce` receives only the `commerce_app` runtime DSN.
- PostgreSQL and Mock-Commerce are not published to the host. Only the frontend and
  backend development ports are published.

Both Alembic version directories are intentionally empty. `SKEL-001` owns the first
domain migration.

## Phase 1 commands

Copy `.env.compose.example` to the ignored `.env.compose`, replace every placeholder,
then run:

```powershell
docker compose --env-file .env.compose config --quiet
docker compose --env-file .env.compose up --build --detach --wait
docker compose --env-file .env.compose run --rm migrate-support alembic -c infrastructure/migrations/support/alembic.ini heads
docker compose --env-file .env.compose run --rm migrate-commerce alembic -c infrastructure/migrations/commerce/alembic.ini heads
docker compose --env-file .env.compose run --rm migrate-support python infrastructure/tests/assert_phase1_catalog.py
docker compose --env-file .env.compose down --volumes
```
