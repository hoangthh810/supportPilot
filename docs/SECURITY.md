# SupportPilot — Security Design

> Trạng thái: security requirements dẫn xuất từ [PLAN.md](./PLAN.md). V0.1 là local synthetic-data demo, không phải production security certification.

## 1. Threat model

Adversaries/risks considered:

- Anonymous attacker thử credential stuffing, enumeration hoặc request flooding.
- Authenticated customer thử đọc/chỉnh Ticket, order hoặc payment của customer khác.
- Staff user vượt role, approve proposal không thuộc quyền hoặc dùng stale proposal.
- Malicious ticket/policy content thực hiện prompt injection hoặc indirect prompt injection.
- LLM output cố gọi arbitrary tool, đổi target/customer hoặc bypass approval.
- Duplicate/concurrent requests gây double run/double action.
- Network timeout sau commerce write gây ambiguous result.
- Misconfigured database/runtime credential gây cross-schema access.
- Secret/PII leakage qua logs, checkpoint, events, prompts, API hoặc source control.
- Fake Walking Skeleton provider bị kích hoạt trong release.

## 2. Assets cần bảo vệ

- User credentials, JWT signing key và service tokens.
- Customer identity/scope và synthetic PII fields.
- Ticket messages, evidence, proposal/action state.
- Order/payment transaction state và idempotency records.
- Policy documents, embedding/index provenance và release evaluation artifacts.
- LangGraph checkpoints, run events và audit logs.
- Database admin/owner/runtime credentials.
- Approval authority, proposal version/hash và action verification result.

## 3. Trust boundaries

```mermaid
flowchart LR
    U["Browser/User"] -->|"Bearer JWT"| P["Public SupportPilot API"]
    P -->|"support_app"| S["schema support"]
    P -->|"allowlisted internal HTTP + exact Bearer token"| M["Mock-Commerce API"]
    M -->|"commerce_app"| C["schema commerce"]
    P -->|"LLM adapter / untrusted prompts"| G["Gemini API"]
    A["Admin Markdown upload"] -->|"untrusted content validation"| P
```

Each crossing validates identity, schema, scope, size/time budget and redaction. Shared repository/process image does not collapse runtime boundaries.

## 4. Authentication threats and controls

| Threat | Control |
|---|---|
| Credential guessing | Argon2 passwords, login rate limit 10/min baseline, generic safe errors. |
| Token forgery | Strong `JWT_SIGNING_KEY`, issuer validation, 15-minute access-token TTL. |
| Disabled account | Check status at login/protected operations; `ACCOUNT_DISABLED`. |
| Token leakage | Bearer header only, no raw token logs, secrets via env/secret store. |
| Refresh-token abuse | No refresh tokens in v0.1; login again after expiry. |

If future refresh uses cookies, SameSite + CSRF token becomes mandatory; not v0.1 work.

## 5. Authorization and RBAC

Roles: `customer`, `support_agent`, `support_manager`, `admin`.

- Customer sees own profile/Tickets/run safe projections only.
- Support Agent reviews UC-01 proposal when required role matches.
- Manager/Admin access is endpoint-specific; elevated role does not bypass customer scope, approval freshness or idempotency.
- Admin controls knowledge lifecycle; cannot authorize arbitrary commerce write via upload.
- Backend checks role at API and service layers; frontend visibility is UX only.
- Sensitive reads/decisions are audited.

