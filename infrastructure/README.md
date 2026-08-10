# SupportPilot local infrastructure

The Compose topology is owned by `INF-001`. `SKEL-001` adds the first support-domain
revision and a temporary Walking Skeleton profile. `DB-002A` adds only the UC-01
commerce persistence contract; there is still no commerce business endpoint,
workflow/approval persistence, queue or Redis service.

## Ownership boundaries

- `db-bootstrap` uses the PostgreSQL bootstrap credential to create extensions and reuse
  the DB-000 role/schema bootstrap.
- `migrate-support` receives only `SUPPORT_MIGRATION_DATABASE_URL` for `support_owner`.
- `migrate-commerce` receives only `COMMERCE_MIGRATION_DATABASE_URL` for `commerce_owner`.
- `backend` receives only the `support_app` runtime DSN and internal service token.
- `mock-commerce` receives only the `commerce_app` runtime DSN and internal service token.
- PostgreSQL and Mock-Commerce are not published to the host. Only the frontend and
  backend development ports are published.

The support Alembic branch starts with the minimal, forward-compatible domain revision
owned by `SKEL-001`. The following `DB-001A` revision upgrades those same final-named
`support.users`, `support.customers`, `support.support_tickets` and
`support.ticket_messages` tables in place. It adds the remaining identity/Ticket columns,
UUID defaults, foreign key and structural checks without dropping or recreating a skeleton
table, so existing synthetic data is preserved. The commerce Alembic branch begins with
`0001_db002a_commerce`, owned by `DB-002A`, and creates exactly
`customers/products/orders/order_items/payments/idempotency_records/audit_logs` plus the
documented commerce enums, constraints and indexes. It contains no seed data or UC-02+
table. `commerce_app` has no support-schema privilege, while commerce idempotency and
audit rows are append-only through runtime grants.

The isolated DB-002A integration harness is
`infrastructure/tests/run_db002a_integration.py`. It requires only the commerce owner
migration DSN plus `commerce_app` and `support_app` runtime DSNs, performs a
downgrade/upgrade round trip, and validates the exact physical contract, grants,
constraints, optimistic versions and transaction rollback. Run it only against the
disposable Compose test database because it intentionally downgrades the commerce branch
to `base` during verification.

## Synthetic UC-01 seed profile

`SEED-001` provides the versioned `payment-mismatch-v01` profile. The Compose
`seed-profile` job connects as `support_app` and `commerce_app` through separate runtime
connections, never performs a cross-schema query, and creates no table. It upserts fixed
synthetic identities and commerce rows, while policy, conservative-path scenarios and the
locked 15-calibration/10-holdout golden dataset remain versioned fixtures for their owning
later tasks.

Run the seed twice to verify normal idempotent operation, then run the checksum and
duplicate smoke harness:

```powershell
docker compose --env-file .env.compose run --rm seed-profile
docker compose --env-file .env.compose run --rm seed-profile
docker compose --env-file .env.compose run --rm seed-profile python infrastructure/tests/run_seed001_integration.py
```

The output contains only profile/checksum/count metadata. Database URLs, password hashes,
internal service tokens and customer message content are never printed.

## Internal Mock-Commerce authentication

`MOCK-AUTH-001` runs Mock-Commerce as a private FastAPI service. Every
`/internal/v1/*` request must provide exact `Authorization: Bearer
<INTERNAL_SERVICE_TOKEN>` before routing, body parsing or ownership lookup. Missing or
malformed credentials return `401 INTERNAL_UNAUTHENTICATED`; a wrong token or user JWT
returns `403 INTERNAL_FORBIDDEN`. The SupportPilot HTTP boundary owns header injection,
and the same internal token is explicitly rejected on public `/api/v1/*` routes.

The container smoke harness verifies the matrix without printing the credential:

```powershell
docker compose --env-file .env.compose run --rm --no-deps -e MOCK_COMMERCE_SMOKE_BASE_URL=http://mock-commerce:8080 backend python infrastructure/tests/run_mock_auth_smoke.py
```

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

## Local authentication

`AUTH-001` provides `POST /api/v1/auth/login` and `GET /api/v1/auth/me` with a
15-minute HS256 access token. `JWT_SIGNING_KEY` must contain at least 32 bytes. There is
no refresh-token endpoint in v0.1, and protected requests reload the current user and
customer scope from PostgreSQL so disabling an account invalidates an existing token.

The v0.1 login limiter permits 10 attempts per 60-second window for each hashed
client-IP and normalized-email pair. It is process-local for the single-backend local
topology, never retains the raw key inputs, and emits `X-RateLimit-Limit`,
`X-RateLimit-Remaining`, `X-RateLimit-Reset` and, when limited, `Retry-After`. A limited
request returns the generic `INVALID_CREDENTIALS` body to avoid account enumeration.
