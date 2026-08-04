# SupportPilot — API Contract

> Trạng thái: normative API contract dẫn xuất từ [PLAN.md](./PLAN.md). Đây là tài liệu thiết kế, không phải implementation.

## 1. API conventions

- Public prefix: `/api/v1`.
- Internal Mock-Commerce prefix: `/internal/v1`.
- JSON request/response; UTF-8.
- User authentication: Bearer JWT access token.
- Internal authentication: exact `Authorization: Bearer <INTERNAL_SERVICE_TOKEN>` trên `/internal/v1/*`.
- User JWT không hợp lệ cho internal API; internal token không hợp lệ cho public API. Không có query/body/cookie credential fallback.
- Mọi response có `correlation_id`.
- Timestamps là ISO-8601 UTC.
- Money là `{ "amount": "decimal-string", "currency": "ISO-code" }`; không dùng binary float.
- POST có side effect theo danh sách §5 bắt buộc `Idempotency-Key`.
- Mỗi synchronous graph advance có budget 60 giây và persist failure/audit trước timeout response.

## 2. Authentication và authorization

| Actor/role | Scope chính |
|---|---|
| Anonymous | Chỉ `POST /auth/login`. |
| Customer | Profile của mình; Ticket/message/run safe view thuộc chính customer; create Ticket/run. |
| Support Agent | Customer summary đã mask, scoped Ticket/run/evidence; pending approvals đúng required role; UC-01 approval. |
| Support Manager | Staff review và audit access theo role; không bypass proposal/version/expiry rules. |
| Admin | Knowledge lifecycle/search và audit access; không bypass customer ownership/business approval. |
| Mock-Commerce service | Chỉ internal APIs qua exact Bearer internal token; không nhận user JWT làm database boundary. |

Authorization được kiểm tra ở router và service layer. Customer ID cho commerce tool phải được backend inject từ authenticated/verified context, không lấy từ LLM input.

## 3. Headers

| Header | Contract |
|---|---|
| `Authorization: Bearer <user JWT>` | Public authenticated endpoints. |
| `Authorization: Bearer <INTERNAL_SERVICE_TOKEN>` | Bắt buộc cho mọi `/internal/v1/*`; SupportPilot HTTP adapter tự inject từ environment. |
| `X-Correlation-ID` | Client có thể gửi; backend validate/normalize hoặc tạo mới; propagate xuyên run/tool/action. |
| `Idempotency-Key` | Bắt buộc cho Ticket/create-run/message/approval decision/knowledge create/publish/reindex/commerce write. |
| `Idempotency-Replayed: true` | Có thể xuất hiện khi response là replay đã persist. |

Không log raw authorization/service token/idempotency payload chứa PII.

## 4. Error envelope

```json
{
  "code": "AGENT_RUN_ALREADY_ACTIVE",
  "message": "A non-terminal agent run already exists for this ticket.",
  "retryable": false,
  "correlation_id": "corr_01...",
  "details": {
    "ticket_id": "uuid",
    "active_run_id": "uuid",
    "active_run_status": "WAITING_APPROVAL",
    "next_required_action": "approval"
  }
}
```

`message` phải customer/staff-safe; `details` không chứa stack trace, checkpoint payload, CoT, secret hoặc cross-customer data.

## 5. Idempotency và replay

Các operations bắt buộc key:

- `POST /api/v1/tickets`
- `POST /api/v1/tickets/{id}/agent-runs`
- `POST /api/v1/tickets/{id}/messages`
- `POST /api/v1/approval-requests/{id}/decision`
- `POST /api/v1/knowledge/documents`
- `POST /api/v1/knowledge/documents/{id}/publish`
- `POST /api/v1/knowledge/documents/{id}/reindex`
- `POST /internal/v1/orders/{id}/sync-payment`

Rules:

