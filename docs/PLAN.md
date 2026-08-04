# Kế hoạch triển khai kỹ thuật SupportPilot

## 1. Executive summary

SupportPilot là hệ thống hỗ trợ khách hàng thương mại điện tử kết hợp bốn năng lực:

- RAG truy xuất chính sách có phiên bản và nguồn trích dẫn.
- AI Agent hiểu ticket, trích xuất dữ liệu và điều phối quy trình.
- Tool calling lấy dữ liệu giao dịch từ API, không dùng RAG cho order/payment/shipment.
- Human-in-the-loop kiểm soát mọi hành động nghiệp vụ làm thay đổi trạng thái.

Đối tượng sử dụng gồm Customer, Support Agent, Support Manager và Admin. Giá trị cốt lõi là giảm thời gian tra cứu thủ công trong khi vẫn duy trì customer isolation, policy grounding, approval, idempotency và audit trail.

Kiến trúc giữ nguyên theo hướng modular monolith: Vue 3 frontend, FastAPI backend, LangGraph workflow, PostgreSQL + pgvector và một Mock-Commerce runtime. SupportPilot và Mock-Commerce dùng chung PostgreSQL instance trong local Compose nhưng sở hữu hai schema và bốn database role tách biệt. SupportPilot chỉ truy cập dữ liệu commerce qua HTTP API.

Provider mặc định của Milestone v0.1 là Gemini API qua LLM adapter. Embedding dùng `intfloat/multilingual-e5-small` revision cố định, chạy local bằng SentenceTransformers với dimension 384. OpenAI và Ollama chỉ là provider thay thế.

Vertical slice ưu tiên:

> Khách đã thanh toán một sản phẩm nhưng đơn chưa được xác nhận, kể cả khi không cung cấp order ID.

Milestone v0.1 chỉ hoàn thành UC-01 Payment Mismatch end-to-end. Vue tạo Ticket trước, sau đó gọi explicit synchronous Agent Run; không có background queue. Kế hoạch này đã được review và là nguồn triển khai chính thức cho v0.1.

Quá trình triển khai ưu tiên `SKEL-001` Walking Skeleton ngay sau foundation: một demo tạm thời nối Vue, FastAPI, PostgreSQL và public API contract bằng fake adapters. Các task sau thay dần fake auth/agent/approval bằng implementation thật mà không đổi contract phía frontend.

## 2. Requirements extracted from the document

### 2.1 Functional requirements

- Nhận ticket từ web form hoặc API.
- Hỗ trợ tiếng Việt chính, có khả năng xử lý tiếng Anh.
- Milestone v0.1 chỉ phân loại và xử lý intent `payment_mismatch`; UC-02–UC-05 được giữ trong thiết kế v1.0 nhưng không thuộc acceptance criteria v0.1.
- Trích xuất order ID, product keyword, amount, time, transaction reference và mô tả lỗi.
- Xác định customer từ authenticated session hoặc email đã xác minh.
- Resolve order trong phạm vi customer dù không có order ID.
- Lấy dữ liệu giao dịch qua internal/mock APIs.
- Truy xuất policy qua RAG với version, effective date và citation.
- Đánh giá evidence bằng business rules deterministic.
- Soạn resolution plan và customer response draft.
- Cho phép approve, edit hoặc reject action.
- Revalidate trạng thái trước khi thực thi action đã duyệt.
- Hiển thị ticket inbox, evidence, citation, approval state và execution timeline.
- Lưu agent run, tool calls, retrieved chunks, quyết định, lỗi và audit events.
- Tự resume chính Agent Run đang `WAITING_CUSTOMER` khi customer gửi message bổ sung.
- Chạy mỗi synchronous graph advance trong tổng budget 60 giây, có deadline propagation và failure state rõ ràng.
- Giữ `attachment_references` trong message request để tương thích tương lai, nhưng v0.1 chỉ chấp nhận omitted hoặc mảng rỗng; mọi mảng khác rỗng bị từ chối rõ ràng trước khi lưu message hoặc resume run.
- Cho phép Admin reindex knowledge document đồng bộ, idempotent và atomic; không queue, không polling và không tự publish document.

### 2.2 Technical constraints

- Backend: FastAPI, Pydantic, SQLAlchemy 2, Alembic.
- Frontend: Vue 3, Vite, TypeScript, Pinia, Vue Router.
- Database chính: PostgreSQL.
- Vector storage: pgvector trong v0.1 và MVP v1.0.
- Agent orchestration: LangGraph, một orchestrator với các node chuyên trách.
- LLM mặc định: Gemini API qua adapter; OpenAI và Ollama chỉ là alternative provider.
- Embedding mặc định: local SentenceTransformers `intfloat/multilingual-e5-small`, dimension 384, revision cố định.
- Mock services phải có interface/adapter để thay bằng external provider.
- Mock-Commerce sở hữu schema `commerce`; SupportPilot sở hữu schema `support`. Không có cross-schema foreign key hoặc direct commerce repository trong SupportPilot.
- Milestone v0.1 chạy đồng bộ, không Redis worker hoặc background queue.
- Không lưu hoặc hiển thị chain-of-thought; chỉ lưu evidence, execution summary, rationale ngắn, tool calls và kết quả.
- Không dùng Kubernetes, Kafka hoặc hạ tầng trả phí không cần thiết trong MVP.
- Không expose arbitrary HTTP, SQL, filesystem hay code execution cho LLM.
- Mọi `/internal/v1/*` chỉ nhận một Bearer service token; user JWT và internal token không được dùng chéo public/internal boundary.

### 2.3 Reconciliation of document ambiguities

| Vấn đề | Nội dung khác nhau | Cách xử lý trong kế hoạch |
|---|---|---|
| Repository | DOCX đề xuất `apps/services/packages`; planning prompt yêu cầu `backend/frontend/...` | Dùng cấu trúc `backend/`, `frontend/`, `docs/`, `infrastructure/`, `tests/`, `scripts/`. |
| Vector store | DOCX nhắc pgvector/Qdrant | pgvector là lựa chọn duy nhất trong v0.1/v1.0; Qdrant chỉ được đánh giá lại khi có nhu cầu scale rõ ràng. |
| Redis/worker | DOCX đề xuất Redis + Celery/RQ; prompt yêu cầu chỉ dùng khi cần | Không dùng trong vertical slice; bổ sung khi cần xử lý nền bền vững hoặc concurrency cao. |
| Approval | “Mọi action thay đổi trạng thái” cần approval; một số tool như draft/escalate có thể tự động | Business write và customer-facing send cần approval. Draft, audit, timeline và escalation nội bộ có thể tự động nhưng vẫn phải audit. |
| Mock services | Tài liệu vừa ưu tiên monolith vừa đề cập module/container riêng | Core SupportPilot là modular monolith; một mock-commerce runtime mô phỏng boundary của external provider nhưng dùng chung repository và image. |
| Phạm vi use case | Có bảy use case nhưng chỉ năm core MVP | v0.1 chỉ UC-01; MVP v1.0 gồm UC-01–UC-05; UC-06–UC-07 là Post-MVP. |
| RAG hybrid search | DOCX nhắc BM25 | v0.1 dùng PostgreSQL FTS kết hợp vector search; BM25/reranker chuyên dụng chỉ thêm nếu evaluation chứng minh cần thiết. |
| Document ingestion | Plan cũ gồm Markdown và PDF | v0.1 chỉ ingest UTF-8 Markdown. Text PDF chuyển sang v1.0; DOCX/OCR để Post-MVP. |
| Field encryption | Schema cũ dùng tên `*_cipher/hash` trong khi v0.1 hoãn encryption | v0.1 dùng cột plaintext tên trung lập và chỉ chứa synthetic local/demo data. Encryption migration add/backfill/switch/drop thuộc v1.0. |
| Agent trigger | Có thể hiểu create-ticket tự chạy agent | Vue gọi `POST /tickets`, nhận `ticket_id`, rồi gọi riêng `POST /tickets/{ticket_id}/agent-runs`. |
| Ticket attachment | Contract cũ giữ `attachment_references` trong khi v0.1 chưa có upload/attachment | Giữ field forward-compatible nhưng omitted/`[]` mới hợp lệ; non-empty trả `422 ATTACHMENTS_NOT_SUPPORTED`, không lưu/ignore/fetch. Ticket attachment bắt đầu từ v1.0. |
| Knowledge reindex | Có endpoint nhưng chưa rõ sync/async, atomic swap và idempotency | v0.1 reindex đồng bộ, trả `200`, giữ active index cũ đến khi index mới hoàn tất rồi swap atomic; failure không làm mất active index và thay config bắt buộc recalibrate. |
| Internal authentication | “Service token” chưa đủ phân biệt user JWT và internal credential | `/internal/v1/*` dùng đúng `Authorization: Bearer <INTERNAL_SERVICE_TOKEN>`; hai loại credential không dùng chéo và token không đi vào log/audit/LLM/frontend. |

## 3. MVP, Post-MVP, Advanced và Out of Scope

| Nhóm | Chức năng | Lý do và giới hạn |
|---|---|---|
| Milestone v0.1 | Chỉ UC-01 Payment Mismatch end-to-end: ticket, identity, Order Resolution, Order/Payment HTTP APIs, Markdown RAG, LangGraph, approval, verified action, audit và Vue review flow | Vertical slice nhỏ nhất chứng minh đủ RAG, agent, API integration và HITL. |
| Milestone v0.1 | Gemini API, local multilingual E5, PostgreSQL + pgvector, explicit synchronous Agent Run và same-run message resume | Không queue; mỗi graph advance có tổng budget 60 giây. |
| Milestone v0.1 | Tối thiểu 20 automated tests quan trọng, không có giới hạn tối đa cứng; target evaluation là 25 golden cases | Coding agent được bổ sung test khi phát hiện regression, concurrency, security hoặc edge case. Golden set được tách calibration/holdout để không tự đánh giá trên dữ liệu đã dùng chọn threshold. |
| Milestone v0.1 | Markdown knowledge ingestion, customer-response draft, basic JSON logs/audit | Không có ticket attachment/upload; chưa upload PDF, chưa gửi email thật và chưa advanced observability. |
| MVP v1.0 | UC-01–UC-05, ticket attachment/upload contract, PDF upload, refresh-token rotation, field-level encryption hoàn chỉnh và advanced observability | Mở rộng sau khi UC-01 và các state/approval/action invariants ổn định. |
| Post-MVP | UC-06 duplicate charge và UC-07 warranty | Có rủi ro và rule phức tạp hơn; triển khai sau năm luồng chính. |
| Post-MVP | Gmail, Zendesk/Freshdesk, Slack, Stripe sandbox | External integration không cần cho giá trị cốt lõi ban đầu. |
| Post-MVP | Redis worker, live SSE ở tải lớn, reranker | Chỉ cần khi workload hoặc evaluation chứng minh lợi ích. |
| Advanced | Multi-tenant SaaS, automatic feedback learning, Qdrant, workflow builder | Tăng mạnh độ phức tạp vận hành và bảo mật. |
| Advanced | Voice support, transcription, local LLM profile, advanced analytics | Không cần cho portfolio MVP. |
| Out of scope | Autonomous refund/cancel không approval, arbitrary URL/SQL/code/filesystem tool | Rủi ro bảo mật và tài chính không chấp nhận được. |
| Out of scope | Kubernetes, Kafka, production payment processing, dữ liệu khách thật | Không phù hợp mục tiêu demo/MVP. |
| Out of scope | Lưu chain-of-thought hoặc raw secrets/card data | Vi phạm nguyên tắc an toàn và riêng tư. |

Release gate v0.1:

- `RAG_THRESHOLD_CALIBRATED=true`; calibration và locked holdout reports tách riêng, gắn exact embedding model/revision/input-format/index với dataset/subset version/checksum.
- SupportPilot runtime không thể đọc schema `commerce`; Mock-Commerce runtime không thể đọc schema `support`.
- Import-boundary test chứng minh hai apps không chia sẻ database model/repository/session và SupportPilot chỉ gọi commerce qua HTTP contracts.
- Approval expiry 24 giờ, message resume và agent timeout 60 giây đều có automated test.
- Timeout không được làm Ticket `RESOLVED`; possible write phải đi qua `UNKNOWN` và reconciliation.
- Các cột plaintext chỉ chứa synthetic local/demo data; không có cột `*_cipher/hash` giả.
- Walking Skeleton chạy được trước full RAG/LangGraph/approval implementation và chỉ dùng fake adapters sau interface đã review; release bắt buộc `WORKFLOW_PROFILE=v0_1` và không còn fake path có thể được kích hoạt.
- Non-empty ticket `attachment_references` luôn trả đúng `422 ATTACHMENTS_NOT_SUPPORTED`; không có attachment table, upload endpoint hoặc side effect trong v0.1.
- Internal Mock-Commerce auth chặn missing/wrong/user-token trước khi validate customer hay business input; token không xuất hiện trong log, audit, tool output hoặc frontend bundle.
- Knowledge reindex replay cùng key trả persisted `200` result, failure giữ nguyên active index, và thay embedding provenance đặt calibration về `false`.

## 4. Use cases

Milestone assignment: UC-01 thuộc v0.1; UC-02–UC-05 thuộc MVP v1.0; UC-06–UC-07 thuộc Post-MVP. Các contract ngoài UC-01 được giữ để bảo toàn kiến trúc nhưng không được đưa vào backlog hoặc Definition of Done v0.1.

Quy tắc chung khi không xác định được order:

- Chỉ tìm trong orders của `verified_customer_id`.
- Score ≥85, chỉ có một ứng viên và cách runner-up ít nhất 15 điểm: chọn tự động và ghi lại evidence.
- Score 60–84 hoặc có nhiều ứng viên tương đương: hiển thị thông tin đã mask để khách xác nhận.
- Score <60: hỏi thêm product, thời gian, amount hoặc transaction reference.
- Không xác minh được customer: dừng trước khi đọc dữ liệu giao dịch.
- Không bao giờ dùng RAG để tìm order hoặc payment.

| Use case | Actor, trigger và input | Extraction, API/tool và policy | Approval, success và failure |
|---|---|---|---|
| UC-01 Payment mismatch | Customer báo đã trả tiền nhưng order chưa confirmed; order ID có thể thiếu | Extract product, order ID, amount, time, transaction ref. Gọi customer context, order search, recent payments, order detail, payment status, payment-order matcher. RAG: payment synchronization policy | `sync_payment_status` cần Support Agent approve. Thành công: order được sync và response không yêu cầu trả lần hai. Thiếu/mâu thuẫn evidence hoặc API lỗi: clarification/manual review. |
| UC-02 Defective return (v1.0) | Customer báo sản phẩm lỗi trong return window | Extract product/item, delivery date, symptom, requested resolution, attachments. Gọi order items, shipment/delivery evidence. RAG: return/refund policy, evidence requirements, approval limit | Return/inspection/refund request cần approval theo amount. Thiếu ảnh/video: yêu cầu bổ sung. Hết hạn hoặc policy không rõ: escalate. |
| UC-03 Shipping delay/cancel (v1.0) | Customer báo giao trễ và muốn hủy/hoàn tiền | Extract order/product, promised date, desired action. Gọi order và shipping events. RAG: SLA, cancellation, return-to-sender policy | Cancel/RTS/refund cần approval. Chưa handover: đề xuất cancel; đã ship: RTS/manual route. Carrier timeout hoặc event mâu thuẫn: retry rồi manual review. |
| UC-04 Wrong/missing item (v1.0) | Customer nhận sai variant hoặc thiếu quantity | Extract received item, expected item, quantity, attachments. Gọi order items, package manifest, delivery proof. RAG: wrong/missing item claim window và remedy | Claim/replacement/partial refund cần approval. Thành công: claim và remedy được tạo. Evidence thiếu: yêu cầu bổ sung; không tự kết luận gian lận. |
| UC-05 Address change (v1.0) | Customer muốn đổi địa chỉ, có thể thiếu order ID | Extract order/product và structured address. Resolve order, shipping state và validate address. RAG: cutoff status, carrier restriction, fee | Address update cần Support Agent approve. Chỉ thực hiện trước handover. Sau handover hoặc address không serviceable: từ chối có giải thích/escalate. |
| UC-06 Duplicate charge | Customer thấy hai giao dịch cho một order | Extract amount, time, transaction refs. Gọi payment history, duplicate detector, order matcher. RAG: duplicate-charge investigation policy | Investigation cần approval; refund cần manager theo threshold. Không đủ hai candidate hoặc trạng thái reversed/pending: không kết luận duplicate. Post-MVP. |
| UC-07 Warranty | Sản phẩm lỗi sau return window nhưng còn warranty | Extract product, serial, purchase time, symptoms. Gọi order item, warranty status và prior claims. RAG: warranty coverage, exclusion, repair SOP | Warranty claim cần approval. Serial mismatch/evidence thiếu: clarification hoặc escalate. Post-MVP. |

## 5. Architecture

```mermaid
flowchart TD
    U["Customer / Support Agent / Manager / Admin"] --> V["Vue 3 application"]
    V --> B["FastAPI modular monolith"]
    B --> AUTH["Authentication + RBAC"]
    B --> T["Ticket / Message / Approval APIs"]
    B --> O["Agent Orchestrator"]
    O --> G["LangGraph workflow"]
    G --> TR["Allowlisted Tool Registry"]
    TR -->|HTTP only| MC["Internal Mock-Commerce API"]
    TR --> R["RAG Retrieval"]
    R --> PGS["PostgreSQL schema support + pgvector"]
    B --> PGS
    MC --> PGC["PostgreSQL schema commerce"]
    G --> LLM["LLM Adapter: Gemini default"]
    G --> A["Approval Interrupt / Resume"]
    A --> T
    B --> N["Response Draft / Internal Alert"]
    B --> AUD["Audit + Run Events"]
    AUD --> PGS
    ING["Markdown RAG Ingestion"] --> PGS
```

### 5.1 Component boundaries

- Vue frontend chỉ gọi public SupportPilot API; không gọi mock-commerce hoặc LLM trực tiếp.
- Vue tạo Ticket bằng `POST /tickets`, sau đó mới gọi `POST /tickets/{ticket_id}/agent-runs`; create-ticket không tự chạy agent.
- FastAPI chịu trách nhiệm auth, customer scope, API validation, ticket lifecycle và orchestration.
- LangGraph quản lý state, routing, interrupt/resume và failure path; không chứa business rule tài chính chỉ trong prompt.
- LangGraph checkpoint store là source of truth duy nhất để resume graph; dùng `agent_run.id` làm `thread_id`, không expose qua public API và không lưu chain-of-thought.
- Tool Registry là allowlist duy nhất agent có thể gọi, áp dụng permission, timeout, idempotency và audit.
- Mock-Commerce API mô phỏng external commerce provider. SupportPilot không import commerce repository và không đọc commerce tables; adapter production có thể thay base URL/credentials mà không đổi graph.
- SupportPilot commerce adapter tự inject `Authorization: Bearer <INTERNAL_SERVICE_TOKEN>` từ environment. LLM không nhìn thấy, chọn hoặc ghi đè credential; frontend không nhận token này.
- PostgreSQL local là một instance nhưng tách schema `support`/`commerce`, owner/runtime role và migration credential. Không có cross-schema foreign key.
- Schema `support` chứa ticket, LangGraph checkpoints, approval, audit, knowledge base và pgvector. Schema `commerce` chứa customer/order/payment seed phục vụ Mock-Commerce.
- RAG ingestion tách khỏi request path; publish tài liệu chỉ sau validation/indexing thành công.
- Approval system lưu immutable proposal snapshot, decision, editor, version và action execution.
- Notification v0.1 chỉ tạo draft/internal record; chưa gửi customer email thật.
- Không Redis, worker hoặc background queue trong v0.1. Khi thêm sau v1.0, queue không được trở thành nguồn dữ liệu chính.
- `support.agent_runs` là source of truth cho business/operational status tổng quan; `support.agent_run_events` là source of truth cho UI timeline; `support.audit_logs` là source of truth cho security/business audit. Events/audit không được dùng reconstruct hoặc resume graph.
- Orchestration service chịu trách nhiệm đồng bộ checkpoint và `agent_runs.status`; startup/recovery reconciliation phải escalate khi hai nguồn vi phạm invariant tại §7.8.

### 5.2 Deployment boundary trong v0.1

- `backend`: public SupportPilot API và synchronous agent runtime; chỉ nhận `support_app` credential.
- `mock-commerce`: cùng codebase/image nhưng chạy entrypoint mock API riêng; chỉ nhận `commerce_app` credential và cùng `INTERNAL_SERVICE_TOKEN` để validate `/internal/v1/*`.
- `postgres`: một instance, có `vector`, `pg_trgm`, `unaccent` và `citext`.
- `db-bootstrap`: one-shot role/schema bootstrap bằng admin credential; không dùng để migrate hoặc chạy application.
- `migrate-support` và `migrate-commerce`: one-shot migration riêng với owner credential tương ứng.
- `frontend`: Vite development server hoặc static build.
- `mailpit`: không nằm trong default v0.1 vì `EMAIL_BACKEND=draft_only`; có thể trở lại ở v1.0.
- `redis`: không có trong v0.1 Compose.

### 5.3 Walking Skeleton boundary

`SKEL-001` tạo demo nối frontend, backend, PostgreSQL và API contract trước full database/RAG/LangGraph:

- Vue login bằng demo fixture, tạo Ticket và gọi explicit Agent Run.
- Backend persist Ticket/message bằng repository interface và minimal forward-compatible support migration.
- `FakeAgentAdapter` trả proposal UC-01 cố định; `FakeApprovalAdapter` hỗ trợ approve/reject; `FakeActionAdapter` trả deterministic `VERIFIED` result trước khi Ticket demo được `RESOLVED`, nhưng không gọi commerce write.
- UI hiển thị proposal, decision và Ticket result qua cùng public response types dự kiến dùng cho v0.1 thật.
- `WORKFLOW_PROFILE=walking_skeleton` chỉ dùng local/test. Final v0.1 dùng `WORKFLOW_PROFILE=v0_1`; CI release phải từ chối walking-skeleton profile.

Các fake adapter không được chứa logic production hoặc được import trực tiếp từ router/UI. Các task DB/Auth/Ticket/RAG/Agent/Approval/Action sau thay implementation phía sau interface; không đổi endpoint, state name hoặc response envelope đã demo. Walking Skeleton không yêu cầu Gemini, embedding, RAG, full LangGraph, real Mock-Commerce transaction, proposal versioning hoặc payment synchronization. `VERIFIED` ở profile này chỉ là deterministic fake contract result để giữ invariant state machine; không được diễn giải là commerce write thật hoặc dùng làm release evidence.

## 6. Modules and responsibilities