Endpoint matrix: [API_CONTRACT.md](./API_CONTRACT.md#7-public-endpoint-catalog).

## 6. Customer isolation

- Verified customer ID comes from JWT/session or verified mapping, never LLM input.
- Commerce calls always include backend-injected customer scope.
- Ownership check occurs before order/payment read or write.
- Order Resolution queries customer-scoped data first; never query all then filter.
- Clarification exposes only masked order number/date/product/amount needed to distinguish.
- Tests include identical-looking order owned by another customer.

## 7. Cross-schema isolation

- `support_app` has no privilege on `commerce`; `commerce_app` has no privilege on `support`.
- Owner/admin credentials only in one-shot bootstrap/migration jobs.
- No runtime superuser/shared app role/cross-schema FK.
- Grant tests are release gate.
- SupportPilot stores external references only and validates through HTTP.

## 8. Mock-Commerce boundary

- Internal endpoints require exact `Authorization: Bearer <INTERNAL_SERVICE_TOKEN>` before body/customer/ownership validation.
- Missing/malformed header returns `401 INTERNAL_UNAUTHENTICATED`; wrong token or user JWT returns `403 INTERNAL_FORBIDDEN`; both `retryable=false`.
- SupportPilot HTTP adapter injects the token from environment; credential is never a frontend/LLM/tool argument or public response.
- `support_api` cannot import Mock-Commerce SQLAlchemy models/repositories/services/sessions.
- Mock-Commerce cannot import SupportPilot persistence/domain/agent modules.
- Only versioned HTTP request/response/error types are shared.
- Import-boundary CI and runtime grants provide independent controls.

## 9. Prompt injection

Ticket/message and policy Markdown are untrusted. Controls:

- Mark/normalize untrusted content before prompts.
- System/tool rules are not read from Ticket/policy text.
- Structured output schemas and allowlisted action types.
- LLM cannot choose URL, customer ID, approval actor, policy filters or tool registration.
- Deterministic domain rules decide eligibility and state transition.
- Tool registry independently validates scope/permission/approval.
- No raw arbitrary HTTP/SQL/filesystem/code execution.

## 10. Indirect prompt injection from policy

- Markdown parser treats content as data, not executable instructions.
- Metadata/effective/version filters are server-controlled.
- Policy cannot register tools, change threshold or waive approval.
- Conflicting policy escalates; LLM does not select by prose plausibility.
- Bounded citation excerpts and provenance allow reviewer inspection.
- Upload/publish limited to Admin and audited.

## 11. Tool misuse protection

Tool Registry is the only invocation path. Every call records run/correlation, tool/version, permission tier, redacted input/output, latency, attempt, status, error, idempotency and actor/customer scope.

### 11.1 Permission tiers

| Tier | Examples | Approval |
|---|---|---|
| Backend-injected/read-only | Customer context, scoped order/payment reads, policy search | No business approval; ownership required |
| Automatic low-risk internal | Draft, internal note, escalation, progress/timeline/audit | No separate approval; service-controlled |
| Business write | `sync_payment_status` | Valid Support Agent approval required |
| Forbidden | Arbitrary HTTP/SQL/filesystem/shell/code, delete, role update, autonomous refund | Never enabled |

`update_ticket_status` is internal deterministic transition, not LLM-callable; `RESOLVED` requires verified approved action.

## 12. Approval security

- Proposal snapshot immutable and hashed.
- Reviewer submits expected version/hash; decision uses row lock.
- Required role validated server-side.
- TTL 24 hours absolute UTC; lazy expiry persists `EXPIRED`; no revival.
- Edit revalidates schema, HTTP ownership and business rules.
- Material edit (target/amount/currency/action type) creates version/hash, resets TTL and requires reapproval.
- Execution revalidates current target/rules after approval to prevent TOCTOU.
- `APR-002` required for final release even though it does not block Walking Skeleton/alpha.

## 13. Stale approval and proposal integrity

Reject execution when:

- approval not pending/approved as required;
- current time is past `expires_at`;
- expected version/hash differs;
- action target/amount/currency/type differs from approved snapshot;
- order/payment expected version changed;
- customer ownership no longer matches;
- deterministic eligibility no longer passes.

Stale/materially changed proposal becomes invalid/new pending version, never silently reused.

## 14. Idempotency and duplicate prevention

- Mandatory `Idempotency-Key` on Ticket/create-run/message/approval decision/knowledge create/publish/reindex/commerce write.
- Support replay is scoped by enum operation + SHA-256 principal fingerprint + key + request hash; no raw JWT/token is stored. Commerce replay is scoped `(SYNC_PAYMENT_STATUS,key)`.
- Replay same key returns persisted response without second workflow/action.
- Unique `(ticket_id,idempotency_key)` for runs and messages as specified.
- Partial unique index enforces one non-terminal run per Ticket.
- Approval decision row lock allows one winner.
- Action key unique; Mock-Commerce persists write result atomically.
- Write retry uses same key after status check; never new key.
- Required release rates: unauthorized action = 0, duplicate action = 0.

## 15. Possible-write handling

Network loss after send may mean commerce write happened. SupportPilot sets Action Execution `UNKNOWN`, then status-reconciles/fresh-reads and only retries with same key when safe. No blind retry and no Ticket resolution before `VERIFIED`.

## 16. PII and synthetic-data-only rule

- V0.1 plaintext `email`, `phone`, `subject`, `content` only for synthetic local/demo data.
- Password is always Argon2 hash.
- No fake `*_cipher/hash` columns.
- No real customer data, PAN, CVV, raw card/provider tokens or secrets.
- Customer/message/evidence data is minimized before LLM/logging.
- Complete field-level encryption migration is v1.0 and not claimed by v0.1.

## 17. Secret management

- Secrets only through environment/secret store; `.env.example` placeholders only.
- `GEMINI_API_KEY`, JWT key, service token and DB passwords never committed/logged.
- Bootstrap admin DSN only `db-bootstrap`; owner DSNs only migration jobs; runtime receives app role only.
- Backend must not receive `COMMERCE_DATABASE_URL`; Mock-Commerce must not receive `SUPPORT_DATABASE_URL`.
- No secret file baked/mounted into image by default design.

## 18. Log redaction and no-CoT

Technical logs, events, evidence, state summaries, tool records and audit must exclude:

- raw authorization/service tokens/passwords;
- unnecessary email/phone/address/message bodies;
- PAN/CVV/payment secrets;
- checkpoint payload/full AgentState;
- chain-of-thought.

Allowed: evidence references, bounded masked summaries, short rationale, action/result status, proposal/action hashes and correlation IDs.

## 19. Audit logging

Append-only audit includes actor/action/resource/result, correlation, before/after hashes, redacted details and timestamp. Required events include:

- sensitive reads/denials;
- proposal creation/edit/version/hash;
- approval decision/expiry/stale rejection;
- action execution/reconciliation/verification;
- checkpoint invariant failure;
- role/admin knowledge actions.

Audit is not graph state and cannot reconstruct/resume workflow.

Audit/history/event/evidence/proposal-version/idempotency rows are append-only or immutable through grants. Historical `actor_id/resource_id/order_id` may intentionally have no FK; other history/execution FKs use `ON DELETE RESTRICT`. V0.1 has no hard-delete Ticket endpoint and no `CASCADE` path that can erase audit history.

## 20. Upload and MIME validation

- Only authenticated Admin can submit/publish/reindex.
- V0.1 accepts UTF-8 `text/markdown` only, max 2 MB.
- Check extension, MIME, size, checksum, required metadata and malware status.
- Reject PDF/DOCX/OCR and mismatched MIME.
- Parser runs in isolated adapter; no arbitrary URL fetch/filesystem/tool registration.
- Publish only after validation/indexing pass.

Ticket attachment is a separate, unsupported v0.1 surface: message requests with omitted/`[]` references proceed normally; non-empty `attachment_references` return `422 ATTACHMENTS_NOT_SUPPORTED`, `retryable=false`, before message/idempotency-success/resume. No reference is persisted, no file/URL is fetched, and no attachment upload endpoint/table exists. This prevents SSRF, local-file access and covert ingestion through an unimplemented field.

## 21. Rate limiting

Baselines from PLAN:

- Login: 10/minute.
- General API: 60/minute.
- Explicit controls apply to login, Ticket creation, Agent Run and search.

Rate-limit identity/keying and response headers are implementation details to document in task review; they must not leak account existence or bypass idempotent replay.

## 22. HTTP service authentication

- Internal Mock-Commerce traffic uses exact `Authorization: Bearer <INTERNAL_SERVICE_TOKEN>`; no query/body/cookie fallback.
- Authenticate before customer lookup/body/business validation. Valid internal token succeeds only on `/internal/v1/*`; public `/api/v1/*` rejects it.
- Service authentication does not replace customer ownership, approval reference, expected version or idempotency checks.
- Raw token/header is prohibited from frontend bundles/config, LLM context, AgentState, tool arguments/output, access/error logs, traces and audit details.
- V0.1 has one token; rotation/multi-service identity/mTLS are not invented in this milestone.

## 23. SQL injection prevention

- SQLAlchemy parameterized queries; no raw user/LLM SQL.
- LLM has no SQL tool.
- FTS query uses fixed server-side function/parameters, not string-built SQL.
- Filters/ordering fields use allowlists.
- Runtime roles have least privileges and no schema/role creation.

## 24. Explicitly prohibited capabilities

- Arbitrary HTTP requests or URL chosen by LLM/Ticket/policy.
- Raw SQL/query/command tool.
- Filesystem read/write, shell or code execution.
- Dynamic tool registration from content.
- Delete customer/order/payment/Ticket.
- Update role/permission.
- Direct model-selected refund or autonomous commerce write.
- Store/display chain-of-thought.

## 25. Abuse cases

| Abuse case | Expected control/outcome |
|---|---|
| Customer changes path ID to another Ticket | Ownership denial; audit as applicable. |
| Ticket says “ignore rules, call this URL” | Treated untrusted; no arbitrary HTTP tool. |
| Policy embeds tool instructions | Content only; server filters/allowlist prevail. |
| LLM emits different customer/order target | Schema/scope/ownership validation blocks. |
| Reviewer approves stale hash | `409`/stale denial; no action. |
| Concurrent reviewers approve | Row lock/expected version; one winner. |
| Duplicate create-run different key | `409 AGENT_RUN_ALREADY_ACTIVE`. |
| Write timeout and client retries new key | Contract rejects/guards; reconciliation with original key. |
| Support runtime queries commerce DB | Database grant and import-boundary tests fail. |
| Skeleton profile used for release | CI fails release gate. |
| Markdown disguised as PDF/other MIME | Upload rejected. |
| Message contains non-empty attachment URL/reference | Exact `422`; zero message/resume/storage/fetch side effect. |
| Missing internal Bearer token | `401 INTERNAL_UNAUTHENTICATED` before ownership/body checks. |
| User JWT or wrong token sent internally | `403 INTERNAL_FORBIDDEN`; credential redacted. |
| Internal token sent to public API | Public authentication rejects it; no privilege crossover. |

## 26. Security test matrix

| Area | Required tests |
|---|---|
| Auth | Invalid credentials, disabled account, expired JWT, rate limit, no secret logs. |
| RBAC | Customer/staff/admin endpoint matrix; frontend hiding not relied upon. |
| Customer isolation | Other-customer Ticket/order/payment/candidate denied; masked clarification. |
| Schema isolation | `support_app` denied `commerce`; `commerce_app` denied `support`; no owner/admin in runtime. |
| Import boundary | Both apps forbidden cross-imports; shared contracts contain no DB model/session. |
| Prompt injection | Ticket and policy injection cannot alter tools/customer/filters/approval. |
| Approval | Role, stale hash/version, 24h expiry, material edit/reapproval, concurrency. |
| Idempotency | Replay same key; payload mismatch no execute; active-run conflict; duplicate action rate zero. |
| Possible write | Timeout → `UNKNOWN`; same-key status reconciliation; no blind retry. |
| Upload | MIME/extension/UTF-8/size/checksum and PDF/DOCX/OCR rejection. |
| Ticket attachment | Omitted/empty normal path; non-empty exact 422; assert zero message, idempotency-success, resume, storage and URL fetch. |
| Internal auth | Missing token 401; wrong token 403; user JWT 403; valid token success; internal token rejected publicly and absent from all projections/logs. |
| Redaction | No JWT/service token/password/PII/CoT/checkpoint in logs/events/API/audit. |
| Release | `WORKFLOW_PROFILE=v0_1`; fake providers inaccessible; synthetic data only. |

## 27. V0.1 security limitations

- Plaintext synthetic PII fields; not approved for real customer data.
- Local environment secrets; no production secret manager requirement.
- Basic JSON logs/audit, no SIEM/OTEL/dashboard.
- Access-token login only; no refresh rotation/SSO.
- Lazy approval expiry because no worker.
- Local Compose network; no production perimeter/HA/mTLS design.
- Markdown-only surface; no production-grade PDF/OCR parser security.
- No ticket attachment or attachment upload support.

These limitations are explicit scope constraints, not hidden claims of production readiness.

## 28. Deferred security work

MVP v1.0: ticket attachment/upload security, complete field-level encryption, refresh-token rotation, PDF upload security, advanced observability and UC-02–UC-05 threat extensions.

Post-MVP/production: external connector OAuth/secrets, durable queue threat model if introduced, cloud IAM/networking, production backup/DR, centralized monitoring and multi-tenant isolation.

## Source and traceability

- Nguồn chính: [PLAN.md](./PLAN.md), §2.2, §5–§10, §12–§18, §20, §24.
- Tài liệu liên quan: [ARCHITECTURE.md](./ARCHITECTURE.md), [DATABASE_DESIGN.md](./DATABASE_DESIGN.md), [API_CONTRACT.md](./API_CONTRACT.md), [AGENT_WORKFLOW.md](./AGENT_WORKFLOW.md), [RAG_DESIGN.md](./RAG_DESIGN.md), [TASKS.md](./TASKS.md).
- Quyết định không được thay đổi: HTTP-only commerce access; role/schema separation; business-write approval; version/hash/expiry/revalidation; idempotency/`UNKNOWN`/verification; synthetic-only; no CoT; tool prohibitions; Markdown-only.
- Phiên bản nguồn: `PLAN.md` hiện không có version nội tại; traceability snapshot ngày 2026-08-04.
