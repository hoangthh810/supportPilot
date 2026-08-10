# SupportPilot — Implementation Task Registry

> Trạng thái: backlog dẫn xuất từ [PLAN.md](./PLAN.md). Tài liệu này không tự bắt đầu task. Mọi task ban đầu là `TODO`, owner là `Unassigned`.

## 1. Status workflow

Allowed task statuses:

```text
TODO
IN_PROGRESS
BLOCKED
IN_REVIEW
DONE
```

Status của task không đồng nghĩa runtime status của Ticket/Agent Run/Approval/Action Execution. Chỉ chuyển task khỏi `TODO` khi người dùng yêu cầu bắt đầu.

## 2. Milestone labels

| Label | Meaning |
|---|---|
| `v0.1-foundation` | Design/foundation/core work enabling the vertical slice. |
| `v0.1-skeleton` | Temporary Walking Skeleton only. |
| `v0.1-alpha` | Real approve/reject/expiry/idempotent action/verification happy path. |
| `v0.1-beta` | Reviewer edit/material reapproval and complete review UX. |
| `final-v0.1` | Security/evaluation/CI/release requirement. |
| `v1.0` | Deferred; no implementation task in this registry. |
| `post-mvp` | Deferred; no implementation task in this registry. |

UC-02–UC-07 are intentionally absent from the v0.1 task records.

## 3. Planned command catalog

Các command là quality gates dự kiến, chưa được chạy ở bước documentation. `FND-001`, `FND-002` và `INF-001` phải freeze exact config/script paths trước task phụ thuộc; đổi path không được đổi acceptance semantics.

| Alias | Planned command/gate |
|---|---|
| `CMD-DOC` | `rg -n "^## Source and traceability$" docs` plus Markdown link/terminology review |
| `CMD-BE-QUALITY` | `ruff check backend`; `mypy backend`; `pytest` relevant backend paths |
| `CMD-FE-QUALITY` | `npm --prefix frontend run typecheck`; `npm --prefix frontend run test`; `npm --prefix frontend run build` |
| `CMD-SUPPORT-MIGRATE` | Alembic support upgrade/downgrade check using only `SUPPORT_MIGRATION_DATABASE_URL` |
| `CMD-COMMERCE-MIGRATE` | Alembic commerce upgrade/downgrade check using only `COMMERCE_MIGRATION_DATABASE_URL` |
| `CMD-COMPOSE` | `docker compose config`; clean `docker compose up --build`; health/smoke checks |
| `CMD-CONTRACT` | Backend API/internal HTTP contract test subset |
| `CMD-E2E` | `npx playwright test` plus API E2E subset |
| `CMD-SECURITY` | Grant/import-boundary/customer-isolation/injection/redaction test subsets |
| `CMD-EVAL` | Versioned evaluation command created by `EVAL-001`; calibration and holdout reports separately |
| `CMD-CI` | CI dry run covering all required gates |

## Agent context-loading policy

### Khi bắt đầu một task

Coding agent phải đọc theo thứ tự:

1. Section của chính task đó trong `docs/TASKS.md`.
2. Các task nằm trong `Dependencies`, nhưng chỉ đọc completion report và các phần liên quan trực tiếp: contract/schema impact, deviations, remaining risks và output/interface mà task hiện tại sử dụng.
3. Danh sách `Required reading` của task.
4. Các file code hiện có nằm trong `Modules/files` của task.

### Không mặc định đọc

Không mặc định đọc lại:

- Toàn bộ `docs/PLAN.md`.
- Toàn bộ `docs/TASKS.md`.
- Toàn bộ chín file tài liệu.
- Tài liệu của phase chưa liên quan.
- Source code ngoài module boundary của task.

### Chỉ đọc thêm khi

Agent chỉ đọc tài liệu ngoài `Required reading` khi một trong các điều kiện sau đúng:

- Required reading dẫn chiếu tới section khác.
- Có contract hoặc terminology không rõ.
- Phát hiện mâu thuẫn giữa code và tài liệu.
- Cần xác minh invariant ảnh hưởng trực tiếp tới task.
- Task thay đổi schema, API, workflow hoặc security boundary liên quan.

Khi đọc thêm, completion report phải ghi:

```text
Additional context loaded:
- file
- section
- reason
```

### Khi nào phải đọc PLAN

Chỉ đọc section cụ thể của `docs/PLAN.md` khi:

- Các tài liệu chuyên môn mâu thuẫn nhau.
- Một quyết định không có trong tài liệu chuyên môn.
- Task đề xuất thay đổi contract hoặc architecture.
- Bắt đầu phase mới và roadmap/task yêu cầu phase review.
- `Required reading` dẫn trực tiếp tới một section PLAN.

Không đọc toàn bộ PLAN nếu chỉ cần một section. `DOC-001` là ngoại lệ duy nhất được mặc định đọc toàn bộ PLAN và toàn bộ bộ tài liệu để đồng bộ.

### Conflict priority

```text
docs/PLAN.md
→ tài liệu chuyên môn tương ứng
→ docs/TASKS.md
→ implementation code
→ comments/examples
```

Nếu phát hiện mâu thuẫn:

- Không tự chọn phương án.
- Không tự sửa PLAN.
- Dừng phần bị ảnh hưởng và báo chính xác file/section.
- Các phần độc lập khác của task vẫn có thể tiếp tục nếu an toàn.

## 4. Phase 0 — Design and contracts

### DOC-001 — Synchronize approved specifications and ADR references

- **Metadata:** Phase 0; size `S`; milestone `v0.1-foundation`; status `DONE`; Owner: Unassigned.
- **Goal:** Produce mutually consistent PLAN-derived docs without changing approved decisions.
- **In scope:** Nine docs, traceability sections, internal links, terminology/contract consistency matrix and ADR references.
- **Out of scope:** Implementation, migration, dependency install, PLAN semantic change or new ADR decision.
- **Modules/files:** `docs/PROJECT_SPEC.md`, `ARCHITECTURE.md`, `DATABASE_DESIGN.md`, `API_CONTRACT.md`, `AGENT_WORKFLOW.md`, `RAG_DESIGN.md`, `SECURITY.md`, `ROADMAP.md`, `TASKS.md`.
- **Input → output:** Approved `PLAN.md` → reviewable topic documents with no contradiction.
- **Dependencies:** None.
- **Required reading:**
  - `docs/PLAN.md` — toàn bộ; nguồn quyết định chính thức cho task đồng bộ tài liệu.
  - `docs/PROJECT_SPEC.md` — toàn bộ, gồm `Source and traceability`.
  - `docs/ARCHITECTURE.md` — toàn bộ, gồm §23 `ADR register` và `Source and traceability`.
  - `docs/DATABASE_DESIGN.md` — toàn bộ, gồm physical contracts và `Source and traceability`.
  - `docs/API_CONTRACT.md` — toàn bộ, gồm endpoint/error contracts và `Source and traceability`.
  - `docs/AGENT_WORKFLOW.md` — toàn bộ, gồm state machines và `Source and traceability`.
  - `docs/RAG_DESIGN.md` — toàn bộ, gồm retrieval/evaluation contracts và `Source and traceability`.
  - `docs/SECURITY.md` — toàn bộ, gồm security test matrix và `Source and traceability`.
  - `docs/ROADMAP.md` — toàn bộ, gồm phase/release gates và `Source and traceability`.
  - `docs/TASKS.md` — toàn bộ registry, context policy, completion reports và traceability.
- **Acceptance criteria:** All nine files exist; each has `Source and traceability`; links resolve; the 15 required consistency checks pass or an unresolved PLAN contradiction is reported.
- **Required tests/commands:** `CMD-DOC`; cross-file grep for statuses/endpoints/24h/60s/5s/12s/E5/RRF/no-CoT.
- **Security:** Do not copy secrets/real data; preserve no-CoT and scope prohibitions.
- **Risks:** Rule drift, duplicated normative content, accidentally inventing unspecified physical contracts.
- **Review checklist:** [ ] PLAN mapping [ ] links [ ] terminology [ ] no semantic change [ ] unresolved items reported.
- **Completion report:** Recorded below using the §16 template; `Task ID: DOC-001`.

#### DOC-001 completion report

- Task ID: `DOC-001`
- Final status: `DONE`
- Owner: Unassigned
- Goal achieved: Nine PLAN-derived documents were reviewed as one contract set, satisfy the DOC-001 acceptance criteria and were approved by the reviewer.
- Files/modules changed: `docs/TASKS.md` task status and this completion report. Reviewed set: `PROJECT_SPEC.md`, `ARCHITECTURE.md`, `DATABASE_DESIGN.md`, `API_CONTRACT.md`, `AGENT_WORKFLOW.md`, `RAG_DESIGN.md`, `SECURITY.md`, `ROADMAP.md`, `TASKS.md`.
- Contract/schema impact: None; this task validated the approved documentation contracts and introduced no new technical decision.
- Migrations created (if authorized): None.
- Tests added/updated: None; documentation-only static checks were executed.
- Required context loaded: Entire `docs/PLAN.md` and all nine PLAN-derived topic documents listed in `Required reading`, as permitted only for `DOC-001`.
- Additional context loaded and reasons: None.
- Dependency completion reports reviewed: None; `DOC-001` has no dependencies.
- Context intentionally not loaded: Implementation source code, dependency modules and documentation outside the approved DOC-001 set.
- Commands run and results: `CMD-DOC` traceability grep PASS (9/9); local Markdown link review PASS; terminology/status/endpoint/24h/60s/5s/12s/E5/RRF/no-CoT grep PASS; file/duplicate/ADR review PASS; stale-marker scan PASS; required consistency checks PASS (15/15).
- Security checks: No secret or real-data material added; internal-token isolation, schema/customer boundary, attachment rejection and no-CoT documentation checks PASS.
- Acceptance criteria evidence: Nine target files exist exactly once; all contain `Source and traceability`; local links resolve; ADR-001–ADR-008 map to PLAN; 15 consistency checks pass; no unresolved contradiction was found in PLAN.
- Risks/limitations remaining: Checks are documentation/static-contract checks, not implementation tests; implementation behavior remains outside DOC-001 scope.
- Deviations from PLAN: None.
- Follow-up tasks unblocked: `FND-001`; it was not started and remains `TODO`.

## 5. Phase 1 — Foundation

### FND-001 — FastAPI foundation shell

- **Metadata:** Phase 1; size `M`; milestone `v0.1-foundation`; status `DONE`; Owner: Unassigned.
- **Goal:** Establish FastAPI config/error/DI/quality shell and fail-fast environment validation.
- **In scope:** Application factory, config contract, error/correlation envelope, health shell, dependency direction and backend quality commands.
- **Out of scope:** Domain services, Ticket/Agent/RAG/approval logic or provider calls.
- **Modules/files:** `backend/apps/support_api/core`, public API shell, backend test/config files.
- **Input → output:** Environment/API conventions → bootable backend shell with typed errors and health response.
- **Dependencies:** `DOC-001`.
- **Required reading:**
  - `docs/ARCHITECTURE.md` — §4 `Modular monolith boundaries`; §6 `FastAPI application boundary`; §13 `Import dependency rules`; §18 `Runtime containers`.
  - `docs/API_CONTRACT.md` — §1 `API conventions`; §3 `Headers`; §4 `Error envelope`; §9.1 `Correlation envelope`.
  - `docs/SECURITY.md` — §17 `Secret management`; §18 `Log redaction and no-CoT`; §24 `Explicitly prohibited capabilities`.
- **Acceptance criteria:** Missing required config fails safely; correlation/error conventions match API docs; no secrets logged; import boundaries prepared.
- **Required tests/commands:** `CMD-BE-QUALITY`; configuration and health unit tests.
- **Security:** Redact secrets; never expose bootstrap/owner DSNs; no arbitrary execution surface.
- **Risks:** Config drift, secret leakage, framework code absorbing domain logic.
- **Review checklist:** [ ] only foundation scope [ ] config matches PLAN [ ] tests pass [ ] no domain coupling [ ] docs updated.
- **Completion report:** Use §11 with `Task ID: FND-001`.

#### FND-001 completion report

- Task ID: `FND-001`
- Final status: `DONE`
- Owner: Unassigned
- Goal achieved: Added the FastAPI foundation shell with typed fail-fast runtime configuration, safe error/correlation handling, dependency injection, redacted JSON logging, health endpoints and backend quality gates; approved by the reviewer.
- Files/modules changed: `.env.example`, `.gitignore`, `pyproject.toml`, `backend/apps/support_api/{app.py,dependencies.py,health.py,main.py}`, `backend/apps/support_api/core/{config.py,correlation.py,errors.py,logging.py}`, package markers, and `backend/tests` foundation tests.
- Contract/schema impact: Implements the approved public correlation/error and runtime-config foundation only; no domain/API business contract change and no database schema impact.
- Migrations created (if authorized): None.
- Tests added/updated: 20 configuration, health, correlation, error-envelope, redaction and import-boundary tests.
- Required context loaded: This FND-001 task section; `docs/ARCHITECTURE.md` §4, §6, §13 and §18; `docs/API_CONTRACT.md` §1, §3, §4 and §9.1; `docs/SECURITY.md` §17, §18 and §24.
- Additional context loaded and reasons: `docs/PLAN.md` §14 to resolve the exact environment contract and the targeted §16 backend health row to resolve health route names; `docs/TASKS.md` command catalog and §16 completion template to execute/report required gates; direct dependent-ID grep for handoff. API_CONTRACT §2 and §10 were incidentally included by the initial contiguous line selection, did not introduce scope, and were not used to implement auth.
- Dependency completion reports reviewed: `DOC-001` completion report; final status `DONE`, no deviations or unresolved PLAN contradiction, and `FND-001` explicitly unblocked.
- Context intentionally not loaded: The rest of PLAN, the other six specialist documents, unrelated TASKS sections/completion reports, and implementation areas outside the FND-001 backend foundation.
- Commands run and results: Python AST parse PASS (18 files); TOML parse PASS; `ruff check --no-cache backend` PASS; `mypy backend` PASS (18 files); `pytest backend/tests -q` PASS (20 tests).
- Security checks: Missing/invalid config fails validation; bootstrap/owner/commerce DSNs are absent from backend settings; settings repr, JSON logs, health and error responses redact secrets; raw Bearer tokens are redacted; safe errors omit input/traceback; import-boundary test rejects Mock-Commerce runtime imports.
- Acceptance criteria evidence: Required-config, runtime-role, provider and timeout invariant tests pass; health responses and all error envelopes propagate `X-Correlation-ID`; secrets are absent from logs/responses; strict Ruff/Mypy and all unit tests pass; foundation imports contain no domain or Mock-Commerce runtime coupling.
- Risks/limitations remaining: `/health/ready` verifies the Phase-1 configuration shell only; database/service readiness checks belong to their owning later tasks. No dependency lockfile is introduced by this task.
- Deviations from PLAN: None.
- Follow-up tasks unblocked: The `FND-001` dependency is now satisfied for `DB-000`, `INF-001`, `SKEL-001` and `MOCK-AUTH-001`; their remaining dependencies still apply and none was started.

### FND-002 — Vue foundation shell

- **Metadata:** Phase 1; size `M`; milestone `v0.1-foundation`; status `DONE`; Owner: Unassigned.
- **Goal:** Establish Vue/Vite/TypeScript/Router/Pinia/typed HTTP shell.
- **In scope:** App shell, routes/layout, typed client, correlation/error handling and frontend quality commands.
- **Out of scope:** Ticket/approval screens or business behavior.
- **Modules/files:** `frontend/src/{router,stores,services,layouts,types}`, frontend config/tests.
- **Input → output:** Public API types → buildable frontend shell with typed client boundaries.
- **Dependencies:** `DOC-001`.
- **Required reading:**
  - `docs/ARCHITECTURE.md` — §5 `Frontend boundary`; §6 `FastAPI application boundary`.
  - `docs/API_CONTRACT.md` — §1 `API conventions`; §2 `Authentication và authorization`; §3 `Headers`; §4 `Error envelope`; §10 `Authentication contracts`.
  - `docs/SECURITY.md` — §4 `Authentication threats and controls`; §5 `Authorization and RBAC`; §17 `Secret management`; §18 `Log redaction and no-CoT`.
- **Acceptance criteria:** Typecheck/build pass; no direct Gemini/Mock-Commerce call; errors/correlation handled consistently.
- **Required tests/commands:** `CMD-FE-QUALITY`.
- **Security:** Tokens not logged; frontend role checks are UX only; no secret bundled.
- **Risks:** API type drift, client bypassing public prefix, hidden authorization assumptions.
- **Review checklist:** [ ] typed API only [ ] no domain scope [ ] tests/build pass [ ] no secrets [ ] docs aligned.
- **Completion report:** Use §11 with `Task ID: FND-002`.

#### FND-002 completion report

- Task ID: `FND-002`
- Final status: `DONE`
- Owner: Unassigned
- Goal achieved: Added the Vue 3/Vite/TypeScript/Router/Pinia foundation with a neutral app shell, typed public HTTP client, correlation/error handling, in-memory user session boundary and reproducible frontend quality commands; all acceptance criteria and required quality gates were approved by the reviewer.
- Files/modules changed: `.gitignore`; `frontend/package.json`, `package-lock.json`, `.env.example`, TypeScript/Vite config, `index.html`, `src/{router,stores,services,layouts,types,views}`, frontend tests and the production bundle security scanner.
- Contract/schema impact: Implements the approved frontend/public API foundation only; no backend endpoint, domain contract, database schema or infrastructure change.
- Migrations created (if authorized): None.
- Tests added/updated: Seven frontend tests across three test files covering the public API prefix, correlation, user Bearer handling, safe error mapping, path escape prevention, in-memory session behavior and the app layout shell.
- Required context loaded: This FND-002 task section; `docs/ARCHITECTURE.md` §5 and §6; `docs/API_CONTRACT.md` §1, §2, §3, §4 and §10; `docs/SECURITY.md` §4, §5, §17 and §18.
- Additional context loaded and reasons: `FND-001` metadata/completion report to satisfy the user's explicit pre-code review-state check; repository file/status inventory to avoid overwriting backend or infrastructure; `docs/TASKS.md` command catalog and §16 completion template to execute/report the required gates; direct dependent-ID grep for handoff.
- Dependency completion reports reviewed: Direct dependency `DOC-001`; final status `DONE`, no deviations or unresolved PLAN contradiction.
- Context intentionally not loaded: `docs/PLAN.md`, the other six specialist documents, unrelated task completion reports, backend implementation contents and any infrastructure implementation.
- Commands run and results: Node `v22.13.0`; npm `10.9.2`; local `npm install` completed with zero reported vulnerabilities; `npm --prefix=frontend run typecheck` PASS; `npm --prefix=frontend run test` PASS (3 files, 7 tests); `npm --prefix=frontend run build` PASS (41 modules); `npm --prefix=frontend run security:scan` PASS; source/dist forbidden-reference grep PASS; `git diff --check` PASS.
- Security checks: Only `VITE_PUBLIC_API_BASE_URL` is exposed to Vite; production bundle scan found no internal service token/key names, database/JWT/Gemini secrets, internal endpoint or Gemini host; user access token remains in-memory and is never logged; HTTP client accepts only `/api/v1`, rejects escape paths and never defines direct Gemini/Mock-Commerce access.
- Acceptance criteria evidence: Strict Vue TypeScript check passes; all frontend tests pass; production build succeeds; typed client propagates `X-Correlation-ID` and maps the approved safe error envelope; no backend/infrastructure diff exists; bundle secret scan passes.
- Risks/limitations remaining: The session store is intentionally memory-only and the shell has no login, Ticket or approval business UI; those behaviors belong to their owning later tasks. Deployment must supply a trusted public API origin ending in `/api/v1` when not using the same-origin default. npm reported zero vulnerabilities but emitted a deprecation warning for transitive `glob@10.5.0`; dependency owners should be monitored during later maintenance.
- Deviations from PLAN: None.
- Follow-up tasks unblocked: The `FND-002` dependency is now satisfied for `INF-001`, `SKEL-001` and `WEB-001`; their remaining dependencies still apply and none was started.