| Module | Trách nhiệm; input → output | Dữ liệu sở hữu | Dependency được phép / không nên phụ thuộc | Public interface |
|---|---|---|---|---|
| Authentication | Credentials/access token → authenticated principal | `support.users`; refresh rotation để v1.0 | Core, support repository, audit / không phụ thuộc agent | `authenticate`, `require_role` |
| Customer | Principal → scoped support customer và external commerce reference | `support.customers`; address profile để v1.0 | Auth, support repository / không gọi LLM hoặc commerce repository | `get_verified_context`, `mask_profile` |
| Product | Product/category lookup | `commerce.products` do Mock-Commerce sở hữu | Commerce repository chỉ trong Mock-Commerce | HTTP product contract, v1.0 |
| Order | Order reads và controlled payment-state transition | `commerce.orders/items` | Commerce repository chỉ trong Mock-Commerce / không phụ thuộc RAG | Internal HTTP `search_orders`, `get_order`, `sync_payment` |
| Payment | Payment reads và matching source | `commerce.payments` | Commerce repository chỉ trong Mock-Commerce / SupportPilot gọi HTTP adapter | Internal HTTP `get_status`, `recent_payments` |
| Shipping | Shipment/events/address rules | Shipments | Commerce repository | `get_shipment`, `validate_address`, `change_address` |
| Ticket | Ticket/message lifecycle và same-run resume | `support.support_tickets`, `support.ticket_messages`; không có attachment persistence v0.1 | Customer, agent orchestrator, audit / không gọi commerce trực tiếp | `create`, `append_message`, `transition` |
| Knowledge Base | Markdown document/version/chunk/index lifecycle | `support.knowledge_documents/chunks/index_versions` | Support DB, local embedding adapter | `ingest_markdown`, `validate`, `publish`, `reindex`, `expire` |
| RAG | Query/filters → ranked cited chunks | Không sở hữu source document | KB repository, embedding adapter / không gọi transactional APIs | `retrieve_policy` |
| Order Resolution | Entities + verified customer → resolved order/clarification | Resolution result trong agent state | Customer-scoped order/payment ports / không dùng RAG | `resolve`, `score_candidates` |
| Policy Engine | Evidence + policy → deterministic eligibility | Versioned rule definitions | Domain schemas / không phụ thuộc framework agent | `evaluate` |
| Agent Orchestration | Ticket → paused/completed workflow; checkpoint/run reconciliation | LangGraph checkpoint state; `agent_runs` metadata summary | Ticket, tools, RAG, approval, audit | `start_run`, `resume_run`, `reconcile_run` |
| Tool Registry | Tool request → validated/audited result | Tool-call records | Integration ports, permissions, audit | `register`, `invoke` |
| Approval | Proposal → approve/edit/reject/execution authorization | Approval requests | Auth/RBAC, audit, action registry | `request`, `decide`, `authorize_execution` |
| Notification | Draft response và internal alert | `support.notifications` | Ticket, audit; email send để v1.0 | `create_draft`, `notify_staff` |
| Audit | Structured security/business event → append-only audit | `support.audit_logs`; không sở hữu workflow state/timeline | Core redaction only / không phụ thuộc domain services | `record_event` |
| Integration adapters | Internal/external HTTP translation | Không sở hữu domain data | HTTP client, config | Order/Payment/Shipping/Email ports |
| Evaluation | Dataset + workflow → metrics/report | Evaluation cases/results | Agent/RAG interfaces, fake providers | `run_suite`, `compare_thresholds` |

Repositories chỉ làm persistence và không gọi service khác. API routers chỉ validate/authenticate và gọi application services; không chứa business logic.

## 7. Database design

Mọi schema contract dưới đây là PostgreSQL-specific và là đầu vào trực tiếp cho Alembic. Quy ước vật lý bắt buộc:

- PK dùng `UUID PRIMARY KEY DEFAULT gen_random_uuid()`. Timestamp dùng `TIMESTAMPTZ` và application/database đều ghi UTC; `created_at`/`updated_at` mặc định `now()` khi có mặt.
- Tiền dùng `NUMERIC(18,2)`; currency dùng `CHAR(3)` với `CHECK (currency ~ '^[A-Z]{3}$')`. Concurrency version dùng `INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1)` và tăng đúng một sau mỗi write thành công.
- Finite lifecycle/status dùng PostgreSQL named enum, viết hoa như state machine/API. Domain service kiểm tra allowed transition; DB chỉ kiểm tra tập giá trị và structural invariants, không có state-transition trigger.
- JSONB chỉ chứa auxiliary projection đã redact, schema-versioned khi cần; field dùng để join, ownership, filter, unique, amount, currency, state hoặc optimistic locking phải là cột riêng. JSONB không được chứa raw authorization, password/secret, card data, chain-of-thought hoặc bản sao checkpoint.
- Các FK lịch sử/audit/execution dùng `ON DELETE RESTRICT` hoặc không FK để giữ lịch sử. v0.1 không có hard-delete Ticket endpoint. `CASCADE` không được dùng trong các bảng dưới đây; retention/anonymization về sau là workflow riêng.
- Bảng được đánh dấu immutable/append-only không có `updated_at`; runtime role chỉ được `INSERT/SELECT`, bị revoke `UPDATE/DELETE`. Không dùng “soft immutability” chỉ bằng convention.
- v0.1 chỉ dùng synthetic local/demo data.

### 7.1 Ownership, role và bootstrap

| Role | Sở hữu/quyền | Credential được phép nhận |
|---|---|---|
| PostgreSQL bootstrap admin | Tạo role, schema, grants và default privileges trong `DB-000` | Chỉ one-shot `db-bootstrap` nhận `POSTGRES_BOOTSTRAP_DATABASE_URL` |
| `support_owner` | Sở hữu schema `support`, chạy support migrations | Chỉ `migrate-support` nhận `SUPPORT_MIGRATION_DATABASE_URL` |
| `commerce_owner` | Sở hữu schema `commerce`, chạy commerce migrations | Chỉ `migrate-commerce` nhận `COMMERCE_MIGRATION_DATABASE_URL` |
| `support_app` | DML cần thiết trong `support`; không quyền trên `commerce` | Chỉ backend nhận `SUPPORT_DATABASE_URL` |
| `commerce_app` | DML cần thiết trong `commerce`; không quyền trên `support` | Chỉ Mock-Commerce nhận `COMMERCE_DATABASE_URL` |

- Không có cross-schema foreign key, shared application role hoặc runtime superuser.
- SupportPilot chỉ lưu `commerce_customer_ref`, order reference và payment reference; không mirror commerce table.
- Mọi order/payment query và write từ SupportPilot đi qua Mock-Commerce HTTP adapter.
- `DB-000` nhận bốn role password secrets, chạy idempotently rồi thoát. Bootstrap credential không được inject vào migration hoặc runtime container.

Migration ownership theo phase:

- **Phase 1:** `DB-000` chỉ tạo roles, schemas, grants/default privileges bằng bootstrap admin. `INF-001` chỉ tạo hai Alembic config/command/versions directory độc lập, kiểm tra `search_path`/owner DSN, và có thể tạo empty baseline revision. Phase 1 tuyệt đối không tạo domain table, domain enum hoặc seed row.
- **Phase 2:** `SKEL-001` là task đầu tiên và duy nhất sở hữu minimal forward-compatible domain migration. Migration này chỉ tạo final-named `support.users`, `support.customers`, `support.support_tickets`, `support.ticket_messages` cùng enum/index tối thiểu cần cho demo; chạy trên PostgreSQL thật, không SQLite/in-memory, temporary table, RAG, payment, workflow, approval hoặc full schema.
- `DB-001A/001B/001C/002A` chỉ mở rộng forward từ migration `SKEL-001`, không drop/recreate dữ liệu skeleton. Support và commerce revision histories độc lập; mỗi migration chạy đúng owner credential tương ứng.

### 7.2 DB-001A: support identity, Ticket và Message

`support.users`:

| Cột | Kiểu/constraint | Quy tắc v0.1 |
|---|---|---|
| `id` | UUID PK, default `gen_random_uuid()` | Bắt buộc |
| `email` | CITEXT NOT NULL UNIQUE | Plaintext synthetic data |
| `password_hash` | TEXT NOT NULL | Argon2 hash; không bao giờ plaintext |
| `role` | `support.user_role` NOT NULL: `CUSTOMER/SUPPORT_AGENT/SUPPORT_MANAGER/ADMIN` | Bắt buộc |
| `status` | `support.account_status` NOT NULL DEFAULT `ACTIVE`: `ACTIVE/DISABLED` | Bắt buộc |
| `last_login_at` | TIMESTAMPTZ nullable | UTC |
| `created_at`, `updated_at` | TIMESTAMPTZ NOT NULL DEFAULT `now()` | UTC |

`support.customers`:

| Cột | Kiểu/constraint | Quy tắc v0.1 |
|---|---|---|
| `id` | UUID PK, default `gen_random_uuid()` | Bắt buộc |
| `user_id` | UUID NOT NULL UNIQUE FK `support.users(id) ON DELETE RESTRICT` | Customer login mapping |
| `commerce_customer_ref` | VARCHAR(128) NOT NULL UNIQUE | External reference, không cross-schema FK |
| `email` | CITEXT NOT NULL | Plaintext synthetic data |
| `phone` | VARCHAR(32) nullable | Plaintext synthetic data |
| `verified_at` | TIMESTAMPTZ nullable | Identity verification |
| `status` | `support.account_status` NOT NULL DEFAULT `ACTIVE` | Bắt buộc |
| `created_at`, `updated_at` | TIMESTAMPTZ NOT NULL DEFAULT `now()` | UTC |

`support.support_tickets`:

| Cột | Kiểu/constraint |
|---|---|
| `id` | UUID PK, default `gen_random_uuid()` |
| `ticket_number` | VARCHAR(32) NOT NULL UNIQUE |
| `customer_id` | UUID NOT NULL FK `support.customers(id) ON DELETE RESTRICT` |
| `source` | `support.ticket_source` NOT NULL: `WEB/API` |
| `subject` | TEXT NOT NULL, plaintext synthetic |
| `intent` | VARCHAR(64) nullable; v0.1 nếu có chỉ nhận `payment_mismatch` |
| `priority` | `support.ticket_priority` NOT NULL DEFAULT `NORMAL`: `LOW/NORMAL/HIGH` |
| `status` | `support.ticket_status` NOT NULL DEFAULT `OPEN`: `OPEN/PROCESSING/WAITING_CUSTOMER/WAITING_APPROVAL/RESOLVED/ESCALATED/CLOSED` |
| `assigned_user_id` | UUID nullable FK `support.users(id) ON DELETE RESTRICT` |
| `lock_version` | INTEGER NOT NULL DEFAULT 1 CHECK `>= 1` |
| `created_at`, `updated_at` | TIMESTAMPTZ NOT NULL DEFAULT `now()` |
| `resolved_at`, `closed_at` | TIMESTAMPTZ nullable |

`support.ticket_messages`:

| Cột | Kiểu/constraint |
|---|---|
| `id` | UUID PK, default `gen_random_uuid()` |
| `ticket_id` | UUID NOT NULL FK `support.support_tickets(id) ON DELETE RESTRICT` |
| `sender_type` | `support.message_sender_type` NOT NULL: `CUSTOMER/STAFF/SYSTEM` |
| `sender_user_id` | UUID nullable FK `support.users(id) ON DELETE RESTRICT` |
| `content` | TEXT NOT NULL, plaintext synthetic |
| `idempotency_key` | VARCHAR(128) NOT NULL |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT `now()` |

Constraints/indexes của DB-001A:

- Unique `(ticket_id, idempotency_key)`; index Ticket `(customer_id, created_at DESC)`, `(status, updated_at DESC)` và Message `(ticket_id, created_at, id)`.
- `CHECK` timestamp: `resolved_at` chỉ khác null khi status `RESOLVED/CLOSED`; `closed_at` chỉ khác null khi status `CLOSED`; domain chịu trách nhiệm đồng bộ timestamp khi transition.
- Không có cột `attachment_references`, attachment JSON, blob/key hoặc attachment FK. `attachment_references` chỉ là forward-compatible API field và non-empty bị reject trước transaction ghi message.
- Không tạo `customer_addresses`, `ticket_attachments`, `email_cipher`, `phone_cipher`, `content_cipher` hoặc lookup-hash columns trong v0.1.

### 7.3 DB-001B: workflow, approval, action và audit

Các named enum vật lý:

- `support.agent_run_status`: `CREATED`, `RUNNING`, `WAITING_CUSTOMER`, `WAITING_APPROVAL`, `EXECUTING`, `VERIFYING`, `COMPLETED`, `ESCALATED`, `FAILED`.
- `support.tool_call_status`: `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`, `TIMED_OUT`.
- `support.approval_status`: `PENDING`, `EDITED_PENDING_REAPPROVAL`, `APPROVED`, `REJECTED`, `EXPIRED`, `SUPERSEDED`, `CONSUMED`, `INVALIDATED`.
- `support.action_execution_status`: `PENDING`, `RUNNING`, `SUCCEEDED`, `VERIFYING`, `VERIFIED`, `FAILED_RETRYABLE`, `FAILED_FINAL`, `UNKNOWN`.
- `support.notification_status`: `DRAFT`, `DELIVERED`, `FAILED`; `support.audit_result`: `SUCCEEDED`, `DENIED`, `FAILED`.
- `support.evidence_kind`: `COMMERCE_API`, `POLICY_CHUNK`, `CUSTOMER_MESSAGE`, `DOMAIN_RULE`; `support.permission_tier`: `BACKEND_SCOPED`, `SAFE_READ`, `BUSINESS_WRITE`, `INTERNAL_WRITE`.
- `support.idempotency_scope`: `TICKET_CREATE`, `AGENT_RUN_CREATE`, `MESSAGE_CREATE`, `APPROVAL_DECISION`, `KNOWLEDGE_DOCUMENT_CREATE`, `KNOWLEDGE_PUBLISH`, `KNOWLEDGE_REINDEX`.

LangGraph checkpoint tables do official PostgreSQL checkpointer migration quản lý trong schema `support`, keyed bằng string representation của `agent_run.id`. Chúng không phải public domain tables, không được sửa schema tùy ý, không làm timeline và không lưu chain-of-thought; checkpoint payload chỉ chứa state tối thiểu cần resume theo §7.8.

#### `support.agent_runs`

| Cột | PostgreSQL contract |
|---|---|
| `id` | UUID PK, default `gen_random_uuid()` |
| `ticket_id` | UUID NOT NULL FK `support.support_tickets(id) ON DELETE RESTRICT` |
| `idempotency_key` | VARCHAR(128) NOT NULL |
| `status` | `support.agent_run_status` NOT NULL DEFAULT `CREATED` |
| `current_node` | VARCHAR(128) nullable |
| `graph_version`, `prompt_version` | VARCHAR(64) NOT NULL |
| `llm_provider` | VARCHAR(32) NOT NULL |
| `llm_model` | VARCHAR(128) NOT NULL |
| `state_summary` | JSONB NOT NULL DEFAULT `'{}'`; chỉ safe UI/ops projection, không raw message/secret/CoT/checkpoint copy |
| `failure_code` | VARCHAR(64) nullable |
| `correlation_id` | UUID NOT NULL |
| `input_tokens`, `output_tokens` | BIGINT NOT NULL DEFAULT 0 CHECK `>= 0` |
| `latency_ms` | BIGINT nullable CHECK `>= 0` |
| `lock_version` | INTEGER NOT NULL DEFAULT 1 CHECK `>= 1` |
| `started_at`, `completed_at` | TIMESTAMPTZ nullable |
| `created_at`, `updated_at` | TIMESTAMPTZ NOT NULL DEFAULT `now()` |

Constraints/indexes: unique `(ticket_id,idempotency_key)`; unique partial `ux_agent_runs_one_nonterminal_ticket` trên `ticket_id WHERE status IN ('CREATED','RUNNING','WAITING_CUSTOMER','WAITING_APPROVAL','EXECUTING','VERIFYING')`; indexes `(ticket_id,created_at DESC)`, `(status,updated_at)` và `(correlation_id)`. `completed_at` bắt buộc cho terminal `COMPLETED/ESCALATED/FAILED` và phải null cho non-terminal. Update qua optimistic `lock_version`.

#### `support.agent_run_events`

| Cột | PostgreSQL contract |
|---|---|
| `id` | UUID PK, default `gen_random_uuid()` |
| `run_id` | UUID NOT NULL FK `support.agent_runs(id) ON DELETE RESTRICT` |
| `sequence` | BIGINT NOT NULL CHECK `> 0` |
| `event_type` | VARCHAR(64) NOT NULL |
| `summary` | TEXT nullable, redacted/customer-safe theo audience |
| `payload` | JSONB NOT NULL DEFAULT `'{}'`; chỉ redacted event metadata, không checkpoint/CoT/raw authorization |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT `now()` |

Unique `(run_id,sequence)`; indexes `(run_id,sequence)` và `(event_type,created_at DESC)`. Append-only/immutable bằng grants; sequence được cấp dưới row/advisory lock để không duplicate/reorder.

#### `support.agent_evidence`

| Cột | PostgreSQL contract |
|---|---|
| `id` | UUID PK, default `gen_random_uuid()` |
| `run_id` | UUID NOT NULL FK `support.agent_runs(id) ON DELETE RESTRICT` |
| `kind` | `support.evidence_kind` NOT NULL |
| `source_ref` | VARCHAR(255) NOT NULL; opaque API/message/rule/chunk reference |
| `chunk_id` | UUID nullable FK `support.knowledge_chunks(id) ON DELETE RESTRICT`; chỉ khác null khi kind `POLICY_CHUNK` |
| `score` | DOUBLE PRECISION nullable CHECK `score >= 0` |
| `rank` | INTEGER nullable CHECK `rank > 0` |
| `summary` | TEXT NOT NULL, masked/redacted |
| `metadata` | JSONB NOT NULL DEFAULT `'{}'`; chỉ provenance/filter/safe hashes, không raw customer payload |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT `now()` |

Indexes `(run_id,kind,created_at)`, `(chunk_id)` khi non-null. Append-only/immutable. CHECK bảo đảm `kind='POLICY_CHUNK'` iff `chunk_id IS NOT NULL`; score/rank không thay thế các cột provenance của knowledge index.

#### `support.tool_calls`

| Cột | PostgreSQL contract |
|---|---|
| `id` | UUID PK, default `gen_random_uuid()` |
| `run_id` | UUID NOT NULL FK `support.agent_runs(id) ON DELETE RESTRICT` |
| `call_group_id` | UUID NOT NULL; giữ nguyên qua retry |
| `tool_name`, `tool_version` | VARCHAR(64) NOT NULL |
| `permission_tier` | `support.permission_tier` NOT NULL |
| `status` | `support.tool_call_status` NOT NULL DEFAULT `PENDING` |
| `attempt` | SMALLINT NOT NULL DEFAULT 1 CHECK `> 0` |
| `input_summary` | JSONB NOT NULL DEFAULT `'{}'`; allowlisted/redacted fields, không service token |
| `output_summary` | JSONB nullable; safe status/reference/amount, không token/raw PII |
| `error_code` | VARCHAR(64) nullable |
| `latency_ms` | BIGINT nullable CHECK `>= 0` |
| `idempotency_key` | VARCHAR(128) nullable; bắt buộc cho `BUSINESS_WRITE` |
| `actor_user_id` | UUID nullable FK `support.users(id) ON DELETE RESTRICT` |
| `customer_id` | UUID nullable FK `support.customers(id) ON DELETE RESTRICT` |
| `lock_version` | INTEGER NOT NULL DEFAULT 1 CHECK `>= 1` |
| `started_at`, `completed_at` | TIMESTAMPTZ nullable |
| `created_at`, `updated_at` | TIMESTAMPTZ NOT NULL DEFAULT `now()` |

Unique `(run_id,call_group_id,attempt)`; indexes `(run_id,created_at)`, `(tool_name,status,created_at)` và partial `(idempotency_key) WHERE idempotency_key IS NOT NULL`. Mỗi attempt update bằng `lock_version` từ pending/running sang một terminal status rồi trở thành immutable theo repository policy; retry tạo attempt row mới. CHECK bắt `BUSINESS_WRITE` có actor, customer và idempotency key.

#### `support.approval_requests`

| Cột | PostgreSQL contract |
|---|---|
| `id` | UUID PK, default `gen_random_uuid()` |
| `run_id` | UUID NOT NULL FK `support.agent_runs(id) ON DELETE RESTRICT` |
| `action_type` | VARCHAR(64) NOT NULL |
| `target_ref` | VARCHAR(255) NOT NULL |
| `required_role` | `support.user_role` NOT NULL CHECK `(required_role <> 'CUSTOMER')` |
| `status` | `support.approval_status` NOT NULL DEFAULT `PENDING` |
| `current_version` | INTEGER NOT NULL DEFAULT 1 CHECK `>= 1` |
| `current_proposal_hash` | VARCHAR(71) NOT NULL CHECK `(current_proposal_hash ~ '^sha256:[0-9a-f]{64}$')` |
| `decided_by` | UUID nullable FK `support.users(id) ON DELETE RESTRICT` |
| `decision` | VARCHAR(16) nullable CHECK `(decision IN ('APPROVE','EDIT','REJECT'))` |
| `decision_reason` | TEXT nullable, redacted |
| `requested_at` | TIMESTAMPTZ NOT NULL DEFAULT `now()` |
| `expires_at` | TIMESTAMPTZ NOT NULL CHECK `expires_at > requested_at` |
| `decided_at` | TIMESTAMPTZ nullable |
| `lock_version` | INTEGER NOT NULL DEFAULT 1 CHECK `>= 1` |
| `created_at`, `updated_at` | TIMESTAMPTZ NOT NULL DEFAULT `now()` |

Indexes `(run_id,created_at DESC)`, `(required_role,status,expires_at)` và partial `(expires_at) WHERE status IN ('PENDING','EDITED_PENDING_REAPPROVAL')`. Sau khi proposal table tồn tại, thêm composite FK `(id,current_version,current_proposal_hash) REFERENCES support.approval_proposal_versions(approval_id,version,proposal_hash) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED`. Decision dùng row lock + expected `current_version/current_proposal_hash/lock_version`. CHECK: pending/edit-pending có decision fields null; approved/consumed yêu cầu `APPROVE` + actor/time; rejected yêu cầu `REJECT` + actor/time; expired/superseded/invalidated yêu cầu decision null và terminal timestamp. Lazy expiry vẫn phải persist `EXPIRED`.

#### `support.approval_proposal_versions`

| Cột | PostgreSQL contract |
|---|---|
| `id` | UUID PK, default `gen_random_uuid()` |
| `approval_id` | UUID NOT NULL FK `support.approval_requests(id) ON DELETE RESTRICT` |
| `version` | INTEGER NOT NULL CHECK `>= 1` |
| `proposal` | JSONB NOT NULL; allowlisted action schema đã redact, gồm action type/target/amount/currency/expected target version, không secret/CoT |
| `proposal_hash` | VARCHAR(71) NOT NULL CHECK `(proposal_hash ~ '^sha256:[0-9a-f]{64}$')`; canonical proposal hash |
| `material_change` | BOOLEAN NOT NULL DEFAULT false |
| `edited_by` | UUID nullable FK `support.users(id) ON DELETE RESTRICT` |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT `now()` |

Unique `(approval_id,version)`, `(approval_id,proposal_hash)` và `(approval_id,version,proposal_hash)` để làm composite FK. Append-only/immutable. CHECK: `material_change=true` bắt buộc `edited_by` khác null. `approval_requests.current_*` luôn trỏ đúng một version/hash; service validate schema, ownership qua HTTP và business rule trước insert.