1. Scope là authenticated principal/service + operation + key. Support scopes: `TICKET_CREATE`, `AGENT_RUN_CREATE`, `MESSAGE_CREATE`, `APPROVAL_DECISION`, `KNOWLEDGE_DOCUMENT_CREATE`, `KNOWLEDGE_PUBLISH`, `KNOWLEDGE_REINDEX`; commerce scope là `(SYNC_PAYMENT_STATUS,key)`.
2. Cùng scope/key/request hash trả exact status/body đã persist; không chạy lại workflow/action/index build.
3. Response replay có thể thêm `Idempotency-Replayed: true`.
4. Write retry luôn dùng lại key; không sinh key mới sau ambiguous response.
5. Khác key nhưng Ticket đã có non-terminal run trả `409 AGENT_RUN_ALREADY_ACTIVE`.
6. Key reuse với request hash khác là conflict và không execute; public conflict code ngoài các endpoint-specific codes chưa được PLAN đặt tên.

## 6. Time, money, pagination và cursor

- Datetime: UTC ISO-8601, ví dụ `2026-08-04T12:00:00Z`.
- Approval TTL: 24 giờ tuyệt đối UTC từ `requested_at`.
- List APIs: `page`, `page_size`; response gồm items và pagination metadata.
- Timeline: opaque `timeline_cursor`; client không parse sequence internals.
- Money: decimal string + currency, ví dụ `{ "amount": "1250000", "currency": "VND" }`.

## 7. Public endpoint catalog

| Endpoint | Role/scope | Success | Contract notes |
|---|---|---:|---|
| `POST /api/v1/auth/login` | Anonymous | 200 | Email/password → access token + actor; rate limited; no refresh token v0.1. |
| `GET /api/v1/auth/me` | Authenticated | 200 | Principal/role/safe profile. |
| `GET /api/v1/customers/me` | Customer | 200 | Masked own profile/verification status. |
| `GET /api/v1/customers/{id}/summary` | Support Agent+ | 200 | Masked summary; audit read. |
| `POST /api/v1/tickets` | Customer | 201 | Ticket + first message transaction; **không chạy agent**. |
| `GET /api/v1/tickets` | Scoped customer/staff | 200 | Paginated summaries. |
| `GET /api/v1/tickets/{id}` | Scoped customer/staff | 200 | Messages, evidence, latest run, approvals, timeline safe projection. |
| `POST /api/v1/tickets/{id}/messages` | Scoped sender | 201/200 | Message-only hoặc same-run resume. |
| `POST /api/v1/tickets/{id}/agent-runs` | Customer-created flow hoặc qualified staff/system | 201 | Synchronous advance; one active run/ticket. |
| `GET /api/v1/agent-runs/{id}` | Scoped view | 200 | Run summary/evidence/errors; no checkpoint/CoT. |
| `GET /api/v1/agent-runs/{id}/events` | Staff | 200 | Ordered persisted timeline; polling. |
| `GET /api/v1/approval-requests` | Support Agent/Manager | 200 | Pending list filtered by role/expiry. |
| `GET /api/v1/approval-requests/{id}` | Qualified reviewer | 200 | Proposal/evidence/impact/version/hash/expiry. |
| `POST /api/v1/approval-requests/{id}/decision` | Qualified reviewer | 200 | Approve/edit/reject and synchronous resume when applicable. |
| `POST /api/v1/knowledge/documents` | Admin | 201 | Markdown validation/index result. |
| `POST /api/v1/knowledge/documents/{id}/publish` | Admin | 200 | Atomic publish after validation/indexing. |
| `POST /api/v1/knowledge/documents/{id}/reindex` | Admin | 200 | Synchronous, idempotent, atomic index swap; không queue/`202`/polling/auto-publish. |
| `POST /api/v1/knowledge/search` | Admin/Support | 200 | Read-only citations with mandatory policy filters. |
| `GET /api/v1/admin/audit-logs` | Admin/Manager | 200 | Redacted audit list. |

Reindex success status và response đã được PLAN chốt tại §8.3.5; không được thay bằng asynchronous job contract.

## 8. Internal Mock-Commerce endpoint catalog

Mọi route validate exact Bearer token **trước** body/customer/ownership/business validation:

- Thiếu hoặc malformed header: `401 INTERNAL_UNAUTHENTICATED`, `retryable=false`.
- Token sai, user JWT hoặc credential không được phép: `403 INTERNAL_FORBIDDEN`, `retryable=false`.
- SupportPilot adapter tự inject token từ `INTERNAL_SERVICE_TOKEN`; token không là tool/LLM argument và không được đưa vào frontend, logs, audit, tracing hay tool-call input/output.
- Raw internal token bị từ chối trên `/api/v1`; không route nào nhận credential qua query/body/cookie.

| Endpoint | Input/scope | Output | Controls |
|---|---|---|---|
| `GET /internal/v1/customers/{id}` | Service auth + customer ref | Scoped customer summary | `CUSTOMER_NOT_FOUND` |
| `GET /internal/v1/customers/{id}/orders` | Date/status/product filters | Candidate orders | Customer filter required |
| `GET /internal/v1/orders/{id}` | Customer scope + order ID | Order detail/version | Ownership; `ORDER_NOT_FOUND` |
| `GET /internal/v1/orders/{id}/items` | Customer/order scope | Items/variant/quantity | Read-only |
| `GET /internal/v1/orders/{id}/payment` | Customer/order scope | Linked payment | No card data |
| `GET /internal/v1/customers/{id}/payments` | Date/status/amount filters | Transactions | Customer-scoped |
| `GET /internal/v1/payments/{id}` | Customer scope + payment ID | Payment detail | No payment secret |
| `POST /internal/v1/orders/{id}/sync-payment` | Expected order version, transaction ref, approval ref | Updated order/version | Service auth, ownership, approval, idempotency, transaction lock |

SupportPilot không được thay internal call bằng direct repository/SQL access.

## 9. Shared schema fragments

### 9.1 Correlation envelope

```json
{
  "correlation_id": "corr_01..."
}
```

### 9.2 Citation

```json
{
  "chunk_id": "uuid",
  "document_id": "uuid",
  "title": "Payment synchronization policy",
  "version": "1.2",
  "heading": "Successful payment with pending order",
  "score": "ranking-score",
  "excerpt": "redacted bounded excerpt",
  "effective_from": "2026-01-01T00:00:00Z",
  "effective_to": null
}
```

RRF/ranking `score` không được diễn giải là evidence confidence. Safe projection có thể bổ sung vector/lexical gate/provenance fields theo [RAG_DESIGN.md](./RAG_DESIGN.md).

### 9.3 Safe run summary

```json
{
  "run_id": "uuid",
  "run_status": "WAITING_APPROVAL",
  "ticket_status": "WAITING_APPROVAL",
  "current_node": "wait_for_approval",
  "next_required_action": "approval",
  "failure_code": null,
  "correlation_id": "corr_01...",
  "timeline_cursor": "opaque"
}
```

Checkpoint payload và full AgentState không thuộc schema public.

### 9.4 Runtime status vocabularies

API projections dùng đúng canonical values; không tạo frontend/API aliases:

- Ticket: `OPEN`, `PROCESSING`, `WAITING_CUSTOMER`, `WAITING_APPROVAL`, `ESCALATED`, `RESOLVED`, `CLOSED`.
- Agent Run: `CREATED`, `RUNNING`, `WAITING_CUSTOMER`, `WAITING_APPROVAL`, `EXECUTING`, `VERIFYING`, `COMPLETED`, `ESCALATED`, `FAILED`; v0.1 không có `CANCELLED`.
- Approval: `PENDING`, `EDITED_PENDING_REAPPROVAL`, `APPROVED`, `REJECTED`, `EXPIRED`, `SUPERSEDED`, `CONSUMED`, `INVALIDATED`.
- Action Execution: `PENDING`, `RUNNING`, `SUCCEEDED`, `VERIFYING`, `VERIFIED`, `FAILED_RETRYABLE`, `FAILED_FINAL`, `UNKNOWN`.