### DB-000 — Database role/schema bootstrap

- **Metadata:** Phase 1; size `S`; milestone `v0.1-foundation`; status `DONE`; Owner: Unassigned.
- **Goal:** Idempotently create two schemas, two owners, two runtime roles and least-privilege grants.
- **In scope:** One-shot bootstrap using `POSTGRES_BOOTSTRAP_DATABASE_URL` plus four role-password secrets, default privileges, revoke cross-schema/public access and grant/catalog assertions.
- **Out of scope:** Alembic, domain enums/tables/seed or any downstream use of bootstrap credential.
- **Modules/files:** Bootstrap script/Compose job and grant integration tests.
- **Input → output:** Admin DSN + four role secrets → `support_owner/support_app/commerce_owner/commerce_app` and isolated schemas.
- **Dependencies:** `FND-001`, PostgreSQL/Compose foundation.
- **Required reading:**
  - `docs/ARCHITECTURE.md` — §11 `PostgreSQL ownership`; §18 `Runtime containers`.
  - `docs/DATABASE_DESIGN.md` — §1 `Design principles`; §3 `Schema ownership và roles`; §4 `Bootstrap process`; §18 `Migration strategy`.
  - `docs/SECURITY.md` — §7 `Cross-schema isolation`; §17 `Secret management`.
- **Acceptance criteria:** Re-run safe; runtime roles denied other schema; admin DSN absent migration/runtime containers; no shared runtime role; Phase-1 catalog has no domain enum/table/seed.
- **Required tests/commands:** `CMD-COMPOSE`; grant matrix integration tests.
- **Security:** Bootstrap credential one-shot only; password values never logged/committed.
- **Risks:** Overbroad default privileges, credential exposure, non-idempotent role DDL.
- **Review checklist:** [ ] exact targets [ ] least privilege [ ] re-run test [ ] cross-schema denial [ ] secret review.
- **Completion report:** Use §11 with `Task ID: DB-000`.

#### DB-000 completion report

- Task ID: `DB-000`
- Final status: `DONE`
- Owner: Unassigned
- Goal achieved: Added an idempotent one-shot PostgreSQL bootstrap for the exact support/commerce owners and runtime roles, isolated schemas, least-privilege/default grants, clean Compose harness and executable catalog/grant assertions; all acceptance criteria, tests and security checks were approved by the reviewer.
- Files/modules changed: `.gitignore`; `infrastructure/db/bootstrap/{compose.yaml,.env.db000.example,bootstrap.sql,run-bootstrap.sh,run-integration.ps1,README.md}` and `infrastructure/db/bootstrap/tests/{assert-catalog.sql,verify-grants.sh}`.
- Contract/schema impact: Creates only `support_owner`, `support_app`, `commerce_owner`, `commerce_app`, the `support`/`commerce` schemas and their grants/default privileges; no extensions, Alembic state, domain enum/table, cross-schema FK or seed data.
- Migrations created (if authorized): None; DB-000 is bootstrap infrastructure and does not own a domain migration.
- Tests added/updated: Clean PostgreSQL Compose integration harness with role-attribute/schema-owner/catalog assertions, two consecutive bootstrap executions, runtime DML/sequence probes, cross-schema denial, runtime `CREATE` denial, PUBLIC isolation, membership isolation and post-clean catalog verification.
- Required context loaded: This DB-000 task section; `docs/ARCHITECTURE.md` §11 and §18; `docs/DATABASE_DESIGN.md` §1, §3, §4 and §18; `docs/SECURITY.md` §7 and §17.
- Additional context loaded and reasons: `docs/TASKS.md` command catalog and §16 completion template to execute/report required gates; direct dependent-ID grep for handoff; repository/Docker inventory and workspace ACL/write checks to resolve the prior infrastructure write blocker. `docs/SECURITY.md` §24 was incidentally included in the initial targeted line selection and did not expand implementation scope.
- Dependency completion reports reviewed: Direct task dependency `FND-001`; final status `DONE`, reviewer-approved, no deviations and DB-000 explicitly listed as unblocked. The non-task PostgreSQL/Compose prerequisite was verified locally with Docker Engine 29.4.0 and Compose 5.1.1.
- Context intentionally not loaded: `docs/PLAN.md`, the other six specialist documents, unrelated task completion reports, backend/frontend implementation contents and `INF-001` implementation scope.
- Commands run and results: Workspace write check PASS outside sandbox; PowerShell runner parse PASS; Docker daemon/server check PASS; Compose config validation PASS; clean `docker compose up --build --detach --wait postgres` PASS; bootstrap execution 1 PASS; identical bootstrap execution 2 PASS; grant/catalog integration job PASS; cleanup PASS with no remaining test container/volume; `git diff --check` PASS.
- Security checks: Bootstrap receives only the admin DSN plus four role-password environments; rendered Compose scope assertion blocks the admin DSN from every other service; real/generated passwords are not committed or printed; roles are LOGIN but NOSUPERUSER/NOCREATEDB/NOCREATEROLE/NOINHERIT/NOREPLICATION/NOBYPASSRLS; PUBLIC and cross-schema privileges are revoked; runtime roles have no role membership or schema `CREATE`.
- Acceptance criteria evidence: Rerun is successful and preserves exact owners; both runtime roles can use future owner-created tables/sequences only in their own schema and are denied the other schema; admin DSN exists only on `db-bootstrap`; roles are distinct with no membership; Phase-1 catalog assertions prove zero application relations and zero domain enums before and after grant probes.
- Risks/limitations remaining: The self-contained `postgres:16-alpine` Compose file is an isolated DB-000 integration harness, not the final local topology or extension-enabled image owned by `INF-001`. The bootstrap URI is passed only to the transient isolated `psql` process and never logged.
- Deviations from PLAN: None.
- Follow-up tasks unblocked: The `DB-000` dependency is now satisfied for `INF-001`, `SKEL-001`, `DB-001A`, `DB-002A` and `DB-001C`; their remaining dependencies still apply and none was started.

### INF-001 — Local Compose and migration-job topology

- **Metadata:** Phase 1; size `M`; milestone `v0.1-foundation`; status `DONE`; Owner: Unassigned.
- **Goal:** Define healthy startup plus two owner-isolated Alembic infrastructures without creating domain schema.
- **In scope:** PostgreSQL/bootstrap/migration shells/mock/backend/frontend container topology, two Alembic configs/commands/versions directories, optional empty baselines, health dependencies and private network.
- **Out of scope:** Domain migration/enum/table/seed, cloud, Redis, queue, Mailpit, OTEL, PDF worker or Kubernetes.
- **Modules/files:** `infrastructure/`, Compose and container health configuration.
- **Input → output:** Images/env contract → ordered healthy local stack.
- **Dependencies:** `DB-000`, `FND-001`, `FND-002`.
- **Required reading:**
  - `docs/ARCHITECTURE.md` — §18 `Runtime containers`; §19 `Docker Compose startup order`; §20 `Deployment view`.
  - `docs/DATABASE_DESIGN.md` — §3 `Schema ownership và roles`; §4 `Bootstrap process`; §18 `Migration strategy`.
  - `docs/SECURITY.md` — §3 `Trust boundaries`; §7 `Cross-schema isolation`; §17 `Secret management`.
  - `docs/ROADMAP.md` — §5 `Phase 1 — Foundation`; §16 `Final release gates`.
- **Acceptance criteria:** `docker compose config` valid; each migration command accepts only its owner DSN/search path; owner/admin DSNs not in runtime; optional baseline is empty; migration heads/catalog contain no domain enum/table; startup order matches architecture.
- **Required tests/commands:** `CMD-COMPOSE`, both Alembic head smoke commands and Phase-1 catalog assertions.
- **Security:** Only frontend/backend expose host as needed; Mock-Commerce private; secrets ignored.
- **Risks:** Env interpolation, health race, migration credential leakage.
- **Review checklist:** [ ] no out-of-scope service [ ] credential matrix [ ] health order [ ] clean config [ ] docs updated.
- **Completion report:** Use §11 with `Task ID: INF-001`.

#### INF-001 completion report

- Task ID: `INF-001`
- Final status: `DONE`
- Owner: Unassigned
- Goal achieved: Added the Phase-1 local Compose topology with ordered healthy startup, extension/bootstrap jobs, two owner-isolated empty Alembic infrastructures, private PostgreSQL/Mock-Commerce services and executable catalog/credential assertions; no domain object or seed was created, and the reviewer approved all acceptance criteria, tests and security checks.
- Files/modules changed: Root `.dockerignore`, `.env.compose.example`, `compose.yaml`, `.gitignore`, `pyproject.toml`; `infrastructure/README.md`; `infrastructure/docker/{backend.Dockerfile,frontend.Dockerfile}`; `infrastructure/containers/mock_commerce_health.py`; `infrastructure/db/bootstrap/{phase1-extensions.sql,run-phase1-bootstrap.sh}`; `infrastructure/migrations/{support,commerce}` Alembic shells; `infrastructure/tests/assert_phase1_catalog.py`; minimal environment-parsing compatibility fix in `backend/apps/support_api/core/config.py`; and this task status/report in `docs/TASKS.md`.
- Contract/schema impact: Adds only the approved PostgreSQL extensions, existing DB-000 roles/schemas/grants and optional schema-owned Alembic version state. Both revision directories and heads remain empty; no domain table, enum, index, cross-schema FK or seed exists.
- Migrations created (if authorized): None. The support and commerce Alembic infrastructures have separate config, command, owner DSN, fixed search path and empty `versions/` directories; `SKEL-001` remains owner of the first domain migration.
- Tests added/updated: Added Phase-1 catalog assertions for exact schema ownership, required extensions and absence of domain relations/enums; added rendered-Compose assertions for DSN/token/port isolation and absence of a seed service. Runtime Compose startup and existing backend/frontend suites were also exercised.
- Required context loaded: This `INF-001` task section; `docs/ARCHITECTURE.md` §18, §19 and §20; `docs/DATABASE_DESIGN.md` §3, §4 and §18; `docs/SECURITY.md` §3, §7 and §17; `docs/ROADMAP.md` §5 and §16.
- Additional context loaded and reasons: `docs/TASKS.md` command catalog and §16 completion template to execute/report gates; repository status/file inventory, root environment/package files, backend health/settings shell, frontend package/Vite config and the existing DB-000 bootstrap Compose/scripts to integrate without replacing approved configuration. The direct dependent task heading was viewed only to confirm it remained `TODO`.
- Dependency completion reports reviewed: Direct dependencies `FND-001`, `FND-002` and `DB-000`; all were reviewer-approved with final status `DONE`, no PLAN deviations and `INF-001` explicitly unblocked.
- Context intentionally not loaded: Entire `docs/PLAN.md`, non-required specialist-document sections, unrelated task completion reports and all domain implementation areas owned by Phase 2 or later.
- Commands run and results: `docker compose config --quiet` PASS; rendered Compose credential/token/port/no-seed assertions PASS; clean `docker compose up --build --detach --wait` PASS; support and commerce Alembic head smoke PASS with empty heads; Phase-1 catalog assertions PASS; backend/frontend health smoke PASS; `pytest` PASS (20 tests); Ruff PASS; Mypy PASS (18 source files); frontend typecheck PASS; frontend tests PASS (3 files, 7 tests); frontend build PASS (41 modules); frontend bundle secret scan PASS; `git diff --check` PASS; smoke-credential/no-revision/no-domain-DDL-or-seed scans PASS; stack/volume cleanup PASS.
- Security checks: Bootstrap/admin and owner DSNs are absent from runtime services; each migration job receives only its own owner DSN; backend and Mock-Commerce receive only their owning runtime DSN and the internal token; frontend receives neither; only backend/frontend publish host ports; PostgreSQL and Mock-Commerce remain private; placeholder/real secret files are ignored and generated smoke credentials were neither committed nor left in the workspace.
- Acceptance criteria evidence: Rendered Compose validates and enforces the credential matrix; health dependencies follow PostgreSQL → bootstrap → isolated migrations → Mock-Commerce/backend → frontend; both Alembic environments enforce the correct owner and `support, pg_catalog` or `commerce, pg_catalog` search path; empty-head and catalog checks prove no domain table/enum/seed; a clean extension-enabled PostgreSQL volume reached a fully healthy stack.
- Risks/limitations remaining: The Mock-Commerce container is intentionally only a private Phase-1 health shell and the existing backend readiness route is a foundation-level process/config check; business endpoints and deeper dependency readiness belong to later owning tasks. Docker Compose stores the one-shot migration credentials in its daemon-managed service configuration, so local developer access to Docker remains privileged as expected.
- Deviations from PLAN: None. One integration correction changed `ALL_BUSINESS_WRITES_REQUIRE_APPROVAL` from an environment-incompatible `Literal[True]` field to a parsed boolean plus an equivalent fail-fast `must be true` invariant; the approved semantic contract is unchanged.
- Follow-up tasks unblocked: `SKEL-001` now has all declared dependencies satisfied, but it was not started and remains `TODO`.

## 6. Phase 2 — Walking Skeleton

### SKEL-001 — End-to-end Walking Skeleton

- **Metadata:** Phase 2; size `M`; milestone `v0.1-skeleton`; status `DONE`; Owner: Unassigned.
- **Goal:** Own the first domain migration and demonstrate Vue → FastAPI → PostgreSQL → fixed proposal → fake decision/result using final-shaped contracts.
- **In scope:** First minimal forward-compatible migration for final-named `support.users/customers/support_tickets/ticket_messages` plus required enum/index, demo login, Ticket/message persistence, explicit run endpoint, fake adapters and basic UI result.
- **Out of scope:** SQLite/in-memory/temp schema, full DB-001A, commerce/RAG/workflow/approval tables, Gemini, embeddings, full LangGraph, real commerce transaction, full edit/payment sync.
- **Modules/files:** Support adapter interfaces, minimal forward-compatible support migration, skeleton Vue views and browser/API smoke tests.
- **Input → output:** `WORKFLOW_PROFILE=walking_skeleton` + synthetic fixture → runnable demo; approve gives fake `VERIFIED` then `RESOLVED`, reject gives `ESCALATED`.
- **Dependencies:** `FND-001`, `FND-002`, `DB-000`, `INF-001`.
- **Required reading:**
  - `docs/ARCHITECTURE.md` — §16 `Walking Skeleton architecture`; §17 `Fake provider replacement path`.
  - `docs/DATABASE_DESIGN.md` — §18 `Migration strategy`; §20 `Walking Skeleton migration policy`.
  - `docs/API_CONTRACT.md` — §11 `Ticket creation contract`; §12 `Explicit Agent Run trigger`; §19 `Walking Skeleton behavior`.
  - `docs/ROADMAP.md` — §6 `Phase 2 — Walking Skeleton`; §7 `Fake component replacement sequence`.
  - `docs/SECURITY.md` — §16 `PII and synthetic-data-only rule`; §24 `Explicitly prohibited capabilities`; §27 `V0.1 security limitations`.
- **Acceptance criteria:** Starts from empty Phase-1 PostgreSQL schemas; migration is the first domain revision and creates only final-named minimal tables/enums/indexes; no temporary/throwaway schema or SQLite; real Ticket persists; explicit create-ticket/create-run; approve fake `VERIFIED`→`RESOLVED`, reject→`ESCALATED`; fakes only behind interfaces; release profile cannot use fakes.
- **Required tests/commands:** `CMD-BE-QUALITY`, `CMD-FE-QUALITY`, `CMD-COMPOSE`, `CMD-E2E` smoke.
- **Security:** Synthetic data only; no commerce write; fake `VERIFIED` clearly non-release; no fake import in router/UI.
- **Risks:** Fake leakage, throwaway schema, frontend coupling to temporary behavior.
- **Review checklist:** [ ] final contracts [ ] forward migration [ ] fake isolation [ ] browser smoke [ ] release guard.
- **Completion report:** Use §11 with `Task ID: SKEL-001`.

#### SKEL-001 completion report