#### `support.action_executions`

| Cột | PostgreSQL contract |
|---|---|
| `id` | UUID PK, default `gen_random_uuid()` |
| `approval_id` | UUID NOT NULL FK `support.approval_requests(id) ON DELETE RESTRICT`, UNIQUE trong UC-01 |
| `proposal_version`, `proposal_hash` | INTEGER/VARCHAR(71) NOT NULL; composite FK tới `(approval_id,version,proposal_hash)` của proposal version |
| `action_type` | VARCHAR(64) NOT NULL; v0.1 chỉ `sync_payment_status` |
| `target_ref` | VARCHAR(255) NOT NULL |
| `idempotency_key` | VARCHAR(128) NOT NULL UNIQUE |
| `status` | `support.action_execution_status` NOT NULL DEFAULT `PENDING` |
| `expected_target_version` | INTEGER NOT NULL CHECK `>= 1` |
| `request_payload` | JSONB NOT NULL DEFAULT `'{}'`; redacted HTTP/business projection, không authorization |
| `result_payload` | JSONB nullable; safe result/version/reference only |
| `error_code` | VARCHAR(64) nullable |
| `lock_version` | INTEGER NOT NULL DEFAULT 1 CHECK `>= 1` |
| `started_at`, `completed_at`, `verified_at` | TIMESTAMPTZ nullable |
| `created_at`, `updated_at` | TIMESTAMPTZ NOT NULL DEFAULT `now()` |

Indexes `(status,updated_at)`, `(target_ref,created_at DESC)`. CHECK: `VERIFIED` bắt buộc `verified_at`; status khác không được có `verified_at`; `UNKNOWN` không được coi là complete/success. Update bằng optimistic `lock_version`; history không cascade/delete.

#### `support.notifications`

| Cột | PostgreSQL contract |
|---|---|
| `id` | UUID PK, default `gen_random_uuid()` |
| `ticket_id` | UUID NOT NULL FK `support.support_tickets(id) ON DELETE RESTRICT` |
| `run_id` | UUID nullable FK `support.agent_runs(id) ON DELETE RESTRICT` |
| `recipient_type` | VARCHAR(16) NOT NULL CHECK `(recipient_type IN ('CUSTOMER','STAFF'))` |
| `recipient_ref` | VARCHAR(255) NOT NULL, masked/opaque |
| `channel` | VARCHAR(16) NOT NULL CHECK `(channel IN ('DRAFT_ONLY','INTERNAL'))` |
| `draft_body` | TEXT NOT NULL, redacted synthetic content |
| `status` | `support.notification_status` NOT NULL DEFAULT `DRAFT` |
| `idempotency_key` | VARCHAR(128) NOT NULL UNIQUE |
| `lock_version` | INTEGER NOT NULL DEFAULT 1 CHECK `>= 1` |
| `created_at`, `updated_at` | TIMESTAMPTZ NOT NULL DEFAULT `now()` |

Indexes `(ticket_id,created_at DESC)`, `(status,created_at)`. `CUSTOMER` bắt buộc `channel='DRAFT_ONLY'` trong v0.1; không có SMTP delivery hoặc customer send timestamp.

#### `support.audit_logs`

| Cột | PostgreSQL contract |
|---|---|
| `id` | UUID PK, default `gen_random_uuid()` |
| `correlation_id` | UUID NOT NULL |
| `actor_type` | VARCHAR(16) NOT NULL CHECK `(actor_type IN ('USER','SERVICE','SYSTEM'))` |
| `actor_id` | UUID nullable, không FK để lịch sử sống lâu hơn principal |
| `action` | VARCHAR(128) NOT NULL |
| `resource_type` | VARCHAR(64) NOT NULL |
| `resource_id` | UUID nullable, không FK để không cascade lịch sử |
| `result` | `support.audit_result` NOT NULL |
| `before_hash`, `after_hash` | VARCHAR(71) nullable; chỉ canonical hashes, không raw snapshot |
| `details` | JSONB NOT NULL DEFAULT `'{}'`; allowlist correlation/error/version/reference/redaction flags, cấm token/raw message/CoT |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT `now()` |

Indexes `(created_at DESC)`, `(correlation_id)`, `(actor_type,actor_id,created_at DESC)`, `(resource_type,resource_id,created_at DESC)` và `(action,result,created_at DESC)`. Append-only bằng grants; không update/delete/cascade.

#### `support.idempotency_records`

Bảng này là hạ tầng bắt buộc để replay nguyên public response, không phải domain mở rộng:

| Cột | PostgreSQL contract |
|---|---|
| `id` | UUID PK, default `gen_random_uuid()` |
| `scope` | `support.idempotency_scope` NOT NULL |
| `principal_fingerprint` | CHAR(64) NOT NULL; SHA-256 của scoped principal, không raw token |
| `idempotency_key` | VARCHAR(128) NOT NULL |
| `request_hash` | CHAR(64) NOT NULL |
| `response_status` | SMALLINT NOT NULL CHECK `BETWEEN 100 AND 599` |
| `response_body` | JSONB NOT NULL; exact redacted response envelope, không authorization/raw PII |
| `resource_type` | VARCHAR(64) NOT NULL |
| `resource_id` | UUID nullable, không FK để record không bị cascade |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT `now()` |
| `expires_at` | TIMESTAMPTZ nullable CHECK `expires_at > created_at` |

Unique `(scope,principal_fingerprint,idempotency_key)`; index `(expires_at)` khi non-null. Immutable. Cùng key nhưng khác `request_hash` trả idempotency-conflict, không replay và không thực thi.

Concurrency/idempotency field được chọn theo write semantics, không thêm máy móc: mutable aggregate/attempt (`agent_runs`, `tool_calls`, `approval_requests`, `action_executions`, `notifications`) có `lock_version`; endpoint-level replay của Ticket/Message/Approval/Knowledge dùng `support.idempotency_records`; business action có key riêng. `agent_run_events`, `agent_evidence`, `approval_proposal_versions`, `audit_logs` và idempotency rows là immutable nên không có `lock_version`/idempotency field riêng; unique sequence/version/hash/scope-key cùng append-only grants là concurrency guard của chúng.

Allowed transitions vẫn do domain service/state machine §9 kiểm tra và có automated tests; expiry check/decision update chạy cùng row lock/transaction. Các constraints trên chỉ chặn invalid value/shape và bảo vệ invariant có thể biểu diễn tại DB.

### 7.4 DB-001C: knowledge và embedding provenance

Named enums: `support.knowledge_document_status` = `DRAFT/VALIDATED/PUBLISHED/SUPERSEDED/EXPIRED`; `support.knowledge_index_status` = `BUILDING/COMPLETED/FAILED`.

`support.knowledge_documents`:

| Cột | PostgreSQL contract |
|---|---|
| `id` | UUID PK, default `gen_random_uuid()` |
| `title` | VARCHAR(255) NOT NULL |
| `policy_type` | VARCHAR(64) NOT NULL |
| `version` | VARCHAR(64) NOT NULL |
| `region`, `language` | VARCHAR(16) NOT NULL |
| `product_category` | VARCHAR(64) NOT NULL DEFAULT `all` |
| `effective_from` | TIMESTAMPTZ NOT NULL |
| `effective_to` | TIMESTAMPTZ nullable CHECK `effective_to > effective_from` |
| `status` | `support.knowledge_document_status` NOT NULL DEFAULT `DRAFT` |
| `source_uri` | TEXT NOT NULL |
| `checksum` | CHAR(64) NOT NULL |
| `active_index_version` | VARCHAR(64) nullable; chỉ trỏ index `COMPLETED` của chính document |
| `lock_version` | INTEGER NOT NULL DEFAULT 1 CHECK `>= 1` |
| `created_at`, `updated_at` | TIMESTAMPTZ NOT NULL DEFAULT `now()` |

Unique `(policy_type,region,language,product_category,version)`; composite FK `(id,active_index_version) REFERENCES support.knowledge_index_versions(document_id,index_version) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED` được thêm sau khi index table tồn tại. Indexes cho active retrieval `(status,policy_type,region,language,product_category,effective_from,effective_to)` và checksum. `DRAFT`/`VALIDATED` reindex không đổi status; `PUBLISHED` document giữ active index cũ đến atomic swap.

`support.knowledge_index_versions`:

| Cột | PostgreSQL contract |
|---|---|
| `id` | UUID PK, default `gen_random_uuid()` |
| `document_id` | UUID NOT NULL FK `support.knowledge_documents(id) ON DELETE RESTRICT` |
| `index_version` | VARCHAR(64) NOT NULL |
| `status` | `support.knowledge_index_status` NOT NULL DEFAULT `BUILDING` |
| `embedding_provider` | VARCHAR(64) NOT NULL |
| `embedding_model` | VARCHAR(255) NOT NULL |
| `embedding_revision` | VARCHAR(64) NOT NULL |
| `embedding_dimension` | INTEGER NOT NULL CHECK `= 384` trong v0.1 |
| `embedding_input_format_version` | VARCHAR(64) NOT NULL |
| `chunk_count` | INTEGER NOT NULL DEFAULT 0 CHECK `>= 0` |
| `calibration_required` | BOOLEAN NOT NULL DEFAULT true |
| `error_code` | VARCHAR(64) nullable |
| `lock_version` | INTEGER NOT NULL DEFAULT 1 CHECK `>= 1` |
| `started_at` | TIMESTAMPTZ NOT NULL DEFAULT `now()` |
| `completed_at` | TIMESTAMPTZ nullable |
| `created_at`, `updated_at` | TIMESTAMPTZ NOT NULL DEFAULT `now()` |

Unique `(document_id,index_version)`; indexes `(document_id,status,created_at DESC)` và `(status,created_at)`. `COMPLETED/FAILED` bắt buộc `completed_at`; chỉ `FAILED` được có `error_code`. Update BUILDING→terminal dùng `lock_version`; row provenance/status immutable sau terminal. Composite FK `(knowledge_documents.id,active_index_version)` tham chiếu `(document_id,index_version)` và được thêm sau khi cả hai bảng tồn tại.

`support.knowledge_chunks`:

| Cột | PostgreSQL contract |
|---|---|
| `id` | UUID PK, default `gen_random_uuid()` |
| `document_id`, `index_version` | UUID/VARCHAR(64) NOT NULL; composite FK tới `knowledge_index_versions(document_id,index_version) ON DELETE RESTRICT` |
| `chunk_index` | INTEGER NOT NULL CHECK `>= 0` |
| `heading_path`, `content` | TEXT NOT NULL |
| `embedding` | `vector(384)` NOT NULL |
| `search_vector` | TSVECTOR NOT NULL |
| `checksum` | CHAR(64) NOT NULL |
| `metadata` | JSONB NOT NULL DEFAULT `'{}'`; chỉ parsed safe metadata, không raw secret/attachment |
| `embedding_provider/model/revision` | VARCHAR(64)/VARCHAR(255)/VARCHAR(64) NOT NULL |
| `embedding_dimension` | INTEGER NOT NULL CHECK `= 384` |
| `embedding_input_format_version` | VARCHAR(64) NOT NULL |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT `now()` |

Unique `(document_id,index_version,chunk_index)`; B-tree `(document_id,index_version)`, GIN `search_vector`; exact vector scan trên corpus nhỏ không cần ANN index. Chunk rows immutable. Provenance trên chunk phải khớp parent index version bằng application validation và migration/repository tests.

Thay model, revision, dimension, input-format hoặc retrieval scoring tạo index version mới, giữ active version cũ cho đến khi toàn bộ chunks validate, rồi swap `active_index_version` trong transaction. Failure persist attempt `FAILED` nhưng không sửa active pointer. Thay embedding config đặt `calibration_required=true` và runtime `RAG_THRESHOLD_CALIBRATED=false` cho đến khi calibration/holdout artifact mới pass.

### 7.5 Commerce schema cho UC-01

Named enums: `commerce.customer_status` = `ACTIVE/DISABLED`; `commerce.product_status` = `ACTIVE/INACTIVE`; `commerce.order_status` = `PENDING_CONFIRMATION/CONFIRMED`; `commerce.order_payment_status` = `PENDING/PAID`; `commerce.payment_status` = `PENDING/SUCCEEDED/FAILED/REVERSED`; `commerce.write_result` = `SUCCEEDED/DENIED/FAILED`.

`commerce.customers`:

| Cột | PostgreSQL contract |
|---|---|
| `id` | UUID PK, default `gen_random_uuid()` |
| `external_ref` | VARCHAR(128) NOT NULL UNIQUE; giá trị SupportPilot lưu ở `commerce_customer_ref` |
| `email` | CITEXT NOT NULL UNIQUE; synthetic plaintext |
| `status` | `commerce.customer_status` NOT NULL DEFAULT `ACTIVE` |
| `is_synthetic` | BOOLEAN NOT NULL DEFAULT true CHECK `(is_synthetic)` |
| `created_at`, `updated_at` | TIMESTAMPTZ NOT NULL DEFAULT `now()` |

Index `(status,created_at DESC)`. Không có FK sang `support.customers`.

`commerce.products`:

| Cột | PostgreSQL contract |
|---|---|
| `id` | UUID PK, default `gen_random_uuid()` |
| `sku` | VARCHAR(64) NOT NULL UNIQUE |
| `name` | VARCHAR(255) NOT NULL |
| `normalized_name` | TEXT NOT NULL |
| `category` | VARCHAR(64) NOT NULL |
| `status` | `commerce.product_status` NOT NULL DEFAULT `ACTIVE` |
| `is_synthetic` | BOOLEAN NOT NULL DEFAULT true CHECK `(is_synthetic)` |
| `created_at`, `updated_at` | TIMESTAMPTZ NOT NULL DEFAULT `now()` |

Indexes `(category,status)`, GIN trigram `normalized_name`. Normalization rule giống Order Resolution Unicode/case/accent contract và được test bằng fixed fixture.

`commerce.orders`:

| Cột | PostgreSQL contract |
|---|---|
| `id` | UUID PK, default `gen_random_uuid()` |
| `customer_id` | UUID NOT NULL FK `commerce.customers(id) ON DELETE RESTRICT` |
| `order_number` | VARCHAR(64) NOT NULL UNIQUE |
| `status` | `commerce.order_status` NOT NULL DEFAULT `PENDING_CONFIRMATION` |
| `payment_status` | `commerce.order_payment_status` NOT NULL DEFAULT `PENDING` |
| `total_amount` | NUMERIC(18,2) NOT NULL CHECK `>= 0` |
| `currency` | CHAR(3) NOT NULL CHECK `(currency ~ '^[A-Z]{3}$')` |
| `version` | INTEGER NOT NULL DEFAULT 1 CHECK `>= 1` |
| `is_synthetic` | BOOLEAN NOT NULL DEFAULT true CHECK `(is_synthetic)` |
| `created_at`, `updated_at` | TIMESTAMPTZ NOT NULL DEFAULT `now()` |

Unique thêm `(id,customer_id)` để làm ownership FK; indexes `(customer_id,created_at DESC)`, `(customer_id,status,created_at DESC)` và `(customer_id,payment_status,created_at DESC)`. Mỗi successful state-changing write dùng `WHERE id=:id AND customer_id=:customer_id AND version=:expected_version`, tăng `version=version+1`; zero row trả `STALE_ORDER` hoặc ownership/not-found theo scoped lookup.

`commerce.order_items`:

| Cột | PostgreSQL contract |
|---|---|
| `id` | UUID PK, default `gen_random_uuid()` |
| `order_id` | UUID NOT NULL FK `commerce.orders(id) ON DELETE RESTRICT` |
| `product_id` | UUID NOT NULL FK `commerce.products(id) ON DELETE RESTRICT` |
| `variant` | VARCHAR(128) nullable |
| `quantity` | INTEGER NOT NULL CHECK `> 0` |
| `unit_amount` | NUMERIC(18,2) NOT NULL CHECK `>= 0` |
| `currency` | CHAR(3) NOT NULL CHECK `(currency ~ '^[A-Z]{3}$')` |
| `is_synthetic` | BOOLEAN NOT NULL DEFAULT true CHECK `(is_synthetic)` |
| `created_at`, `updated_at` | TIMESTAMPTZ NOT NULL DEFAULT `now()` |

Index `(order_id,id)` và `(product_id)`. Service kiểm tra item currency khớp order và tổng amount trước commit; không dùng trigger cộng tổng.

`commerce.payments`:

| Cột | PostgreSQL contract |
|---|---|
| `id` | UUID PK, default `gen_random_uuid()` |
| `customer_id` | UUID NOT NULL FK `commerce.customers(id) ON DELETE RESTRICT` |
| `order_id` | UUID nullable |
| `transaction_ref` | VARCHAR(128) nullable |
| `status` | `commerce.payment_status` NOT NULL |
| `amount` | NUMERIC(18,2) NOT NULL CHECK `> 0` |
| `currency` | CHAR(3) NOT NULL CHECK `(currency ~ '^[A-Z]{3}$')` |
| `payment_method` | VARCHAR(32) NOT NULL; synthetic category, không card/account secret |
| `paid_at` | TIMESTAMPTZ nullable |
| `version` | INTEGER NOT NULL DEFAULT 1 CHECK `>= 1` |
| `is_synthetic` | BOOLEAN NOT NULL DEFAULT true CHECK `(is_synthetic)` |
| `created_at`, `updated_at` | TIMESTAMPTZ NOT NULL DEFAULT `now()` |

Composite FK `(order_id,customer_id) REFERENCES commerce.orders(id,customer_id) ON DELETE RESTRICT` bảo đảm linked payment thuộc cùng customer; null `order_id` cho phép UC-01 payment chưa match. Unique partial `transaction_ref WHERE transaction_ref IS NOT NULL`; indexes `(customer_id,paid_at DESC)`, `(customer_id,status,amount,currency,paid_at DESC)` và `(order_id) WHERE order_id IS NOT NULL`. `SUCCEEDED` bắt buộc `paid_at`; status khác không được suy diễn success. Successful link/update tăng payment `version` bằng expected version nếu payment row bị thay đổi.

`commerce.idempotency_records` là contract bắt buộc cho write `SYNC_PAYMENT_STATUS`:

| Cột | PostgreSQL contract |
|---|---|
| `id` | UUID PK, default `gen_random_uuid()` |
| `operation` | VARCHAR(64) NOT NULL CHECK `(operation = 'SYNC_PAYMENT_STATUS')` |
| `idempotency_key` | VARCHAR(128) NOT NULL |
| `request_hash` | CHAR(64) NOT NULL |
| `order_id` | UUID NOT NULL FK `commerce.orders(id) ON DELETE RESTRICT` |
| `response_status` | SMALLINT NOT NULL CHECK `BETWEEN 100 AND 599` |
| `response_body` | JSONB NOT NULL; redacted exact internal response, không bearer token |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT `now()` |

Unique `(operation,idempotency_key)`; index `(order_id,created_at DESC)`. Immutable. Same key/same hash replay response; same key/different hash trả idempotency conflict.

`commerce.audit_logs` giữ UC-01 write audit độc lập:

| Cột | PostgreSQL contract |
|---|---|
| `id` | UUID PK, default `gen_random_uuid()` |
| `correlation_id` | UUID NOT NULL |
| `action` | VARCHAR(64) NOT NULL CHECK `(action = 'SYNC_PAYMENT_STATUS')` |
| `order_id` | UUID NOT NULL, không FK để lịch sử không cascade |
| `result` | `commerce.write_result` NOT NULL |
| `before_hash`, `after_hash` | VARCHAR(71) nullable |
| `details` | JSONB NOT NULL DEFAULT `'{}'`; approval opaque ref, versions/error/redaction flags; không token/raw payload |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT `now()` |

Indexes `(correlation_id)`, `(order_id,created_at DESC)`, `(action,result,created_at DESC)`. Append-only bằng grants.

Không có FK từ `support` sang `commerce`; không mirror row. Shipping, refund, fulfillment, address và warranty tables không được tạo trong v0.1. Seed `payment-mismatch-v01` chỉ insert rows có `is_synthetic=true`, fixed UUID/checksum, và chạy lại bằng natural/unique keys mà không duplicate.

Optimistic concurrency chỉ tồn tại nơi v0.1 có mutable business write: `orders.version` và `payments.version`. `customers`, `products` và `order_items` là seed-owned/immutable sau bootstrap trong UC-01, không có update endpoint nên cố ý không thêm speculative `version` field; thay đổi fixture tạo seed version/profile mới.

### 7.6 Transaction, locking và idempotency

- Ticket và message đầu tiên được tạo trong một transaction.
- Agent-run creation khóa/check Ticket; partial unique index là lớp bảo vệ cuối cho invariant một non-terminal run/ticket.
- Approval decision dùng `SELECT ... FOR UPDATE`, `expected_version` và `expected_proposal_hash` để chỉ một quyết định thắng.
- Action execution khóa approval trong SupportPilot; Mock-Commerce tự khóa order/payment và kiểm tra expected version trong transaction riêng.
- Mock `sync-payment` xác thực internal Bearer token trước body/customer validation; sau đó trong một transaction khóa scoped order/payment, kiểm tra approval opaque ref, request hash, customer ownership và expected order/payment version, cập nhật/link payment nếu cần, tăng mỗi version đã sửa đúng một, cập nhật order `payment_status=PAID`/`status=CONFIRMED`, rồi insert commerce audit và idempotency response. Bất kỳ bước nào fail thì toàn transaction rollback.
- HTTP retry của write action luôn dùng lại `Idempotency-Key`; không tạo key mới.
- Knowledge publish, index-version swap và version supersede chạy trong transaction. Reindex build chunks trong index version `BUILDING`; chỉ sau validation đầy đủ mới chuyển `COMPLETED` và atomic swap active pointer. Failure chuyển attempt `FAILED`, giữ active pointer cũ.
- Replay reindex cùng principal/key/request hash trả persisted `200` body từ `support.idempotency_records`; key trùng nhưng request khác trả conflict, không tạo index attempt mới.
- Message phải commit trước khi same-run resume; resume timeout không rollback message.
- Non-empty `attachment_references` bị reject trước message transaction, nên không có message, idempotency response thành công hoặc resume side effect.
- Order Resolution là read-only; dùng snapshot nhất quán, không giữ lock qua LLM/API call.

### 7.7 Encryption migration v1.0

Các cột `email`, `phone`, `subject`, `content` là plaintext chỉ vì v0.1 dùng synthetic local/demo data; schema này không được dùng với dữ liệu khách thật. v1.0 thực hiện nhiều migration riêng:

1. Thêm `email_cipher`, `email_lookup_hash`, `phone_cipher`, `phone_lookup_hash` và `content_cipher`.
2. Backfill từ cột plaintext.
3. Chuyển application sang dual-read/dual-write.
4. Xác minh backfill và lookup hashes.
5. Ngừng đọc plaintext.
6. Drop plaintext bằng migration riêng.

Không đổi kiểu in-place, không đổi tên plaintext thành `*_cipher`, và không gộp add/backfill/switch/drop trong một migration.

### 7.8 Checkpoint, run status, timeline và audit ownership

