# SupportPilot — Project Specification

> Trạng thái: tài liệu kỹ thuật dẫn xuất từ [PLAN.md](./PLAN.md). Nếu có khác biệt, `PLAN.md` có ưu tiên cao hơn.

## 1. Mục tiêu dự án

SupportPilot là hệ thống hỗ trợ khách hàng thương mại điện tử kết hợp truy xuất chính sách có nguồn, AI Agent điều phối workflow, dữ liệu giao dịch qua API và human-in-the-loop cho hành động nghiệp vụ. Mục tiêu là giảm thời gian tra cứu và xử lý thủ công nhưng vẫn giữ customer isolation, policy grounding, approval, idempotency và audit trail.

Milestone v0.1 chỉ chứng minh một vertical slice hoàn chỉnh cho **UC-01 Payment Mismatch**. Các use case còn lại chỉ mô tả định hướng sản phẩm, không phải backlog triển khai v0.1.

## 2. Bài toán nghiệp vụ

Nhân viên hỗ trợ thường phải ghép ba nhóm thông tin:

- Nội dung ticket không cấu trúc, đôi khi thiếu order ID.
- Trạng thái order/payment có tính giao dịch và phải lấy từ hệ thống commerce.
- Chính sách có version, effective date và phạm vi áp dụng.

Quy trình thủ công dễ chọn nhầm order, dùng policy hết hạn hoặc thực hiện write trước khi có người đủ quyền duyệt. SupportPilot chuẩn hóa việc xác minh customer, resolve order, thu thập evidence, truy xuất policy, đề xuất action, approval, execution và verification.

## 3. Giá trị hệ thống

- Rút ngắn thời gian tra cứu order/payment và policy.
- Cung cấp citation và provenance để reviewer kiểm chứng.
- Ngăn business write tự động không có approval.
- Ngăn cross-customer và cross-schema access.
- Làm rõ failure, timeout, retry và possible-write `UNKNOWN`.
- Tạo timeline và audit trail mà không lưu chain-of-thought.

## 4. Đối tượng sử dụng

| Actor | Trách nhiệm và quyền chính |
|---|---|
| Customer | Đăng nhập, tạo Ticket, gửi thông tin bổ sung và xem dữ liệu thuộc phạm vi của mình. |
| Support Agent | Review evidence/proposal; approve, edit hoặc reject action trong phạm vi quyền. Là reviewer của `sync_payment_status` trong v0.1. |
| Support Manager | Có quyền review theo role, xem audit phù hợp và xử lý các tier cao hơn khi được đưa vào milestone tương ứng. |
| Admin | Quản trị knowledge documents, chạy publish/reindex/search kiểm tra và xem audit đã redact. |

RBAC được enforce tại API và service layer; việc ẩn nút trên Vue không phải security boundary.

## 5. Functional requirements

1. Nhận ticket từ Vue hoặc API và lưu message đầu tiên trong cùng transaction.
2. Tạo Agent Run bằng request riêng sau khi đã nhận `ticket_id`.
3. Chỉ xử lý intent `payment_mismatch` trong v0.1; intent ngoài phạm vi phải conservative escalation.
4. Trích xuất order ID, product keyword, amount, time và transaction reference.
5. Xác định customer từ authenticated principal; LLM không được chọn customer ID.
6. Resolve order trong customer scope kể cả khi không có order ID.
7. Lấy order/payment evidence qua Mock-Commerce HTTP API, không qua RAG hoặc direct database read.
8. Truy xuất active policy từ Markdown knowledge base với citation, version và effective date.
9. Đánh giá evidence bằng deterministic domain/policy rules.
10. Tạo immutable proposal và response draft có grounding.
11. Cho phép reviewer đủ quyền approve, edit hoặc reject.
12. Revalidate schema, ownership và business rules trước business write.
13. Execute idempotently và đọc lại target để verify.
14. Chỉ chuyển Ticket sang `RESOLVED` sau Action Execution `VERIFIED`.
15. Resume chính Agent Run đang `WAITING_CUSTOMER` khi customer gửi message mới.
16. Hiển thị Ticket, evidence, citations, approval state và timeline qua Vue polling.
17. Persist checkpoint, run summary, events, tool calls, evidence, approval/action state và audit đúng ownership.
18. Với message API, chỉ chấp nhận `attachment_references` bị bỏ qua hoặc `[]`; danh sách không rỗng phải bị từ chối bằng `422 ATTACHMENTS_NOT_SUPPORTED` trước khi lưu message hoặc resume Agent Run.
19. Cho phép Admin reindex knowledge document đồng bộ, idempotent, trả `200`, giữ active index cũ đến khi atomic swap thành công và không tự publish document.
20. Mọi `/internal/v1/*` dùng exact Bearer service token; SupportPilot adapter tự inject token và không để token đi vào frontend, LLM, log, audit hoặc tool-call projection.