- Task ID: `SKEL-001`
- Final status: `DONE`
- Owner: Unassigned
- Goal achieved: Implemented the first runnable Vue → final-shaped FastAPI API → real PostgreSQL Walking Skeleton for UC-01, with explicit Ticket/run requests, fixed proposal review, deterministic fake action verification, approved-path `VERIFIED` → `RESOLVED` and rejected-path `ESCALATED`; all acceptance criteria, quality checks, Compose and E2E smoke tests were approved by the reviewer.
- Files/modules changed: `pyproject.toml`, `compose.yaml`; backend application/config/database composition; new `backend/apps/support_api/walking_skeleton/{contracts,adapters,repository,service,router}.py`; support revision `infrastructure/migrations/support/versions/0001_walking_skeleton.py`; both Alembic environment transaction fixes; Vue API types/service and `HomeView.vue`; HTTP client binding fix; backend/frontend/E2E tests; `infrastructure/README.md`; and this task status/report.
- Contract/schema impact: Adds only final-named `support.users`, `support.customers`, `support.support_tickets`, `support.ticket_messages`, their minimal required final enums/constraints/indexes and two synthetic demo identities. Commerce remains without domain tables; no workflow, approval, action, RAG or attachment table was created. Public paths and response/state names match the approved login, Ticket, explicit run and approval contracts.
- Migrations created (if authorized): `0001_walking_skeleton` is the authorized first support-domain revision owned by `SKEL-001`; commerce has no revision. It runs with `support_owner`, retains `commerce` isolation and uses PostgreSQL only—no SQLite, temporary or throwaway schema.
- Tests added/updated: Added backend approve/reject, Ticket/run idempotency/conflict, release-profile guard and router/fake import-boundary tests; added frontend final-public-path/auth test; added real HTTP/PostgreSQL E2E assertions for exact skeleton relations/enums, Ticket/message persistence and both terminal outcomes.
- Required context loaded: This `SKEL-001` task section; `docs/ARCHITECTURE.md` §16 and §17; `docs/DATABASE_DESIGN.md` §18 and §20; `docs/API_CONTRACT.md` §11, §12 and §19; `docs/ROADMAP.md` §6 and §7; `docs/SECURITY.md` §16, §24 and §27.
- Additional context loaded and reasons: Direct dependency completion reports for `FND-001`, `FND-002`, `DB-000` and `INF-001`; `docs/DATABASE_DESIGN.md` §6 and §10 plus `docs/API_CONTRACT.md` §7, §10 and §14 to avoid guessing final physical columns, status vocabulary, demo login and decision contract; command catalog/completion template; relevant existing backend/frontend/infrastructure source; browser local-testing instructions for the required UI smoke; direct dependent-ID grep for handoff.
- Dependency completion reports reviewed: `FND-001`, `FND-002`, `DB-000` and `INF-001`; all were reviewer-approved, final status `DONE`, without blocking PLAN deviations.
- Context intentionally not loaded: Entire `docs/PLAN.md`, unrelated specialist-document sections, unrelated task reports and implementation areas owned by Gemini/RAG/LangGraph, production approval/action, real commerce, attachment or later UC tasks.
- Commands run and results: Installed only declared skeleton auth dependencies into the existing virtualenv; Ruff PASS; strict Mypy PASS (26 files); backend tests PASS (24); frontend typecheck PASS; frontend tests PASS (4 files, 8 tests); frontend build PASS (46 modules); bundle security scan PASS; `docker compose config` PASS; clean Compose build/start/health PASS; real HTTP/PostgreSQL E2E PASS for approve and reject; browser UI smoke PASS through `RESOLVED`/`COMPLETED`/`VERIFIED`; support Alembic `heads/current` both report `0001_walking_skeleton`; commerce head remains empty; `git diff --check` PASS; test container/volume cleanup PASS.
- Security checks: Demo data uses `.test` identities and Argon2 password hashes; access tokens are short-lived signed Bearer tokens; customer and reviewer roles are separated; Ticket repository uses only `support_app` and parameterized SQL; no backend commerce import/query/write or external HTTP action exists; router/UI do not import fake implementations; frontend bundle has no internal token/secret; `v0_1` rejects fake providers; no Gemini, RAG, LangGraph, arbitrary URL/tool, attachment or chain-of-thought path was introduced.
- Acceptance criteria evidence: Clean empty Phase-1 schemas migrate to exactly the four permitted support tables and six required final enums; Ticket and first message persist transactionally before any run; run creation is a separate public request with replay and active-run conflict behavior; fake adapters are behind protocols and composition root; approve resolves only after deterministic `VERIFIED`, reject escalates without action; UI shows the persisted Ticket, proposal and terminal result; release-profile fake guard is tested.
- Risks/limitations remaining: Run/approval/proposal state is intentionally in-memory and lost on backend restart; only Ticket/message and terminal Ticket status persist. Demo auth, fixed proposal and fake verification are local/test scaffolding, explicitly not production evidence, and are replaced by their owning later tasks.
- Deviations from PLAN: None. Two prerequisite integration defects were corrected without semantic change: Alembic now commits its session-level search path before the migration transaction, and the browser HTTP client binds native `window.fetch` correctly.
- Follow-up tasks unblocked: Reviewer approval is recorded and `SKEL-001` is now `DONE`; its dependency is satisfied for `DB-001A`, `DB-002A` and `DB-001C`. Their remaining dependencies still apply, and none was started.

## 7. Phase 3 — Core database, auth and Ticket APIs

### DB-001A — Core support identity and Ticket persistence

- **Metadata:** Phase 3; size `M`; milestone `v0.1-foundation`; status `DONE`; Owner: Unassigned.
- **Goal:** Extend skeleton data into final `users/customers/support_tickets/ticket_messages` contract.
- **In scope:** Plaintext synthetic columns, FKs/constraints/indexes, forward backfill and repositories.
- **Out of scope:** Field cipher/lookup-hash, address, attachment, workflow hoặc knowledge tables.
- **Modules/files:** Support models, migration and repositories.
- **Input → output:** Minimal skeleton schema/data → full DB-001A schema preserving data.
- **Dependencies:** `SKEL-001`, `DB-000`, `INF-001`.
- **Required reading:**
  - `docs/DATABASE_DESIGN.md` — §3 `Schema ownership và roles`; §6 `Support identity, Ticket và Message (DB-001A)`; §10 `Status definitions và transition ownership`; §17 `Sensitive data handling`; §18 `Migration strategy`.
  - `docs/SECURITY.md` — §6 `Customer isolation`; §7 `Cross-schema isolation`; §16 `PII and synthetic-data-only rule`.
  - `docs/ARCHITECTURE.md` — §11 `PostgreSQL ownership`.
- **Acceptance criteria:** §DATABASE_DESIGN core tables/constraints/indexes; no drop/recreate; synthetic-only note and migration path verified.
- **Required tests/commands:** `CMD-SUPPORT-MIGRATE`, repository/constraint tests, `CMD-BE-QUALITY` relevant subset.
- **Security:** Plaintext only synthetic; Argon2 password hash; no fake cipher columns; role isolation.
- **Risks:** Destructive skeleton migration, null/backfill error, accidental real-data claim.
- **Review checklist:** [ ] schema matches docs [ ] forward-only [ ] constraints/indexes [ ] grants [ ] tests/rollback review.
- **Completion report:** Use §11 with `Task ID: DB-001A`.

#### DB-001A completion report

- Task ID: `DB-001A`
- Final status: `DONE`
- Owner: Unassigned
- Goal achieved: Upgraded the four final-named Walking Skeleton support tables to the complete DB-001A physical contract through an in-place forward Alembic revision, preserving existing rows and identifiers without dropping or recreating a table; all acceptance criteria, migration checks, repository/constraint tests and security checks were approved by the reviewer.
- Files/modules changed: `infrastructure/migrations/support/versions/0002_db001a_core_support.py`; `infrastructure/tests/run_db001a_integration.py`; `backend/tests/test_db001a_migration.py`; `infrastructure/README.md`; and this task status/report in `docs/TASKS.md`.
- Contract/schema impact: Adds UUID generation defaults to all four primary keys; adds nullable `users.last_login_at`, `customers.phone`, `support_tickets.assigned_user_id` and `support_tickets.closed_at`; adds the same-schema assigned-user `RESTRICT` FK plus v0.1 intent and closed-time structural checks. Existing enums, unique constraints, indexes, Ticket resolution invariant and all skeleton data remain intact. No attachment, cipher/hash, address, workflow, knowledge or commerce object was added.
- Migrations created (if authorized): `0002_db001a_core_support`, revising `0001_walking_skeleton`. Upgrade uses only `ALTER COLUMN`, `ADD COLUMN`, `ADD FOREIGN KEY` and `ADD CHECK`; downgrade removes only DB-001A additions and restores skeleton UUID-default behavior. Neither direction drops or recreates a skeleton table.
- Tests added/updated: Added three AST migration guards against table drop/recreate and deferred columns; added a real PostgreSQL integration suite covering pre-upgrade fixture preservation, exact columns/defaults/constraints/indexes, all support FK delete behaviors, no cross-schema FK, runtime grants/isolation, invalid intent/version/timestamps/FKs, existing repository replay/customer scope/status compatibility, and downgrade/upgrade data preservation.
- Required context loaded: This `DB-001A` task section; `docs/DATABASE_DESIGN.md` §3, §6, §10, §17 and §18; `docs/SECURITY.md` §6, §7 and §16; `docs/ARCHITECTURE.md` §11.
- Additional context loaded and reasons: Direct dependency completion reports for `SKEL-001`, `DB-000` and `INF-001`; `docs/TASKS.md` status workflow, command catalog and completion template to execute/report required gates; the existing support Alembic environment and skeleton revision, runtime database factory/repository, backend tests, Compose topology, infrastructure test harness and README to implement and verify the forward migration without replacing approved configuration; downstream dependency headings only for the completion handoff.
- Dependency completion reports reviewed: `SKEL-001`, `DB-000` and `INF-001`; all are reviewer-approved with final status `DONE`, no blocking PLAN deviation, and the required support owner/runtime-role boundary is available.
- Context intentionally not loaded: Entire `docs/PLAN.md`; non-required document sections; unrelated completion reports; frontend code; commerce implementation; and all AUTH-001, TKT-001, workflow, approval, knowledge and later-task implementation areas.
- Commands run and results: Targeted Ruff PASS; migration guard tests PASS (3); strict Mypy PASS (27 source files); full backend Ruff PASS; full backend tests PASS (27); Compose config PASS; support Alembic `heads/current` both reported `0002_db001a_core_support`; isolated PostgreSQL DB-001A integration PASS for downgrade-to-skeleton, fixture insert, forward upgrade, physical/constraint/grant/repository checks and final downgrade/upgrade round trip; `git diff --check` PASS. The isolated Compose project, network and test volume were removed after the successful run.
- Security checks: Only synthetic `.test` identities/content were used; password hashes remain Argon2; no real PII/payment secret or fake cipher/hash field was introduced; `support_app` can use the upgraded support tables but still has no `commerce` schema usage; all FKs remain within `support` with `RESTRICT`; owner credential remained confined to the migration/test container and no credential value was logged or committed.
- Acceptance criteria evidence: A fixture created while the database was at `0001_walking_skeleton` compared byte-for-value equal on every pre-existing field after `0002`; catalog assertions prove the exact DB-001A columns, UUID defaults, named checks/FKs/indexes and zero cross-schema FK; invalid structural writes fail; repository create/replay/customer isolation/status operations pass under `support_app`; AST guards prove no table replacement in either migration direction.
- Risks/limitations remaining: Plaintext identity/Ticket/message fields are explicitly synthetic-only until the deferred v1.0 encryption migration. Downgrading intentionally discards values in the four DB-001A-added nullable columns, while preserving all pre-existing skeleton fields and rows. The current Walking Skeleton repository remains temporary and its replacement belongs to AUTH-001/TKT-001.
- Deviations from PLAN: None. The first integration run exposed only a test-adapter detail: asyncpg returns PostgreSQL internal `char` catalog fields as bytes; the assertion now normalizes that representation without changing schema semantics, and the complete rerun passed.
- Follow-up tasks unblocked: Reviewer approval is recorded and `DB-001A` is now `DONE`; `AUTH-001` and `DB-001B3` have all declared dependencies satisfied. The DB-001A dependency is also satisfied for `TKT-001`, `SEED-001`, `DB-001B1` and other listed downstream tasks whose remaining dependencies still apply. None was started.

### AUTH-001 — Access-token authentication and RBAC

- **Metadata:** Phase 3; size `M`; milestone `v0.1-foundation`; status `DONE`; Owner: Unassigned.
- **Goal:** Replace demo auth with local JWT access-token login, RBAC and demo accounts.
- **In scope:** Login/me, Argon2 verification, 15-minute JWT, disabled accounts, role dependencies and rate limit.
- **Out of scope:** Refresh rotation, OAuth/SSO or production identity provider.
- **Modules/files:** `support_api` auth API/service/repository/security tests.
- **Input → output:** Credentials → authenticated scoped principal or safe typed error.
- **Dependencies:** `DB-001A`, `SKEL-001`.
- **Required reading:**
  - `docs/API_CONTRACT.md` — §2 `Authentication và authorization`; §3 `Headers`; §4 `Error envelope`; §10 `Authentication contracts`; §17 `Error/status matrix`.
  - `docs/SECURITY.md` — §4 `Authentication threats and controls`; §5 `Authorization and RBAC`; §16 `PII and synthetic-data-only rule`; §17 `Secret management`; §21 `Rate limiting`.
  - `docs/DATABASE_DESIGN.md` — §6.1 `support.users`; §6.2 `support.customers`.
- **Acceptance criteria:** Role/status/customer scope enforced backend; sample synthetic accounts; no token/password logs.
- **Required tests/commands:** `CMD-BE-QUALITY`, auth/API/security tests.
- **Security:** JWT issuer/signing key, Argon2, throttling, no enumeration/secret leakage.
- **Risks:** Role bypass, token handling bug, demo credentials leaking outside demo docs.
- **Review checklist:** [ ] API contract [ ] RBAC service check [ ] expiry/disabled [ ] rate limit [ ] redaction.
- **Completion report:** Use §11 with `Task ID: AUTH-001`.

#### AUTH-001 completion report

- Task ID: `AUTH-001`
- Final status: `DONE`
- Owner: Unassigned
- Goal achieved: Replaced Walking Skeleton demo authentication with a dedicated PostgreSQL-backed local auth boundary providing contract-shaped login/me, 15-minute issuer-validated JWT access tokens, current-state account/customer checks, router/service RBAC and a generic anti-enumeration login rate limit; all acceptance criteria, quality gates, Compose/E2E regressions and security checks were approved by the reviewer.
- Files/modules changed: New `backend/apps/support_api/auth/{contracts,dependencies,rate_limit,repository,router,service}.py`; backend composition and safe error-header support; Walking Skeleton contracts/router/service/repository integration to consume authenticated actors without owning auth; `.env.example`, `.env.compose.example`, auth/config/skeleton tests, `infrastructure/tests/run_auth_integration.py`, DB-001A integration compatibility, `infrastructure/README.md`, and this task status/report.
- Contract/schema impact: Implements `POST /api/v1/auth/login` and `GET /api/v1/auth/me`; preserves the documented login response and adds safe principal/customer-scope projection for me. Public failures use only `INVALID_CREDENTIALS`, `ACCOUNT_DISABLED`, `UNAUTHENTICATED` and `FORBIDDEN`; rate-limit denial is HTTP 429 with the generic `INVALID_CREDENTIALS` envelope plus rate headers, avoiding a new public code. No schema, Ticket API or refresh-token contract changed.
- Migrations created (if authorized): None. AUTH-001 uses the approved DB-001A `support.users/customers` columns and updates `last_login_at`/`updated_at` through `support_app` only.
- Tests added/updated: Added auth service/API/security tests for exact login/me responses, issuer/expiry/role validation, current DB role/status/customer scope, disabled login and post-issue invalidation, router/service RBAC, generic unknown/wrong-password behavior, 10/minute limiting and bounded identity memory, strong JWT config, absent secret/token/password output and no refresh endpoint. Updated Walking Skeleton regressions and DB-001A repository integration for the separated auth repository.
- Required context loaded: This `AUTH-001` task section; `docs/API_CONTRACT.md` §2, §3, §4, §10 and §17; `docs/SECURITY.md` §4, §5, §16, §17 and §21; `docs/DATABASE_DESIGN.md` §6.1 and §6.2.
- Additional context loaded and reasons: Direct dependency completion reports for `DB-001A` and `SKEL-001`; the single `/auth/me` row in `docs/API_CONTRACT.md` §7 because required §10 defines login but not the task-required me projection; current app composition, settings/error/logging foundations, Walking Skeleton auth/repository usage, backend tests, Compose topology and infrastructure E2E harness needed to replace auth without implementing TKT-001; downstream dependency headings only for completion handoff.
- Dependency completion reports reviewed: `DB-001A` and `SKEL-001`; both are reviewer-approved with final status `DONE`, no blocking PLAN deviation, approved Argon2 synthetic identities and the required runtime support-role boundary.
- Context intentionally not loaded: Entire `docs/PLAN.md`; unrelated specialist-document sections and completion reports; frontend implementation; TKT-001 implementation; Mock-Commerce/internal auth; workflow/RAG/approval production code; and every other later task.
- Commands run and results: Targeted Ruff/tests PASS; final Ruff PASS; strict Mypy PASS (35 source files); full backend tests PASS (44); `docker compose config` PASS; clean isolated Compose build/start/health PASS; real PostgreSQL/HTTP AUTH-001 integration PASS for login/me, Argon2, `last_login_at`, current customer scope, tampered JWT, disabled account and 10/minute limit; Walking Skeleton approve/reject regression PASS; final hardened AUTH integration rerun PASS; `git diff --check` PASS. Both isolated Compose runs were removed with their networks and volumes.
- Security checks: HS256 accepts only the configured issuer/key and requires `sub/role/iat/exp/jti`; JWT key is fail-fast at 32 bytes minimum and access TTL is fixed at 15 minutes; every protected request reloads user/customer state from PostgreSQL; unknown accounts execute dummy Argon2 verification; login keys are SHA-256 fingerprints of client IP plus normalized email and never retain raw inputs; repository SQL is static and parameterized; backend log scans found no password, raw JWT/Bearer token or signing key; no secret was committed or returned.
- Acceptance criteria evidence: Customer, agent and admin role tests prove router and service enforcement; current-role mismatch invalidates an issued token; disabled state returns `ACCOUNT_DISABLED` at login only after correct-password verification and on every protected operation; real customer identity resolves to the approved customer row; demo database hashes remain Argon2; login and me return exact safe envelopes with correlation; rate-limit headers and generic body pass; all 44 backend tests and both real-stack regressions pass.
- Risks/limitations remaining: The limiter is intentionally process-local for the single-backend v0.1 local topology and resets on restart; distributed enforcement belongs after v0.1. It keys each 60-second window by the hash of client IP plus normalized email and caps tracked active identities at 10,000. There is no refresh token, OAuth/SSO or production identity provider. The ignored local `.env.compose` currently has a 27-character JWT key and must be replaced by a value of at least 32 bytes before the next normal Compose start; it was not modified by this task.
- Deviations from PLAN: None. One startup integration defect was corrected during testing: Pydantic does not coerce an environment string into `Literal[15]`, so the field remains typed `int` with an equivalent fail-fast `must equal 15` validator. An initial test-only response annotation was also corrected; final quality and real-stack reruns passed.
- Follow-up tasks unblocked: Reviewer approval is recorded and `AUTH-001` is now `DONE`; `TKT-001` has all declared dependencies satisfied. AUTH-001 also satisfies its dependency edge for `KB-001`, `AG-001`, `AG-003` and later security/E2E tasks whose remaining dependencies still apply. None was started.

### TKT-001 — Final Ticket and message APIs

