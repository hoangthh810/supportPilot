# SupportPilot local infrastructure

The Compose topology is owned by `INF-001`. `SKEL-001` adds the first support-domain
revision and a temporary Walking Skeleton profile. There is still no commerce domain,
workflow/approval persistence, queue or Redis service.

## Ownership boundaries

- `db-bootstrap` uses the PostgreSQL bootstrap credential to create extensions and reuse
  the DB-000 role/schema bootstrap.
- `migrate-support` receives only `SUPPORT_MIGRATION_DATABASE_URL` for `support_owner`.
- `migrate-commerce` receives only `COMMERCE_MIGRATION_DATABASE_URL` for `commerce_owner`.
- `backend` receives only the `support_app` runtime DSN.
- `mock-commerce` receives only the `commerce_app` runtime DSN.
- PostgreSQL and Mock-Commerce are not published to the host. Only the frontend and
  backend development ports are published.

The support Alembic branch starts with the minimal, forward-compatible domain revision
owned by `SKEL-001`. The following `DB-001A` revision upgrades those same final-named
`support.users`, `support.customers`, `support.support_tickets` and
`support.ticket_messages` tables in place. It adds the remaining identity/Ticket columns,
UUID defaults, foreign key and structural checks without dropping or recreating a skeleton
table, so existing synthetic data is preserved. The commerce Alembic branch remains empty.

## Walking Skeleton commands

Copy `.env.compose.example` to the ignored `.env.compose`, replace every placeholder,
then run:

```powershell
docker compose --env-file .env.compose config --quiet
docker compose --env-file .env.compose up --build --detach --wait
docker compose --env-file .env.compose run --rm migrate-support alembic -c infrastructure/migrations/support/alembic.ini heads
docker compose --env-file .env.compose run --rm migrate-commerce alembic -c infrastructure/migrations/commerce/alembic.ini heads
docker compose --env-file .env.compose run --rm --no-deps -e SKELETON_BASE_URL=http://backend:8000/api/v1 migrate-support python infrastructure/tests/run_skeleton_e2e.py
docker compose --env-file .env.compose down --volumes
```

The UI is available at `http://localhost:5173`. Synthetic credentials are
`customer@example.test` / `demo-password` and `agent@example.test` / `demo-password`.
The fake action never calls or writes to Mock-Commerce and its `VERIFIED` result is not
release evidence. The `v0_1` release profile rejects fake providers at startup.