Invariant bắt buộc:

> Checkpoint là source of truth cho graph resume. `agent_runs` là source of truth cho trạng thái nghiệp vụ tổng quan của run. `agent_run_events` là source of truth cho timeline. `audit_logs` là source of truth cho audit.

- Checkpoint lưu state tối thiểu cần tiếp tục workflow, keyed bằng `agent_run.id`; public API chỉ trả safe projection từ services, không trả checkpoint payload.
- `agent_runs.state_summary` chỉ là redacted summary phục vụ list/detail/operations, không phải bản sao đầy đủ của AgentState.
- Mỗi state-changing orchestration operation phải persist checkpoint và cập nhật `agent_runs.status/current_node` trong một service transaction khi checkpointer hỗ trợ cùng database transaction. Nếu không atomic được, ghi reconciliation marker và chạy deterministic reconciliation trước khi trả success.
- Event timeline và audit có thể ghi trong cùng transaction/outbox-style pending record, nhưng lỗi ghi event/audit không được biến chúng thành nguồn resume thay thế.

Startup/recovery check:

- Checkpoint tồn tại nhưng `agent_runs` không còn resumable: không resume; chuyển Ticket `ESCALATED` nếu chưa terminal và ghi `agent_run.checkpoint_invariant_failed`.
- `agent_runs` là `WAITING_CUSTOMER`/`WAITING_APPROVAL` nhưng checkpoint không tồn tại: không tạo run mới ngầm; chuyển run/Ticket `ESCALATED` và ghi cùng audit event.
- Checkpoint state và `agent_runs.status/current_node` lệch nhưng có thể xác định update đã commit một phía: reconciliation dùng checkpoint cho resume state, domain transition rules cho business status, ghi before/after summary và correlation ID.
- Không reconstruct checkpoint từ `agent_run_events` hoặc `audit_logs`.

## 8. REST API contract

### 8.1 Quy ước chung

- Public prefix: `/api/v1`.
- Internal mock prefix: `/internal/v1`.
- Public user auth: `Authorization: Bearer <user JWT>`; internal auth: đúng `Authorization: Bearer <INTERNAL_SERVICE_TOKEN>`.
- User JWT không hợp lệ cho `/internal/v1/*`; internal token không hợp lệ cho `/api/v1/*`. Không nhận credential qua query/body/cookie fallback.
- Error: `code`, `message`, `retryable`, `correlation_id`, `details`.
- `POST /tickets`, `POST /tickets/{id}/agent-runs`, `POST /tickets/{id}/messages`, approval decision, knowledge create/publish/reindex và commerce write bắt buộc `Idempotency-Key`. Login và read-only `POST /knowledge/search` không dùng idempotency record.
- Mọi response có `correlation_id`.
- Replay cùng idempotency key trả nguyên status/body đã persist và có thể thêm `Idempotency-Replayed: true`; không chạy workflow/action lần hai.
- List API v0.1 dùng `page/page_size`; timeline response dùng `timeline_cursor`.
- Money gồm `amount` dạng decimal string và `currency`.
- Citation gồm `chunk_id`, `document_id`, `title`, `version`, `heading`, `score`, `excerpt`, `effective_from/to`.
- Mỗi synchronous graph advance có tổng budget `WORKFLOW_REQUEST_TIMEOUT_SECONDS=60`; API persist failure state/audit trước khi trả timeout.

Idempotency scope là `(authenticated principal/service, operation, Idempotency-Key)`: Ticket create → `TICKET_CREATE`; Agent Run → `AGENT_RUN_CREATE`; Message → `MESSAGE_CREATE`; Approval decision → `APPROVAL_DECISION`; Knowledge create/publish/reindex → `KNOWLEDGE_DOCUMENT_CREATE/KNOWLEDGE_PUBLISH/KNOWLEDGE_REINDEX`; internal sync-payment → commerce `(SYNC_PAYMENT_STATUS,key)`. Cùng scope/key nhưng khác request hash luôn conflict; không endpoint write nào dùng key global xuyên operation.

### 8.2 Public endpoints v0.1

| Nhóm / Endpoint | Auth, request và response | Lỗi, idempotency và approval |
|---|---|---|
| `POST /auth/login` | Email/password → access token, actor profile | `INVALID_CREDENTIALS`, `ACCOUNT_DISABLED`; rate limited. Refresh rotation để v1.0. |
| `GET /auth/me` | Authenticated principal → role và scoped profile | `UNAUTHENTICATED` |
| `GET /customers/me` | Customer → masked profile và verification status | Không cho truyền customer ID khác |
| `GET /customers/{id}/summary` | Support Agent+ → masked summary | `CUSTOMER_NOT_FOUND/FORBIDDEN`; audit read |
| `POST /tickets` | Customer; subject/body/source → Ticket và first message | Idempotent; không tự chạy agent |
| `GET /tickets` | Staff/customer-scoped filters → paginated summaries | Customer chỉ thấy ticket của mình |
| `GET /tickets/{id}` | Scoped actor → messages, evidence, latest run, approvals, timeline | `TICKET_NOT_FOUND/FORBIDDEN` |
| `POST /tickets/{id}/messages` | Scoped sender; content và forward-compatible `attachment_references` → message hoặc same-run resume result | Omitted/`[]` mới hợp lệ; non-empty trả `422 ATTACHMENTS_NOT_SUPPORTED` trước mọi write/resume; idempotent dual response `201`/`200` |
| `POST /tickets/{id}/agent-runs` | Customer-created flow hoặc qualified staff/system → synchronous run result | Idempotent; một non-terminal run/ticket; active conflict trả `409` |
| `GET /agent-runs/{id}` | Staff/customer-safe view → run summary, evidence, errors | Customer không thấy internal-only details |
| `GET /agent-runs/{id}/events` | Staff → ordered DB-backed timeline | Read-only; polling trong v0.1 |
| `GET /approval-requests` | Support Agent/Manager → pending list theo role | Role-filtered |
| `GET /approval-requests/{id}` | Qualified reviewer → proposal, evidence, impact | `APPROVAL_NOT_FOUND/FORBIDDEN` |
| `POST /approval-requests/{id}/decision` | `approve/edit/reject`, reason, expected version/hash và optional edited action → decision/resume result | Idempotent; expiry/stale/role validation; resume đồng bộ |
| `POST /knowledge/documents` | Admin; Markdown + metadata → validation/index result | Idempotent `KNOWLEDGE_DOCUMENT_CREATE`; chỉ `text/markdown`, size/checksum validation |
| `POST /knowledge/documents/{id}/publish` | Admin → published version/chunk count | Idempotent `KNOWLEDGE_PUBLISH`; không publish nếu validation/indexing fail |
| `POST /knowledge/documents/{id}/reindex` | Admin → synchronous persisted reindex result `200` | Không queue/`202`/polling; atomic swap; idempotent; config/scoring change buộc calibration lại |
| `POST /knowledge/search` | Admin/Support → citations | Read-only; policy filters bắt buộc |
| `GET /admin/audit-logs` | Admin/Manager filters → redacted audit records | Không expose secrets/raw message |

### 8.3 Contract chi tiết cho synchronous trigger/resume

#### 8.3.1 Tạo Ticket

`POST /api/v1/tickets` tạo Ticket và first message trong một transaction, không khởi chạy agent. Response `201`:

- `ticket_id`
- `ticket_number`
- `ticket_status=OPEN`
- `correlation_id`

Vue chỉ gọi create-run sau khi nhận `ticket_id`.

#### 8.3.2 Tạo Agent Run

`POST /api/v1/tickets/{ticket_id}/agent-runs` tạo run, chuyển Ticket `OPEN/ESCALATED → PROCESSING` theo allowed transition và chạy đồng bộ đến interruption hoặc terminal state tiếp theo.

Response `201` gồm `run_id`, `run_status`, `ticket_status`, `next_required_action`, optional `approval_request_id`, `correlation_id`, `timeline_cursor`. Các status có thể trả tại boundary: `WAITING_CUSTOMER`, `WAITING_APPROVAL`, `COMPLETED`, `ESCALATED`, `FAILED`.

Invariant active run:

- Non-terminal status gồm `CREATED`, `RUNNING`, `WAITING_CUSTOMER`, `WAITING_APPROVAL`, `EXECUTING`, `VERIFYING`.
- Cùng `Idempotency-Key`: trả response đã persist, không tạo run mới.
- Key khác khi đã có non-terminal run: trả HTTP `409`, `code=AGENT_RUN_ALREADY_ACTIVE`, `retryable=false`; `details` chứa `ticket_id`, `active_run_id`, `active_run_status`, `next_required_action`.
- Không có status `CANCELLED` hoặc cancel endpoint trong v0.1.

Timeout trước business write trả HTTP `504`, `code=WORKFLOW_REQUEST_TIMEOUT`, `retryable=true`, cùng `run_id`, `run_status=FAILED`, `ticket_status=ESCALATED`, `correlation_id`. Run timeout là terminal; retry tạo run mới với key mới.

#### 8.3.3 Customer gửi thông tin bổ sung

`POST /api/v1/tickets/{ticket_id}/messages` nhận `content`, optional `attachment_references: string[]` và `Idempotency-Key`.

- `attachment_references` omitted hoặc `[]`: hợp lệ và tiếp tục message/resume contract bên dưới.
- `attachment_references` non-empty: validate fail trước mọi side effect; không insert message, không persist successful idempotency response, không fetch/store reference và không resume run. Trả HTTP `422`, `code=ATTACHMENTS_NOT_SUPPORTED`, `retryable=false`, `details={"supported_from":"v1.0"}`; không ignore im lặng.
- v0.1 không có ticket attachment upload endpoint, attachment table hoặc background fetch. Markdown upload chỉ áp dụng Knowledge Base.

- Nếu Ticket không ở `WAITING_CUSTOMER`: chỉ lưu message, trả `201`, `resume_attempted=false`.
- Nếu Ticket và active run cùng ở `WAITING_CUSTOMER`: lưu message trước; khóa/check Ticket và run; chuyển Ticket sang `PROCESSING`, run sang `RUNNING`; resume chính run cũ đến interruption/terminal state tiếp theo.
- Response resume `200 MessageResumeResponse` gồm `message_id`, `ticket_id`, `ticket_status`, `run_id`, `run_status`, `resume_attempted=true`, `next_required_action`, optional `approval_request_id`, `correlation_id`, `timeline_cursor`.
- Nếu resume timeout, không rollback message; trả `504 WORKFLOW_REQUEST_TIMEOUT` nhưng vẫn có `message_id/run_id`; run `FAILED`, Ticket `ESCALATED`, audit `agent_run.timeout`.
- Nếu Ticket `WAITING_CUSTOMER` nhưng không còn resumable run, vẫn lưu message; Ticket `ESCALATED`; trả `200`, `resume_attempted=false`, `run_status=ESCALATED`; audit `agent_run.resume_invariant_failed`; không âm thầm tạo run mới.
- Duplicate cùng idempotency key không tạo message hoặc resume lần hai.

#### 8.3.4 Approval decision

`POST /api/v1/approval-requests/{id}/decision` kiểm tra `expires_at`, `expected_version` và `expected_proposal_hash` trong cùng row lock/transaction.

- Expired: persist `EXPIRED`, chuyển run/ticket `ESCALATED`, audit `approval.expired`, trả `409 APPROVAL_EXPIRED`.
- Material edit: validate schema/ownership/business rules, tạo proposal version/hash mới, reset TTL 24 giờ và dừng tại `EDITED_PENDING_REAPPROVAL`.
- Non-material edit: có thể approve trong cùng request, không kéo dài TTL hiện tại.
- Approve hợp lệ: resume với budget 60 giây, execute → verify → response → Ticket transition.
- Reject: chuyển approval `REJECTED`, run/ticket `ESCALATED`; không thực thi action.

Rollout giữ nguyên final contract nhưng triển khai theo hai mức:

- **v0.1-alpha:** approve, reject, expiry, role validation, expected version/hash, idempotent execution và verification. Đây là real approval happy path đầu tiên thay fake approval của Walking Skeleton.
- **v0.1-beta/final:** reviewer edit, material/non-material classification, immutable proposal version/hash mới, TTL reset và reapproval.
- `APR-002` không chặn `SKEL-001` hoặc alpha approve/reject happy path, nhưng full Vue edit flow, `E2E-001B` và final Definition of Done v0.1 vẫn phụ thuộc `APR-002`.

#### 8.3.5 Knowledge reindex

`POST /api/v1/knowledge/documents/{document_id}/reindex` yêu cầu Admin JWT và `Idempotency-Key`, chạy đồng bộ trong request budget riêng của ingestion/reindex, không dùng agent workflow queue. Thành công luôn trả HTTP `200`:

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

- `document_status` chỉ có `DRAFT/VALIDATED/PUBLISHED/SUPERSEDED/EXPIRED`; reindex không tự publish hoặc đổi lifecycle status. `DRAFT/VALIDATED` vẫn giữ nguyên status.
- `previous_index_version` nullable khi document chưa có active index; các field còn lại trong success response không nullable và `chunk_count >= 0`.
- Với `PUBLISHED` document, active index cũ tiếp tục phục vụ query trong lúc build. Sau khi chunks/provenance/count validate, backend chuyển index mới `COMPLETED` và swap active pointer atomically. Failure giữ nguyên active pointer; failed attempt vẫn được persist để audit.
- Thay provider/model/revision/dimension/input format hoặc retrieval-scoring config luôn trả `calibration_required=true`, persist flag trên index và đặt effective runtime/release config `RAG_THRESHOLD_CALIBRATED=false`.
- Replay cùng principal/key/request hash trả nguyên persisted status/body và header `Idempotency-Replayed: true`; không build lần hai. Không có `202`, job ID hay polling endpoint trong v0.1.

Error envelope:

| HTTP/code | Retryable | Khi nào |
|---|---:|---|
| `404 KNOWLEDGE_DOCUMENT_NOT_FOUND` | false | Document không tồn tại hoặc ngoài admin scope |
| `409 KNOWLEDGE_DOCUMENT_NOT_REINDEXABLE` | false | Status `SUPERSEDED/EXPIRED` hoặc đã có conflicting in-request operation |
| `409 EMBEDDING_CONFIGURATION_MISMATCH` | false | Runtime provider/model/revision/dimension/input format không khớp contract/index request |
| `422 REINDEX_VALIDATION_FAILED` | false | Markdown/chunk/provenance/schema validation không đạt |
| `500 REINDEX_EXECUTION_FAILED` | true | Embedding/database/provider failure tạm thời; active index cũ vẫn nguyên |
| `504 REINDEX_EXECUTION_FAILED` | true | Vượt `KNOWLEDGE_REINDEX_TIMEOUT_SECONDS=120`; persist failed attempt trước response, active index cũ vẫn nguyên |

### 8.4 Internal Mock-Commerce APIs v0.1

Mọi route `/internal/v1/*` validate exact Bearer service token trước customer lookup, ownership hoặc business-body validation:

- Thiếu/malformed header: HTTP `401`, `code=INTERNAL_UNAUTHENTICATED`, `retryable=false`.
- Bearer token sai, user JWT hoặc credential không được phép: HTTP `403`, `code=INTERNAL_FORBIDDEN`, `retryable=false`.
- SupportPilot HTTP adapter inject token từ `INTERNAL_SERVICE_TOKEN`; LLM/tool arguments không có field credential và frontend không nhận biến này.
- Raw header/token không xuất hiện trong access log, error details, audit `details`, tool input/output summary hoặc tracing. v0.1 chỉ có một internal service token; rotation/multi-service identity ngoài phạm vi.

| Endpoint | Contract | Errors và write controls |
|---|---|---|
| `GET /internal/v1/customers/{id}` | Service auth → scoped customer summary | `CUSTOMER_NOT_FOUND` |
| `GET /internal/v1/customers/{id}/orders` | Filters date/status/product → order candidates | Customer ID bắt buộc |
| `GET /internal/v1/orders/{id}` | → order detail và version | `ORDER_NOT_FOUND` |
| `GET /internal/v1/orders/{id}/items` | → item/variant/quantity | Read-only |
| `POST /internal/v1/orders/{id}/sync-payment` | Expected order version, transaction ref, approval ref → new status/version | Idempotency bắt buộc; `STALE_ORDER`, `PAYMENT_MISMATCH`, `APPROVAL_REQUIRED` |
| `GET /internal/v1/orders/{id}/payment` | → linked payment | Read-only |
| `GET /internal/v1/customers/{id}/payments` | Date range/status/amount → transactions | Customer scoped |
| `GET /internal/v1/payments/{id}` | → payment detail | Không trả payment secret |

Shipping/refund/fulfillment APIs thuộc v1.0; payment investigation và warranty APIs thuộc Post-MVP. Chúng không được implement hoặc đưa vào v0.1 acceptance criteria.

## 9. Agent workflow

### 9.1 AgentState sơ bộ

State chứa:

- Ticket/run/correlation identifiers.
- Authenticated customer scope.
- Normalized ticket context và untrusted-content markers.
- Intent, confidence, entities, missing fields.
- Order candidates, scores và resolution status.
- Business evidence và exact source references.
- Policy citations, retrieval scores và conflicts.
- Evidence sufficiency và deterministic rule results.
- Proposed actions và response draft.
- Approval ID/status/version.
- Execution and verification results.
- Retry/error summaries.
- Graph/prompt/tool versions.
- Absolute/monotonic workflow deadline và remaining budget.
- Embedding/index provenance dùng cho evidence.

State không chứa chain-of-thought.

### 9.2 LangGraph profiles và node mapping

#### 9.2.1 Active graph profile v0.1

```text
receive_ticket
→ identify_customer
→ extract_payment_mismatch_context
→ resolve_order
→ retrieve_evidence
→ retrieve_policy
→ evaluate_and_propose
→ wait_for_approval
→ execute_verify_respond
```

- Intent được endpoint/use-case configuration và deterministic guard xác định là `payment_mismatch`; v0.1 không gọi LLM riêng cho classification. Nội dung rõ ràng ngoài UC-01 chuyển `ESCALATED` với `UNSUPPORTED_INTENT`.
- `extract_payment_mismatch_context` gộp normalize và structured extraction cho order ID, product, amount/time, transaction reference; ưu tiên tối đa một structured-output Gemini call.
- `retrieve_evidence` gộp customer-scoped Order/Payment HTTP reads nhưng vẫn persist từng tool call/event.
- `evaluate_and_propose` gọi deterministic policy engine trước; LLM không override business rule. Tối đa một grounded LLM call cho proposal/response khi cần.
- `execute_verify_respond` là subgraph/nhóm internal nodes; execution, verification, response draft, Ticket transition và từng Action Execution/event vẫn được persist riêng.
- Audit được ghi bởi service/middleware/event hooks ở mọi boundary, không phụ thuộc vào một node cuối duy nhất.

| Target node architecture | Mapping trong v0.1 | Trạng thái |
|---|---|---|
| `receive_ticket` | `receive_ticket` + deterministic UC-01 guard | Active |
| `identify_customer` | `identify_customer` | Active |
| `classify_intent` | Không gọi LLM; guard trong `receive_ticket` | Chỉ kích hoạt từ v1.0 |
| `extract_entities` | `extract_payment_mismatch_context` | Gộp/active |
| `resolve_order` | `resolve_order` | Active |
| `request_missing_information` | Conditional route/pause trong extraction/resolution | Gộp/active |
| `retrieve_business_data` | `retrieve_evidence` | Gộp/active |
| `retrieve_policy` | `retrieve_policy` | Active |
| `evaluate_evidence`, `generate_resolution_plan`, `check_approval_requirement` | `evaluate_and_propose`; deterministic rules tách khỏi prompt | Gộp/active |
| `wait_for_approval` | `wait_for_approval` | Active |
| `execute_action`, `verify_action`, `generate_customer_response`, `update_ticket` | `execute_verify_respond` subgraph/internal nodes | Gộp/active |
| `write_audit_log` | Service/middleware/event hooks | Không là graph terminal node v0.1 |
| `handle_failure` | Typed orchestration failure routes/hooks | Active infrastructure |

#### 9.2.2 Target node contracts v1.0

Danh mục dưới đây giữ nguyên làm target architecture cho v1.0; v0.1 chỉ implement mapping phía trên.

| Node | Input → output; tools | Routing, retry và failure |
|---|---|---|
| `receive_ticket` | Ticket/message → normalized context, injection flags | Invalid/empty → `handle_failure`; deterministic, không retry |
| `identify_customer` | Auth principal/channel identity → verified customer ID | Không verified → request identity; tuyệt đối không gọi commerce |
| `classify_intent` | Context → intent/confidence; Gemini adapter | Structured-output tối đa 2 attempts; thấp → manual/clarification |
| `extract_entities` | Context → entities/missing fields; Gemini adapter | Tối đa 2 attempts; vẫn thiếu → request info |
| `resolve_order` | Customer + entities → candidate result | Gọi search orders/payment; ambiguous → clarification |
| `request_missing_information` | Missing fields/candidates → safe question | Pause đến message mới; không lộ PII |
| `retrieve_business_data` | Resolved order → order/payment/shipping evidence | Read tool tối đa 3 attempts; timeout/mismatch → failure/manual |
| `retrieve_policy` | Intent/entity filters → citations | RAG retry một lần; score thấp/conflict → insufficient |
| `evaluate_evidence` | API evidence + citations → deterministic eligibility | Không đủ → clarification/escalation; không LLM override |
| `generate_resolution_plan` | Eligibility → proposed actions/rationale; Gemini adapter | Tối đa 2 attempts; action phải nằm allowlist |
| `check_approval_requirement` | Proposed actions → approval tier | Business write/send → approval; internal draft/audit → auto |
| `wait_for_approval` | Immutable proposal version/hash → approval ID/status/expiry | LangGraph interrupt; resume chỉ bằng validated backend event |
| `execute_action` | Approved non-expired proposal → tool result | Revalidate schema, ownership qua HTTP và business rules; write retry chỉ với cùng key; stale/material edit → approval lại |
| `verify_action` | Result → fresh target state | Một read retry; mismatch → failed/manual |
| `generate_customer_response` | Verified outcome + citations → draft | Không claim thành công nếu verify fail |
| `update_ticket` | Outcome → ticket status/message/internal note | Internal deterministic transition; không phải approval tool và LLM không gọi trực tiếp; `RESOLVED` chỉ sau `VERIFIED` |
| `write_audit_log` | Run summary → audit/events | Audit failure làm run degraded và alert; không bỏ qua âm thầm |
| `handle_failure` | Typed error → retry/escalate/customer-safe response | Phân biệt retryable, validation, permission và provider failure |

### 9.3 Retry policy chung

- Mỗi synchronous graph advance có budget 60 giây theo monotonic clock và 5 giây cuối dành cho persist state/audit/HTTP response.
- Mỗi Gemini attempt có timeout tối đa 12 giây. Effective timeout không được vượt remaining budget trừ finalization reserve.
- LLM structured output có tối đa 2 attempts tính cả initial attempt; retry chỉ bắt đầu khi còn ít nhất `12 + 5 = 17` giây.
- Read API: tối đa 3 attempts, exponential backoff ngắn, chỉ retry timeout/5xx.
- RAG: một retry; sau đó no-answer/manual review.
- Write API: không semantic retry mù; kiểm tra action status rồi retry cùng idempotency key.
- Permission/validation/4xx business error: không retry.
- Mọi retry tạo run event và tool-call attempt riêng.