- **Metadata:** Phase 3; size `M`; milestone `v0.1-foundation`; status `DONE`; Owner: Unassigned.
- **Goal:** Replace skeleton Ticket repository/service with create/list/detail and dual message/resume contract.
- **In scope:** Ownership, Ticket+first-message transaction, idempotency, list/detail projections, attachment pre-validation and message commit-before-resume orchestration port.
- **Out of scope:** Agent node logic, attachment storage/fetch/upload or PDF upload.
- **Modules/files:** Support Ticket API/service/repositories/tests.
- **Input → output:** Scoped Ticket/message requests → `201` message-only or `200` same-run resume result through stable types.
- **Dependencies:** `AUTH-001`, `DB-001A`, `SKEL-001`.
- **Required reading:**
  - `docs/API_CONTRACT.md` — §5 `Idempotency và replay`; §7 `Public endpoint catalog`; §11 `Ticket creation contract`; §12 `Explicit Agent Run trigger`; §13 `Message same-run resume`; §17 `Error/status matrix`.
  - `docs/DATABASE_DESIGN.md` — §6.3 `support.support_tickets`; §6.4 `support.ticket_messages`; §7.11 `support.idempotency_records`; §14 `Idempotency storage`.
  - `docs/AGENT_WORKFLOW.md` — §9 `Clarification và same-run message resume`; §11.1 `Ticket`; §11.2 `Agent Run`; §12 `Timeout propagation`.
  - `docs/SECURITY.md` — §6 `Customer isolation`; §14 `Idempotency and duplicate prevention`; §20 `Upload and MIME validation`.
- **Acceptance criteria:** `POST /tickets` never auto-runs agent; ownership/idempotency pass; omitted/`[]` attachments take normal path; non-empty returns exact `422 ATTACHMENTS_NOT_SUPPORTED`, `retryable=false`, before message/idempotency-success/fetch/resume; timeout/invariant message semantics preserved.
- **Required tests/commands:** `CMD-BE-QUALITY`, `CMD-CONTRACT` Ticket/message integration subset.
- **Security:** Customer isolation, masked projections, rate limit, no checkpoint/CoT exposure.
- **Risks:** Transaction/resume coupling, duplicate message, hidden create-run side effect.
- **Review checklist:** [x] explicit trigger [x] dual response [x] ownership [x] replay [x] failure persistence.
- **Completion report:** Use §11 with `Task ID: TKT-001`.

#### TKT-001 completion report

- Task ID: `TKT-001`
- Final status: `DONE`
- Owner: Unassigned
- Goal achieved: Replaced the Walking Skeleton-owned Ticket create path with a dedicated final Ticket API/service/repository boundary providing transactional create, scoped paginated list, safe detail and the v0.1 dual message/resume contract, while retaining the explicit separate Agent Run trigger and introducing no hidden run creation; the reviewer approved the implementation and all acceptance criteria.
- Files/modules changed: New `backend/apps/support_api/tickets/{contracts,rate_limit,repository,router,service}.py`; backend application composition; Walking Skeleton contracts/router/service plus repository compatibility import; Ticket test fakes and contract tests; Walking Skeleton regression tests; DB-001A repository compatibility harness; and this task status/report in `docs/TASKS.md`.
- Contract/schema impact: Implements final `POST/GET /api/v1/tickets`, `GET /api/v1/tickets/{id}` and `POST /api/v1/tickets/{id}/messages` behavior over the existing DB-001A tables. Omitted/empty attachment references follow the normal path; any non-empty list returns exact `422 ATTACHMENTS_NOT_SUPPORTED`, `retryable=false`, before persistence, limiter consumption or resume. Valid messages commit before the resume port; message-only returns `201`, same-run resume and missing-invariant paths return `200`, and timeout returns `504 WORKFLOW_REQUEST_TIMEOUT` while retaining the message and escalating the Ticket. No attachment, workflow, audit or idempotency table was added.
- Migrations created (if authorized): None. TKT-001 uses only the reviewer-approved final-named `support.support_tickets` and `support.ticket_messages` DB-001A contract.
- Tests added/updated: Added Ticket API/service contract coverage for create/replay/conflict/no-auto-run, pagination, staff/customer ownership, safe detail projection, omitted/empty/non-empty attachments, message replay/conflict, rate limiting, same-run resume, missing-resume invariant and timeout persistence; updated Walking Skeleton and DB-001A repository regressions for the final Ticket owner.
- Required context loaded: This `TKT-001` task section; `docs/API_CONTRACT.md` §5, §7, §11, §12, §13 and §17; `docs/DATABASE_DESIGN.md` §6.3, §6.4, §7.11 and §14; `docs/AGENT_WORKFLOW.md` §9, §11.1, §11.2 and §12; `docs/SECURITY.md` §6, §14 and §20.
- Additional context loaded and reasons: Direct dependency completion reports for `AUTH-001`, `DB-001A` and `SKEL-001`; only API_CONTRACT §1 and §6 for the public prefix, per-response correlation and exact page/page-size convention omitted from the required sections; completion template/command catalog; current Ticket/auth/application composition, final DB-001A migrations, affected tests and the direct dependent-ID rows needed for a scoped implementation and handoff.
- Dependency completion reports reviewed: `AUTH-001`, `DB-001A` and `SKEL-001`; all are reviewer-approved with final status `DONE`, no blocking PLAN deviation, and provide authenticated customer scope, final Ticket/message tables and the explicit Walking Skeleton run boundary.
- Context intentionally not loaded: Entire `docs/PLAN.md`; unrelated document sections and task reports; frontend implementation; Mock-Commerce; Gemini/RAG/LangGraph node implementation; production approval/action; attachment storage/upload; and every later task implementation area.
- Commands run and results: Initial targeted Ruff/Mypy surfaced and then cleared import/typing issues; targeted Ticket/Walking Skeleton contract tests PASS (10); final Ruff PASS for backend and the affected infrastructure harness; strict Mypy PASS (43 source files); full backend tests PASS (53); `git diff --check` PASS; attachment/network, checkpoint/CoT and commerce-access scans PASS with zero matches. A Docker availability probe could not reach `DockerDesktopLinuxEngine`, so no optional Compose/real-PostgreSQL rerun was possible; `CMD-COMPOSE` is not a required TKT-001 command, while the required `CMD-BE-QUALITY` and local `CMD-CONTRACT` Ticket/message subset passed.
- Security checks: Customer reads/writes are scoped by authenticated user plus customer ID and return indistinguishable `TICKET_NOT_FOUND` outside scope; staff receives only safe projections; write limiting is principal/operation scoped; in-memory replay keys are SHA-256 fingerprints and database idempotency keys are scoped SHA-256 values; repository SQL is static/parameterized and uses only `support`; attachment values are never stored, fetched or interpreted; public responses contain no checkpoint, chain-of-thought, token or secret.
- Acceptance criteria evidence: Ticket and first message share one repository transaction and create never calls the resume/run boundary; scoped list/detail and idempotent replay/conflict tests pass; both valid attachment-empty forms persist normally; non-empty attachment tests prove exact rejection with unchanged messages and no resume; same key produces one message and one resume; missing checkpoint/invariant keeps the message, creates no run and escalates; timeout keeps the message, escalates and replays the same typed failure without a second resume.
- Risks/limitations remaining: The real same-run workflow adapter, run `FAILED` transition and audit event are intentionally owned by later workflow/audit tasks; the default port therefore treats a waiting Ticket without that adapter as the documented invariant failure and never creates a run. Exact response replay is process-local until `DB-001B3` supplies approved durable response storage; DB-level resource replay still prevents duplicate Ticket/message persistence after restart. Per-request `correlation_id` is intentionally fresh on HTTP replay. Docker Desktop was unavailable, so the updated PostgreSQL compatibility harness was type/lint checked but not rerun against a live database in this task session.
- Deviations from PLAN: None. Durable exact response persistence and workflow/audit state are staged behind their declared later database/workflow tasks rather than being implemented early by TKT-001.
- Follow-up tasks unblocked: Reviewer approval is recorded and `TKT-001` is now `DONE`; its dependency edge is satisfied for `AG-001`, `AG-003`, `WEB-001`, `E2E-001C`, `E2E-001D` and `SEC-001`, whose remaining dependencies still apply. None was started.

## 8. Phase 4 — Mock-Commerce and Order Resolution

### DB-002A — UC-01 commerce schema

- **Metadata:** Phase 4; size `M`; milestone `v0.1-foundation`; status `DONE`; Owner: Unassigned.
- **Goal:** Add the exact physical seven-table commerce persistence contract required by UC-01.
- **In scope:** `customers/products/orders/order_items/payments/idempotency_records/audit_logs`, named enums, UUID/TIMESTAMPTZ/NUMERIC(18,2)/uppercase CHAR(3), customer-scoped indexes, partial transaction uniqueness, RESTRICT FKs, expected versions and append-only grants.
- **Out of scope:** Shipping, refund, warranty, support imports or cross-schema FK.
- **Modules/files:** Mock-Commerce models, commerce migration and DB tests.
- **Input → output:** Internal HTTP data contract → isolated transactional commerce schema.
- **Dependencies:** `DB-000`, `INF-001`, `SKEL-001`.
- **Required reading:**
  - `docs/DATABASE_DESIGN.md` — §3 `Schema ownership và roles`; §9 `Commerce schema cho UC-01 (DB-002A)`; §12 `Transaction boundaries`; §13 `Locking strategy`; §14 `Idempotency storage`; §18 `Migration strategy`.
  - `docs/ARCHITECTURE.md` — §10 `Mock-Commerce boundary`; §11 `PostgreSQL ownership`; §12 `HTTP-only commerce access rule`.
  - `docs/SECURITY.md` — §6 `Customer isolation`; §7 `Cross-schema isolation`; §8 `Mock-Commerce boundary`; §16 `PII and synthetic-data-only rule`.
- **Acceptance criteria:** Exact DATABASE_DESIGN/PLAN columns/types/enums/checks/indexes/FKs; unique order number and non-null transaction ref; orders/payments increment version exactly once; sync state+idempotency+audit atomic; no cross-schema FK; support runtime denied.
- **Required tests/commands:** `CMD-COMMERCE-MIGRATE`, constraint/grant tests.
- **Security:** No card data; `commerce_app` only; no support schema privilege.
- **Risks:** FK/index order, cross-schema leak, status/version mismatch.
- **Review checklist:** [x] exact physical schema [x] no extra UC tables [x] constraints/indexes/FK behavior [x] grants/immutability [x] transaction tests.
- **Completion report:** Use §11 with `Task ID: DB-002A`.

#### DB-002A completion report

- Task ID: `DB-002A`
- Final status: `DONE`
- Owner: Unassigned
- Goal achieved: Added the first commerce-domain revision and exact seven-table UC-01 persistence contract, with commerce-owned SQLAlchemy metadata, named enums, constrained money/currency/synthetic fields, customer-scoped indexes, same-schema `RESTRICT` foreign keys, optimistic versions, partial transaction-reference uniqueness, append-only idempotency/audit grants and isolated PostgreSQL verification. The reviewer approved the implementation and all acceptance criteria.
- Files/modules changed: New `backend/apps/mock_commerce_api/persistence/models.py` and package markers; commerce Alembic metadata wiring and `infrastructure/migrations/commerce/versions/0001_db002a_commerce.py`; static migration/model tests; real PostgreSQL integration harness; reverse import-boundary test; `infrastructure/README.md`; and this task status/report in `docs/TASKS.md`.
- Contract/schema impact: Creates only `commerce.customers`, `products`, `orders`, `order_items`, `payments`, `idempotency_records` and `audit_logs`; six named commerce enums; documented UUID/TIMESTAMPTZ/NUMERIC(18,2)/uppercase CHAR(3) columns; exact unique/check/index/FK behavior; and no cross-schema relation. `orders` and `payments` alone carry optimistic `version`; non-null payment transaction references are uniquely indexed; idempotency and audit rows are runtime append-only. No seed, support object, endpoint or UC-02+ table was added.
- Migrations created (if authorized): `0001_db002a_commerce`, the authorized first commerce-domain revision with `down_revision=None`. It runs only as `commerce_owner`, upgrades/downgrades transactionally, leaves the final head at `0001_db002a_commerce`, and fully removes its seven tables and six enums on downgrade.
- Tests added/updated: Added seven static metadata/migration contract tests plus a real PostgreSQL round-trip harness covering exact tables/columns/types/enums/indexes/FKs, unique and check constraints, customer isolation, support-role denial, append-only grants, expected-version one-winner updates, stale-version zero-row behavior, atomic state/idempotency/audit commit and rollback-on-conflict; added Mock-Commerce-to-Support import isolation coverage.
- Required context loaded: This `DB-002A` task section; `docs/DATABASE_DESIGN.md` §3, §9, §12, §13, §14 and §18; `docs/ARCHITECTURE.md` §10, §11 and §12; `docs/SECURITY.md` §6, §7, §8 and §16.
- Additional context loaded and reasons: Direct dependency completion reports for `DB-000`, `INF-001` and `SKEL-001`; command catalog/completion template; current commerce Alembic shell, bootstrap/default grants, Compose credential wiring, Phase-1 Mock-Commerce health process, existing migration-test patterns and infrastructure README needed to add the first commerce revision without replacing valid configuration; direct dependent-ID rows only for handoff.
- Dependency completion reports reviewed: `DB-000`, `INF-001` and `SKEL-001`; all are reviewer-approved with final status `DONE`, no blocking PLAN deviation, and provide the isolated owner/runtime roles, extension-enabled commerce migration shell and first-domain-migration ownership sequence required by DB-002A. TKT-001 was separately confirmed `DONE` as requested but is not a direct DB-002A dependency.
- Context intentionally not loaded: Entire `docs/PLAN.md`; non-required document sections and unrelated task reports; SupportPilot implementation; commerce authentication/API/seed/order/payment services; shipping/refund/warranty/claim flows; and all later tasks.
- Commands run and results: Static Ruff PASS; strict Mypy PASS (47 source files); DB-002A static tests PASS (7); final full backend tests PASS (61); Docker Engine 29.4.0 available after starting the installed Docker Desktop; isolated `supportpilot-db002a` PostgreSQL/bootstrap/migration build and startup PASS; final expanded migration downgrade/upgrade round trip PASS; exact physical/constraint/grant/transaction integration PASS; commerce Alembic `heads` and `current` both `0001_db002a_commerce`; `git diff --check` PASS; scope/import/security scans PASS; isolated containers/network/volume cleanup PASS.
- Security checks: Migration and metadata contain no support reference, cross-schema FK, seed, real PII, PAN/CVV/provider secret or UC-02+ object; every fixture is deterministic synthetic `.test` data used only inside the disposable harness; `support_app` is denied commerce schema usage and `commerce_app` is denied support; owner credential remains migration-only; all SQL is static/parameterized; audit/idempotency runtime UPDATE/DELETE privileges are absent; Mock-Commerce source cannot import SupportPilot runtime modules.
- Acceptance criteria evidence: Catalog assertions prove exactly seven domain tables, six enums and the documented physical types; all six FK constraints target `commerce` and report `ON DELETE RESTRICT`; unique order number, customer-scoped indexes, composite payment ownership and partial transaction-ref uniqueness are exercised; invalid currency/amount/version/synthetic/status/action/operation writes fail; order/payment expected-version updates return version 2 exactly once and stale expected version returns zero rows; injected idempotency conflict rolls back both state versions and audit insert; runtime grant probes independently enforce both schema isolation and append-only history.
- Risks/limitations remaining: DB-002A intentionally provides persistence only. Synthetic seed profiles, internal authentication, order/payment HTTP APIs and production synchronization logic remain owned by their declared later tasks. Product normalization fixtures are structurally supported but the normalization algorithm belongs to seed/service work. The destructive downgrade/upgrade harness must continue to run only against its disposable Compose project.
- Deviations from PLAN: None. Real PostgreSQL testing required explicitly qualifying extension-owned `public.citext` and `public.gin_trgm_ops` because the approved commerce migration search path remains locked to `commerce, pg_catalog`; isolation was preserved rather than widened.
- Follow-up tasks unblocked: Reviewer approval is recorded and DB-002A is now `DONE`; its dependency edge is satisfied for `SEED-001`, `MOCK-ORD-001` and `MOCK-PAY-001`, whose remaining dependencies still apply. None was started.

### SEED-001 — Synthetic UC-01 seed profile

- **Metadata:** Phase 4; size `S`; milestone `v0.1-foundation`; status `IN_REVIEW`; Owner: Unassigned.
- **Goal:** Create repeatable `payment-mismatch-v01` support/commerce/policy/evaluation fixtures.
- **In scope:** Fixed IDs/checksums, roles/customer/orders/payments/policies/ambiguity/isolation/failure fixtures and idempotent seed.
- **Out of scope:** Real data or UC-02+ fixtures for implementation.
- **Modules/files:** Seed scripts and test fixtures.
- **Input → output:** Fixed seed profile → reproducible local dataset; second run no duplicates.
- **Dependencies:** `DB-001A`, `DB-002A`.
- **Required reading:**
  - `docs/PROJECT_SPEC.md` — §13.1 `UC-01 success path`; §13.2 `UC-01 conservative paths`; §14 `Assumptions`; §16 `Release criteria v0.1`.
  - `docs/DATABASE_DESIGN.md` — §6 `Support identity, Ticket và Message (DB-001A)`; §9 `Commerce schema cho UC-01 (DB-002A)`; §19 `Seed strategy`.
  - `docs/RAG_DESIGN.md` — §6 `Metadata contract`; §23 `Evaluation dataset split`; §28 `Required tests`.
  - `docs/SECURITY.md` — §16 `PII and synthetic-data-only rule`.
- **Acceptance criteria:** All fixtures listed in PLAN §23; synthetic markers; version/checksum stable.
- **Required tests/commands:** Seed twice under `CMD-COMPOSE`; checksum and duplicate smoke tests.
- **Security:** No real PII/payment secret; cross-customer isolation fixture intentional and masked.
- **Risks:** Insufficient edge cases, non-idempotent seed, accidental sensitive sample data.
- **Review checklist:** [ ] synthetic only [ ] fixed IDs/checksums [ ] repeatability [ ] required cases [ ] no extra UC.
- **Completion report:** Use §11 with `Task ID: SEED-001`.

#### SEED-001 completion report