Chi tiết giao tiếp nằm tại [API_CONTRACT.md](./API_CONTRACT.md); workflow nằm tại [AGENT_WORKFLOW.md](./AGENT_WORKFLOW.md).

## 6. Non-functional requirements

| Nhóm | Yêu cầu v0.1 |
|---|---|
| An toàn | Không business write thiếu approval; không cross-customer/cross-schema read; không arbitrary HTTP/SQL/filesystem/code execution. |
| Tin cậy | Idempotency, locks, partial unique index, status reconciliation và typed failure paths. |
| Hiệu năng | Mỗi synchronous graph advance có budget 60 giây; 5 giây cuối dành cho finalization. |
| Khả năng kiểm chứng | Citation/provenance đầy đủ, deterministic rules, append-only timeline/audit, versioned evaluation artifacts. |
| Bảo mật dữ liệu | Chỉ synthetic data; log redaction; không PAN/CVV/provider secret; không chain-of-thought. |
| Maintainability | Modular monolith, adapter interfaces, import-boundary tests, task nhỏ và review độc lập. |
| Reproducibility | Local Compose, fixed seed profile, version/checksum cho dataset và knowledge. |
| Quality | Tối thiểu 20 automated tests quan trọng; không có hard maximum. Golden set 25 cases tách 15 calibration/10 holdout. |

## 7. Technical constraints

- Frontend: Vue 3, Vite, TypeScript, Pinia và Vue Router.
- Backend: FastAPI modular monolith, Pydantic, SQLAlchemy 2 và Alembic.
- Orchestration: LangGraph với checkpoint trong PostgreSQL.
- Database: PostgreSQL; vector storage bằng pgvector.
- Mock-Commerce là runtime riêng; SupportPilot chỉ gọi qua HTTP.
- LLM mặc định: Gemini API qua adapter với `GEMINI_MODEL=gemini-3.6-flash`; OpenAI/Ollama chỉ là alternative.
- Embedding mặc định: local SentenceTransformers `intfloat/multilingual-e5-small`, revision `c007d7ef6fd86656326059b28395a7a03a7c5846`, dimension 384 và input format `e5-prefix-v1`.
- RAG v0.1 chỉ nhận UTF-8 Markdown.
- Không Redis, Celery, Kafka, Kubernetes hoặc background queue trong v0.1.
- Không expose chain-of-thought hoặc checkpoint payload qua API.

## 8. Milestone v0.1

Phạm vi bắt buộc:

- UC-01 Payment Mismatch end-to-end.
- Explicit Ticket creation rồi explicit synchronous Agent Run.
- Same-run customer message resume.
- Customer-scoped Order Resolution và Mock-Commerce HTTP reads/write.
- Markdown ingestion, E5 embedding, deterministic vector+FTS+RRF retrieval.
- v0.1 LangGraph profile, approval interrupt/resume và verified action.
- Vue login, Ticket, evidence/citation/timeline và approval/edit/reject flow.
- Basic JSON logs, events, redacted audit, security/evaluation/CI gates.
- Ticket attachment không được hỗ trợ hoặc lưu trong v0.1; field forward-compatible chỉ hợp lệ khi omitted/`[]`.
- Synchronous knowledge reindex với atomic index swap, provenance và recalibration flag.

Walking Skeleton là demo tạm qua adapters. Final release phải dùng `WORKFLOW_PROFILE=v0_1` và không còn fake path có thể kích hoạt.

## 9. MVP v1.0

MVP v1.0 mở rộng UC-01–UC-05 sau khi v0.1 ổn định, đồng thời bổ sung ticket attachment/upload endpoint, PDF upload, refresh-token rotation, field-level encryption hoàn chỉnh và advanced observability. Đây không phải acceptance criteria hay backlog triển khai v0.1.

## 10. Post-MVP