Profile v0.1 không hard-code ba Gemini calls. Pre-approval path ưu tiên tối đa hai initial calls: một structured extraction và một grounded proposal/response call khi cần, tương ứng tối đa 24 giây nếu không retry. Schema retry chỉ chạy khi remaining budget đủ; HTTP/RAG/checkpoint work và finalization reserve luôn chịu global deadline. Approval decision và message resume là synchronous advance riêng, nhận budget 60 giây mới.

Khi vượt workflow budget trước business write:

- Cooperative-cancel operation; persist Agent Run `FAILED`, `failure_code=WORKFLOW_REQUEST_TIMEOUT` và Ticket `ESCALATED`.
- Ghi audit `agent_run.timeout` với run ID, current node, elapsed time và correlation ID; không ghi raw ticket/secret.
- Trả HTTP `504`; không tự resume run failed.

Nếu deadline/connection loss xảy ra sau khi write request đã gửi nhưng chưa rõ kết quả, Action Execution chuyển `UNKNOWN`; không blind retry. Mọi lần tiếp tục phải status-reconcile/verify bằng cùng idempotency key, và Ticket không được `RESOLVED` trước `VERIFIED`.

Trước mọi resume, orchestrator phải load checkpoint bằng `thread_id=agent_run.id`, kiểm tra run/ticket resumable và áp dụng recovery rules §7.8. Thiếu/mâu thuẫn checkpoint không được tạo run mới ngầm.

### 9.4 State machines và allowed transitions

#### Ticket

| From | To | Điều kiện |
|---|---|---|
| `OPEN` | `PROCESSING` | Explicit Agent Run bắt đầu |
| `PROCESSING` | `WAITING_CUSTOMER` | Thiếu identity/order/evidence |
| `WAITING_CUSTOMER` | `PROCESSING` | Message mới đã lưu và same run resume |
| `PROCESSING` | `WAITING_APPROVAL` | Valid business proposal |
| `WAITING_APPROVAL` | `PROCESSING` | Valid approve hoặc non-material edit+approve; material edit giữ Ticket `WAITING_APPROVAL` với approval version mới |
| `PROCESSING` | `ESCALATED` | Run failure, timeout hoặc insufficient evidence |
| `WAITING_APPROVAL` | `ESCALATED` | Reject hoặc approval expiry 24 giờ |
| `PROCESSING` | `RESOLVED` | Action Execution `VERIFIED` và response đã lưu |
| `RESOLVED` | `CLOSED` | Closure rule |
| `RESOLVED` | `PROCESSING` | Customer reopen |
| `ESCALATED` | `PROCESSING` | Explicit Agent Run mới |

Không cho phép `WAITING_APPROVAL → RESOLVED` trực tiếp.

#### Agent Run

- `CREATED → RUNNING`.
- `RUNNING → WAITING_CUSTOMER | WAITING_APPROVAL | EXECUTING | ESCALATED | FAILED`.
- `WAITING_CUSTOMER → RUNNING` qua message resume.
- `WAITING_APPROVAL → RUNNING` qua valid non-expired approved decision; material edit tiếp tục chờ reapproval, reject/expiry đi `ESCALATED`.
- `WAITING_APPROVAL → ESCALATED` khi reject hoặc approval hết hạn.
- `RUNNING → FAILED` khi hết workflow budget.
- `RUNNING → EXECUTING` chỉ với approved proposal chưa hết hạn.
- `EXECUTING → VERIFYING | FAILED`.
- `VERIFYING → COMPLETED | ESCALATED | FAILED`.

`COMPLETED`, `ESCALATED`, `FAILED` là terminal cho run hiện tại. v0.1 không có `CANCELLED`; timeout retry tạo Agent Run mới.

#### Approval

- `PENDING → APPROVED | REJECTED | EXPIRED | SUPERSEDED`.
- `PENDING → EDITED_PENDING_REAPPROVAL` khi material edit.
- `EDITED_PENDING_REAPPROVAL → APPROVED | REJECTED | EXPIRED`.
- `APPROVED → CONSUMED | INVALIDATED`.
- `expires_at = requested_at + APPROVAL_TTL_HOURS`, với TTL 24 giờ UTC tuyệt đối.
- Expiration được phát hiện lazy nhưng phải persist thành `EXPIRED`; không revive approval expired.

#### Action Execution

- `PENDING → RUNNING`.
- `RUNNING → SUCCEEDED | FAILED_RETRYABLE | FAILED_FINAL | UNKNOWN`.
- `SUCCEEDED → VERIFYING`.
- `VERIFYING → VERIFIED | FAILED_RETRYABLE | FAILED_FINAL`.
- `FAILED_RETRYABLE → RUNNING` với cùng idempotency key.
- `UNKNOWN → VERIFYING | FAILED_RETRYABLE | FAILED_FINAL`.

Ticket chỉ chuyển `RESOLVED` sau `VERIFIED`.

## 10. Tool registry

Mọi tool call lưu: run/correlation ID, tool/version, permission tier, redacted input, output summary, latency, attempt, status, error code, idempotency key và actor/customer scope.

V0.1 chỉ enable các read tools cần cho UC-01, `search_policy` và write tool `sync_payment_status`. Tool của UC-02–UC-05 giữ contract cho v1.0; UC-06–UC-07 để Post-MVP. SupportPilot tools gọi commerce qua HTTP adapter, không import commerce repository.

Commerce tool schemas không có credential field. HTTP adapter tự inject `Authorization: Bearer <INTERNAL_SERVICE_TOKEN>` sau schema validation và trước network call; LLM không xem/chọn/thay token. Tool input/output/event/audit chỉ lưu redacted business projection, tuyệt đối không lưu authorization header hoặc token value.

### 10.1 Read-only tools

| Tool | Input → output; service | Timeout/retry | Permission |
|---|---|---|---|
| `get_customer_context` | Verified principal → masked customer context; Customer module | 2s, 1 retry | Backend-injected scope |
| `search_customer_orders` | Customer ID, product/date/status filters → candidates; Order API | 3s, 2 retries | `SAFE_READ`, customer scoped |
| `get_order` | Customer scope + order ID → order/version | 3s, 2 retries | Ownership enforced |
| `get_order_items` | Customer/order → items | 3s, 2 retries | Ownership enforced |
| `get_recent_customer_payments` | Customer/date/amount → payments | 3s, 2 retries | Ownership enforced |
| `get_payment_status` | Customer + payment/order ref → status | 3s, 2 retries | No card data |
| `match_payment_to_order` | Candidate orders/payments → ranked pair evidence; deterministic local service | 1s, no retry | Read-only |
| `get_shipping_status` | Customer/order/tracking → events; v1.0 | 3s, 2 retries | Ownership enforced |
| `get_delivery_evidence` | Customer/order/shipment → redacted proof; v1.0 | 4s, 1 retry | Support Agent for sensitive proof |
| `validate_shipping_address` | Customer + structured address → valid/serviceable; v1.0 | 3s, 1 retry | Address never logged raw |
| `search_policy` | Query + metadata filters → citations | 5s, 1 retry | Policy only |
| `get_ticket_history` | Customer/topic/date → summarized tickets | 3s, 1 retry | Scoped; no raw unrelated messages |
| `find_duplicate_payments` | Customer/order/time window → candidate pairs | 3s, 2 retries | Post-MVP |
| `get_warranty_status` | Item + serial hash → coverage/prior claims | 3s, 2 retries | Post-MVP |

Read-only tools không cần idempotency key.

### 10.2 Write tools requiring approval

| Tool | Input → output; service | Timeout/retry/idempotency | Permission |
|---|---|---|---|
| `sync_payment_status` | Order/payment/expected versions/approval → updated order | 5s; status-check rồi một retry cùng key | Support Agent approval |
| `create_return_request` | Order/item/reason/evidence/approval → request; v1.0 | 5s; unique request key | Support Agent |
| `create_refund_request` | Order/item/amount/reason/approval → pending refund; v1.0 | 5s; duplicate check + key | Agent/Manager theo threshold |
| `create_return_to_sender` | Shipment/reason/approval → RTS request; v1.0 | 5s; unique shipment action | Support Agent |
| `send_customer_message` | Ticket/recipient/approved content → delivery result; v1.0 | 5s; message key | Support Agent |
| `create_missing_item_claim` | Order/item/quantity/evidence → claim; v1.0 | 5s; unique open claim | Support Agent |
| `create_replacement_request` | Accepted claim/item/quantity → replacement; v1.0 | 5s; unique claim action | Agent/Manager theo giá trị |
| `update_shipping_address` | Shipment/new address/expected version → result; v1.0 | 5s; same action key | Support Agent |
| `create_payment_investigation` | Transaction set/evidence → investigation | 5s; transaction-set hash | Support Agent, Post-MVP |
| `create_warranty_claim` | Item/serial hash/evidence → claim | 5s; item/serial key | Support Agent, Post-MVP |

### 10.3 Automatic low-risk write tools

| Tool | Rule |
|---|---|
| `create_email_draft` | Tạo draft, không gửi; idempotent theo run/ticket/version. |
| `add_internal_note` | Chỉ staff thấy, nội dung redacted; audit bắt buộc. |
| `escalate_ticket` | Cho phép tự động gán queue/severity nhưng không thực hiện commerce action. |
| `record_ticket_progress` | Chỉ cập nhật trạng thái kỹ thuật trung gian và timeline. |
| `update_ticket_status` | Internal deterministic transition theo Ticket state machine; không cần approval riêng và không được LLM gọi trực tiếp. `RESOLVED` chỉ sau approved business action đã `VERIFIED`. |
| `send_internal_notification` | Chỉ gửi cho staff về approval/error; không gửi customer. |
| `write_audit_event` | System-only, agent không tự chọn payload tùy ý. |

### 10.4 Tools bị cấm trong v0.1

- Arbitrary HTTP request.
- SQL query/command.
- Filesystem read/write.
- Shell hoặc code execution.
- Delete customer/order/payment/ticket.
- Update role/permission.
- Direct model-selected refund execution.
- Tool registration động từ ticket hoặc policy document.

## 11. Order Resolution design

### 11.1 Inputs và identity

- `verified_customer_id` chỉ lấy từ JWT/session, verified email mapping hoặc OTP flow.
- LLM không được truyền hoặc sửa customer ID.
- Entities: order ID, product keyword/category, amount, currency, approximate date, transaction reference và payment method.
- Nếu có order ID, vẫn kiểm tra ownership trước khi dùng.

### 11.2 Candidate search

1. Query orders của customer trong 30 ngày gần nhất.
2. Nếu không có candidate và intent cho phép, mở rộng tối đa 90 ngày.
3. Normalize Unicode, case và accent; dùng trigram/fuzzy product matching.
4. Lấy recent payments của cùng customer để bổ sung evidence.
5. Không query toàn hệ thống rồi mới lọc.

### 11.3 Score

- Product/category match: tối đa 40.
- Recency phù hợp intent: tối đa 20.
- Order `payment_status=PENDING`: 15.
- Có payment `status=SUCCEEDED` phù hợp: 15.
- Amount/payment method/transaction ref match: tối đa 10.

Quyết định:

- ≥85, duy nhất và hơn runner-up ≥15: auto-resolve.
- 60–84 hoặc margin <15: yêu cầu customer xác nhận.
- <60: hỏi thêm thông tin hoặc manual review.
- Nhiều candidate ≥85: không tự chọn.
- Mỗi component score và evidence phải được lưu để test/reproduce.

### 11.4 Safe clarification

Chỉ hiển thị:

- Order number đã rút gọn.
- Ngày đặt.
- Product category/tên rút gọn.
- Amount cần thiết để phân biệt.

Không hiển thị địa chỉ, điện thoại, payment details hoặc order của customer khác.

### 11.5 Entity-resolution tests

- Một order rõ ràng không có order ID.
- Hai order cùng product khác ngày.
- Hai order cùng ngày khác amount.
- Payment succeeded không link order.
- Customer khác có order giống hệt.
- Product keyword sai chính tả/không dấu.
- Không có candidate trong 30 ngày nhưng có trong 90 ngày.
- Candidate score sát ngưỡng và margin nhỏ.
- API timeout hoặc payment/order ownership mismatch.

## 12. RAG design

### 12.1 Supported documents

Milestone v0.1:

- UTF-8 Markdown cho seed policies và tài liệu do repository quản lý.
- Từ chối PDF, DOCX, OCR và các MIME khác `text/markdown`.

Text-based PDF chuyển sang v1.0. DOCX/OCR chỉ đánh giá Post-MVP nếu có nhu cầu thực tế.

### 12.2 Pipeline

1. Nhận Markdown và tạo checksum.
2. Validate extension, MIME, size, malware status và required metadata.
3. Parse Markdown trong isolated adapter.
4. Normalize whitespace/headings nhưng giữ section boundaries.
5. Extract title, heading path, version và effective dates.
6. Chunk theo section, target content 450 tokens và overlap 75; target không phải độ dài cố định và phải co lại để toàn passage input nằm trong model context limit.
7. Sinh normalized embedding bằng local SentenceTransformers adapter.
8. Lưu source document, chunks, `vector(384)`, FTS vector và exact embedding model/revision/input-format/index provenance vào PostgreSQL.
9. Chạy validation queries trước khi publish.
10. Publish atomically; version cũ chuyển `SUPERSEDED`, không xóa.
11. Reindex synchronous tạo `knowledge_index_versions` attempt mới; `PUBLISHED` index cũ tiếp tục active, chỉ swap pointer trong transaction sau khi attempt `COMPLETED`. Failed attempt không đổi active pointer.
12. Expired policy bị loại khỏi query hiện tại nhưng vẫn truy xuất được cho historical audit.

Reindex không đổi document lifecycle: `DRAFT`/`VALIDATED` không tự thành `PUBLISHED`; `PUBLISHED` giữ status. Replay cùng idempotency key dùng persisted result, không tạo attempt/chunks mới. Bất kỳ thay đổi embedding/retrieval provenance nào đặt `calibration_required=true` và `RAG_THRESHOLD_CALIBRATED=false` trước khi index mới có thể là release evidence.

### 12.3 E5 embedding input contract

Query input bắt buộc:

```text
query: {normalized_query}
```

Policy passage input bắt buộc:

```text
passage: {title}
{heading_path}
{chunk_content}
```

Quy tắc:

- Dùng đúng tokenizer của `EMBEDDING_MODEL` tại exact `EMBEDDING_REVISION`; không dùng tokenizer gần tương đương hoặc revision mặc định khác.
- Token count bao gồm prefix, title, heading path, newline/separator và chunk content. Toàn embedding input không được vượt `model_max_length` của model/revision.
- `RAG_CHUNK_TOKENS=450` là target cho chunk content, không phải fixed size hoặc hard cap của toàn passage. Title/heading dài làm content budget giảm tương ứng; không truncate prefix/title/heading âm thầm.
- Query và passage dùng cùng Unicode/whitespace normalization policy, cùng model/revision và `EMBEDDING_NORMALIZE=true`.
- Persist `embedding_input_format_version=e5-prefix-v1` trên mỗi index/chunk provenance. Query runtime phải dùng input-format version khớp active index.
- Đổi prefix, field order, separators, normalization hoặc `EMBEDDING_INPUT_FORMAT_VERSION` được coi như đổi model: tạo index version mới, reindex toàn corpus, đặt calibration flags về `false` và chạy lại calibration/holdout evaluation.

### 12.4 Required metadata

- `policy_type`, `title`, `version`.
- `effective_from`, `effective_to`.
- `region`, `language`.
- `product_category` hoặc `all`.
- `heading_path`, `chunk_index`.
- `source_uri`, `checksum`.
- `embedding_provider`, `embedding_model`, `embedding_revision`, `embedding_dimension`, `embedding_input_format_version`, `index_version`.
- `status`: `DRAFT/VALIDATED/PUBLISHED/SUPERSEDED/EXPIRED`.
- Các metadata chuyên biệt như carrier, approval role, refund limit hoặc claim window.

### 12.5 Hybrid retrieval and RRF contract

Embedding mặc định là local `sentence_transformers`, model `intfloat/multilingual-e5-small`, dimension 384, immutable revision `c007d7ef6fd86656326059b28395a7a03a7c5846` và input format `e5-prefix-v1`. Corpus v0.1 dùng exact vector search; không reranker.

Pipeline deterministic:

1. Filter trước retrieval theo `policy_type`, `region`, `product_category`, `language`, effective date và document status `PUBLISHED`. `EXPIRED`/`SUPERSEDED`/wrong-version chunks không được vào candidate set.
2. Exact vector search trên filtered set lấy top 10, sort cosine similarity giảm dần rồi `chunk_id` tăng dần để tie-break.
3. PostgreSQL FTS trên cùng filtered set lấy top 10. Query dùng `plainto_tsquery('simple', normalized_query)`; lexical score dùng `ts_rank_cd(search_vector, tsquery, 32)`, sort giảm dần rồi `chunk_id` tăng dần.
4. Ghi riêng `vector_similarity` và `lexical_confidence`; vector dưới calibrated vector threshold không vượt vector evidence gate.
5. Union hai ranking, deduplicate theo `chunk_id`, rồi dùng Reciprocal Rank Fusion:

```text
RRF(d) = Σ 1 / (k + rank_i(d))
```

6. `k = RRF_K = 60` là development ranking default. Rank bắt đầu từ 1; chunk có ở cả hai nhánh nhận tổng hai thành phần nhưng chỉ xuất hiện một lần.
7. Một chunk chỉ đủ điều kiện citation/business evidence khi vượt ít nhất một calibrated confidence gate: `vector_similarity >= RAG_MIN_SIMILARITY` hoặc `lexical_confidence >= RAG_MIN_LEXICAL_CONFIDENCE`.
8. Sau evidence gate, sort theo RRF giảm dần, tie-break theo vector similarity, lexical confidence rồi `chunk_id`; trả tối đa 5 citations.
9. RRF chỉ dùng ranking; RRF score không phải evidence confidence và không thay thế vector/lexical threshold.
10. Lexical-only match dưới lexical threshold phải no-answer/escalation. FTS exact match không bypass metadata, effective-date, version, status hoặc conflict checks.

`RAG_MIN_SIMILARITY=0.72` chỉ là development placeholder chưa có ý nghĩa release với E5-small và phải được hiệu chỉnh lại từ đầu. `RAG_MIN_LEXICAL_CONFIDENCE` không có release default trước calibration. Cả vector và lexical threshold được sweep/chọn trên golden calibration subset thật cho exact model/revision/input-format/index; threshold được áp dụng trước khi citation trở thành business evidence. Release chỉ bật evidence gates khi calibration artifact khớp exact model/revision/input format/index/dataset version.

Calibration target:

- Recall@5 cho payment policy ít nhất 90%.
- Không chấp nhận irrelevant policy như evidence đủ tin cậy.
- Holdout false-positive policy evidence count phải bằng 0.
- Nếu không có threshold thỏa cả hai điều kiện, dùng conservative no-answer/escalation thay vì giảm guardrail.
- Thay model/revision/dimension/input-format, retrieval scoring hoặc golden dataset version làm calibration status quay lại `false`.

### 12.6 No-answer và conflict

Agent không được kết luận chắc chắn nếu:

- Không có active chunk vượt vector hoặc lexical calibrated confidence gate.
- Top chunks không hỗ trợ điều kiện đang xét.
- Hai active policy cùng scope/effective period mâu thuẫn mà không có quan hệ supersede rõ.
- Citation thiếu version/effective date.
- API evidence không đủ dù policy đã rõ.

Khi conflict, hệ thống hiển thị cả hai citation, gắn `policy_conflict=true` và escalate. Không để LLM tự chọn policy chỉ vì văn bản nghe hợp lý hơn.

## 13. Repository structure

```text
supportPilot/
├── backend/
│   ├── apps/
│   │   ├── support_api/
│   │   │   ├── api/             # Public SupportPilot routers
│   │   │   ├── core/            # Config, errors, security, DI
│   │   │   ├── db/              # support engine/session/checkpointer
│   │   │   ├── models/          # Chỉ SQLAlchemy models schema support
│   │   │   ├── schemas/         # Public API/agent schemas
│   │   │   ├── repositories/    # Chỉ support persistence
│   │   │   ├── services/        # Ticket/domain/orchestration services
│   │   │   ├── agents/          # v0.1 profile, target nodes, checkpoints
│   │   │   ├── tools/           # Registry + HTTP-backed commerce tools
│   │   │   ├── rag/             # Markdown ingestion/retrieval/citation
│   │   │   ├── integrations/    # Commerce/LLM/embedding/draft adapters
│   │   │   ├── approvals/       # HITL state machine
│   │   │   └── audit/           # Audit/event/redaction
│   │   └── mock_commerce_api/
│   │       ├── api/              # Internal `/internal/v1` routers
│   │       ├── core/             # Service auth/config
│   │       ├── db/               # commerce engine/session
│   │       ├── models/           # Chỉ SQLAlchemy models schema commerce
│   │       ├── repositories/     # Chỉ commerce persistence
│   │       └── services/         # Order/Payment behavior
│   ├── packages/
│   │   ├── common/               # Schema-neutral primitives only
│   │   └── commerce_contracts/   # Versioned HTTP request/response/error types
│   ├── migrations/
│   │   ├── support/              # Chạy bằng support_owner
│   │   └── commerce/             # Chạy bằng commerce_owner
│   └── tests/
│       ├── import_boundaries/
│       ├── contracts/
│       └── integration/
├── frontend/
│   ├── src/
│   │   ├── views/               # Login, Inbox, Ticket, Approval, Knowledge
│   │   ├── components/          # Ticket/evidence/timeline/action UI
│   │   ├── layouts/
│   │   ├── router/
│   │   ├── stores/              # Auth, ticket, approval, notification
│   │   ├── services/            # Typed HTTP client
│   │   ├── composables/         # Polling/SSE, forms, permissions
│   │   ├── types/
│   │   └── utils/
│   └── tests/
├── docs/                        # Reviewed specifications và ADRs
├── infrastructure/              # Compose, Dockerfiles, CI config
├── tests/
│   ├── e2e/
│   ├── contracts/
│   ├── evaluation/
│   └── security/
└── scripts/                     # DB bootstrap, seed, evaluation và local maintenance
```

Import/dependency rules:

- `support_api` không import SQLAlchemy model, repository, service hoặc database session từ `mock_commerce_api`.
- `mock_commerce_api` không import SupportPilot model, repository, domain service, agent hoặc database session.
- Chỉ `packages/commerce_contracts` được chia sẻ cho versioned HTTP request/response schemas, HTTP error codes và contract types. Không đặt database model/repository/session hoặc business service trong shared packages.
- `packages/common` chỉ chứa schema-neutral primitives như correlation/error base; không trở thành nơi chia sẻ domain logic.
- SupportPilot luôn gọi Mock-Commerce qua HTTP adapter, kể cả khi cùng process image/repository.
- Import-boundary test chạy trong CI và fail khi dependency graph vi phạm các rule trên.