- Task ID: `SEED-001`
- Final status: `IN_REVIEW`
- Owner: Unassigned
- Goal achieved: Created the deterministic synthetic `payment-mismatch-v01` profile with fixed identities and commerce IDs, idempotent support/commerce runtime-role upserts, active/expired/conflicting Markdown policy fixtures, all required conservative-path scenario fixtures, and an exactly 25-case versioned golden dataset split into 15 calibration and 10 locked holdout cases.
- Files/modules changed: New `backend/seeds/payment_mismatch_v01` seed package and versioned fixtures; `backend/tests/test_seed_profile.py`; `infrastructure/tests/run_seed001_integration.py`; the Compose `seed-profile` job; seed usage in `infrastructure/README.md`; and this task status/report in `docs/TASKS.md`.
- Contract/schema impact: No table, enum, constraint, index or migration was created or changed. The seed uses separate `support_app` and `commerce_app` connections with no cross-schema query. It upserts three fixed support users, one verified support customer, two synthetic commerce customers, one synthetic product, three scoped orders/items and one succeeded payment; policy/scenario/evaluation fixtures remain versioned files for their owning later tasks. No Ticket, idempotency record or audit record is seeded.
- Migrations created (if authorized): None; SEED-001 runs only after the existing DB-001A and DB-002A heads.
- Tests added/updated: Added six static profile tests for locked identity/version/checksum, fixed unique IDs, policy metadata, exact golden split/strata, conservative scenario coverage, connection isolation and sensitive-data exclusions; added a real PostgreSQL harness that seeds twice and compares profile/database snapshots for stable checksums and zero duplicates.
- Required context loaded: This `SEED-001` task section; `docs/PROJECT_SPEC.md` §13.1, §13.2, §14 and §16; `docs/DATABASE_DESIGN.md` §6, §9 and §19; `docs/RAG_DESIGN.md` §6, §23 and §28; `docs/SECURITY.md` §16.
- Additional context loaded and reasons: `docs/PLAN.md` §23 only because the acceptance criteria directly require every fixture listed there; existing support/commerce migrations and commerce metadata to target exact final columns without schema changes; current Compose/Dockerfile/bootstrap grants and infrastructure README to add an isolated runtime-role seed command without replacing valid infrastructure; auth repository/service only to preserve the established demo-login identity and Argon2 contract.
- Dependency completion reports reviewed: `DB-001A` and `DB-002A`; both are reviewer-approved with final status `DONE`, no blocking PLAN deviation, and expose the final support identity/Ticket and seven-table commerce contracts required by the profile.
- Context intentionally not loaded: The rest of `docs/PLAN.md`; unrelated documentation sections and task reports; frontend implementation; internal Mock-Commerce HTTP implementation; knowledge database/indexing implementation; LangGraph, production approval/action and UC-02–UC-07 implementation.
- Commands run and results: Targeted Ruff PASS; final full Ruff PASS; targeted seed tests PASS (6); final full backend tests PASS (67); targeted Mypy PASS (5 files) and full backend Mypy PASS (51 source files); Compose config PASS; isolated `supportpilot-seed001` PostgreSQL bootstrap and both migration heads PASS; final Compose seed pass 1 and pass 2 emitted identical profile version/counts/checksum `sha256:461c806e4d4ecbcbcde3423ca31ad70b68d90fcbb8b696db6d20b13a978daf61`; PostgreSQL checksum/duplicate harness PASS with `repeatable=true`, `duplicate_free=true` and snapshot checksum `5dd4a9fce7a110fc18fbdb5ff1a959d7b02b05e29201df0e13fe91783d0003e2`; scope/security scans PASS; `git diff --check` PASS. Both disposable Compose test projects and their volumes/networks were removed.
- Security checks: All identities use `.test` addresses and fixed synthetic markers; the known local demo password is stored only as an Argon2 hash; no real PII, PAN, CVV, card/provider token, bearer token value or raw payment secret is present; seed output contains only profile/checksum/count metadata; support and commerce SQL are isolated by separate runtime connections; the intentional other-customer order is referenced only by a masked fixed identifier for denial testing.
- Acceptance criteria evidence: The locked manifest and SHA-256 test prove stable profile version/checksum and fixed IDs; catalog-constrained PostgreSQL writes prove all database rows remain synthetic; policy fixtures cover active, expired and conflict states with required metadata; scenarios cover success, ambiguity, isolation, timeout, stale order, duplicate retry, approval expiry, material edit and possible-write `UNKNOWN`; golden tests prove exactly 15 calibration plus 10 locked holdout cases with retrieval ground truth; identical second-run summary and database snapshot prove idempotency and no duplicate rows.
- Risks/limitations remaining: The fixed reference timestamp is intentional deterministic fixture data, so later time-window resolution tests must use the profile reference clock. Policy files are not ingested until `KB-001`; scenario and golden fixtures are not execution/evaluation evidence until their owning workflow/RAG/evaluation tasks consume them. Seed upserts restore profile-owned mutable fields to their fixed baseline and therefore should remain a local synthetic/demo command only.
- Deviations from PLAN: None.
- Follow-up tasks unblocked: After reviewer approval and a separate `DONE` transition, SEED-001 will satisfy its dependency edge for `MOCK-ORD-001`, `MOCK-PAY-001`, `KB-001` and `EVAL-001`; each task's remaining dependencies still apply. None was started.

### MOCK-AUTH-001 — Internal Bearer authentication boundary

- **Metadata:** Phase 4; size `S`; milestone `v0.1-foundation`; status `TODO`; Owner: Unassigned.
- **Goal:** Enforce the exact authentication and token-isolation contract for `/internal/v1/*`.
- **In scope:** Exact `Authorization: Bearer <INTERNAL_SERVICE_TOKEN>` middleware, SupportPilot adapter contract, validation order, public/internal isolation and redaction.
- **Out of scope:** Token rotation, mTLS, multiple service identities or user authentication changes.
- **Modules/files:** Mock-Commerce core/auth middleware, SupportPilot HTTP adapter contract and security tests.
- **Input → output:** Internal request → valid service context or exact typed auth error before body/ownership lookup.
- **Dependencies:** `FND-001`, `INF-001`.
- **Required reading:**
  - `docs/API_CONTRACT.md` — §1 `API conventions`; §2 `Authentication và authorization`; §3 `Headers`; §8 `Internal Mock-Commerce endpoint catalog`; §17 `Error/status matrix`.
  - `docs/ARCHITECTURE.md` — §10 `Mock-Commerce boundary`; §12 `HTTP-only commerce access rule`; §18 `Runtime containers`.
  - `docs/SECURITY.md` — §8 `Mock-Commerce boundary`; §17 `Secret management`; §18 `Log redaction and no-CoT`; §22 `HTTP service authentication`; §26 `Security test matrix`.
- **Acceptance criteria:** Missing/malformed token → `401 INTERNAL_UNAUTHENTICATED`; wrong token/user JWT → `403 INTERNAL_FORBIDDEN`; valid token succeeds; public API rejects internal token; token absent from frontend/LLM/tool arguments/logs/audit/traces/output.
- **Required tests/commands:** `CMD-CONTRACT`, `CMD-SECURITY`, auth-order and redaction tests.
- **Security:** Environment injection only; constant-time comparison where applicable; never persist raw token.
- **Risks:** Credential crossover, token leakage, auth after ownership validation.
- **Review checklist:** [ ] exact header [ ] 401/403 matrix [ ] validation order [ ] public isolation [ ] redaction.
- **Completion report:** Use §11 with `Task ID: MOCK-AUTH-001`.

### MOCK-ORD-001 — Mock Order HTTP API

- **Metadata:** Phase 4; size `M`; milestone `v0.1-foundation`; status `TODO`; Owner: Unassigned.
- **Goal:** Expose customer-scoped order search/detail/items and sync-payment contract without support imports.
- **In scope:** `/internal/v1` order endpoints, service auth, ownership, expected version, idempotent sync stub/behavior.
- **Out of scope:** Shipping/refund/warranty or direct SupportPilot coupling.
- **Modules/files:** Mock-Commerce API/services/repositories and shared `commerce_contracts` HTTP types.
- **Input → output:** Scoped HTTP request → candidates/detail/version or controlled sync result/error.
- **Dependencies:** `DB-002A`, `SEED-001`, `MOCK-AUTH-001`.
- **Required reading:**
  - `docs/API_CONTRACT.md` — §5 `Idempotency và replay`; §8 `Internal Mock-Commerce endpoint catalog`; §15 `Mock-Commerce payment synchronization`; §17 `Error/status matrix`; §18 `Retry rules`.
  - `docs/DATABASE_DESIGN.md` — §9.3 `commerce.orders`; §9.4 `commerce.order_items`; §9.5 `commerce.payments`; §9.6 `commerce.idempotency_records`; §9.7 `commerce.audit_logs`; §12 `Transaction boundaries`; §13 `Locking strategy`.
  - `docs/ARCHITECTURE.md` — §10 `Mock-Commerce boundary`; §12 `HTTP-only commerce access rule`; §13 `Import dependency rules`.
  - `docs/SECURITY.md` — §6 `Customer isolation`; §8 `Mock-Commerce boundary`; §14 `Idempotency and duplicate prevention`; §22 `HTTP service authentication`.
- **Acceptance criteria:** Other-customer denied; `ORDER_NOT_FOUND/STALE_ORDER/PAYMENT_MISMATCH/APPROVAL_REQUIRED`; same-key write safe.
- **Required tests/commands:** `CMD-CONTRACT`, Mock-Commerce integration/failure tests.
- **Security:** Service token, customer scope, approval ref, no support DB/import.
- **Risks:** Contract drift, idempotency transaction split, data overexposure.
- **Review checklist:** [ ] HTTP-only types [ ] ownership [ ] expected version [ ] write atomicity [ ] redaction.
- **Completion report:** Use §11 with `Task ID: MOCK-ORD-001`.

### MOCK-PAY-001 — Mock Payment HTTP API

- **Metadata:** Phase 4; size `S`; milestone `v0.1-foundation`; status `TODO`; Owner: Unassigned.
- **Goal:** Expose customer-scoped recent payment/status/order-link reads for UC-01.
- **In scope:** Internal customer payments, order payment and payment detail endpoints.
- **Out of scope:** Investigation/refund/duplicate-charge logic or card data.
- **Modules/files:** Mock-Commerce payment API/services/repositories/contracts/tests.
- **Input → output:** Customer/order/date/amount filters → redacted transaction evidence.
- **Dependencies:** `DB-002A`, `SEED-001`, `MOCK-AUTH-001`.
- **Required reading:**
  - `docs/API_CONTRACT.md` — §8 `Internal Mock-Commerce endpoint catalog`; §17 `Error/status matrix`.
  - `docs/DATABASE_DESIGN.md` — §9.5 `commerce.payments`; §12 `Transaction boundaries`; §13 `Locking strategy`.
  - `docs/SECURITY.md` — §6 `Customer isolation`; §8 `Mock-Commerce boundary`; §16 `PII and synthetic-data-only rule`; §18 `Log redaction and no-CoT`; §22 `HTTP service authentication`.
- **Acceptance criteria:** Customer scope enforced; status/amount/currency/ref/time available; no PAN/CVV/secret.
- **Required tests/commands:** `CMD-CONTRACT`, payment ownership/redaction tests.
- **Security:** Service auth and least response data; no support import.
- **Risks:** Cross-customer leakage, payment secret exposure, inconsistent order link.
- **Review checklist:** [ ] scope [ ] schema [ ] redaction [ ] errors [ ] import boundary.
- **Completion report:** Use §11 with `Task ID: MOCK-PAY-001`.

### RES-001 — Deterministic Order Resolution

- **Metadata:** Phase 4; size `M`; milestone `v0.1-foundation`; status `TODO`; Owner: Unassigned.
- **Goal:** Resolve UC-01 order without order ID using customer-scoped candidates and reproducible scoring.
- **In scope:** 30/90-day search, normalization/fuzzy matching, component score, ≥85/margin15 and 60–84 branches, safe clarification.
- **Out of scope:** RAG, LLM customer selection or cross-customer/global search.
- **Modules/files:** Support resolution service + HTTP ports and tests.
- **Input → output:** Entities + verified customer → resolved order, masked clarification or typed manual result.
- **Dependencies:** `MOCK-ORD-001`, `MOCK-PAY-001`.
- **Required reading:**
  - `docs/PROJECT_SPEC.md` — §13.1 `UC-01 success path`; §13.2 `UC-01 conservative paths`.
  - `docs/AGENT_WORKFLOW.md` — §6 `Node contracts v0.1`; §8 `Conditional routing`; §9 `Clarification và same-run message resume`; §22 `Test scenarios`.
  - `docs/API_CONTRACT.md` — §8 `Internal Mock-Commerce endpoint catalog`.
  - `docs/SECURITY.md` — §6 `Customer isolation`; §11 `Tool misuse protection`.
- **Acceptance criteria:** Score components persisted/reproducible; all §11.5 scenarios; customer isolation.
- **Required tests/commands:** `CMD-BE-QUALITY`, resolution unit/integration tests.
- **Security:** Backend-injected customer; masked candidates; no addresses/phones/payment details.
- **Risks:** Wrong-order auto selection, fuzzy-match bias, threshold edge errors.
- **Review checklist:** [ ] deterministic score [ ] thresholds/margin [ ] isolation [ ] masked UX [ ] edge tests.
- **Completion report:** Use §11 with `Task ID: RES-001`.

## 9. Phase 5 — Knowledge Base and RAG

### DB-001C — Knowledge index-version and embedding provenance schema

- **Metadata:** Phase 5; size `M`; milestone `v0.1-foundation`; status `TODO`; Owner: Unassigned.
- **Goal:** Persist exact physical document/index-version/chunk contract with atomic active-index pointer.
- **In scope:** Named enums; `knowledge_documents`, `knowledge_index_versions`, `knowledge_chunks`; `vector(384)`, FTS, composite FKs, lifecycle/scope uniqueness, immutable provenance and failure state.
- **Out of scope:** PDF/OCR, encryption or alternate vector store.
- **Modules/files:** Support knowledge migration/models/repositories.
- **Input → output:** Exact E5 contract → versioned reindexable schema.
- **Dependencies:** `DB-000`, `INF-001`, `SKEL-001`.
- **Required reading:**
  - `docs/DATABASE_DESIGN.md` — §8 `Knowledge và embedding provenance (DB-001C)`; §16 `Knowledge versioning`; §18 `Migration strategy`.
  - `docs/RAG_DESIGN.md` — §12 `Embedding provenance`; §13 `PostgreSQL storage`; §19 `Policy lifecycle and versioning`; §22 `Reindex and recalibration rules`.
  - `docs/SECURITY.md` — §10 `Indirect prompt injection from policy`; §19 `Audit logging`; §20 `Upload and MIME validation`.
- **Acceptance criteria:** Exact columns/types/enums/checks/indexes; active pointer references completed index of same document; provider/model/revision/dimension/input-format/index persisted on parent/chunk; failure leaves active pointer; chunks/terminal provenance immutable; calibration reset path.
- **Required tests/commands:** `CMD-SUPPORT-MIGRATE`, pgvector/FTS repository/provenance tests.
- **Security:** Markdown synthetic/admin-managed; no cross-schema relation.
- **Risks:** Vector dimension/revision mismatch, ambiguous index swap, missing provenance.
- **Review checklist:** [ ] vector(384) [ ] exact provenance [ ] lifecycle/version [ ] indexes [ ] migration tests.
- **Completion report:** Use §11 with `Task ID: DB-001C`.

### KB-001 — Markdown ingestion and E5 indexing

- **Metadata:** Phase 5; size `M`; milestone `v0.1-foundation`; status `TODO`; Owner: Unassigned.
- **Goal:** Validate/parse/chunk/embed/publish Markdown with exact tokenizer/input-format contract.
- **In scope:** MIME/UTF-8/2MB/checksum/metadata, section parsing, 450-target/75-overlap budget, E5 query/passage provenance and atomic publish.
- **Out of scope:** PDF/DOCX/OCR, arbitrary URL fetch or release calibration selection.
- **Modules/files:** Support KB/RAG ingestion adapters/services/tests.
- **Input → output:** Valid Markdown + metadata → versioned chunks/index or typed rejection.
- **Dependencies:** `DB-001C`, `SEED-001`.
- **Required reading:**
  - `docs/RAG_DESIGN.md` — §4 `Supported format và ingestion boundary` through §13 `PostgreSQL storage`; §19 `Policy lifecycle and versioning`; §27 `Security considerations`; §28 `Required tests`.
  - `docs/API_CONTRACT.md` — §7 `Public endpoint catalog`; §16 `Knowledge contracts`; §17 `Error/status matrix`.
  - `docs/SECURITY.md` — §9 `Prompt injection`; §10 `Indirect prompt injection from policy`; §20 `Upload and MIME validation`; §24 `Explicitly prohibited capabilities`.
  - `docs/DATABASE_DESIGN.md` — §8 `Knowledge và embedding provenance (DB-001C)`; §16 `Knowledge versioning`.
- **Acceptance criteria:** Whole passage within exact context; title/heading shrink content; input-format change reindexes/recalibrates.
- **Required tests/commands:** `CMD-BE-QUALITY`, parser/tokenizer/MIME/security/reindex tests.
- **Security:** Treat policy as untrusted; isolated parser; admin-only; no tool instruction execution.
- **Risks:** Token miscount, silent truncation, injection, partial publish.
- **Review checklist:** [ ] exact prefixes [ ] exact revision/tokenizer [ ] limits [ ] atomic lifecycle [ ] security tests.
- **Completion report:** Use §11 with `Task ID: KB-001`.

### KB-002 — Synchronous knowledge reindex

- **Metadata:** Phase 5; size `M`; milestone `v0.1-foundation`; status `TODO`; Owner: Unassigned.
- **Goal:** Deliver the exact synchronous, idempotent and atomic reindex API contract.
- **In scope:** `POST /api/v1/knowledge/documents/{id}/reindex`, `200` provenance response, 120-second budget, index attempt lifecycle, atomic pointer swap, replay and calibration reset.
- **Out of scope:** Queue, `202`, job/polling endpoint, auto-publish, PDF/OCR or lifecycle expansion.
- **Modules/files:** Support knowledge API/service/repositories and failure/idempotency tests.
- **Input → output:** Admin request + key → exact `200` result or documented typed error while preserving active index.
- **Dependencies:** `KB-001`, `DB-001C`, `AUTH-001`.
- **Required reading:**
  - `docs/RAG_DESIGN.md` — §12 `Embedding provenance`; §13 `PostgreSQL storage`; §19 `Policy lifecycle and versioning`; §22 `Reindex and recalibration rules`; §26 `Environment contract`.
  - `docs/API_CONTRACT.md` — §5 `Idempotency và replay`; §16.1 `Synchronous reindex`; §17 `Error/status matrix`.
  - `docs/DATABASE_DESIGN.md` — §8 `Knowledge và embedding provenance (DB-001C)`; §12 `Transaction boundaries`; §16 `Knowledge versioning`.
  - `docs/SECURITY.md` — §5 `Authorization and RBAC`; §10 `Indirect prompt injection from policy`; §19 `Audit logging`; §20 `Upload and MIME validation`.
- **Acceptance criteria:** `DRAFT/VALIDATED/PUBLISHED` status unchanged; published old index active until new index validates/completes; atomic swap; failure/timeout persists failed attempt and preserves pointer; replay avoids rebuild; config/scoring change sets calibration false; exact response/error/status/retryable contract; never `202`/queue/polling.
- **Required tests/commands:** `CMD-BE-QUALITY`, `CMD-CONTRACT`, PostgreSQL failure-injection/idempotency tests.
- **Security:** Admin only; no arbitrary source fetch; no secret/raw content in response/error/audit.
- **Risks:** Non-atomic pointer, partial chunks served, timeout rollback hiding failed attempt.
- **Review checklist:** [ ] exact 200 body [ ] lifecycle unchanged [ ] atomic/failure path [ ] replay [ ] recalibration.
- **Completion report:** Use §11 with `Task ID: KB-002`.