- UC-06 Duplicate Charge.
- UC-07 Warranty.
- Gmail, Zendesk/Freshdesk, Slack và Stripe sandbox connectors.
- Queue/worker, realtime delivery và reranker khi workload/evaluation chứng minh cần.

## 11. Advanced features

- Multi-tenant SaaS và workflow builder.
- Automatic feedback learning và advanced analytics.
- Qdrant hoặc vector infrastructure khác khi có scale requirement.
- Voice support, transcription và local LLM profile.

## 12. Out of scope

- UC-02–UC-07 implementation trong v0.1.
- Autonomous refund/cancel hoặc business write không approval.
- Redis, Celery, Kafka, Kubernetes và background queue trong v0.1.
- PDF, DOCX, OCR, real email send, refresh-token rotation, complete field encryption và advanced observability trong v0.1.
- Ticket attachment, attachment upload endpoint, attachment storage hoặc fetch file/URL trong v0.1.
- Production payment processing hoặc dữ liệu khách thật.
- Arbitrary URL/HTTP, SQL, filesystem, shell hoặc code-execution tools.
- Lưu chain-of-thought, raw secrets, PAN hoặc CVV.

## 13. Use cases và milestone assignment

| ID | Use case | Hành vi chính | Milestone |
|---|---|---|---|
| UC-01 | Payment Mismatch | Resolve customer order; đối chiếu payment succeeded với order pending; retrieve payment-sync policy; approve và verify `sync_payment_status`. | **v0.1 — duy nhất được implement** |
| UC-02 | Defective Return | Xác minh item/delivery/evidence và return/refund policy. | MVP v1.0 — mô tả định hướng |
| UC-03 | Shipping Delay/Cancel | Đối chiếu shipping events, SLA và cancellation/RTS policy. | MVP v1.0 — mô tả định hướng |
| UC-04 | Wrong/Missing Item | Đối chiếu order item/package evidence và claim/remedy policy. | MVP v1.0 — mô tả định hướng |
| UC-05 | Address Change | Kiểm tra shipping state, address validity và cutoff policy. | MVP v1.0 — mô tả định hướng |
| UC-06 | Duplicate Charge | Xác định candidate duplicate transactions và investigation/refund path. | Post-MVP — mô tả định hướng |
| UC-07 | Warranty | Xác minh item/serial/coverage và warranty claim path. | Post-MVP — mô tả định hướng |

### 13.1 UC-01 success path

1. Customer tạo Ticket, sau đó Vue tạo Agent Run riêng.
2. Agent xác định customer và trích xuất payment-mismatch context.
3. Order Resolution chọn đúng order hoặc hỏi thêm an toàn.
4. Mock-Commerce cung cấp order/payment evidence qua HTTP.
5. RAG trả active payment policy citations vượt calibrated gate.
6. Deterministic policy engine tạo proposal `sync_payment_status`.
7. Support Agent approve proposal còn hạn và đúng version/hash.
8. Backend revalidate, execute idempotently và verify bằng fresh read.
9. Sau `VERIFIED`, response draft được lưu và Ticket chuyển `RESOLVED`.

### 13.2 UC-01 conservative paths

- Customer chưa verified: không đọc commerce data.
- Order ambiguous: Ticket/run `WAITING_CUSTOMER`, chỉ hiển thị candidate đã mask.
- Unsupported intent, thiếu evidence hoặc policy conflict: `ESCALATED`.
- Approval reject/expired: không execute; run/Ticket `ESCALATED`.
- Workflow timeout trước write: run `FAILED`, Ticket `ESCALATED`, HTTP `504`.
- Write outcome chưa rõ: Action Execution `UNKNOWN`; reconcile/verify, không blind retry và không resolve Ticket.

## 14. Assumptions

- Một tenant demo, toàn bộ dữ liệu là synthetic.
- Web session đã đăng nhập là identity source của vertical slice.
- Support Agent approve `sync_payment_status`; currency mặc định VND.
- Payment API không trả card data.
- Policy seed là Markdown có version/effective date rõ.
- Exact vector search đủ cho corpus v0.1; UI dùng polling.
- Approval TTL là 24 giờ tuyệt đối UTC và phát hiện lazy.
- Không LLM classification call riêng trong v0.1; tối đa một extraction call và một grounded proposal/response call khi cần.

## 15. Success metrics