## 14. Environment variables

Secret thật không bao giờ commit. `.env.example` chỉ có placeholder.

| Nhóm | Biến | Giá trị mẫu | Bắt buộc/phạm vi | Quy tắc |
|---|---|---|---|---|
| Application | `APP_ENV` | `development` | Có | `development`, `test`, `demo` |
| Application | `APP_NAME` | `SupportPilot` | Có | Không chứa secret |
| Application | `API_HOST` | `0.0.0.0` | Có | Container bind address |
| Application | `API_PORT` | `8000` | Có | Backend port |
| Application | `FRONTEND_ORIGIN` | `http://localhost:5173` | Có | CORS allowlist |
| Application | `CORRELATION_HEADER` | `X-Correlation-ID` | Có | Dùng xuyên API/run/tool/action |
| Workflow | `WORKFLOW_REQUEST_TIMEOUT_SECONDS` | `60` | Có | Tổng budget cho mỗi synchronous graph advance |
| Workflow | `WORKFLOW_FINALIZATION_RESERVE_SECONDS` | `5` | Có | Dành cho persist state/audit/response; không cấp cho LLM/tool |
| Workflow | `WORKFLOW_PROFILE` | `v0_1` | Có | `walking_skeleton` chỉ local/test; CI release chỉ chấp nhận `v0_1` |
| PostgreSQL init | `POSTGRES_USER` | `postgres` | Local Postgres container | Bootstrap admin; không inject vào app |
| PostgreSQL init | `POSTGRES_DB` | `supportpilot` | Local Postgres container | Database dùng chung instance, tách schema |
| PostgreSQL init | `POSTGRES_PASSWORD` | `replace-me` | Local Postgres container | Secret, không commit |
| PostgreSQL bootstrap | `POSTGRES_BOOTSTRAP_DATABASE_URL` | `postgresql://postgres:replace-me@postgres:5432/supportpilot` | Chỉ `db-bootstrap`/DB-000 | Admin DSN; không inject vào migrations/runtime |
| PostgreSQL bootstrap | `SUPPORT_OWNER_PASSWORD` | `replace-me` | Chỉ `db-bootstrap` | Secret dùng tạo `support_owner` |
| PostgreSQL bootstrap | `COMMERCE_OWNER_PASSWORD` | `replace-me` | Chỉ `db-bootstrap` | Secret dùng tạo `commerce_owner` |
| PostgreSQL bootstrap | `SUPPORT_APP_PASSWORD` | `replace-me` | `db-bootstrap` và construct support runtime DSN | Secret, không commit |
| PostgreSQL bootstrap | `COMMERCE_APP_PASSWORD` | `replace-me` | `db-bootstrap` và construct commerce runtime DSN | Secret, không commit |
| PostgreSQL runtime | `SUPPORT_DATABASE_URL` | `postgresql+asyncpg://support_app:replace-me@postgres:5432/supportpilot` | Backend | Backend chỉ nhận role `support_app` |
| PostgreSQL runtime | `COMMERCE_DATABASE_URL` | `postgresql+asyncpg://commerce_app:replace-me@postgres:5432/supportpilot` | Mock-Commerce | Backend không được nhận biến này |
| PostgreSQL migration | `SUPPORT_MIGRATION_DATABASE_URL` | `postgresql+asyncpg://support_owner:replace-me@postgres:5432/supportpilot` | Chỉ `migrate-support` | Không inject vào backend runtime |
| PostgreSQL migration | `COMMERCE_MIGRATION_DATABASE_URL` | `postgresql+asyncpg://commerce_owner:replace-me@postgres:5432/supportpilot` | Chỉ `migrate-commerce` | Không inject vào Mock-Commerce runtime |
| PostgreSQL | `DB_POOL_SIZE` | `10` | Không | Runtime connections |
| PostgreSQL | `DB_POOL_TIMEOUT_SECONDS` | `5` | Không | Runtime pool timeout |
| Authentication | `JWT_SIGNING_KEY` | `replace-me` | Có | Secret, không commit |
| Authentication | `JWT_ISSUER` | `supportpilot` | Có | Token issuer |
| Authentication | `ACCESS_TOKEN_TTL_MINUTES` | `15` | Có | v0.1 login lại khi hết hạn |
| Authentication | `PASSWORD_HASH_SCHEME` | `argon2` | Có | Password luôn hash |
| Authentication | `AUTH_RATE_LIMIT_PER_MINUTE` | `10` | Có | Login baseline |
| LLM | `LLM_PROVIDER` | `gemini` | Có | Default v0.1 |
| LLM | `GEMINI_MODEL` | `gemini-3.6-flash` | Có | Specific stable model, không dùng `latest` alias |
| LLM | `GEMINI_API_KEY` | `replace-me` | Demo Gemini | Secret, không commit |
| LLM | `LLM_TIMEOUT_SECONDS` | `12` | Có | Timeout từng Gemini attempt |
| LLM | `LLM_STRUCTURED_OUTPUT_MAX_ATTEMPTS` | `2` | Có | Tính cả initial attempt; retry cần ít nhất 17 giây remaining |
| LLM | `LLM_MAX_TOKENS_PER_RUN` | `12000` | Có | Run budget |
| Alternative LLM | `OPENAI_MODEL` | `provider-model-name` | Không | Chỉ dùng khi `LLM_PROVIDER=openai` |
| Alternative LLM | `OPENAI_API_KEY` | `replace-me` | Không | Không cần cho default v0.1 |
| Alternative LLM | `OLLAMA_BASE_URL` | `http://ollama:11434` | Không | Không có container mặc định |
| Alternative LLM | `OLLAMA_MODEL` | `local-model-name` | Không | Không thuộc v0.1 acceptance criteria |
| Embedding | `EMBEDDING_PROVIDER` | `sentence_transformers` | Có | Chạy local |
| Embedding | `EMBEDDING_MODEL` | `intfloat/multilingual-e5-small` | Có | Không dùng embedding API ngoài |
| Embedding | `EMBEDDING_REVISION` | `c007d7ef6fd86656326059b28395a7a03a7c5846` | Có | Immutable revision |
| Embedding | `EMBEDDING_DIMENSION` | `384` | Có | Phải khớp `vector(384)` |
| Embedding | `EMBEDDING_INPUT_FORMAT_VERSION` | `e5-prefix-v1` | Có | Prefix/field order/separator contract; thay đổi buộc reindex/recalibration |
| Embedding | `EMBEDDING_DEVICE` | `cpu` | Có | Default v0.1 |
| Embedding | `EMBEDDING_NORMALIZE` | `true` | Có | Cosine retrieval |
| RAG | `RAG_CHUNK_TOKENS` | `450` | Có | Target content tokens; effective budget trừ prefix/title/heading |
| RAG | `RAG_CHUNK_OVERLAP` | `75` | Có | Section-aware overlap |
| RAG | `RAG_TOP_K_CANDIDATES` | `10` | Có | Trước fusion |
| RAG | `RAG_TOP_K` | `5` | Có | Citation result |
| RAG | `RRF_K` | `60` | Có | Development ranking parameter; không phải confidence threshold |
| RAG | `RAG_MIN_SIMILARITY` | `0.72` | Development | Placeholder cho tới calibration |
| RAG | `RAG_MIN_LEXICAL_CONFIDENCE` | `replace-after-calibration` | Release | Không có default release trước calibration |
| RAG | `RAG_THRESHOLD_CALIBRATED` | `false` | Có | `true` nghĩa cả vector/lexical gates đã calibrated cho exact provenance |
| Knowledge | `KNOWLEDGE_REINDEX_TIMEOUT_SECONDS` | `120` | Có | Tổng synchronous reindex budget cho corpus Markdown v0.1; không dùng workflow 60s/queue |
| Approval | `APPROVAL_TTL_HOURS` | `24` | Có | Absolute UTC hours |
| Approval | `ALL_BUSINESS_WRITES_REQUIRE_APPROVAL` | `true` | Có | Không được override trong v0.1 |
| Mock-Commerce | `MOCK_COMMERCE_BASE_URL` | `http://mock-commerce:8080/internal/v1` | Backend | HTTP boundary duy nhất |
| Mock-Commerce | `INTERNAL_SERVICE_TOKEN` | `replace-me` | Chỉ Backend/Mock-Commerce | Một Bearer service token cho `/internal/v1/*`; không inject frontend/migrations/LLM |
| Mock-Commerce | `MOCK_SEED_PROFILE` | `payment-mismatch-v01` | Local/demo | Synthetic data |
| Mock-Commerce | `DEFAULT_CURRENCY` | `VND` | Có | UC-01 default |
| Knowledge upload | `ALLOWED_UPLOAD_TYPES` | `text/markdown` | Có | Chỉ Knowledge Base; PDF bị từ chối trong v0.1 |
| Knowledge upload | `MAX_UPLOAD_MB` | `2` | Có | Chỉ Markdown knowledge document, không áp dụng Ticket message |
| Logging | `LOG_LEVEL` | `INFO` | Có | Không log secrets/raw authorization |
| Logging | `LOG_FORMAT` | `json` | Có | Basic observability |
| Security | `REQUEST_RATE_LIMIT_PER_MINUTE` | `60` | Có | API baseline |
| Email | `EMAIL_BACKEND` | `draft_only` | Có | Không gửi customer email trong v0.1 |
| Test | `LLM_PROVIDER` | `fake` | Test | Deterministic fixtures; không gọi Gemini |
| Test | `EMBEDDING_PROVIDER` | `fake` | Unit/API tests | Retrieval integration/calibration vẫn chạy exact E5 revision |

`EMBEDDING_API_KEY`, refresh-token variables, PII encryption keys, SMTP/OTEL/Redis variables không thuộc v0.1. Không có `TICKET_ATTACHMENTS_ENABLED` hoặc ticket-upload env: attachment bị cố định disable theo API contract v0.1. Owner/admin credentials chỉ tồn tại trong one-shot bootstrap/migration environments; runtime services không được nhận chúng. `INTERNAL_SERVICE_TOKEN` chỉ được đọc bởi SupportPilot HTTP adapter và Mock-Commerce auth middleware; config repr/diagnostics phải redact giá trị.

Trong local Compose, `POSTGRES_BOOTSTRAP_DATABASE_URL` được dựng từ cùng `POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB`; bốn owner/runtime DSN được dựng từ đúng role password secret tương ứng. Không duy trì hai giá trị password độc lập cho cùng một role.

## 15. Testing strategy

| Lớp | Phạm vi |
|---|---|
| Unit | UC-01 scoring, payment rules, state transitions, redaction, idempotency và deadline calculation |
| Repository | Role/grant/migration isolation, physical constraints/indexes, immutable rows, partial active-run/transaction-ref uniqueness, optimistic versions và pgvector/FTS trên PostgreSQL thật |
| API integration | Auth/RBAC, attachment rejection, explicit ticket→run trigger, message resume, synchronous reindex, approval expiry, 409/422/504 envelopes |
| Tool contract | UC-01 HTTP schemas, exact internal Bearer auth, customer ownership, timeout/retry, audit và permission tiers |
| LangGraph node | Input/output state, structured-output failure và conditional routes |
| Agent workflow | Pause/same-run resume, clarification, 60-second timeout, provider failure và stale approval |
| RAG retrieval | E5 prefix/token budget, vector/FTS candidates, RRF dedupe/ranking, calibrated evidence gates, version/effective-date filter, conflicts và no-answer |
| Approval/action | Double decision, 24-hour expiry, material edit/reapproval, `UNKNOWN`, verification và reject path |
| Security | Cross-schema/cross-customer access, public/internal credential separation, token non-disclosure, prompt injection, attachment/MIME rejection, rate limit và log redaction |
| E2E | Browser/API UC-01 từ explicit Ticket/run đến verified action và timeline |
| Regression evaluation | Versioned 25-case golden dataset, threshold sweep và calibrated release artifact |
| Failure injection | HTTP timeout/5xx, LLM malformed/slow output, possible write, embedding/model revision change |

### 15.1 Mocking

- LLM: deterministic fake trả fixture theo ticket ID; có fixture malformed/timeout.
- Embedding: deterministic hash/vector fixture.
- Payment/Order: Mock-Commerce HTTP API, không import/mock commerce repository tại SupportPilot E2E.
- Email: `draft_only` adapter.
- Time: injectable wall clock cho expiry/recency và monotonic clock cho workflow deadline.

### 15.2 Automated test allocation v0.1

Milestone v0.1 yêu cầu tối thiểu 20 automated tests quan trọng. Target baseline ban đầu là 20 test dưới đây; coding agent phải bổ sung test khi phát hiện regression, concurrency issue, security issue hoặc edge case. Không có giới hạn tối đa cứng cho automated tests.

- 3 database role/plaintext/state tests.
- 3 ticket/agent-run/message-resume API tests.
- 3 Order Resolution và HTTP-boundary tests.
- 3 embedding/RAG/provenance/calibration tests.
- 3 agent timeout/approval-expiry/edit tests.
- 2 action idempotency/unknown/verification tests.
- 2 security/injection/redaction tests.
- 1 browser UC-01 happy path.

Các RAG tests bắt buộc, có thể nằm trong baseline hoặc bổ sung ngoài baseline:

- Chunk xuất hiện đồng thời ở vector và FTS chỉ còn một citation, RRF nhận đủ hai rank contribution.
- Vector score cao nhưng sai policy version bị metadata filter loại.
- FTS exact match nhưng policy expired không bypass filter.
- Lexical-only match dưới lexical threshold trả no-answer/escalation.
- Vector-only match vượt calibrated vector threshold có thể làm evidence.
- Hai active policies conflict được trả cùng citations và escalate.
- Không có candidate vượt confidence gate trả no-answer/escalation.

Các contract/invariant tests bắt buộc khác, có thể nằm trong baseline hoặc bổ sung ngoài baseline:

- `attachment_references` omitted và `[]` tạo message/resume bình thường; non-empty trả đúng `422 ATTACHMENTS_NOT_SUPPORTED`, không insert message, không fetch/store và không resume run.
- Reindex thành công trả synchronous `200` với đầy đủ provenance/count/status; `DRAFT/VALIDATED` không tự publish; `PUBLISHED` active index chỉ swap sau complete; injected failure giữ pointer cũ.
- Reindex replay cùng key trả persisted result, không tạo index/chunks lần hai; config mismatch/validation/execution failure trả đúng code/retryable và config change reset calibration.
- Internal API: missing header → 401; wrong token → 403; user JWT → 403; internal token bị public auth từ chối; token không xuất hiện trong log/audit/tool summaries.
- Phase 1 migration test chứng minh chỉ roles/schemas/Alembic infrastructure tồn tại và không có domain table; `SKEL-001` test chứng minh chỉ minimal final-named support tables/enums/indexes được tạo.
- Workflow repository tests chứng minh one-nonterminal-run, event sequence uniqueness/append-only grants, immutable proposal version/hash, expected-version concurrency, `UNKNOWN` không resolve và Ticket `RESOLVED` chỉ sau `VERIFIED`.
- Commerce repository tests chứng minh customer-scoped composite FK, partial unique transaction ref, `NUMERIC(18,2)`/uppercase currency, stale expected version bị chặn, successful sync tăng version đúng một và idempotency/audit ghi cùng transaction.

### 15.3 Golden evaluation v0.1

Target cố định ban đầu là 25 cases, chia trước khi chạy evaluation:

| Subset | Số case | Mục đích và quy tắc |
|---|---:|---|
| Calibration | 15 | Có retrieval ground truth; dùng để sweep/chọn vector và lexical thresholds. Có relevant, irrelevant, expired/version-conflict và no-answer cases. |
| Holdout | 10 | Khóa riêng trước calibration; chỉ đánh giá final quality sau khi threshold đã chốt. Không dùng tune threshold/RRF/prompt. |

Calibration subset mặc định: 5 relevant payment-policy, 4 vector/lexical branch variants, 3 expired/wrong-version/conflict và 3 irrelevant/no-answer cases.

Holdout subset mặc định: 3 order-resolution/payment-policy cases, 2 policy version/no-answer cases, 2 approval/action cases và 3 timeout/malformed-output/prompt-injection/provider-failure cases. Holdout cases không được trùng semantic fixture với calibration cases.

### 15.4 Calibration và holdout acceptance criteria

- Golden dataset và từng subset có version/checksum; split manifest được commit trước threshold selection.
- Calibration report ghi exact E5 model/revision/input-format/index version, dataset/subset checksum, relevant/irrelevant score distributions, vector/lexical threshold sweep và threshold cuối cùng.
- Sweep nhiều threshold; không chỉ thử `0.72`.
- Threshold cuối được ghi vào release environment; `RAG_THRESHOLD_CALIBRATED=true` chỉ sau calibration pass.
- Sau khi khóa threshold, chạy holdout đúng một final evaluation pass; không tune lại trên holdout. Nếu fail và cần thay đổi, tạo dataset/evaluation version mới và thực hiện lại split/calibration.
- Release report tách riêng calibration metrics và holdout metrics; cả hai ghi Recall@5, no-answer precision và false-positive policy evidence count.
- Release report ghi dataset version/checksum, exact embedding model/revision/input format, RRF parameter và vector/lexical thresholds đã chọn.
- Thay embedding model/revision/dimension/input format, retrieval scoring hoặc dataset version làm calibration status quay lại `false`.

## 16. Docker Compose proposal

| Container | Port/volume/health/dependency |
|---|---|
| `postgres` | `5432`; named volume; `pg_isready`; cài pgvector |
| `db-bootstrap` | One-shot; chờ PostgreSQL healthy; dùng admin DSN chạy `DB-000`, tạo hai owner/two app roles, schemas, grants/default privileges; idempotent rồi exit |
| `migrate-support` | One-shot backend image; chỉ nhận `support_owner` DSN; migrate schema `support` |
| `migrate-commerce` | One-shot Mock-Commerce image; chỉ nhận `commerce_owner` DSN; migrate schema `commerce` |
| `seed` | One-shot profile `payment-mismatch-v01`; chờ cả hai migration; synthetic fixed IDs/checksums; idempotent |
| `mock-commerce` | `8080`; chỉ nhận `commerce_app` + `INTERNAL_SERVICE_TOKEN`; chờ commerce migration/seed; `/health` không trả secret |
| `backend` | `8000`; chỉ nhận `support_app` + `INTERNAL_SERVICE_TOKEN`; chờ support migration và Mock-Commerce healthy; `/health/live`, `/health/ready` không trả secret |
| `frontend` | `5173` dev; chờ backend ready; production build phục vụ static |
| `local-llm` | Optional alternative-provider profile; không thuộc acceptance criteria v0.1 |

- Một private Compose network; chỉ frontend/backend expose ra host. Mock-Commerce chỉ cần backend truy cập nội bộ.
- Startup: PostgreSQL → DB bootstrap → hai migrations → seed → Mock-Commerce → backend → frontend.
- Bootstrap/admin credential chỉ vào `postgres`/`db-bootstrap`; owner credentials chỉ vào migration tương ứng; runtime credential không được dùng migrate.
- `INTERNAL_SERVICE_TOKEN` chỉ vào `backend` và `mock-commerce`; không vào frontend, PostgreSQL, bootstrap, migrations, seed, LLM hoặc embedding process config.
- Hai migration không chạy từ backend replicas và không chia sẻ owner credential.
- Seed dùng fixed IDs/checksums và có thể chạy lại an toàn.
- Health check kiểm tra support migration version, Mock-Commerce connectivity và expected embedding revision/index state.
- Không mount secret file vào image; local dùng ignored `.env`.
- Không Redis, queue, Mailpit, OTEL collector hoặc PDF worker trong default v0.1 stack.

## 17. Observability and audit

v0.1 chỉ yêu cầu basic structured logging, persisted run events và audit trail. Distributed tracing, OTEL collector, production dashboards/alerts và advanced metrics thuộc v1.0.

### 17.1 Phân loại dữ liệu

- Technical logs: request, status, latency, retry, stack trace đã redact; có retention ngắn.
- Audit logs: actor, action, target, decision, before/after hashes, result; append-only và retention dài hơn.
- Conversation data: ticket messages; ticket attachments chỉ bắt đầu từ v1.0. Không trộn message content vào technical logs.
- Agent evidence: exact API reference và policy chunk IDs; không lưu CoT.

### 17.2 Trường bắt buộc

- Correlation ID xuyên ticket → run → node → tool → approval → action.
- Node/tool latency và attempt.
- LLM provider/model, token input/output, estimated cost.
- RAG query filters, vector/lexical branch ranks/scores, RRF score, evidence-gate result và chunk IDs.
- Approval proposal hash, required role, approver, edit và reason.
- Final action, idempotency key và verification state.
- Error code, retryability và escalation.
- PII redaction indicator.
- Workflow deadline, remaining budget tại timeout và `agent_run.timeout` event.
- Embedding provider/model/revision/input-format/index version và calibration/holdout artifact versions.
- Checkpoint/run reconciliation result và `agent_run.checkpoint_invariant_failed` event khi có.

### 17.3 v0.1 quality signals

- JSON logs có timestamp UTC, level, event, correlation ID, run/ticket ID đã scope và latency.
- Audit có proposal hash/version, approval expiry/edit/decision, action idempotency và verification result.
- Automated/evaluation report ghi agent success/escalation, timeout, RAG no-answer/wrong-version và approval outcome counts.
- Unauthorized action, cross-schema read và duplicate action phải bằng 0 trong test suite.
- Không yêu cầu production metrics backend, distributed traces hoặc dashboard trong v0.1.

## 18. Security

- JWT access token, Argon2 password hashing và login throttling. Refresh-token rotation thuộc v1.0; v0.1 yêu cầu login lại khi access token hết hạn.
- RBAC tại API và service layer, không chỉ ẩn nút frontend.
- Customer scope backend-injected cho mọi commerce tool.
- `/internal/v1/*` bắt buộc exact Bearer `INTERNAL_SERVICE_TOKEN`; missing/malformed trả `401 INTERNAL_UNAUTHENTICATED`, wrong/user JWT trả `403 INTERNAL_FORBIDDEN` trước khi validate customer/business input. Internal token bị từ chối trên public API.
- Không nhận internal token qua query/body; không log/audit/tool-output/LLM/frontend expose token. HTTP adapter tự inject từ secret config, không cho model cung cấp credential.
- Ownership check trước khi đọc order/payment/shipment.
- Database grants chặn `support_app` đọc `commerce` và `commerce_app` đọc `support`; grant tests là release gate.
- Import-boundary CI chặn `support_api`/`mock_commerce_api` import chéo models, repositories, services hoặc DB sessions; chỉ versioned HTTP contracts được chia sẻ.
- Treat ticket và policy text là untrusted content; non-empty ticket attachment references bị từ chối trước persistence/resume trong v0.1.
- Tool allowlist và schema validation; LLM không chọn URL/customer ID/approval actor.
- Proposal snapshot/hash và revalidation chống stale approval.
- Idempotency, unique constraints và row lock chống duplicate action.
- `email`, `phone`, `subject`, `content` là plaintext synthetic local/demo trong v0.1; không được dùng dữ liệu khách thật. Complete field-level encryption và lookup hashes thuộc migration v1.0.
- Không lưu PAN, CVV, token hay raw provider secret.
- Structured redaction trước logging/LLM input.
- Knowledge upload/ingestion chỉ chấp nhận UTF-8 `text/markdown`, tối đa 2 MB, checksum và metadata validation; PDF và MIME khác bị từ chối. Quy tắc này không tạo ticket-upload capability.
- Parameterized SQL qua SQLAlchemy; không expose raw query.
- Rate limit login, ticket creation, agent runs và search endpoints.
- Refund threshold và manager role; detect repeated claims/refunds.
- Secret chỉ qua environment/secret store; không commit.
- Bootstrap/admin/owner credentials không được inject vào runtime services; runtime roles không có schema/role creation privilege.
- Audit admin access và role changes.
- CSRF không áp dụng Bearer header thuần; nếu dùng cookie refresh thì bắt buộc SameSite/CSRF token.