### RAG-001 — Deterministic hybrid retrieval

- **Metadata:** Phase 5; size `M`; milestone `v0.1-foundation`; status `TODO`; Owner: Unassigned.
- **Goal:** Implement metadata-first exact vector+FTS retrieval, RRF ranking and calibrated evidence gates.
- **In scope:** Vector top10, FTS top10, dedupe, RRF k=60, vector/lexical gates, top5 citations, conflict/no-answer/provenance.
- **Out of scope:** Reranker, BM25 service, Qdrant or arbitrary threshold lowering.
- **Modules/files:** Support retrieval/embedding adapter and tests.
- **Input → output:** Query + filters → gated citations/conflict/no-answer with branch scores/provenance.
- **Dependencies:** `KB-001`.
- **Required reading:**
  - `docs/RAG_DESIGN.md` — §6 `Metadata contract`; §9 `Exact tokenizer and embedding configuration` through §18 `Citation schema`; §20 `Policy conflict` through §25 `Metrics and release artifact`; §28 `Required tests`.
  - `docs/DATABASE_DESIGN.md` — §8.3 `support.knowledge_chunks`; §16 `Knowledge versioning`.
  - `docs/SECURITY.md` — §9 `Prompt injection`; §10 `Indirect prompt injection from policy`; §11 `Tool misuse protection`; §18 `Log redaction and no-CoT`.
- **Acceptance criteria:** All seven mandatory RAG cases; RRF never confidence; `0.72` treated as meaningless release placeholder for new e5-small model and recalibrated from scratch on the 15-case calibration set; deterministic tie-break; no calibrated flag without matching artifact.
- **Required tests/commands:** `CMD-BE-QUALITY`, RAG repository/integration test subset.
- **Security:** Server-controlled metadata/effective filters; injection cannot bypass gate/version/conflict.
- **Risks:** False evidence, score semantics confusion, threshold overfit.
- **Review checklist:** [ ] branch top10 [ ] dedupe/RRF [ ] gates before evidence [ ] top5 [ ] seven cases.
- **Completion report:** Use §11 with `Task ID: RAG-001`.

### TOOL-001 — UC-01 Tool Registry and read adapters

- **Metadata:** Phase 5; size `M`; milestone `v0.1-foundation`; status `TODO`; Owner: Unassigned.
- **Goal:** Provide allowlisted typed read tools with scope, internal-token-injecting HTTP adapter, deadline, retries and audit records.
- **In scope:** Customer/order/payment/policy tools, schema validation, permission tiers, exact Bearer adapter injection/redaction and per-attempt records.
- **Out of scope:** Business write implementation or arbitrary/dynamic tools.
- **Modules/files:** Support tool registry and integration adapters/contracts/tests.
- **Input → output:** Validated tool request → redacted result/tool-call record or typed error.
- **Dependencies:** `MOCK-AUTH-001`, `MOCK-ORD-001`, `MOCK-PAY-001`, `RAG-001`.
- **Required reading:**
  - `docs/AGENT_WORKFLOW.md` — §6 `Node contracts v0.1`; §8 `Conditional routing`; §15 `Tool failure`; §20 `Event persistence`.
  - `docs/API_CONTRACT.md` — §8 `Internal Mock-Commerce endpoint catalog`; §15 `Mock-Commerce payment synchronization`; §17 `Error/status matrix`; §18 `Retry rules`.
  - `docs/ARCHITECTURE.md` — §8 `Tool Registry boundary`; §12 `HTTP-only commerce access rule`; §13 `Import dependency rules`; §14 `Module dependency guide`.
  - `docs/SECURITY.md` — §8 `Mock-Commerce boundary`; §11 `Tool misuse protection`; §17 `Secret management`; §22 `HTTP service authentication`; §24 `Explicitly prohibited capabilities`.
- **Acceptance criteria:** LLM cannot select URL/customer/actor/credential; adapter injects token only from env; 401/403 typed failures and token redaction pass; exact timeouts/retry; forbidden tools impossible; import boundary pass.
- **Required tests/commands:** `CMD-BE-QUALITY`, `CMD-CONTRACT`, failure/import tests.
- **Security:** Allowlist, backend scope, no arbitrary HTTP/SQL/filesystem/code, redaction.
- **Risks:** Generic HTTP escape hatch, retry over budget, tool result leakage.
- **Review checklist:** [ ] allowlist only [ ] schemas/scope [ ] deadline/retry [ ] audit [ ] forbidden capability tests.
- **Completion report:** Use §11 with `Task ID: TOOL-001`.

## 10. Phase 6 — LangGraph Agent

### DB-001B1 — Run, checkpoint, event, evidence and tool-call persistence

- **Metadata:** Phase 6; size `M`; milestone `v0.1-foundation`; status `TODO`; Owner: Unassigned.
- **Goal:** Add official PostgreSQL checkpointer integration and exact `agent_runs/agent_run_events/agent_evidence/tool_calls` physical contract.
- **In scope:** Named run/tool/evidence/permission enums, columns/types/checks/indexes, one-nonterminal partial index, event sequence, immutable evidence and retry attempts.
- **Out of scope:** Approval/action/notification/audit/idempotency tables, transition triggers or full AgentState duplicate.
- **Modules/files:** Support workflow/checkpointer migration, repositories and reconciliation tests.
- **Input → output:** DATABASE_DESIGN §7.1–§7.5 → constrained resumable run persistence.
- **Dependencies:** `DB-001A`, `DB-001C`.
- **Required reading:**
  - `docs/DATABASE_DESIGN.md` — §7.1 `LangGraph checkpoint tables` through §7.5 `support.tool_calls`; §10.2 `Agent Run values`; §11 `Checkpoint ownership và reconciliation`; §18 `Migration strategy`.
  - `docs/AGENT_WORKFLOW.md` — §4 `Checkpoint và thread ownership`; §11.2 `Agent Run`; §18 `Checkpoint reconciliation`; §20 `Event persistence`.
  - `docs/SECURITY.md` — §18 `Log redaction and no-CoT`; §19 `Audit logging`.
- **Acceptance criteria:** Exact physical contract; second active run rejected; completed timestamp invariant; event sequence immutable/ordered; policy chunk evidence FK/check; business-write tool fields required; checkpoint keyed by run ID, no copy/CoT; reconciliation repository tests pass.
- **Required tests/commands:** `CMD-SUPPORT-MIGRATE`, PostgreSQL constraint/concurrency/grant/reconciliation tests.
- **Security:** Checkpoint private; state/event/tool/evidence projections redacted; immutable grants enforced.
- **Risks:** Checkpointer schema/transaction drift, FK migration order, false atomicity.
- **Review checklist:** [ ] exact tables/enums [ ] partial index [ ] append-only [ ] checkpoint ownership [ ] reconciliation.
- **Completion report:** Use §11 with `Task ID: DB-001B1`.

### DB-001B2 — Approval, action and notification persistence

- **Metadata:** Phase 6; size `M`; milestone `v0.1-foundation`; status `TODO`; Owner: Unassigned.
- **Goal:** Add exact `approval_requests/approval_proposal_versions/action_executions/notifications` contract independently.
- **In scope:** Approval/action/notification enums, immutable version/hash composite FK, 24h expiry fields/indexes, optimistic locks, `UNKNOWN` and verified timestamp invariant.
- **Out of scope:** Run/event/tool/audit/idempotency tables or transition triggers.
- **Modules/files:** Support approval/action migration, repositories and concurrency tests.
- **Input → output:** DATABASE_DESIGN §7.6–§7.9 → constrained approval/action persistence.
- **Dependencies:** `DB-001B1`.
- **Required reading:**
  - `docs/DATABASE_DESIGN.md` — §7.6 `support.approval_requests` through §7.9 `support.notifications`; §10.3 `Approval values`; §10.4 `Action Execution values`; §12 `Transaction boundaries`; §13 `Locking strategy`; §15 `Approval proposal versioning`.
  - `docs/AGENT_WORKFLOW.md` — §10 `Approval interrupt/resume`; §11.3 `Approval`; §11.4 `Action Execution`; §16 `Possible-write UNKNOWN flow`; §17 `Verification flow`.
  - `docs/SECURITY.md` — §12 `Approval security`; §13 `Stale approval and proposal integrity`; §14 `Idempotency and duplicate prevention`; §15 `Possible-write handling`; §19 `Audit logging`.
- **Acceptance criteria:** Exact columns/types/checks/indexes/RESTRICT FKs; current proposal composite reference; proposal versions immutable; material edit actor check; decision row lock/version/hash; one UC-01 execution/approval; `UNKNOWN` never success; only `VERIFIED` has `verified_at`; no cascade.
- **Required tests/commands:** `CMD-SUPPORT-MIGRATE`, PostgreSQL constraint/concurrency tests.
- **Security:** Proposal/payload allowlists and hashes; no credential/raw PII; history retained.
- **Risks:** Circular/composite FK order, stale decision race, accidental mutable proposal.
- **Review checklist:** [ ] exact tables/enums [ ] composite FK [ ] expiry/locks [ ] UNKNOWN/VERIFIED [ ] no cascade.
- **Completion report:** Use §11 with `Task ID: DB-001B2`.

### DB-001B3 — Append-only audit and support idempotency persistence

- **Metadata:** Phase 6; size `S`; milestone `v0.1-foundation`; status `TODO`; Owner: Unassigned.
- **Goal:** Add exact `audit_logs` and generic `idempotency_records` physical contracts and grants.
- **In scope:** Audit result/idempotency scope enums, redacted hash/projection fields, scoped principal fingerprint, request hash, exact response replay, indexes and immutable grants.
- **Out of scope:** Domain workflow tables, retention deletion job or raw token/snapshot persistence.
- **Modules/files:** Support audit/idempotency migration, repositories and grant/replay tests.
- **Input → output:** DATABASE_DESIGN §7.10–§7.11 → durable audit and endpoint replay.
- **Dependencies:** `DB-001A`.
- **Required reading:**
  - `docs/DATABASE_DESIGN.md` — §7.10 `support.audit_logs`; §7.11 `support.idempotency_records`; §14 `Idempotency storage`; §18 `Migration strategy`.
  - `docs/AGENT_WORKFLOW.md` — §20 `Event persistence`; §21 `Audit integration`.
  - `docs/SECURITY.md` — §14 `Idempotency and duplicate prevention`; §18 `Log redaction and no-CoT`; §19 `Audit logging`.
- **Acceptance criteria:** Exact physical contract; update/delete denied; no history FK cascade; same scope/principal/key/hash replays exact status/body; mismatched hash conflicts without execution; knowledge scopes included; no raw token/PII/CoT.
- **Required tests/commands:** `CMD-SUPPORT-MIGRATE`, PostgreSQL grant/idempotency/security tests.
- **Security:** SHA-256 principal fingerprint only; response/details redacted; append-only runtime grants.
- **Risks:** Unsafe response persistence, overbroad grants, scope collision.
- **Review checklist:** [ ] exact scopes [ ] replay/hash conflict [ ] append-only [ ] no history cascade [ ] redaction.
- **Completion report:** Use §11 with `Task ID: DB-001B3`.

### AG-001 — v0.1 graph foundation and explicit run

- **Metadata:** Phase 6; size `M`; milestone `v0.1-foundation`; status `TODO`; Owner: Unassigned.
- **Goal:** Replace FakeAgent with checkpoint-backed v0.1 receive/identity/extraction profile and global deadline.
- **In scope:** Explicit run API/orchestrator, checkpoint/run reconciliation, deterministic UC-01 guard, at-most-one extraction call, 60/5/12 budgets.
- **Out of scope:** Commerce action, RAG proposal completion or classification LLM call.
- **Modules/files:** Support agent state/profile/nodes/API/recovery tests.
- **Input → output:** Ticket → validated payment context or typed unsupported/identity/timeout failure.
- **Dependencies:** `DB-001B1`, `DB-001B3`, `TOOL-001`, `AUTH-001`, `TKT-001`, `SKEL-001`.
- **Required reading:**
  - `docs/AGENT_WORKFLOW.md` — §3 `AgentState contract` through §6 `Node contracts v0.1`; §8 `Conditional routing`; §11.1 `Ticket`; §11.2 `Agent Run`; §12 `Timeout propagation`; §13 `Retry policy`; §14 `Provider failure`; §18 `Checkpoint reconciliation`.
  - `docs/API_CONTRACT.md` — §12 `Explicit Agent Run trigger`; §17 `Error/status matrix`; §18 `Retry rules`.
  - `docs/DATABASE_DESIGN.md` — §7.1 `LangGraph checkpoint tables`; §7.2 `support.agent_runs`; §10.1 `Ticket values`; §10.2 `Agent Run values`; §11 `Checkpoint ownership và reconciliation`.
  - `docs/SECURITY.md` — §6 `Customer isolation`; §9 `Prompt injection`; §18 `Log redaction and no-CoT`; §24 `Explicitly prohibited capabilities`.
- **Acceptance criteria:** Active-run replay/409; no `CANCELLED`; timeout persists `FAILED`/Ticket `ESCALATED`/audit before 504; checkpoint invariant audit.
- **Required tests/commands:** `CMD-BE-QUALITY`, node/API/deadline/recovery tests.
- **Security:** No CoT; no LLM customer/URL; checkpoint not exposed; unsupported intent conservative.
- **Risks:** Cooperative cancellation, checkpoint/run drift, hidden classification call.
- **Review checklist:** [ ] exact profile [ ] explicit trigger [ ] budgets [ ] recovery [ ] no classification.
- **Completion report:** Use §11 with `Task ID: AG-001`.

### AG-002A — Order resolution and business evidence nodes

- **Metadata:** Phase 6; size `M`; milestone `v0.1-foundation`; status `TODO`; Owner: Unassigned.
- **Goal:** Add resolve-order/retrieve-evidence behavior through customer-scoped HTTP tools.
- **In scope:** Candidate resolution, clarification interrupt, order/payment reads and per-tool/event persistence.
- **Out of scope:** RAG/proposal/approval/action.
- **Modules/files:** Agent resolution/evidence nodes and graph/import tests.
- **Input → output:** Extracted state → resolved business evidence or `WAITING_CUSTOMER`/escalation.
- **Dependencies:** `AG-001`, `RES-001`, `MOCK-ORD-001`, `MOCK-PAY-001`.
- **Required reading:**
  - `docs/AGENT_WORKFLOW.md` — §3 `AgentState contract`; §6 `Node contracts v0.1`; §8 `Conditional routing`; §9 `Clarification và same-run message resume`; §15 `Tool failure`; §20 `Event persistence`.
  - `docs/API_CONTRACT.md` — §8 `Internal Mock-Commerce endpoint catalog`; §17 `Error/status matrix`; §18 `Retry rules`.
  - `docs/DATABASE_DESIGN.md` — §7.3 `support.agent_run_events`; §7.4 `support.agent_evidence`; §7.5 `support.tool_calls`; §10 `Status definitions và transition ownership`; §11 `Checkpoint ownership và reconciliation`.
  - `docs/SECURITY.md` — §6 `Customer isolation`; §8 `Mock-Commerce boundary`; §11 `Tool misuse protection`; §18 `Log redaction and no-CoT`.
- **Acceptance criteria:** No commerce repository import; safe clarification; same-run checkpoint state; HTTP retry/deadline respected.
- **Required tests/commands:** `CMD-BE-QUALITY`, graph/integration/import-boundary tests.
- **Security:** Backend customer scope; masked candidates; no global query/data leak.
- **Risks:** Wrong route after clarification, duplicate reads/events, direct import shortcut.
- **Review checklist:** [ ] HTTP-only [ ] score branches [ ] pause state [ ] deadlines [ ] isolation tests.
- **Completion report:** Use §11 with `Task ID: AG-002A`.

### AG-002B — Policy retrieval, evaluation and proposal

- **Metadata:** Phase 6; size `M`; milestone `v0.1-foundation`; status `TODO`; Owner: Unassigned.
- **Goal:** Add gated policy retrieval, deterministic evaluation and grounded proposal generation.
- **In scope:** `retrieve_policy`, `evaluate_and_propose`, evidence sufficiency, immutable proposal inputs and at-most-one grounded LLM call when needed.
- **Out of scope:** Approval persistence, execution or LLM override of rule.
- **Modules/files:** Agent RAG/policy/proposal nodes/services/tests.
- **Input → output:** Business evidence → cited proposal or conservative clarification/escalation.
- **Dependencies:** `AG-002A`, `RAG-001`.
- **Required reading:**
  - `docs/AGENT_WORKFLOW.md` — §3 `AgentState contract`; §6 `Node contracts v0.1`; §8 `Conditional routing`; §10 `Approval interrupt/resume`; §20 `Event persistence`.
  - `docs/API_CONTRACT.md` — §14 `Approval decision contract`; §17 `Error/status matrix`.
  - `docs/DATABASE_DESIGN.md` — §7.4 `support.agent_evidence`; §7.6 `support.approval_requests`; §7.7 `support.approval_proposal_versions`; §10.3 `Approval values`.
  - `docs/RAG_DESIGN.md` — §14 `Deterministic retrieval pipeline` through §22 `Reindex and recalibration rules`.
  - `docs/SECURITY.md` — §10 `Indirect prompt injection from policy`; §11 `Tool misuse protection`; §12 `Approval security`; §13 `Stale approval and proposal integrity`; §18 `Log redaction and no-CoT`.
- **Acceptance criteria:** No-answer/conflict blocks action; action allowlist; deterministic rule persisted; exact citations/provenance.
- **Required tests/commands:** `CMD-BE-QUALITY`, graph/RAG/policy/failure tests.
- **Security:** Policy injection cannot alter tools/scope/approval; no unsupported action.
- **Risks:** LLM overreach, uncalibrated evidence, proposal/hash inconsistency.
- **Review checklist:** [ ] gate before evidence [ ] deterministic eligibility [ ] one grounded call max [ ] immutable proposal [ ] failure routes.
- **Completion report:** Use §11 with `Task ID: AG-002B`.

## 11. Phase 7 — Approval and verified action

### APR-001 — Alpha approval core

- **Metadata:** Phase 7; size `M`; milestone `v0.1-alpha`; status `TODO`; Owner: Unassigned.
- **Goal:** Implement real approve/reject/24h expiry/role/expected version+hash/concurrency path.
- **In scope:** Approval API/repository/service, lazy expiry, row lock, idempotent decision and audit.
- **Out of scope:** Reviewer edit/material classification (`APR-002`).
- **Modules/files:** Support approvals API/service/repository/tests.
- **Input → output:** Immutable proposal → pending/approved/rejected/expired state and validated resume event.
- **Dependencies:** `AG-002B`, `AUTH-001`, `DB-001B2`, `DB-001B3`.
- **Required reading:**
  - `docs/AGENT_WORKFLOW.md` — §10 `Approval interrupt/resume`; §11.3 `Approval`; §12 `Timeout propagation`; §17 `Verification flow`.
  - `docs/API_CONTRACT.md` — §5 `Idempotency và replay`; §14 `Approval decision contract`; §17 `Error/status matrix`; §18 `Retry rules`.
  - `docs/DATABASE_DESIGN.md` — §7.6 `support.approval_requests`; §7.7 `support.approval_proposal_versions`; §13 `Locking strategy`; §14 `Idempotency storage`; §15 `Approval proposal versioning`.
  - `docs/SECURITY.md` — §12 `Approval security`; §13 `Stale approval and proposal integrity`; §14 `Idempotency and duplicate prevention`; §19 `Audit logging`.