Allowed transitions are normative in [AGENT_WORKFLOW.md](./AGENT_WORKFLOW.md#11-state-machines); database stores the same values as described in [DATABASE_DESIGN.md](./DATABASE_DESIGN.md#10-status-definitions-và-transition-ownership).

## 10. Authentication contracts

### 10.1 Login request

```json
{
  "email": "customer@example.test",
  "password": "demo-password"
}
```

### 10.2 Login response

```json
{
  "access_token": "redacted",
  "token_type": "Bearer",
  "expires_in_seconds": 900,
  "actor": {
    "id": "uuid",
    "role": "customer",
    "status": "active"
  },
  "correlation_id": "corr_01..."
}
```

V0.1 không có refresh-token endpoint; user login lại khi token hết hạn.

## 11. Ticket creation contract

### 11.1 Request

```http
POST /api/v1/tickets
Authorization: Bearer <token>
Idempotency-Key: ticket-create-001
Content-Type: application/json
```

```json
{
  "subject": "Đã thanh toán nhưng đơn chưa xác nhận",
  "body": "Tôi đã thanh toán cái ghế nhưng trạng thái vẫn pending.",
  "source": "web"
}
```

### 11.2 Response `201`

```json
{
  "ticket_id": "uuid",
  "ticket_number": "SP-000001",
  "ticket_status": "OPEN",
  "correlation_id": "corr_01..."
}
```

Ticket và first message commit trong một transaction. Endpoint này **không tạo hoặc chạy Agent Run**.

## 12. Explicit Agent Run trigger

Required client sequence:

```text
POST /tickets
→ nhận ticket_id
→ POST /tickets/{ticket_id}/agent-runs
```

### 12.1 Request

```http
POST /api/v1/tickets/{ticket_id}/agent-runs
Authorization: Bearer <token>
Idempotency-Key: run-create-001
```

Body có thể là empty object/use-case configuration theo typed contract; PLAN không chốt additional request fields. Client không truyền customer ID hoặc provider override.

### 12.2 Response `201`

```json
{
  "run_id": "uuid",
  "run_status": "WAITING_APPROVAL",
  "ticket_status": "WAITING_APPROVAL",
  "next_required_action": "approval",
  "approval_request_id": "uuid",
  "correlation_id": "corr_01...",
  "timeline_cursor": "opaque"
}
```

Boundary statuses: `WAITING_CUSTOMER`, `WAITING_APPROVAL`, `COMPLETED`, `ESCALATED`, `FAILED`.

### 12.3 Active-run conflict

- Non-terminal: `CREATED`, `RUNNING`, `WAITING_CUSTOMER`, `WAITING_APPROVAL`, `EXECUTING`, `VERIFYING`.
- Same key: replay stored response.
- Different key: `409 AGENT_RUN_ALREADY_ACTIVE`, `retryable=false`, details gồm ticket/run/status/next action.
- Không `CANCELLED` hoặc cancel endpoint v0.1.

### 12.4 Timeout response

Trước business write, deadline vượt 60 giây:

```json
{
  "code": "WORKFLOW_REQUEST_TIMEOUT",
  "message": "The synchronous workflow advance exceeded its deadline.",
  "retryable": true,
  "correlation_id": "corr_01...",
  "details": {
    "run_id": "uuid",
    "run_status": "FAILED",
    "ticket_status": "ESCALATED"
  }
}
```

HTTP `504`; failure/audit persist trước response. Retry tạo run mới bằng key mới vì timed-out run terminal.

## 13. Message same-run resume

### 13.1 Request

```http
POST /api/v1/tickets/{ticket_id}/messages
Authorization: Bearer <token>
Idempotency-Key: message-001
```

```json
{
  "content": "Đơn được đặt hôm qua, số tiền 1.250.000 VND.",
  "attachment_references": []
}
```

`attachment_references` omitted hoặc `[]` hợp lệ. Danh sách non-empty bị reject trước mọi side effect:

```json
{
  "code": "ATTACHMENTS_NOT_SUPPORTED",
  "message": "Ticket attachments are not supported in v0.1.",
  "retryable": false,
  "correlation_id": "corr_01...",
  "details": { "supported_from": "v1.0" }
}
```

Response là HTTP `422`; không insert message, không persist successful idempotency response, không fetch/store file hoặc URL và không resume Agent Run. V0.1 không có ticket attachment upload endpoint hoặc attachment table.

### 13.2 Message-only response `201`

Khi Ticket không `WAITING_CUSTOMER`:

```json
{
  "message_id": "uuid",
  "ticket_id": "uuid",
  "ticket_status": "OPEN",
  "resume_attempted": false,
  "correlation_id": "corr_01..."
}
```

### 13.3 Same-run resume response `200`

Khi Ticket và active run đều `WAITING_CUSTOMER`, backend commit message, lock/check state, rồi resume **chính run cũ**:

```json
{
  "message_id": "uuid",
  "ticket_id": "uuid",
  "ticket_status": "WAITING_APPROVAL",
  "run_id": "same-run-uuid",
  "run_status": "WAITING_APPROVAL",
  "resume_attempted": true,
  "next_required_action": "approval",
  "approval_request_id": "uuid",
  "correlation_id": "corr_01...",
  "timeline_cursor": "opaque"
}
```

- Resume có budget 60 giây mới.
- Timeout không rollback message; trả `504` kèm message/run IDs, run `FAILED`, Ticket `ESCALATED`.
- Waiting Ticket thiếu resumable checkpoint/run: vẫn lưu message, không tạo run ngầm; `200`, `resume_attempted=false`, escalated state và audit invariant failure.
- Same key không tạo message/resume lần hai.

## 14. Approval decision contract

### 14.1 Request

```json
{
  "decision": "approve",
  "reason": "Evidence and policy support payment synchronization.",
  "expected_version": 1,
  "expected_proposal_hash": "sha256:...",
  "edited_action": null
}
```

`decision`: `approve`, `edit`, `reject`. Exact edited-action schema phải khớp allowlisted action contract.

### 14.2 Processing rules

1. Lock approval row.
2. Check actor role, current status, `expires_at`, expected version/hash.
3. Edit phải revalidate schema, HTTP ownership và deterministic business rules.
4. Material edit tạo immutable version/hash mới, reset 24-hour TTL và dừng `EDITED_PENDING_REAPPROVAL`.
5. Non-material edit có thể approve cùng request, không kéo dài TTL.
6. Valid approval resume graph với budget 60 giây mới.
7. Reject/expired không execute và escalates run/Ticket.

### 14.3 Response shape

```json
{
  "approval_id": "uuid",
  "approval_status": "APPROVED",
  "proposal_version": 1,
  "proposal_hash": "sha256:...",
  "run_id": "uuid",
  "run_status": "COMPLETED",
  "ticket_status": "RESOLVED",
  "action_execution_status": "VERIFIED",
  "next_required_action": null,
  "correlation_id": "corr_01...",
  "timeline_cursor": "opaque"
}
```

Ticket `RESOLVED` chỉ hợp lệ nếu action status `VERIFIED` và response đã lưu.

### 14.4 Expired approval

HTTP `409`, code `APPROVAL_EXPIRED`; persist `EXPIRED`, run/Ticket `ESCALATED`, audit `approval.expired`. Expired approval không revive.

## 15. Mock-Commerce payment synchronization

### 15.1 Request example

```http
POST /internal/v1/orders/{order_id}/sync-payment
Authorization: Bearer <INTERNAL_SERVICE_TOKEN>
Idempotency-Key: action-execution-uuid
```

```json
{
  "customer_ref": "synthetic-customer-ref",
  "transaction_ref": "synthetic-txn-ref",
  "expected_order_version": 3,
  "approval_ref": "approval-uuid",
  "proposal_hash": "sha256:..."
}
```

Field names beyond the PLAN concepts are illustrative logical contract; `commerce_contracts` must freeze exact names before implementation.

### 15.2 Rules

- Validate exact internal Bearer auth before customer/body/ownership validation; token never enters request schema, response, logs, audit or tool-call projection.
- Lock order/payment and validate expected version/status/amount/currency/transaction relationship.
- Persist idempotency result atomically with state change.
- Return updated order/version; SupportPilot performs fresh read verification.
- Errors explicitly named by PLAN: `STALE_ORDER`, `PAYMENT_MISMATCH`, `APPROVAL_REQUIRED`, `ORDER_NOT_FOUND`.
- Connection loss after send may yield SupportPilot Action `UNKNOWN`; status-check/verify before retry with same key.

## 16. Knowledge contracts

- Upload accepts only `text/markdown`, max 2 MB, required metadata and checksum validation.
- PDF/DOCX/OCR rejected in v0.1.
- Publish only after validation/indexing success.
- Search returns at most five gated citations and full safe provenance; no raw embedding/checkpoint data.

### 16.1 Synchronous reindex

```http
POST /api/v1/knowledge/documents/{document_id}/reindex
Authorization: Bearer <admin JWT>
Idempotency-Key: reindex-document-v2
```

Success luôn là HTTP `200 OK`:

```json
{
  "document_id": "uuid",
  "document_version": "v1",
  "previous_index_version": "idx-001",
  "new_index_version": "idx-002",
  "reindex_status": "COMPLETED",
  "document_status": "PUBLISHED",
  "chunk_count": 12,
  "embedding_provider": "sentence_transformers",
  "embedding_model": "intfloat/multilingual-e5-small",
  "embedding_revision": "c007d7ef6fd86656326059b28395a7a03a7c5846",
  "embedding_dimension": 384,
  "embedding_input_format_version": "e5-prefix-v1",
  "calibration_required": true,
  "correlation_id": "uuid"
}
```

- `previous_index_version` có thể null; các provenance fields còn lại non-null và `chunk_count >= 0`.
- Reindex giữ nguyên document lifecycle (`DRAFT/VALIDATED/PUBLISHED`), không tự publish. `SUPERSEDED/EXPIRED` không reindexable.
- Published document tiếp tục dùng active index cũ trong lúc build; chỉ sau full validation mới chuyển index mới `COMPLETED` và atomic swap pointer.
- Failure persist failed attempt nhưng không phá active index. Timeout riêng là `KNOWLEDGE_REINDEX_TIMEOUT_SECONDS=120`.
- Provider/model/revision/dimension/input-format hoặc retrieval-scoring change đặt `calibration_required=true` và effective `RAG_THRESHOLD_CALIBRATED=false`.
- Replay cùng principal/key/hash trả exact persisted `200` body và không build lại. Không `202`, job ID, queue hoặc polling endpoint.

| HTTP/code | Retryable | Contract |
|---|---:|---|
| `404 KNOWLEDGE_DOCUMENT_NOT_FOUND` | false | Missing/outside admin scope |
| `409 KNOWLEDGE_DOCUMENT_NOT_REINDEXABLE` | false | `SUPERSEDED/EXPIRED` hoặc conflicting operation |
| `409 EMBEDDING_CONFIGURATION_MISMATCH` | false | Runtime/index embedding contract mismatch |
| `422 REINDEX_VALIDATION_FAILED` | false | Markdown/chunk/provenance/schema invalid |
| `500 REINDEX_EXECUTION_FAILED` | true | Transient embedding/database/provider failure |
| `504 REINDEX_EXECUTION_FAILED` | true | Vượt 120 giây; failed attempt persisted |

Exact RAG contract: [RAG_DESIGN.md](./RAG_DESIGN.md).

## 17. Error/status matrix

### 17.1 Codes explicitly fixed by PLAN

| HTTP | Code | Retryable | Context |
|---:|---|---|---|
| 401 | `INVALID_CREDENTIALS` | false | Login failure |
| 403/401 | `ACCOUNT_DISABLED` | false | Disabled actor |
| 401 | `UNAUTHENTICATED` | false | Missing/invalid JWT |
| 403 | `FORBIDDEN` | false | Role/ownership denial |
| 404 | `CUSTOMER_NOT_FOUND` | false | Customer lookup |
| 404 | `TICKET_NOT_FOUND` | false | Ticket scope/lookup |
| 404 | `APPROVAL_NOT_FOUND` | false | Approval lookup |
| 401 | `INTERNAL_UNAUTHENTICATED` | false | Missing/malformed internal Bearer token |
| 403 | `INTERNAL_FORBIDDEN` | false | Wrong token, user JWT or disallowed credential on internal API |
| 422 | `ATTACHMENTS_NOT_SUPPORTED` | false | Non-empty ticket message attachment references |
| 409 | `AGENT_RUN_ALREADY_ACTIVE` | false | Different key with non-terminal run |
| 504 | `WORKFLOW_REQUEST_TIMEOUT` | true | Synchronous advance deadline |
| 409 | `APPROVAL_EXPIRED` | false | Lazy expiry at decision |
| 404 | `ORDER_NOT_FOUND` | false | Mock-Commerce order |
| 409 | `STALE_ORDER` | false | Expected version mismatch |
| 409/422 | `PAYMENT_MISMATCH` | false | Evidence/state mismatch |
| 403/409 | `APPROVAL_REQUIRED` | false | Missing/invalid approval reference |
| 404 | `KNOWLEDGE_DOCUMENT_NOT_FOUND` | false | Reindex target missing/out of scope |
| 409 | `KNOWLEDGE_DOCUMENT_NOT_REINDEXABLE` | false | Reindex disallowed by lifecycle/conflict |
| 409 | `EMBEDDING_CONFIGURATION_MISMATCH` | false | Embedding/index contract mismatch |
| 422 | `REINDEX_VALIDATION_FAILED` | false | Reindex validation failure |
| 500/504 | `REINDEX_EXECUTION_FAILED` | true | Reindex runtime failure or 120-second timeout |

### 17.2 Typed failure names fixed outside endpoint error table

- `UNSUPPORTED_INTENT` causes conservative escalation in v0.1.
- `agent_run.checkpoint_invariant_failed`, `agent_run.resume_invariant_failed`, `agent_run.timeout`, `approval.expired` are audit/event names, not automatically public API codes.

Không tự thêm public code khác mà không cập nhật contract review.

## 18. Retry rules

- LLM: 12 giây/attempt, tối đa 2 attempts; retry chỉ khi remaining budget ≥17 giây.
- Read HTTP: tối đa 3 attempts, short exponential backoff, chỉ timeout/5xx.
- RAG: một retry rồi no-answer/manual review.
- Write HTTP: no blind semantic retry; status-check then same key.
- Permission/validation/business 4xx: không retry.
- Public replay là idempotency behavior, không phải workflow retry.

## 19. Walking Skeleton behavior

Walking Skeleton dùng **cùng endpoint/path/response/state names**:

- Demo login fixture.
- Ticket thật persist PostgreSQL.
- `FakeAgentAdapter` fixed UC-01 proposal.
- `FakeApprovalAdapter` approve/reject.
- `FakeActionAdapter` trả deterministic `VERIFIED` trước demo `RESOLVED`, không commerce write.

Không tạo fake-only public endpoint. `WORKFLOW_PROFILE=walking_skeleton` chỉ local/test; final CI từ chối profile/fake path.

## 20. Versioning và backward compatibility

- Public/internal prefixes versioned `v1`.
- Walking Skeleton và final implementation giữ same public envelope/state names.
- `packages/commerce_contracts` là nơi duy nhất chia sẻ internal HTTP types; không DB types.
- Additive optional field cần safe client behavior; breaking path/schema/state/error semantic change cần PLAN/ADR review.
- Proposal, graph, prompt, tool, policy, embedding/index và dataset versions được persist theo domain contract.
- Không dùng provider/model change để thay API contract ngầm.

## Source and traceability

- Nguồn chính: [PLAN.md](./PLAN.md), §8, §9.3–§9.4, §10, §14, §20, §23–§24.
- Tài liệu liên quan: [PROJECT_SPEC.md](./PROJECT_SPEC.md), [ARCHITECTURE.md](./ARCHITECTURE.md), [DATABASE_DESIGN.md](./DATABASE_DESIGN.md), [AGENT_WORKFLOW.md](./AGENT_WORKFLOW.md), [RAG_DESIGN.md](./RAG_DESIGN.md), [SECURITY.md](./SECURITY.md).
- Quyết định không được thay đổi: explicit create-ticket/create-run; no implicit run; 60/5/12-second budgets; active-run `409`; same-run message resume; 24-hour approval; HTTP-only commerce access; idempotency; `RESOLVED` only after `VERIFIED`.
- Các request fields chưa được PLAN chốt vẫn được đánh dấu illustrative; attachment, reindex và internal-auth status/error contracts ở trên là normative theo PLAN.
- Phiên bản nguồn: `PLAN.md` hiện không có version nội tại; traceability snapshot ngày 2026-08-04.