## 19. Assumptions

- Một tenant demo và dữ liệu hoàn toàn giả lập.
- Web session đã đăng nhập là identity source của vertical slice.
- Support Agent là reviewer cho `sync_payment_status`.
- Currency mặc định VND.
- Payment provider trả transaction reference, status, amount, currency và paid time nhưng không trả card data.
- Policy seed của vertical slice là Markdown và có version/effective date rõ.
- Vue gọi create-ticket rồi explicit create-run; mỗi synchronous advance chạy đến interruption/terminal state trong tối đa 60 giây.
- v0.1 không gọi LLM classification riêng; ưu tiên tối đa một extraction call và một grounded proposal/response call khi cần, mỗi attempt tối đa 12 giây. Approval/message resume nhận budget 60 giây mới.
- LangGraph checkpoint trong PostgreSQL là source of truth cho same-run resume với `thread_id=agent_run.id`; không background queue trong v0.1.
- Exact vector search đủ cho corpus MVP.
- UI dùng polling; realtime broker/SSE chưa cần cho v0.1.
- English support là khả năng tương thích, không phải bộ UI song ngữ hoàn chỉnh.
- `0.72` chỉ là development placeholder; calibration report là release gate nhưng không ngăn xây vertical slice.
- Approval TTL là 24 giờ tuyệt đối UTC và được phát hiện lazy vì không có worker.
- Plaintext v0.1 chỉ chứa synthetic data; field encryption, refresh rotation, PDF và advanced observability thuộc v1.0.
- Mọi quyết định tại mục 20 đã được review và có hiệu lực làm default triển khai.

## 20. Technical decisions requiring review

Tất cả quyết định dưới đây đã được duyệt; không còn decision blocker trước khi triển khai v0.1.

| Quyết định | Default đã duyệt | Lý do/trade-off và ảnh hưởng khi đổi |
|---|---|---|
| LLM provider | Gemini API qua adapter; `GEMINI_MODEL` từ env | OpenAI/Ollama là alternative. Đổi provider phải chạy lại prompts/evaluation nhưng không đổi graph contract. |
| LLM timeout | 12 giây/attempt, tối đa 2 attempts tính cả initial; workflow 60 giây và finalization reserve 5 giây | v0.1 bỏ classification call và ưu tiên tối đa hai initial calls trước approval (extraction + grounded proposal khi cần), tối đa 24 giây nếu không retry. Retry chỉ bắt đầu khi còn ≥17 giây. |
| Embedding | Local `intfloat/multilingual-e5-small`, revision cố định, normalized, dimension 384, input format `e5-prefix-v1` | Query dùng `query:`; policy dùng `passage:` + title/heading/content. Đổi model/revision/dimension/input format bắt buộc reindex và recalibrate. |
| Vector/lexical search | Metadata-first pgvector exact top10 + PostgreSQL FTS top10; RRF k=60; top5 sau calibrated evidence gates | RRF chỉ ranking, không confidence. Qdrant/BM25/reranker chỉ khi evaluation chứng minh cần. |
| RAG confidence gates | Vector cosine `0.72` chỉ là development placeholder; lexical gate chưa có default có ý nghĩa | Release phải sweep lại cả vector/lexical gate từ đầu trên 15-case calibration split, rồi đánh giá đúng một lần trên 10-case locked holdout; CI yêu cầu calibrated artifact khớp model/revision/input format/RRF config. |
| Redis/queue | Không dùng trong v0.1 | Explicit synchronous Agent Run đơn giản và reviewable; durable queue để sau v1.0 khi có nhu cầu. |
| Walking Skeleton | `SKEL-001` sau foundation, dùng fake adapters sau final public interfaces và minimal forward-compatible Ticket persistence | Cho demo sớm; release CI cấm `WORKFLOW_PROFILE=walking_skeleton`. |
| LangGraph profile | v0.1 graph riêng cho payment mismatch; full node catalog là target v1.0 | Không LLM classification call; merged nodes vẫn persist action/events và giữ deterministic business rules. |
| Workflow persistence ownership | Checkpoint resume; `agent_runs` run status; `agent_run_events` timeline; `audit_logs` audit | Không reconstruct graph từ events/audit; startup/recovery invariant failure phải escalate/audit. |
| Agent trigger | Vue gọi `POST /tickets`, rồi `POST /tickets/{id}/agent-runs` | Tránh side effect ẩn trong create-ticket và làm idempotency/timeout contract rõ ràng. |
| Ticket attachment v0.1 | Giữ request field nhưng chỉ chấp nhận omitted/`[]`; non-empty trả `422 ATTACHMENTS_NOT_SUPPORTED` trước mọi side effect | Bảo toàn forward compatibility mà không tạo attachment storage/upload/security surface trước v1.0. |
| Active Agent Run | Một non-terminal run/ticket; cùng key replay, key khác trả `409 AGENT_RUN_ALREADY_ACTIVE` | Không trả run hiện có cho trigger khác vì sẽ che duplicate intent. |
| Agent cancellation | Không có `CANCELLED` hoặc cancel endpoint trong v0.1 | Không có queue/operator cancel trigger; timeout dùng `FAILED`, manual handling dùng `ESCALATED`. |
| Message resume | `POST /messages` tự resume chính run cũ đồng bộ khi Ticket/run đều `WAITING_CUSTOMER` | Không tạo run mới ngầm; message vẫn được lưu nếu resume timeout/invariant fail. |
| Mock API/database boundary | Một Mock-Commerce runtime; schema/owner/runtime role tách khỏi SupportPilot | SupportPilot chỉ gọi HTTP, không direct commerce read/cross-schema FK. |
| Internal service auth | Một exact Bearer `INTERNAL_SERVICE_TOKEN` cho `/internal/v1/*`; user JWT/internal token không dùng chéo | Adapter inject secret ngoài LLM; auth chạy trước ownership/body validation; token không vào logs/audit/tool/frontend. Rotation/mTLS để sau v0.1. |
| DB bootstrap | One-shot admin DSN cho `DB-000`; owner/runtime credentials riêng | Reproducible local startup và least privilege; bootstrap DSN không tới migrations/runtime. |
| Migration ownership | Phase 1 chỉ bootstrap + Alembic infrastructure/optional empty baseline; `SKEL-001` Phase 2 tạo minimal final-named domain migration | Loại bỏ ownership chồng lấn và giữ đường migration forward-only cho DB-001A/B/C/002A. |
| Physical DB contract | UUID/TIMESTAMPTZ, named enums, NUMERIC(18,2), CHAR(3), explicit FK RESTRICT/index/idempotency/version/append-only rules tại §7 | Coding agent không tự thêm field/table hoặc chọn delete/concurrency semantics; không transition trigger. |
| PII v0.1 | Plaintext columns tên trung lập, chỉ synthetic local/demo | Không giả encryption. v1.0 add/backfill/switch/drop qua nhiều migration. |
| Auth | Local JWT access token; login lại khi hết hạn | Refresh-token rotation và SSO để v1.0/Post-MVP. |
| Approval | Mọi UC-01 business write cần approval; TTL 24 giờ UTC, lazy expiry | Không business calendar/worker trong v0.1. Expired approval không revive. |
| Approval rollout | Alpha: approve/reject/expiry/verify; beta/final: reviewer edit/version/TTL reset/reapproval | `APR-002` không chặn skeleton/alpha happy path nhưng vẫn chặn final release DoD. |
| Proposal edit | Revalidate schema/HTTP ownership/business rules; immutable version/hash mới; material edit bắt buộc reapproval và reset TTL | Target, amount, currency hoặc action type là material. Non-material same-request approval giữ TTL cũ. |
| Ticket status update | Internal deterministic transition, không approval riêng, LLM không gọi trực tiếp | Ticket chỉ `RESOLVED` sau approved business action đã `VERIFIED`. |
| Document formats | Chỉ Markdown trong v0.1 | PDF/complete upload security surface để v1.0; DOCX/OCR Post-MVP. |
| Knowledge reindex | Synchronous `200`, persisted idempotent result, atomic active-index swap; failure giữ index cũ; không auto-publish | Không queue/202/polling trong v0.1. Mọi embedding/retrieval provenance change reset calibration. |
| UI updates | Polling | SSE/WebSocket chưa cần trong v0.1. |
| Scope | v0.1 UC-01; v1.0 UC-01–UC-05; Post-MVP UC-06–UC-07 | Ngăn backlog v0.1 mở rộng ngoài vertical slice. |
| Cloud/repository | Local Compose; `backend/apps/support_api`, `backend/apps/mock_commerce_api`, shared `packages/commerce_contracts`, plus frontend/docs/infrastructure/tests/scripts | Import-boundary CI chặn shared DB model/repository/session; cloud deployment chọn sau v1.0. |

## 21. Phase roadmap

| Phase | Kết quả kiểm chứng được | Phụ thuộc |
|---|---|---|
| Phase 0 — Design and contracts | PLAN, API/state/schema/adapter contracts, E5 input format, deterministic RRF và checkpoint ownership được review | Không |
| Phase 1 — Foundation | FastAPI/Vue/Compose, PostgreSQL roles/schemas/grants, hai Alembic config/command/directory và optional empty baselines; tuyệt đối chưa có domain table | Phase 0 |
| Phase 2 — Walking Skeleton | `SKEL-001` sở hữu minimal forward-compatible final-named support domain migration và demo login → create Ticket → fake proposal → approve/reject → Ticket result | Phase 1 |
| Phase 3 — Core database, auth and Ticket APIs | Complete DB-001A, access-token RBAC, production Ticket/message repository/API thay skeleton fakes | Phase 2 |
| Phase 4 — Mock-Commerce and Order Resolution | Commerce schema/seed, Order/Payment HTTP APIs và deterministic Order Resolution | Phase 3 |
| Phase 5 — Knowledge Base and RAG | DB-001C, Markdown ingestion, exact E5 prefix contract, vector+FTS+RRF, provenance và evaluation dataset split | Phase 4 |
| Phase 6 — LangGraph Agent | DB-001B1/B2/B3 physical workflow/checkpoint/approval/audit persistence, v0.1 graph profile, explicit run, deadline và same-run resume | Phase 5 |
| Phase 7 — Approval and verified action | v0.1-alpha approve/reject/expiry/verify trước; v0.1-beta/final reviewer edit/reapproval; payment sync và `UNKNOWN` reconciliation | Phase 6 |
| Phase 8 — Full Vue review flow | Thay skeleton UI adapters bằng full evidence/citation/timeline/approval/edit/error flow | Phase 7 |
| Phase 9 — Security, evaluation, CI and release | Tối thiểu 20 tests, 15-case calibration + 10-case holdout, import/grant/security gates, clean Compose demo | Phase 8 |
| Release v0.1 | Chỉ release khi full v0.1 profile, edit/reapproval DoD, calibrated thresholds và mọi gate §3/§24 pass | Phase 9 |
| MVP v1.0 | Encryption migration, refresh rotation, PDF, advanced observability và UC-02–UC-05 | Stable v0.1 |
| Post-MVP | UC-06–UC-07, real connectors, queue/scale khi cần | MVP v1.0 |

## 22. Detailed task backlog

Mỗi task dưới đây phải hoàn thành và review độc lập trong một coding session, không tự thay đổi contract/business rule. Size `S/M`; không còn task `L` trong v0.1.

### Phase 0 — Design and contracts

| ID / size | Mục tiêu/phạm vi; ngoài task | Modules dự kiến | Input → output; Done/AC | Phụ thuộc; test/lệnh; rủi ro |
|---|---|---|---|---|
| `DOC-001`, S | Đồng bộ các spec/ADR từ PLAN đã duyệt; không code | `docs/*` | PLAN → docs không mâu thuẫn về scope/provider/schema/state/API | None; markdown/link review; risk: rule drift |

### Phase 1 — Foundation

| ID / size | Mục tiêu/phạm vi; ngoài task | Modules dự kiến | Input → output; Done/AC | Phụ thuộc; test/lệnh; rủi ro |
|---|---|---|---|---|
| `FND-001`, M | FastAPI config/error/DI/quality shell; không domain | backend core/API health | Env contract → app fail-fast khi thiếu required config | DOC-001; lint/type/unit; risk: config secret leak |
| `FND-002`, M | Vue/Vite/TS/Router/Pinia/typed HTTP shell; không ticket UI | frontend core | API types → build/typecheck pass | DOC-001; frontend build/typecheck; risk: contract drift |
| `DB-000`, S | Idempotent bootstrap hai owners/two app roles, schemas, grants/default privileges; không Alembic/domain enum/table/seed | bootstrap script/Compose job | Admin DSN + 4 role secrets → empty least-privilege schemas. AC: runtime role bị chặn schema còn lại; catalog không có domain table | FND-001/PostgreSQL; grant/catalog integration tests; risk: bootstrap credential exposure |
| `INF-001`, M | Compose startup; hai Alembic config/commands/versions dirs + optional empty baselines; không domain migration/cloud/Redis | infrastructure + migration shells | Images/env → healthy ordered stack và owner-isolated migration commands. AC: owner/admin DSN không ở runtime; Phase-1 migration heads không tạo domain enum/table | DB-000/FND-001/FND-002; `docker compose config`, Alembic head/catalog smoke; risk: env/search-path drift |

### Phase 2 — Walking Skeleton

| ID / size | Mục tiêu/phạm vi; ngoài task | Modules dự kiến | Input → output; Done/AC | Phụ thuộc; test/lệnh; rủi ro |
|---|---|---|---|---|
| `SKEL-001`, M | Sở hữu migration domain đầu tiên và demo tối thiểu Vue login → persist Ticket → fixed fake proposal → fake approve/reject → Ticket result. Không Gemini/embedding/RAG/full LangGraph/real commerce/write-schema | `support_api` adapters + support migration; Vue skeleton views | Empty Phase-1 schema → chỉ final-named `users/customers/support_tickets/ticket_messages` + enum/index tối thiểu trên PostgreSQL, rồi runnable demo bằng final public response/state names. AC: không SQLite/in-memory/temp/full workflow/RAG/commerce table; Ticket thật persist; approve→fake `VERIFIED`→`RESOLVED`, reject→`ESCALATED`; Playwright pass; release không dùng fake | FND-001/FND-002/DB-000/INF-001; migration catalog/API/browser smoke; risk: fake leakage/throwaway schema |

`SKEL-001` chỉ tạo minimal final-named Ticket/message columns cần persist demo. `DB-001A` mở rộng forward-only, backfill synthetic fixture rồi thêm final FK/NOT NULL/index; không tạo bảng tạm hoặc drop/recreate skeleton data.

### Phase 3 — Core database, auth and Ticket APIs

| ID / size | Mục tiêu/phạm vi; ngoài task | Modules dự kiến | Input → output; Done/AC | Phụ thuộc; test/lệnh; rủi ro |
|---|---|---|---|---|
| `DB-001A`, M | Hoàn thiện plaintext `users/customers/support_tickets/ticket_messages` từ minimal skeleton migration; không cipher/hash/address/attachment | `support_api` models/migration/repos | §7.2 → forward migration/rollback-safe path. AC: constraints/indexes, skeleton fixture backfill và synthetic-only note | SKEL-001/DB-000/INF-001; repository tests/Alembic; risk: migration from skeleton |
| `AUTH-001`, M | Thay demo auth bằng access-token JWT/RBAC/demo accounts; không refresh rotation/OAuth | `support_api` auth API/service/repos | Credentials → scoped principal; disabled/cross-role blocked | DB-001A/SKEL-001; auth/security tests |
| `TKT-001`, M | Thay skeleton repository/service bằng full create/list/detail và message dual contract; không agent-node/attachment logic | `support_api` Ticket API/service/repos | Ticket/message → `201` message-only hoặc `200` same-run resume. AC: omitted/empty attachments hợp lệ; non-empty → 422 không write/resume; ownership, idempotency, invariant-fail/timeout; skeleton types không đổi | AUTH-001/DB-001A/SKEL-001; API integration tests; risk: transaction vs resume boundary |

### Phase 4 — Mock-Commerce and Order Resolution

| ID / size | Mục tiêu/phạm vi; ngoài task | Modules dự kiến | Input → output; Done/AC | Phụ thuộc; test/lệnh; rủi ro |
|---|---|---|---|---|
| `DB-002A`, M | Exact physical `customers/products/orders/order_items/payments/idempotency_records/audit_logs` theo §7.5; không shipping/refund/warranty | `mock_commerce_api` models/migration | Empty commerce schema → UC-01 schema với money/currency/status/customer scope/partial txn unique/expected version/append-only grants. AC: sync transaction tăng version đúng một và ghi idempotency+audit atomically | DB-000/INF-001/SKEL-001; PostgreSQL migration/constraint/transaction tests; risk: cross-schema leakage |
| `SEED-001`, S | `payment-mismatch-v01` synthetic users/orders/payments/Markdown policy/ambiguity fixtures; không real data | seed scripts/fixtures | Fixed profile → repeatable IDs/checksums; run twice không duplicate | DB-001A/DB-002A; seed smoke; risk: insufficient edge cases |
| `MOCK-AUTH-001`, S | Exact Bearer auth middleware cho `/internal/v1/*`; không rotation/mTLS/multi-token | Mock core/auth + Support adapter contract | `INTERNAL_SERVICE_TOKEN` → auth trước body/ownership. AC: missing 401, wrong/user JWT 403, token redacted; public auth từ chối internal token | FND-001/INF-001; auth/log tests; risk: credential leakage |
| `MOCK-ORD-001`, M | Customer-scoped order search/detail và sync contract; không support imports | Mock Order API | Authenticated HTTP filters/write → candidates/detail/versioned sync; other customer/stale version blocked | DB-002A/SEED-001/MOCK-AUTH-001; contract/transaction tests |
| `MOCK-PAY-001`, S | Recent payments/status/order link; không investigation/refund | Mock Payment API | Authenticated customer/order filters → redacted payment | DB-002A/SEED-001/MOCK-AUTH-001; contract tests |
| `RES-001`, M | UC-01 candidate generation/scoring/safe clarification; không RAG | resolution service + HTTP ports | Entities/customer → resolved order/clarification; score explainable và isolated | MOCK-ORD-001/MOCK-PAY-001; unit/integration tests |

### Phase 5 — Knowledge Base and RAG

| ID / size | Mục tiêu/phạm vi; ngoài task | Modules dự kiến | Input → output; Done/AC | Phụ thuộc; test/lệnh; rủi ro |
|---|---|---|---|---|
| `DB-001C`, M | Exact physical knowledge documents/index versions/chunks `vector(384)`, active pointer và provenance | `support_api` KB migration | E5 contract → atomic/reindexable schema. AC: completed-only pointer, immutable chunks/index provenance, failure preserves active version | DB-000/INF-001/SKEL-001; pgvector/repository/transaction tests; risk: circular/composite FK order |
| `KB-001`, M | Markdown-only validation, tokenizer-aware E5 prefix/chunk budget, embedding, publish/version; không PDF/OCR | `support_api` KB/RAG ingestion | Markdown → chunks within model context with exact provenance | DB-001C/SEED-001; parser/tokenizer/security tests |
| `KB-002`, M | Synchronous idempotent reindex endpoint/atomic swap; không queue/202/polling/auto-publish | `support_api` KB API/service/repos | Admin request → exact §8.3.5 `200` hoặc typed error. AC: `DRAFT/VALIDATED` giữ nguyên; `PUBLISHED` old index active đến complete; failure/replay/config-reset semantics pass | KB-001/DB-001C/AUTH-001; API/failure/idempotency tests |
| `RAG-001`, M | Metadata-first vector+FTS top10, deterministic RRF k=60, dedupe, vector/lexical evidence gates, top5 citations/conflict; không reranker | retrieval/embedding adapter | Query → gated citations/no-answer plus branch scores/provenance. AC: bảy required RAG cases §15.2 pass | KB-001; retrieval tests; risk: uncalibrated thresholds |
| `TOOL-001`, M | UC-01 allowlist, schemas, internal-token-injecting HTTP adapter, permission, deadline/retry/audit wrapper; không write tool | `support_api` tool registry/HTTP adapters | Tool call → validated result/tool record; credential không là tool arg/output; arbitrary tool/import boundary impossible | MOCK-AUTH-001/MOCK-ORD-001/MOCK-PAY-001/RAG-001; contract/failure/import/redaction tests |

### Phase 6 — LangGraph Agent

| ID / size | Mục tiêu/phạm vi; ngoài task | Modules dự kiến | Input → output; Done/AC | Phụ thuộc; test/lệnh; rủi ro |
|---|---|---|---|---|
| `DB-001B1`, M | Checkpointer integration + exact `agent_runs/agent_run_events/agent_evidence/tool_calls`; không approval/action/audit tables | workflow migration/repos | §7.3 → run persistence. AC: one non-terminal partial index, event sequence/append-only, tool/evidence checks, no checkpoint copy/CoT, reconciliation repository tests | DB-001A/DB-001C; PostgreSQL migration/concurrency/grant tests; risk: checkpointer transaction semantics |
| `DB-001B2`, M | Exact `approval_requests/approval_proposal_versions/action_executions/notifications`; không agent/event/audit tables | approval/action migration/repos | §7.3 → constrained approval/action persistence. AC: immutable version/hash composite FK, expiry/version locks, `UNKNOWN`, VERIFIED timestamp and no cascade | DB-001B1; PostgreSQL migration/concurrency tests; risk: enum/FK migration order |
| `DB-001B3`, S | Exact append-only `audit_logs` + generic `idempotency_records`; runtime grants/indexes/redacted JSON contract | audit/idempotency migration/repos | §7.3 → durable audit/replay. AC: update/delete denied; same-key/hash replay, mismatched hash conflict; no history FK cascade | DB-001A; PostgreSQL grant/idempotency tests; risk: unsafe response persistence |
| `AG-001`, M | Thay FakeAgent bằng v0.1 graph profile: checkpoint/run reconciliation, explicit run, receive/identity/deterministic UC-01 guard/one-call extraction và 60-second deadline; không commerce action | `support_api` agent state/profile/nodes/API | Ticket → validated payment context hoặc typed failure. AC: no classification LLM call; timeout 504/run `FAILED`/Ticket `ESCALATED`; checkpoint invariant audit; 12s/5s budget | DB-001B1/DB-001B3/TOOL-001/AUTH-001/TKT-001/SKEL-001; node/API/recovery tests; risk: checkpoint/deadline cancellation |
| `AG-002A`, M | Resolve order và collect commerce evidence chỉ qua HTTP tools; không RAG/proposal | agent resolution/evidence nodes | State → order/payment evidence or clarification/escalation. AC: không import commerce repositories | AG-001/RES-001/MOCK-ORD-001/MOCK-PAY-001; graph/import-boundary tests |
| `AG-002B`, M | Retrieve gated RAG evidence, deterministic `evaluate_and_propose` và tối đa một grounded proposal/response call; không approval persistence/execution | agent RAG/policy/proposal nodes | Evidence → cited proposal or conservative escalation | AG-002A/RAG-001; graph tests; risk: LLM overreach |