- **Acceptance criteria:** Double/stale/expired/unauthorized decision safe; expired never revive; expected version/hash required.
- **Required tests/commands:** `CMD-BE-QUALITY`, approval API/concurrency/expiry tests.
- **Security:** Server role, 24h UTC, hash/version/row lock, audit complete.
- **Risks:** Race, lazy-expiry inconsistency, stale approval acceptance.
- **Review checklist:** [ ] role [ ] expiry [ ] version/hash [ ] idempotency/concurrency [ ] no edit scope.
- **Completion report:** Use §11 with `Task ID: APR-001`.

### ACT-001 — Idempotent payment sync and verification

- **Metadata:** Phase 7; size `M`; milestone `v0.1-alpha`; status `TODO`; Owner: Unassigned.
- **Goal:** Revalidate, execute approved `sync_payment_status`, handle `UNKNOWN` and verify fresh state.
- **In scope:** Approved write tool, Mock Order write, action records, same-key status reconcile/read-back verification.
- **Out of scope:** Refund/other business writes or unapproved retry.
- **Modules/files:** Support write tool/action service, Mock Order sync API and failure tests.
- **Input → output:** Approved current proposal → `VERIFIED` or typed retryable/final/unknown outcome.
- **Dependencies:** `APR-001`, `MOCK-ORD-001`, `MOCK-PAY-001`.
- **Required reading:**
  - `docs/AGENT_WORKFLOW.md` — §10 `Approval interrupt/resume`; §11.4 `Action Execution`; §13 `Retry policy`; §16 `Possible-write UNKNOWN flow`; §17 `Verification flow`.
  - `docs/API_CONTRACT.md` — §8 `Internal Mock-Commerce endpoint catalog`; §14 `Approval decision contract`; §15 `Mock-Commerce payment synchronization`; §17 `Error/status matrix`; §18 `Retry rules`.
  - `docs/DATABASE_DESIGN.md` — §7.8 `support.action_executions`; §9.3 `commerce.orders`; §9.5 `commerce.payments`; §9.6 `commerce.idempotency_records`; §9.7 `commerce.audit_logs`; §12 `Transaction boundaries`; §13 `Locking strategy`.
  - `docs/SECURITY.md` — §12 `Approval security`; §13 `Stale approval and proposal integrity`; §14 `Idempotency and duplicate prevention`; §15 `Possible-write handling`; §22 `HTTP service authentication`.
- **Acceptance criteria:** Revalidate schema/HTTP ownership/rules; atomic commerce idempotency; possible write→`UNKNOWN`; no blind retry.
- **Required tests/commands:** `CMD-BE-QUALITY`, `CMD-CONTRACT`, transaction/idempotency/failure-injection tests.
- **Security:** Approval ref/version/hash, customer scope, stable key, no raw payment secrets.
- **Risks:** Duplicate action, false success, race with stale order, ambiguous network outcome.
- **Review checklist:** [ ] revalidation [ ] same key [ ] atomicity [ ] unknown path [ ] fresh verification.
- **Completion report:** Use §11 with `Task ID: ACT-001`.

### AG-003 — Resume, execute/verify/respond and Ticket transition

- **Metadata:** Phase 7; size `M`; milestone `v0.1-alpha`; status `TODO`; Owner: Unassigned.
- **Goal:** Complete approval/message resume and deterministic terminal flow.
- **In scope:** Fresh-budget resume, execute/verify/respond subgraph, event hooks and domain Ticket transition.
- **Out of scope:** Real email send or reviewer edit implementation.
- **Modules/files:** Agent subgraph/orchestrator/domain services/integration tests.
- **Input → output:** Valid resume event → interruption/terminal outcome with persisted timeline/audit.
- **Dependencies:** `ACT-001`, `APR-001`, `TKT-001`.
- **Required reading:**
  - `docs/AGENT_WORKFLOW.md` — §9 `Clarification và same-run message resume` through §12 `Timeout propagation`; §16 `Possible-write UNKNOWN flow` through §21 `Audit integration`.
  - `docs/API_CONTRACT.md` — §13 `Message same-run resume`; §14 `Approval decision contract`; §15 `Mock-Commerce payment synchronization`; §17 `Error/status matrix`; §18 `Retry rules`.
  - `docs/DATABASE_DESIGN.md` — §7.2 `support.agent_runs`; §7.3 `support.agent_run_events`; §7.6 `support.approval_requests`; §7.8 `support.action_executions`; §10 `Status definitions và transition ownership`; §11 `Checkpoint ownership và reconciliation`; §12 `Transaction boundaries`; §13 `Locking strategy`.
  - `docs/SECURITY.md` — §12 `Approval security`; §13 `Stale approval and proposal integrity`; §14 `Idempotency and duplicate prevention`; §15 `Possible-write handling`; §18 `Log redaction and no-CoT`; §19 `Audit logging`; §22 `HTTP service authentication`.
- **Acceptance criteria:** Message not rolled back on timeout; checkpoint reconciliation; unverified action never resolves; update status not separately approved/LLM-callable.
- **Required tests/commands:** `CMD-BE-QUALITY`, graph integration/timeout/resume/verification tests.
- **Security:** Only validated backend resume events; no checkpoint payload/CoT; response makes no false success claim.
- **Risks:** Double resume, inconsistent checkpoint/status, premature Ticket resolution.
- **Review checklist:** [ ] same-run/fresh budget [ ] approval validation [ ] persist internal steps [ ] verified invariant [ ] failure audit.
- **Completion report:** Use §11 with `Task ID: AG-003`.

### APR-002 — Reviewer edit and reapproval

- **Metadata:** Phase 7; size `S`; milestone `v0.1-beta`; status `TODO`; Owner: Unassigned.
- **Goal:** Complete final reviewer-edit semantics without blocking skeleton/alpha.
- **In scope:** Schema/ownership/rule revalidation, immutable proposal version/hash, material/non-material classification, TTL reset/reapproval.
- **Out of scope:** New action types, bulk approval or bypass of existing approval.
- **Modules/files:** Approval edit service/API/schema/tests.
- **Input → output:** Edited action + expected version/hash → approved non-material result or new pending material version.
- **Dependencies:** `APR-001`, `ACT-001`, `TOOL-001`.
- **Required reading:**
  - `docs/AGENT_WORKFLOW.md` — §10 `Approval interrupt/resume`; §11.3 `Approval`; §17 `Verification flow`.
  - `docs/API_CONTRACT.md` — §14 `Approval decision contract`; §17 `Error/status matrix`.
  - `docs/DATABASE_DESIGN.md` — §7.6 `support.approval_requests`; §7.7 `support.approval_proposal_versions`; §15 `Approval proposal versioning`.
  - `docs/SECURITY.md` — §12 `Approval security`; §13 `Stale approval and proposal integrity`; §19 `Audit logging`.
- **Acceptance criteria:** Target/amount/currency/type material; material resets TTL/reapproves; non-material preserves TTL; stale/invalid edit safe.
- **Required tests/commands:** `CMD-BE-QUALITY`, edit matrix/API/concurrency tests.
- **Security:** Reviewer role, canonical hash/version, HTTP ownership and deterministic business revalidation.
- **Risks:** Misclassification, hash canonicalization drift, approval revival/TTL extension.
- **Review checklist:** [ ] edit matrix [ ] new immutable version [ ] TTL rules [ ] revalidation [ ] final DoD linkage.
- **Completion report:** Use §11 with `Task ID: APR-002`.

## 12. Phase 8 — Full Vue review flow

### WEB-001 — Real login, Ticket and Agent Run UI

- **Metadata:** Phase 8; size `M`; milestone `final-v0.1`; status `TODO`; Owner: Unassigned.
- **Goal:** Replace skeleton demo adapters with real auth/Ticket/create-run/inbox and robust states.
- **In scope:** Login, create Ticket then run, inbox/loading/empty/denied/error, replay/409/504 handling.
- **Out of scope:** Approval controls/evidence-detail UI.
- **Modules/files:** Vue views/stores/services/components/tests.
- **Input → output:** User input/public API → real Ticket/run status visible with unchanged skeleton types.
- **Dependencies:** `SKEL-001`, `FND-002`, `TKT-001`, `AG-002B`.
- **Required reading:**
  - `docs/API_CONTRACT.md` — §1 `API conventions` through §4 `Error envelope`; §7 `Public endpoint catalog`; §10 `Authentication contracts`; §11 `Ticket creation contract`; §12 `Explicit Agent Run trigger`; §17 `Error/status matrix`.
  - `docs/ARCHITECTURE.md` — §5 `Frontend boundary`; §6 `FastAPI application boundary`.
  - `docs/SECURITY.md` — §4 `Authentication threats and controls`; §5 `Authorization and RBAC`; §17 `Secret management`; §18 `Log redaction and no-CoT`.
- **Acceptance criteria:** Explicit two-request sequence; duplicate active/timeout safe UX; no implicit run.
- **Required tests/commands:** `CMD-FE-QUALITY`, component/API mock tests.
- **Security:** Token handling, no frontend-only auth assumption, safe errors/no raw PII.
- **Risks:** Contract drift, duplicate submission, stale client state.
- **Review checklist:** [ ] explicit sequence [ ] loading/errors [ ] replay/409/504 [ ] typed client [ ] accessibility basics.
- **Completion report:** Use §11 with `Task ID: WEB-001`.

### WEB-002 — Ticket detail, evidence and timeline UI

- **Metadata:** Phase 8; size `M`; milestone `final-v0.1`; status `TODO`; Owner: Unassigned.
- **Goal:** Present scoped messages, evidence/citations and polling timeline safely.
- **In scope:** Ticket detail, message send/resume status, masked evidence/citations, timeline cursor polling.
- **Out of scope:** Approval edit controls.
- **Modules/files:** Vue detail/components/stores/services/tests.
- **Input → output:** Safe detail/events APIs → reviewable current Ticket/run state.
- **Dependencies:** `WEB-001`, `AG-003`.
- **Required reading:**
  - `docs/API_CONTRACT.md` — §7 `Public endpoint catalog`; §9.2 `Citation`; §9.3 `Safe run summary`; §13 `Message same-run resume`.
  - `docs/AGENT_WORKFLOW.md` — §9 `Clarification và same-run message resume`; §11.1 `Ticket`; §11.2 `Agent Run`; §20 `Event persistence`.
  - `docs/RAG_DESIGN.md` — §15 `Reciprocal Rank Fusion`; §16 `Evidence confidence gates`; §17 `Final ranking và top 5`; §18 `Citation schema`.
  - `docs/SECURITY.md` — §6 `Customer isolation`; §18 `Log redaction and no-CoT`.
- **Acceptance criteria:** Same-run resume states shown; RRF not labeled confidence; no CoT/checkpoint/raw PII.
- **Required tests/commands:** `CMD-FE-QUALITY`, UI polling/message/citation tests.
- **Security:** Ownership denial UI, safe excerpts/masking, no internal-only payload.
- **Risks:** Poll race/stale cursor, score mislabel, sensitive-data display.
- **Review checklist:** [ ] polling/cursor [ ] resume UX [ ] citation semantics [ ] masking [ ] error/empty states.
- **Completion report:** Use §11 with `Task ID: WEB-002`.

### WEB-003 — Approval/edit/reapproval UI

- **Metadata:** Phase 8; size `M`; milestone `v0.1-beta`; status `TODO`; Owner: Unassigned.
- **Goal:** Deliver final approve/edit/reject/expiry/stale/material reapproval review flow.
- **In scope:** Proposal/evidence/impact display, decision form, version/hash, edit classification outcome and final action result.
- **Out of scope:** Bulk approval or new action type.
- **Modules/files:** Vue approval components/views/stores/services/tests.
- **Input → output:** Approval safe projection → decision/resume result with clear pending/expired/reapproval states.
- **Dependencies:** `WEB-002`, `APR-001`, `APR-002`, `ACT-001`.
- **Required reading:**
  - `docs/API_CONTRACT.md` — §7 `Public endpoint catalog`; §14 `Approval decision contract`; §17 `Error/status matrix`.
  - `docs/AGENT_WORKFLOW.md` — §10 `Approval interrupt/resume`; §11.3 `Approval`; §11.4 `Action Execution`; §17 `Verification flow`.
  - `docs/SECURITY.md` — §5 `Authorization and RBAC`; §12 `Approval security`; §13 `Stale approval and proposal integrity`.
  - `docs/DATABASE_DESIGN.md` — §7.6 `support.approval_requests`; §7.7 `support.approval_proposal_versions`; §7.8 `support.action_executions`.
- **Acceptance criteria:** Reviewer sees impact/evidence; stale/expired/material paths clear; no action success before verified.
- **Required tests/commands:** `CMD-FE-QUALITY`, UI/API approval tests.
- **Security:** Role-aware UI plus backend enforcement; expected hash/version; no hidden approval bypass.
- **Risks:** Accidental approve after edit, stale UI, insufficient impact disclosure.
- **Review checklist:** [ ] decision matrix [ ] version/hash [ ] expiry [ ] reapproval [ ] verified result only.
- **Completion report:** Use §11 with `Task ID: WEB-003`.

## 13. Phase 9 — Security, evaluation, CI and release

### E2E-001A — Explicit Ticket/Run and timeout E2E

- **Metadata:** Phase 9; size `S`; milestone `v0.1-alpha`; status `TODO`; Owner: Unassigned.
- **Goal:** Prove explicit Ticket→Agent Run happy path to `WAITING_APPROVAL` and timeout contract.
- **In scope:** Browser/API create-ticket/create-run, active conflict/replay and pre-write 504 persistence.
- **Out of scope:** Approval/action and message resume.
- **Modules/files:** API/browser E2E fixtures/tests.
- **Input → output:** Synthetic seed → `WAITING_APPROVAL` or persisted `FAILED`/`ESCALATED` 504.
- **Dependencies:** `WEB-001`, `AG-001`, `AG-002B`.
- **Required reading:**
  - `docs/API_CONTRACT.md` — §11 `Ticket creation contract`; §12 `Explicit Agent Run trigger`; §17 `Error/status matrix`.
  - `docs/AGENT_WORKFLOW.md` — §5 `Active graph profile v0.1`; §8 `Conditional routing`; §11 `State machines`; §12 `Timeout propagation`.
  - `docs/SECURITY.md` — §6 `Customer isolation`; §14 `Idempotency and duplicate prevention`; §18 `Log redaction and no-CoT`.
  - `docs/ROADMAP.md` — §15 `Final v0.1 vertical slice`; §16 `Final release gates`.
- **Acceptance criteria:** No implicit run; one active run; timeout audit/state visible.
- **Required tests/commands:** `CMD-COMPOSE`, `CMD-E2E` selected suite.
- **Security:** Customer scope and safe failure body; no secret/CoT.
- **Risks:** Flaky real-time timeout, hidden fixture coupling.
- **Review checklist:** [ ] explicit requests [ ] replay/409 [ ] 504 persistence [ ] deterministic fixture [ ] cleanup.
- **Completion report:** Use §11 with `Task ID: E2E-001A`.

### E2E-001B — Approval/edit/action failure E2E

- **Metadata:** Phase 9; size `S`; milestone `v0.1-beta`; status `TODO`; Owner: Unassigned.
- **Goal:** Prove approval expiry/material reapproval and `UNKNOWN`/verification safety.
- **In scope:** Expired/stale/material edit, approve/reject, write failure injection, same-key reconcile and final verified transition.
- **Out of scope:** Message resume.
- **Modules/files:** API E2E/failure fixtures.
- **Input → output:** Pending proposal → safe escalated/reapproval/verified terminal result.
- **Dependencies:** `WEB-003`, `APR-002`, `ACT-001`, `AG-003`.
- **Required reading:**
  - `docs/API_CONTRACT.md` — §14 `Approval decision contract`; §15 `Mock-Commerce payment synchronization`; §17 `Error/status matrix`.
  - `docs/AGENT_WORKFLOW.md` — §10 `Approval interrupt/resume`; §11.3 `Approval`; §11.4 `Action Execution`; §16 `Possible-write UNKNOWN flow`; §17 `Verification flow`.
  - `docs/DATABASE_DESIGN.md` — §7.6 `support.approval_requests`; §7.7 `support.approval_proposal_versions`; §7.8 `support.action_executions`.
  - `docs/SECURITY.md` — §12 `Approval security`; §13 `Stale approval and proposal integrity`; §14 `Idempotency and duplicate prevention`; §15 `Possible-write handling`.
- **Acceptance criteria:** No expired/stale action; `UNKNOWN` not resolved; material version reapproved; verified happy path resolves.
- **Required tests/commands:** `CMD-COMPOSE`, `CMD-E2E` failure suite.
- **Security:** Role/version/hash/ownership/idempotency assertions.
- **Risks:** Failure injection not representing ambiguous write, race flakiness.
- **Review checklist:** [ ] expiry/edit [ ] unknown [ ] same key [ ] verification [ ] audit/timeline.
- **Completion report:** Use §11 with `Task ID: E2E-001B`.

### E2E-001C — Same-run customer message resume E2E

- **Metadata:** Phase 9; size `S`; milestone `final-v0.1`; status `TODO`; Owner: Unassigned.
- **Goal:** Prove customer clarification resumes the same run and handles timeout/invariant failure.
- **In scope:** `WAITING_CUSTOMER`, message commit, `200` resume, same run/thread, missing checkpoint and timeout paths.
- **Out of scope:** New-run retry semantics beyond explicit terminal retry.
- **Modules/files:** API/browser message-resume E2E.
- **Input → output:** Clarification message → same run continues or safe persisted failure.
- **Dependencies:** `WEB-002`, `AG-003`, `TKT-001`.
- **Required reading:**
  - `docs/API_CONTRACT.md` — §13 `Message same-run resume`; §17 `Error/status matrix`.
  - `docs/AGENT_WORKFLOW.md` — §9 `Clarification và same-run message resume`; §11.1 `Ticket`; §11.2 `Agent Run`; §12 `Timeout propagation`; §18 `Checkpoint reconciliation`.
  - `docs/DATABASE_DESIGN.md` — §7.1 `LangGraph checkpoint tables`; §7.2 `support.agent_runs`; §7.3 `support.agent_run_events`.
  - `docs/SECURITY.md` — §6 `Customer isolation`; §14 `Idempotency and duplicate prevention`; §18 `Log redaction and no-CoT`.