| Metric | Target v0.1 |
|---|---:|
| UC-01 verified end-to-end flow | Pass |
| Payment-policy Recall@5 | ≥ 90% |
| Holdout false-positive policy evidence | 0 |
| Unauthorized actions | 0 |
| Duplicate actions | 0 |
| Cross-schema runtime reads | 0 |
| Automated tests quan trọng | ≥ 20; được phép tăng |
| Golden evaluation cases | 25: 15 calibration + 10 holdout |

No-answer precision phải đạt target được version hóa trong evaluation artifact; `PLAN.md` chưa chốt một giá trị số cố định cho metric này.

## 16. Release criteria v0.1

- Chỉ UC-01 chạy với seed `payment-mismatch-v01`.
- Explicit `POST /tickets` → `POST /tickets/{id}/agent-runs` và same-run message resume pass E2E.
- Message attachment compatibility pass E2E: omitted/`[]` đi theo normal path; non-empty trả exact `422 ATTACHMENTS_NOT_SUPPORTED`, `retryable=false`, không persist/fetch/resume.
- Workflow timeout 60 giây, finalization reserve 5 giây và LLM timeout 12 giây/attempt được test.
- Approval TTL 24 giờ, stale/material edit/reapproval và action `UNKNOWN`/verification pass.
- Ticket chỉ `RESOLVED` sau Action Execution `VERIFIED`.
- Exact E5 model/revision/dimension/input format và RRF/gate provenance được persist.
- Calibration và holdout reports độc lập, `RAG_THRESHOLD_CALIBRATED=true` và các quality metrics pass.
- Grant/import/security gates pass; không runtime nào đọc schema của runtime kia.
- Internal API auth pass exact matrix: thiếu Bearer token trả `401 INTERNAL_UNAUTHENTICATED`; token sai hoặc user JWT trả `403 INTERNAL_FORBIDDEN`; internal token bị từ chối ở public API và luôn được redact.
- Knowledge reindex trả synchronous `200`, replay không rebuild, không `202`/queue/polling/auto-publish; failure giữ active index cũ và config change reset calibration.
- Compose chạy từ môi trường sạch; release profile không dùng fake providers.
- Không secret hoặc dữ liệu khách thật được commit.

## 17. Glossary

| Thuật ngữ | Định nghĩa |
|---|---|
| Agent Run | Một lần tiến workflow gắn Ticket; có operational status và checkpoint riêng. |
| Approval | Quyết định của reviewer đủ quyền trên immutable proposal version/hash. |
| Business evidence | Dữ liệu giao dịch từ HTTP APIs và policy chunks đã qua confidence/version gates. |
| Business write | Hành động làm thay đổi commerce state; v0.1 là `sync_payment_status`. |
| Checkpoint | LangGraph state tối thiểu dùng để resume; không phải UI timeline hoặc audit. |
| Citation | Tham chiếu chunk/document/version/effective date và retrieval provenance. |
| Golden set | Dataset 25 cases, tách calibration và locked holdout. |
| Human-in-the-loop | Workflow dừng để người có quyền review/approve/edit/reject proposal. |
| Material edit | Thay target, amount, currency hoặc action type; bắt buộc proposal version/hash mới và reapproval. |
| Mock-Commerce | Runtime riêng sở hữu schema `commerce`, chỉ được SupportPilot truy cập qua HTTP. |
| RRF | Reciprocal Rank Fusion; chỉ dùng xếp hạng, không phải confidence. |
| Walking Skeleton | Demo tạm nối Vue/FastAPI/PostgreSQL bằng adapters/fakes, không phải release implementation. |

## Source and traceability

- Nguồn chính: [PLAN.md](./PLAN.md), §1–§4, §15, §19–§20, §23–§24.
- Tài liệu liên quan: [ARCHITECTURE.md](./ARCHITECTURE.md), [API_CONTRACT.md](./API_CONTRACT.md), [ROADMAP.md](./ROADMAP.md), [TASKS.md](./TASKS.md).
- Quyết định không được thay đổi: scope UC-01 v0.1; stack; HTTP-only commerce access; provider/model; approval/verification invariant; timeout; RAG contract; synthetic-only/no-CoT.
- Phiên bản nguồn: `PLAN.md` hiện không có version nội tại; traceability snapshot dùng nội dung hiện hành ngày 2026-08-04.