### Phase 7 — Approval and verified action

| ID / size | Mục tiêu/phạm vi; ngoài task | Modules dự kiến | Input → output; Done/AC | Phụ thuộc; test/lệnh; rủi ro |
|---|---|---|---|---|
| `APR-001`, M | v0.1-alpha approval: approve/reject/24h expiry/role/expected version+hash/concurrency; không reviewer edit | `support_api` approvals/API/repos | Proposal → pending/approved/rejected/expired. AC: double/stale/expired decision safe, audit complete | AG-002B/AUTH-001/DB-001B2/DB-001B3; concurrency/API tests |
| `ACT-001`, M | Revalidate, idempotent payment sync, execution/verification/reconciliation; không refund/other writes | write tool/Mock Order API | Approved action → `VERIFIED` hoặc typed failure. AC: possible write→`UNKNOWN`, no blind retry, same key | APR-001/MOCK-ORD-001/MOCK-PAY-001; transaction/failure tests |
| `AG-003`, M | Approval/message resume, `execute_verify_respond`, event hooks và deterministic Ticket transition; không email send | agent subgraph/orchestrator | Resume → interruption/terminal outcome. AC: fresh 60s budget; message not rollback; checkpoint reconciliation; unverified action never resolves Ticket | ACT-001/APR-001/TKT-001; graph integration tests |
| `APR-002`, S | v0.1-beta/final reviewer edit, immutable version/hash, material/non-material TTL/reapproval; không chặn Walking Skeleton hoặc alpha happy path | approval edit service | Edited action → validated proposal version. AC: target/amount/currency/type reset TTL; non-material giữ TTL; final DoD/E2E phụ thuộc task này | APR-001/ACT-001/TOOL-001; edit matrix tests |

### Phase 8 — Full Vue review flow

| ID / size | Mục tiêu/phạm vi; ngoài task | Modules dự kiến | Input → output; Done/AC | Phụ thuộc; test/lệnh; rủi ro |
|---|---|---|---|---|
| `WEB-001`, M | Thay skeleton demo adapters bằng full login, explicit create-ticket→create-run, inbox/loading/error; không approval UI | Vue views/stores/services | User submit → real Ticket/run visible; skeleton public types giữ nguyên; duplicate/409/504 handled | SKEL-001/FND-002/TKT-001/AG-002B; component tests |
| `WEB-002`, M | Ticket detail, messages, evidence/citation/timeline polling; không approval controls | Vue detail/components | Detail API → safe review UI; no CoT/raw PII | WEB-001/AG-003; UI tests |
| `WEB-003`, M | Full approve/edit/reject, expiry/stale/material reapproval; không bulk approval | Vue approval components | Proposal → decision/result; impact/evidence shown before action | WEB-002/APR-001/APR-002/ACT-001; UI/API tests |

### Phase 9 — Security, evaluation, CI and release

| ID / size | Mục tiêu/phạm vi; ngoài task | Modules dự kiến | Input → output; Done/AC | Phụ thuộc; test/lệnh; rủi ro |
|---|---|---|---|---|
| `E2E-001A`, S | Explicit create-ticket→create-run happy/timeout contracts; không approval/action | API/browser E2E | Seed → `WAITING_APPROVAL` or 504 with persisted states | WEB-001/AG-001/AG-002B; Playwright/API Compose test |
| `E2E-001B`, S | Approval expiry, material edit/reapproval, `UNKNOWN`/verification; không message resume | API E2E | Pending proposal → safe terminal result | WEB-003/APR-002/ACT-001/AG-003; failure-injection test |
| `E2E-001C`, S | Customer message tự resume same run từ `WAITING_CUSTOMER`; không new run | API/browser E2E | Clarification → same run continues; timeout/invariant paths verified | WEB-002/AG-003/TKT-001; E2E test |
| `E2E-001D`, S | Ticket attachment compatibility contract; không upload/storage | API E2E | omitted/`[]` → normal message path; non-empty → exact 422 và zero message/resume/storage side effect | TKT-001/AG-003; API/PostgreSQL assertions |
| `E2E-001E`, S | Synchronous knowledge reindex contract; không queue/polling | API/repository E2E | Published/draft/failure/replay/config-change fixtures → exact 200/error, atomic pointer và calibration reset | KB-002/RAG-001; failure-injection/PostgreSQL assertions |
| `OBS-001`, S | Basic JSON logs, correlation, checkpoint/run reconciliation events, timeline và redacted audit; không OTEL/dashboard | core/audit | Runtime → reviewable safe events; timeout/expiry/provenance/invariant fields present; service token absent | DB-001B1/DB-001B3/AG-003/APR-002/ACT-001; log/audit tests |
| `SEC-001`, M | Plaintext guard, attachment 422/no-side-effect, cross-schema/customer isolation, public/internal credential separation, import boundaries, prompt injection, knowledge MIME/rate-limit/redaction; không production encryption | security/import-boundary tests | Runtime/dependency graph → security gates pass; five internal-auth tests §15.2 pass | DB-001A/DB-001B1/DB-001B2/DB-001B3/DB-001C/AUTH-001/TKT-001/TOOL-001/MOCK-AUTH-001/MOCK-ORD-001/MOCK-PAY-001/RAG-001; security suite |
| `EVAL-001`, M | Versioned 25-case split: 15 calibration + 10 locked holdout; vector/lexical sweep và separate release metrics; không model training | evaluation scripts/artifacts | Golden set → calibration + holdout reports with checksum/model/revision/input format/thresholds/Recall@5/no-answer precision/false positives | SEED-001/RAG-001/AG-002B; evaluation command; risk: holdout leakage/overfit |
| `CI-001`, M | Lint/type/minimum tests/build/security/import/migration/evaluation gates; không deploy | CI config | Commit → reproducible report; fail Phase-1 domain leakage, walking-skeleton profile, uncalibrated/missing/mismatched artifact hoặc holdout failure | E2E-001A/E2E-001B/E2E-001C/E2E-001D/E2E-001E/OBS-001/SEC-001/EVAL-001; CI dry run; Gemini replaced by fake in CI |
| `DEP-001`, S | Clean-machine local demo packaging/instructions; không cloud/Kubernetes | infrastructure/docs | Release tag → one-command v0.1 demo | CI-001; Compose smoke |

UC-02–UC-05, PDF, encryption migration, refresh rotation và advanced observability chỉ được lập backlog triển khai khi bắt đầu v1.0. UC-06–UC-07 và queue/scale/connectors chỉ lập backlog Post-MVP.

## 23. Vertical slice execution sequence

### 23.1 Implementation order và Walking Skeleton replacement

1. Hoàn thành application shells, PostgreSQL roles/schemas/grants, hai Alembic config/commands/directories và optional empty baselines; catalog vẫn chưa có domain table.
2. `SKEL-001` tạo domain migration đầu tiên chỉ với minimal final-named support identity/Ticket/message tables, rồi thêm demo login, final public Ticket/run/approval response types và fake adapters.
3. Chạy Walking Skeleton: Vue → FastAPI → PostgreSQL → fixed proposal → fake approve/reject → Ticket result.
4. `DB-001A`, `AUTH-001`, `TKT-001` mở rộng schema và thay demo auth/Ticket implementation sau cùng interfaces; không đổi frontend contract.
5. Thêm exact internal Bearer auth, Mock-Commerce HTTP/commerce physical schema và Order Resolution, rồi thay fake evidence source.
6. Thêm Markdown/E5/RRF RAG, synchronous atomic reindex và thay fixed policy/proposal evidence.
7. Thêm checkpoint-backed LangGraph v0.1 profile và thay `FakeAgentAdapter`.
8. Triển khai v0.1-alpha approval/action (approve/reject/expiry/verify) để có real happy path; `APR-002` chưa chặn bước này.
9. Triển khai `APR-002` reviewer edit/reapproval và full Vue review UI; đây vẫn là final v0.1 release requirement.
10. Chạy security, calibration/holdout, CI và clean-machine release gates. CI cấm `WORKFLOW_PROFILE=walking_skeleton` trong release.

### 23.2 Final v0.1 runtime sequence

1. Customer đăng nhập bằng demo account.
2. Vue gọi `POST /api/v1/tickets` với “Tôi đã thanh toán cái ghế nhưng chưa được xác nhận”; v0.1 không gửi ticket attachment.
3. Backend tạo Ticket `OPEN` và first message trong transaction, trả `201` với `ticket_id`; chưa chạy agent.
4. Vue dùng key mới gọi `POST /api/v1/tickets/{ticket_id}/agent-runs`.
5. Backend kiểm tra invariant một non-terminal run/ticket, tạo Agent Run `CREATED`, chuyển Ticket `PROCESSING`, đặt monotonic deadline 60 giây và chạy graph đồng bộ.
6. Deterministic UC-01 guard xác nhận `payment_mismatch`; Agent không gọi LLM classification riêng, chỉ structured-extract/normalize `product_keyword=ghế`, `order_id=null` và lấy customer scope từ authenticated principal.
7. Order Resolution chỉ gọi customer-scoped Order/Payment HTTP APIs của Mock-Commerce; adapter tự inject internal Bearer token và token không đi vào AgentState/tool payload.
8. Scorer chọn order rõ ràng hoặc chuyển Ticket/run sang `WAITING_CUSTOMER` và tạo clarification an toàn.
9. Nếu cần bổ sung, customer gọi `POST /messages` với `attachment_references` omitted/`[]`; backend commit message rồi resume chính run cũ với budget 60 giây mới. Non-empty attachment references trả 422 trước commit/resume; không tạo run mới.
10. Agent lấy order `payment_status=PENDING` và payment `status=SUCCEEDED` qua HTTP.
11. RAG dùng exact E5 prefix/input-format contract, metadata-first vector+FTS top10 và RRF k=60; chỉ trả active policy citations vượt calibrated vector/lexical gate cùng full provenance.
12. Policy engine xác nhận evidence đủ; Agent tạo immutable `sync_payment_status` proposal version/hash.
13. Graph interrupt tại `WAITING_APPROVAL`; UI hiển thị evidence, citation, impact và `expires_at`.
14. Support Agent approve/edit/reject với expected version/hash. Material edit tạo proposal/version mới và yêu cầu approve lại.
15. Approval hợp lệ resume graph với budget 60 giây mới; expired approval trả `409` và chuyển run/ticket `ESCALATED`.
16. Khi approve, backend revalidate schema, ownership qua Mock-Commerce HTTP và deterministic business rules.
17. Backend gọi idempotent sync API, lưu Action Execution và đọc lại order để verify. Possible write timeout dùng `UNKNOWN` và reconciliation, không blind retry.
18. Chỉ sau `VERIFIED`, Agent tạo response draft; internal transition chuyển Ticket `RESOLVED` mà không cần approval riêng cho `update_ticket_status`.
19. Backend persist timeline, evidence, tool calls, approval/action events và redacted audit; UI polling hiển thị kết quả cuối.

Mọi timeout trước business write chuyển run `FAILED`, Ticket `ESCALATED`, ghi `agent_run.timeout` và trả `504`. Run hiện tại là terminal; explicit retry tạo run mới. V0.1 không có `CANCELLED`.

Seed phải có ít nhất:

- Một customer đã xác minh.
- Một Support Agent và một Manager.
- Một order “ghế” `PENDING_CONFIRMATION/payment_status=PENDING` với payment `SUCCEEDED` phù hợp.
- Một order khác để test ambiguity.
- Một order giống của customer khác để test isolation.
- Active payment policy, expired version và conflict fixture.
- Các fixture timeout, stale order và duplicate retry.
- Fixture approval expired/material edit và possible write `UNKNOWN`.
- Versioned 25-case golden dataset với retrieval ground truth subset.

## 24. Definition of Done

### Cho từng task

- Contract/schema và ví dụ được cập nhật.
- Business rule nằm trong service/policy engine, không chỉ trong prompt.
- Happy path, error path và retry path có test.
- Auth, role và customer scope được kiểm tra.
- Log/audit không chứa secret hoặc PII thừa.
- Idempotency/concurrency được kiểm tra nếu task có write.
- UI có loading, empty, denied và error state nếu liên quan.
- Lint, typecheck và test liên quan pass.
- Demo fixture tái hiện được.
- Không tạo migration/schema change ngoài spec đã review.
- Migration phải dùng exact PostgreSQL physical contract §7: type/nullability/default/enum/FK/delete/index/check/idempotency/version/immutability; không tự thêm field/table hoặc transition trigger.
- Task Phase 1 không được tạo domain enum/table/seed; chỉ `SKEL-001` Phase 2 được tạo minimal domain migration đầu tiên.
- Task đủ nhỏ để review độc lập; không kéo thêm UC/milestone hoặc provider ngoài phạm vi.
- Nếu liên quan workflow, deadline 60 giây, LLM timeout 12 giây, reserve 5 giây và terminal state phải có test.

### Cho Milestone v0.1

- Chỉ UC-01 chạy end-to-end bằng synthetic `payment-mismatch-v01` data; không có implementation UC-02+.
- Vue thực hiện explicit `POST /tickets` → `POST /tickets/{id}/agent-runs`; duplicate active run khác key trả `409 AGENT_RUN_ALREADY_ACTIVE`.
- Same-run message resume, approval resume/expiry và timeout contracts pass E2E.
- Ticket `attachment_references` omitted/`[]` đi đúng message path; non-empty luôn trả `422 ATTACHMENTS_NOT_SUPPORTED`, `retryable=false`, `details.supported_from=v1.0`, không message/idempotent-success/fetch/store/resume side effect. Không có ticket attachment table/upload endpoint/env enable flag.
- Không-order-ID được resolve hoặc hỏi lại đúng threshold.
- Chỉ Markdown ingestion; RAG citation chứa document, chunk, version, heading, score và embedding/index provenance.
- Exact E5 model/revision/dimension 384/input format `e5-prefix-v1` được persist; query/passage prefix contract được test; reindex path không trộn embedding version hoặc input-format version.
- `POST /knowledge/documents/{id}/reindex` chỉ trả synchronous persisted `200` success với exact fields §8.3.5; không `202`/queue/polling/auto-publish. Published active index chỉ swap atomically sau complete; failure giữ index cũ; replay không tạo attempt mới; config change đặt calibration về false.
- Deterministic hybrid retrieval thực hiện metadata filter → vector top 10 + FTS top 10 → dedupe → RRF `k=60` → calibrated evidence gates → top 5; RRF score không được dùng làm confidence.
- Vector cosine `0.72` và lexical gate đều không được coi là release threshold. 15-case calibration report phải chốt cả hai gate; 10-case locked holdout report phải pass độc lập với Recall@5 payment policy ≥90%, no-answer precision đạt target đã version hóa và false-positive evidence bằng 0; `RAG_THRESHOLD_CALIBRATED=true`.
- Không business write nào chạy thiếu approval hợp lệ.
- Reviewer edit revalidate schema/HTTP ownership/business rules; material edit tạo version/hash mới và reapproval.
- Approval hết hạn sau 24 giờ UTC; expired approval không execute hoặc revive.
- Ticket chỉ `RESOLVED` sau Action Execution `VERIFIED`; `UNKNOWN` phải reconcile, không blind retry.
- Agent Run v0.1 không có `CANCELLED`; timeout run là `FAILED`, Ticket `ESCALATED`, audit được persist trước `504`.
- LangGraph checkpoint là nguồn duy nhất để resume với `thread_id=agent_run.id`; `agent_runs` chỉ giữ overall status, `agent_run_events` chỉ giữ timeline và `audit_logs` chỉ giữ audit. Startup/recovery reconciliation không được reconstruct state từ timeline/audit và phải escalate/audit mọi invariant mismatch.
- Unauthorized action rate và duplicate action rate bằng 0.
- Tối thiểu 20 automated tests quan trọng và CI pass; 20 chỉ là baseline ban đầu, không phải giới hạn tối đa, và phải bổ sung test cho regression/concurrency/security/edge case phát hiện trong triển khai.
- Đúng 25 golden cases được version hóa và khóa split thành 15 calibration + 10 holdout; hai report tách biệt phải ghi dataset checksum, split manifest, model, revision, dimension, input-format version, RRF config, calibrated thresholds, Recall@5, no-answer precision và false-positive evidence.
- Grant tests chứng minh SupportPilot runtime không đọc `commerce` và Mock-Commerce runtime không đọc `support`.
- Internal-auth tests chứng minh missing header → `401 INTERNAL_UNAUTHENTICATED`, wrong token/user JWT → `403 INTERNAL_FORBIDDEN`, internal token không vào public API và không xuất hiện trong log/audit/tool output/frontend.
- Import-boundary tests chứng minh hai app không import database/repository/model nội bộ của nhau; chỉ `commerce_contracts` và phần primitive thuần trong `common` được dùng chung.
- Phase-1 catalog chỉ có empty schemas/migration infrastructure; `SKEL-001` tạo đúng bốn final-named minimal support tables. Các migration sau đi forward-only, đúng owner, không drop/recreate skeleton data.
- Physical support workflow tables §7.3 tồn tại với one-nonterminal-run, event sequence, immutable proposal/version/hash, expected-version concurrency, append-only audit, durable idempotency, `UNKNOWN` và `RESOLVED`-only-after-`VERIFIED` invariants.
- Physical commerce tables §7.5 dùng `NUMERIC(18,2)`, uppercase `CHAR(3)`, unique order number/partial transaction ref, customer-scoped ownership, expected versions và atomic sync/idempotency/audit; không có cross-schema FK hoặc table ngoài UC-01.
- Không có hard-delete Ticket API; audit/action/execution history không cascade và append-only grants chặn update/delete.
- Plaintext columns chỉ chứa synthetic data; không có fake `*_cipher/hash` columns.
- Compose chạy được từ môi trường sạch.
- Release chạy `WORKFLOW_PROFILE=v0_1`; CI phải từ chối `walking_skeleton`, fake agent, fake approval hoặc fixed proposal còn nằm trên release path.
- Public documentation, sample credentials và demo instructions hoàn chỉnh.
- Không commit secret hoặc dữ liệu khách thật.
- Ticket attachments/upload, PDF upload, refresh-token rotation, complete field-level encryption, advanced observability, Redis/queue và customer email send chưa được yêu cầu.

## 25. Questions blocking implementation

Không còn câu hỏi chặn triển khai Milestone v0.1. Change-spec và các quyết định bổ sung tại mục 20 đã được duyệt, gồm:

- Không có Agent Run `CANCELLED` trong v0.1.
- Active run khác idempotency key trả `409 AGENT_RUN_ALREADY_ACTIVE`.
- Gemini timeout 12 giây/attempt, workflow 60 giây và finalization reserve 5 giây.
- `DB-000` dùng one-shot `POSTGRES_BOOTSTRAP_DATABASE_URL`; owner/runtime credentials tách riêng.
- `SKEL-001` dùng final public contracts và fake adapters chỉ trong `walking_skeleton`; release bắt buộc thay hết fake path bằng profile `v0_1`.
- Exact E5 `e5-prefix-v1`, deterministic vector/FTS/RRF contract và vector/lexical calibration gates là contract triển khai, không phải lựa chọn tùy ý của coding agent.
- Checkpoint, run summary, timeline và audit có ownership tách biệt theo §7.8; invariant failure phải escalate/audit, không reconstruct hoặc tạo run mới ngầm.
- Golden set v0.1 khóa ở 25 cases với split 15 calibration/10 holdout; automated tests có minimum 20 và không có hard maximum.
- Ticket attachment field chỉ là forward-compatible contract: non-empty trả 422, không persistence/upload/resume cho đến v1.0.
- Knowledge reindex đồng bộ `200`, idempotent, atomic swap, không auto-publish/queue/polling; embedding/retrieval config change reset calibration.
- `/internal/v1/*` dùng một exact Bearer `INTERNAL_SERVICE_TOKEN`; user JWT/internal token không dùng chéo và secret không xuất hiện ngoài hai runtime services.
- Phase 1 không tạo domain table; `SKEL-001` Phase 2 sở hữu minimal final-named migration đầu tiên. §7 là physical PostgreSQL contract bắt buộc, không phải gợi ý.

Mọi thay đổi sau đây phải quay lại review scope/ADR trước khi implement: thêm UC-02+, đổi provider/model/revision, đổi schema ownership, thêm queue, dùng dữ liệu khách thật, thêm PDF/encryption/refresh rotation/advanced observability vào v0.1 hoặc thay approval/timeout/state-machine semantics.

## 26. Planned documentation files

| File | Sections dự kiến |
|---|---|
| `docs/PROJECT_SPEC.md` | Goals; actors; business problem; functional requirements; MVP/Post-MVP/out-of-scope; seven use cases; success metrics; assumptions |
| `docs/ARCHITECTURE.md` | Context/component diagrams; modular boundaries; checkpoint/run/timeline/audit ownership; Support/Mock-Commerce HTTP và import boundaries; Walking Skeleton replacement path; deployment view; ADR links |
| `docs/DATABASE_DESIGN.md` | Exact physical support/commerce tables; extensions; relationships/delete rules; checkpoint ownership; enums/transitions; indexes; redacted JSON; locking/idempotency/versioning; Phase-1/SKEL forward migration ownership/seed policy |
| `docs/API_CONTRACT.md` | Conventions; public JWT/internal Bearer separation; ticket attachment 422; synchronous reindex; public/internal endpoints; errors/retryability; idempotency; pagination; examples |
| `docs/AGENT_WORKFLOW.md` | v0.1 active graph profile và v1 target nodes; checkpoint/thread ownership; transitions; retry/failure; interrupt/resume/reconciliation; tool permissions; versioning; no-CoT policy |
| `docs/RAG_DESIGN.md` | Markdown ingestion; exact E5/index provenance; synchronous atomic reindex; metadata-first vector/FTS top10; RRF k=60; calibrated gates; citation/version/conflict/expiry; calibration/holdout evaluation |
| `docs/SECURITY.md` | Threat model; RBAC; public/internal token separation; customer/schema isolation; prompt injection; tool misuse; approval; PII/secrets; attachment/knowledge-upload security; abuse controls |
| `docs/ROADMAP.md` | Phases 0–9; Phase-1 migration boundary; Walking Skeleton/fake replacement; dependencies; final vertical slice; MVP/Post-MVP; release gates; risks |
| `docs/TASKS.md` | Task backlog từ mục 22 gồm `SKEL-001`; owner/status fields; acceptance criteria; test commands; explicit dependencies; review checklist |