- **Acceptance criteria:** No hidden new run; message survives timeout; invariant failure escalates/audits.
- **Required tests/commands:** `CMD-COMPOSE`, `CMD-E2E` resume subset.
- **Security:** Message/customer ownership; masked candidates; no checkpoint exposure.
- **Risks:** Transaction/resume timing, accidentally creating duplicate run.
- **Review checklist:** [ ] message first [ ] same run/thread [ ] timeout [ ] missing checkpoint [ ] idempotency.
- **Completion report:** Use §11 with `Task ID: E2E-001C`.

### E2E-001D — Ticket attachment rejection contract E2E

- **Metadata:** Phase 9; size `S`; milestone `final-v0.1`; status `TODO`; Owner: Unassigned.
- **Goal:** Prove forward-compatible attachment field behavior without implementing attachments.
- **In scope:** Message requests with omitted, empty and non-empty `attachment_references`, including DB/resume/fetch side-effect assertions.
- **Out of scope:** Upload endpoint, storage table/blob, URL retrieval, PDF/DOCX/OCR.
- **Modules/files:** API E2E fixtures/tests and PostgreSQL side-effect assertions.
- **Input → output:** Message variants → normal `201/200` or exact `422 ATTACHMENTS_NOT_SUPPORTED`.
- **Dependencies:** `TKT-001`, `AG-003`.
- **Required reading:**
  - `docs/API_CONTRACT.md` — §13.1 `Request`; §17 `Error/status matrix`.
  - `docs/AGENT_WORKFLOW.md` — §9 `Clarification và same-run message resume`.
  - `docs/DATABASE_DESIGN.md` — §6.4 `support.ticket_messages`; §12 `Transaction boundaries`.
  - `docs/SECURITY.md` — §20 `Upload and MIME validation`; §25 `Abuse cases`; §26 `Security test matrix`.
- **Acceptance criteria:** Omitted/`[]` preserve normal idempotent message/resume behavior; non-empty returns `422`, `retryable=false`, `details.supported_from=v1.0`; zero message/success replay/resume/storage/fetch side effect.
- **Required tests/commands:** `CMD-COMPOSE`, `CMD-E2E`, DB assertions and fake-fetch spy.
- **Security:** Proves no SSRF/local file fetch and no silent ignore.
- **Risks:** Test observes response but misses background/DB side effect.
- **Review checklist:** [ ] exact envelope [ ] no message [ ] no resume [ ] no storage/fetch [ ] normal omitted/empty path.
- **Completion report:** Use §11 with `Task ID: E2E-001D`.

### E2E-001E — Synchronous knowledge reindex E2E

- **Metadata:** Phase 9; size `S`; milestone `final-v0.1`; status `TODO`; Owner: Unassigned.
- **Goal:** Prove exact synchronous reindex, atomic pointer and recalibration behavior end to end.
- **In scope:** Published/draft/validated success, failed/timeout attempt, replay, config change and exact response/errors.
- **Out of scope:** Queue, `202`, job/polling, auto-publish or PDF.
- **Modules/files:** Knowledge API/repository E2E fixtures and failure injection.
- **Input → output:** Reindex fixtures → exact `200` provenance or typed error with active index preserved.
- **Dependencies:** `KB-002`, `RAG-001`.
- **Required reading:**
  - `docs/API_CONTRACT.md` — §5 `Idempotency và replay`; §16.1 `Synchronous reindex`; §17 `Error/status matrix`.
  - `docs/RAG_DESIGN.md` — §19 `Policy lifecycle and versioning`; §22 `Reindex and recalibration rules`; §28 `Required tests`.
  - `docs/DATABASE_DESIGN.md` — §8 `Knowledge và embedding provenance (DB-001C)`; §12 `Transaction boundaries`; §16 `Knowledge versioning`.
  - `docs/SECURITY.md` — §20 `Upload and MIME validation`; §26 `Security test matrix`.
- **Acceptance criteria:** No async artifacts; lifecycle unchanged; old published index serves until atomic swap; failure/timeout persists failed attempt and preserves pointer; replay avoids second build; model/revision/dimension/input/scoring change resets calibration.
- **Required tests/commands:** `CMD-COMPOSE`, `CMD-E2E`, PostgreSQL/failure-injection assertions.
- **Security:** Admin-only and no source/secret leakage.
- **Risks:** Race/flaky timeout, insufficient proof of atomic visibility.
- **Review checklist:** [ ] exact 200/errors [ ] lifecycle [ ] atomic/failure [ ] replay [ ] calibration reset.
- **Completion report:** Use §11 with `Task ID: E2E-001E`.

### OBS-001 — Basic observability, timeline and audit

- **Metadata:** Phase 9; size `S`; milestone `final-v0.1`; status `TODO`; Owner: Unassigned.
- **Goal:** Provide reviewable JSON logs, ordered run events, reconciliation signals and redacted audit.
- **In scope:** Correlation, latency/attempt/version/provenance/approval/action/timeout/invariant fields and redaction tests.
- **Out of scope:** OTEL, production dashboards/alerts or distributed tracing.
- **Modules/files:** Core logging, run events, audit/redaction tests.
- **Input → output:** Runtime operations → safe technical logs/timeline/audit projections.
- **Dependencies:** `DB-001B1`, `DB-001B3`, `AG-003`, `APR-002`, `ACT-001`.
- **Required reading:**
  - `docs/ARCHITECTURE.md` — §15 `Workflow persistence ownership`; §21 `Failure boundaries`.
  - `docs/AGENT_WORKFLOW.md` — §18 `Checkpoint reconciliation`; §20 `Event persistence`; §21 `Audit integration`.
  - `docs/DATABASE_DESIGN.md` — §7.2 `support.agent_runs`; §7.3 `support.agent_run_events`; §7.10 `support.audit_logs`; §11 `Checkpoint ownership và reconciliation`.
  - `docs/SECURITY.md` — §18 `Log redaction and no-CoT`; §19 `Audit logging`.
- **Acceptance criteria:** Required §17 fields; internal service token absent from every log/event/audit/tool projection; no CoT/raw PII; ownership of checkpoint/run/events/audit preserved.
- **Required tests/commands:** `CMD-BE-QUALITY`, log/event/audit/redaction tests.
- **Security:** Append-only audit, safe summaries, admin access audited.
- **Risks:** Sensitive log fields, conflating event/audit/checkpoint, missing failure event.
- **Review checklist:** [ ] correlation [ ] required fields [ ] redaction [ ] ownership [ ] failure signals.
- **Completion report:** Use §11 with `Task ID: OBS-001`.

### SEC-001 — V0.1 security gates

- **Metadata:** Phase 9; size `M`; milestone `final-v0.1`; status `TODO`; Owner: Unassigned.
- **Goal:** Enforce plaintext guard, attachment rejection, public/internal token isolation, customer/schema/import boundaries and prompt/MIME/rate/redaction controls.
- **In scope:** Threat matrix, exact five-case internal-auth tests, attachment zero-side-effect tests, runtime grants/import rules, idempotency fingerprint/redaction, injection/tool misuse and release profile guard.
- **Out of scope:** Production encryption, SSO, SIEM or cloud hardening.
- **Modules/files:** Security/import-boundary tests and minimal enforcement code/config.
- **Input → output:** Runtime/dependency graph → passing security release evidence.
- **Dependencies:** `DB-001A`, `DB-001B1`, `DB-001B2`, `DB-001B3`, `DB-001C`, `AUTH-001`, `TKT-001`, `TOOL-001`, `MOCK-AUTH-001`, `MOCK-ORD-001`, `MOCK-PAY-001`, `RAG-001`.
- **Required reading:**
  - `docs/SECURITY.md` — toàn bộ; task security gate là ngoại lệ theo domain document, còn PLAN chỉ được nạp theo global policy.
  - `docs/ARCHITECTURE.md` — §10 `Mock-Commerce boundary` through §13 `Import dependency rules`; §18 `Runtime containers`.
  - `docs/API_CONTRACT.md` — §2 `Authentication và authorization`; §5 `Idempotency và replay`; §8 `Internal Mock-Commerce endpoint catalog`; §13 `Message same-run resume`; §17 `Error/status matrix`.
  - `docs/DATABASE_DESIGN.md` — §3 `Schema ownership và roles`; §7.10 `support.audit_logs`; §7.11 `support.idempotency_records`; §9.6 `commerce.idempotency_records`; §9.7 `commerce.audit_logs`; §17 `Sensitive data handling`.
- **Acceptance criteria:** Unauthorized/cross-schema/duplicate action = 0; missing internal token 401, wrong/user JWT 403, valid success, public rejection and redaction pass; non-empty attachment exact 422/no side effect; immutable audit/idempotency grants; forbidden imports/tools impossible; no real data/secrets/CoT.
- **Required tests/commands:** `CMD-SECURITY`, relevant quality suites.
- **Security:** This task owns final security matrix; findings cannot be waived by prompt/UI.
- **Risks:** False-positive test coverage, environment-only grant pass, fake profile leakage.
- **Review checklist:** [ ] threat matrix [ ] grants/imports [ ] injection/tools [ ] redaction/data [ ] release profile.
- **Completion report:** Use §11 with `Task ID: SEC-001`.

### EVAL-001 — Calibration and locked holdout evaluation

- **Metadata:** Phase 9; size `M`; milestone `final-v0.1`; status `TODO`; Owner: Unassigned.
- **Goal:** Produce versioned 15-case calibration and 10-case locked holdout release reports.
- **In scope:** Dataset/split/checksums, vector/lexical sweep, separate metrics/artifacts and mismatch invalidation.
- **Out of scope:** Model training or tuning on holdout.
- **Modules/files:** Evaluation scripts/datasets/artifacts/tests.
- **Input → output:** Versioned 25-case golden set → calibrated thresholds + one final holdout report.
- **Dependencies:** `SEED-001`, `RAG-001`, `AG-002B`.
- **Required reading:**
  - `docs/RAG_DESIGN.md` — §23 `Evaluation dataset split`; §24 `Calibration procedure`; §25 `Metrics and release artifact`; §28 `Required tests`.
  - `docs/AGENT_WORKFLOW.md` — §6 `Node contracts v0.1`; §8 `Conditional routing`; §22 `Test scenarios`.
  - `docs/PROJECT_SPEC.md` — §15 `Success metrics`; §16 `Release criteria v0.1`.
  - `docs/ROADMAP.md` — §16 `Final release gates`.
- **Acceptance criteria:** Recalibrate vector and lexical gates from scratch on calibration split (`0.72` cannot be promoted); Recall@5 ≥90%; false-positive evidence 0; no-answer precision versioned; exact model/revision/dimension/input format/RRF/threshold provenance.
- **Required tests/commands:** `CMD-EVAL`; checksum/split leakage/reproducibility checks.
- **Security:** Synthetic data only; injection/provider-failure cases; artifact no secrets.
- **Risks:** Holdout leakage/overfit, non-reproducible revision, placeholder threshold promoted.
- **Review checklist:** [ ] split committed first [ ] calibration only tuning [ ] separate reports [ ] provenance [ ] targets.
- **Completion report:** Use §11 with `Task ID: EVAL-001`.

### CI-001 — V0.1 CI and release gates

- **Metadata:** Phase 9; size `M`; milestone `final-v0.1`; status `TODO`; Owner: Unassigned.
- **Goal:** Make lint/type/test/build/security/import/evaluation/release-profile checks reproducible.
- **In scope:** Backend/frontend quality, ≥20 tests, E2E, security/import/grants, evaluation artifact match and no-fake release gate.
- **Out of scope:** Deployment/push or real Gemini calls in CI.
- **Modules/files:** CI configuration and deterministic fake-provider test profile.
- **Input → output:** Commit → reproducible pass/fail report.
- **Dependencies:** `E2E-001A`, `E2E-001B`, `E2E-001C`, `E2E-001D`, `E2E-001E`, `OBS-001`, `SEC-001`, `EVAL-001`.
- **Required reading:**
  - `docs/TASKS.md` — §3 `Planned command catalog`; completion reports của direct dependencies; §15 `Global review checklist`.
  - `docs/ROADMAP.md` — §14 `Phase 9 — Security, evaluation, CI and release`; §16 `Final release gates`.
  - `docs/SECURITY.md` — §26 `Security test matrix`; §27 `V0.1 security limitations`.
  - `docs/PROJECT_SPEC.md` — §16 `Release criteria v0.1`.
- **Acceptance criteria:** Fails Phase-1 domain enum/table leakage, walking skeleton/fake path, attachment/internal-auth/reindex E2E failure, uncalibrated/missing/mismatched artifact, holdout/security/import/grant/test failure.
- **Required tests/commands:** `CMD-CI`; CI dry run.
- **Security:** Secrets absent; Gemini replaced by fake; release artifacts/checksums verified.
- **Risks:** CI/local drift, skipped gate, nondeterministic E2E/evaluation.
- **Review checklist:** [ ] every gate wired [ ] no secret/provider call [ ] artifact provenance [ ] fake rejection [ ] dry run.
- **Completion report:** Use §11 with `Task ID: CI-001`.

### DEP-001 — Clean-machine local demo packaging

- **Metadata:** Phase 9; size `S`; milestone `final-v0.1`; status `TODO`; Owner: Unassigned.
- **Goal:** Provide one-command clean local v0.1 demo and reviewed instructions.
- **In scope:** Compose packaging, placeholder env/sample credentials, bootstrap/migrate/seed/start/demo/cleanup instructions and smoke check.
- **Out of scope:** Cloud/Kubernetes/production deploy or commit/push.
- **Modules/files:** Infrastructure/docs/demo scripts as approved.
- **Input → output:** Release tag + documented prerequisites → reproducible local UC-01 demo.
- **Dependencies:** `CI-001`.
- **Required reading:**
  - `docs/ARCHITECTURE.md` — §18 `Runtime containers`; §19 `Docker Compose startup order`; §20 `Deployment view`.
  - `docs/ROADMAP.md` — §15 `Final v0.1 vertical slice`; §16 `Final release gates`; §19 `Scope-control rules`.
  - `docs/SECURITY.md` — §3 `Trust boundaries`; §7 `Cross-schema isolation`; §17 `Secret management`; §27 `V0.1 security limitations`.
  - `docs/TASKS.md` — completion report của `CI-001`; §3 `Planned command catalog`.
- **Acceptance criteria:** Clean machine starts healthy stack; profile `v0_1`; synthetic data; all release instructions complete.
- **Required tests/commands:** `CMD-COMPOSE`, smoke/E2E happy path.
- **Security:** Placeholder secrets only; no owner/admin credential in runtime; no real data/fake release path.
- **Risks:** Hidden local dependency, platform env differences, accidental secret inclusion.
- **Review checklist:** [ ] clean start [ ] credential matrix [ ] v0_1 profile [ ] demo steps [ ] no out-of-scope service.
- **Completion report:** Use §11 with `Task ID: DEP-001`.

## 14. Deferred milestones (not v0.1 tasks)

| Milestone | Deferred themes | Backlog rule |
|---|---|---|
| MVP v1.0 | UC-02–UC-05, ticket attachment/upload, PDF, refresh-token rotation, full field encryption, advanced observability | Create task IDs only after stable v0.1 and PLAN/ADR review. |
| Post-MVP | UC-06–UC-07, real connectors, queue/scale/realtime/reranker when evidence supports | No implementation task in current registry. |

## 15. Global review checklist

Every task review must confirm:

- [ ] Goal, in-scope and out-of-scope match this record and PLAN.
- [ ] Task remains independently reviewable in one coding session.
- [ ] Contract/schema/docs/examples updated where relevant.
- [ ] Business rule remains deterministic/domain-owned, not prompt-only.
- [ ] Happy/error/retry paths tested proportionally.
- [ ] Auth/role/customer/schema scope enforced.
- [ ] Idempotency/concurrency checked for writes.
- [ ] Logs/events/audit contain no secret, unnecessary PII, checkpoint payload or CoT.
- [ ] No UC/provider/infrastructure/migration beyond approved scope.
- [ ] Relevant quality commands pass and results are reported.

## Task execution prompt template

```text
Thực hiện duy nhất task <TASK_ID> theo docs/TASKS.md.

Context loading:
1. Đọc section của <TASK_ID>.
2. Đọc completion report của các dependency trực tiếp.
3. Đọc đúng danh sách Required reading của task.
4. Kiểm tra các module/file hiện tại thuộc scope.

Không đọc lại toàn bộ PLAN hoặc toàn bộ docs trừ khi Required reading yêu cầu hoặc phát hiện mâu thuẫn.

Trước khi code:
- xác nhận dependency đã DONE;
- chuyển task từ TODO sang IN_PROGRESS;
- báo các contract chính sẽ tuân thủ.

Sau khi hoàn thành:
- chạy required commands;
- kiểm tra acceptance criteria;
- cập nhật task thành IN_REVIEW;
- điền completion report;
- không tự chuyển DONE;
- không bắt đầu task khác;
- không commit hoặc push.
```

## 16. Completion report template

```markdown
## Task completion report

- Task ID:
- Final status: IN_REVIEW | DONE
- Owner:
- Goal achieved:
- Files/modules changed:
- Contract/schema impact:
- Migrations created (if authorized):
- Tests added/updated:
- Required context loaded:
- Additional context loaded and reasons:
- Dependency completion reports reviewed:
- Context intentionally not loaded:
- Commands run and results:
- Security checks:
- Acceptance criteria evidence:
- Risks/limitations remaining:
- Deviations from PLAN: None | describe and request review
- Follow-up tasks unblocked:
```

Do not mark `DONE` solely because code exists; all acceptance criteria, tests, docs and review evidence must pass.

## Source and traceability

- Nguồn chính: [PLAN.md](./PLAN.md), §21–§24; task contracts also trace to §5–§20.
- Tài liệu liên quan: [PROJECT_SPEC.md](./PROJECT_SPEC.md), [ARCHITECTURE.md](./ARCHITECTURE.md), [DATABASE_DESIGN.md](./DATABASE_DESIGN.md), [API_CONTRACT.md](./API_CONTRACT.md), [AGENT_WORKFLOW.md](./AGENT_WORKFLOW.md), [RAG_DESIGN.md](./RAG_DESIGN.md), [SECURITY.md](./SECURITY.md), [ROADMAP.md](./ROADMAP.md).
- Quyết định không được thay đổi: task IDs/order/dependencies and reviewed acceptance semantics; UC-01-only v0.1; Walking Skeleton temporary; alpha/beta/final approval split; all core architecture/security/RAG/workflow contracts.
- All task statuses are initially `TODO`; all owners are `Unassigned` as required.
- Phiên bản nguồn: `PLAN.md` hiện không có version nội tại; traceability snapshot ngày 2026-08-04.
