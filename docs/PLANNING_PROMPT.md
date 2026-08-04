Hãy đọc toàn bộ file mô tả dự án SupportPilot được cung cấp và xem đây là nguồn yêu cầu chính thức của dự án.

Ở bước này, tuyệt đối chưa viết code, chưa khởi tạo project và chưa cài đặt dependency.

Nhiệm vụ của bạn là phân tích tài liệu và tạo một kế hoạch triển khai kỹ thuật chi tiết, có thể được sử dụng trực tiếp để phát triển dự án theo từng task nhỏ.

## 1. Nguyên tắc làm việc

- Không tự ý mở rộng phạm vi ngoài tài liệu.
- Không bổ sung công nghệ chỉ để làm kiến trúc phức tạp hơn.
- Ưu tiên modular monolith trước microservices.
- Ưu tiên giải pháp đơn giản, dễ kiểm thử và phù hợp với project portfolio.
- Không sử dụng Kubernetes, Kafka hoặc cloud service trả phí trong MVP nếu tài liệu không yêu cầu.
- PostgreSQL là database chính.
- pgvector được sử dụng cho dữ liệu embedding của RAG.
- Backend sử dụng FastAPI.
- Frontend sử dụng Vue 3, Vite, TypeScript, Pinia và Vue Router.
- Agent workflow sử dụng LangGraph.
- Các dịch vụ Order, Payment, Shipping, Refund và Warranty trong MVP được xây dựng dưới dạng internal/mock API.
- Thiết kế phải cho phép thay thế mock service bằng external provider trong tương lai thông qua adapter hoặc interface phù hợp.
- Các hành động làm thay đổi dữ liệu phải có cơ chế human approval khi tài liệu yêu cầu.
- Không hiển thị hoặc lưu toàn bộ chain-of-thought của LLM. Chỉ lưu execution summary, evidence, tool calls và quyết định cuối cùng.

Khi tài liệu không quy định rõ một vấn đề, không được âm thầm tự quyết định. Hãy ghi vấn đề đó vào một trong hai mục:

- Assumption: giả định tạm thời có thể thay đổi.
- Technical decision requiring review: quyết định kỹ thuật cần người dùng phê duyệt.

## 2. Kết quả đầu ra bắt buộc

Kế hoạch phải bao gồm đầy đủ các phần sau.

### A. Tóm tắt dự án

- Mục tiêu của SupportPilot.
- Đối tượng sử dụng.
- Vấn đề nghiệp vụ được giải quyết.
- Giá trị của RAG, AI Agent, tool calling và human-in-the-loop trong hệ thống.
- Những nội dung không thuộc phạm vi dự án.

### B. Phạm vi tính năng

Phân loại rõ:

- MVP.
- Post-MVP.
- Advanced features.
- Out of scope.

Với mỗi chức năng, ghi rõ lý do tại sao nó thuộc nhóm đó.

### C. Use case

Liệt kê toàn bộ use case có trong tài liệu.

Với mỗi use case, mô tả:

- Actor.
- Trigger.
- Dữ liệu đầu vào.
- Thông tin cần trích xuất.
- API hoặc tool cần gọi.
- Policy cần truy xuất bằng RAG.
- Điều kiện cần human approval.
- Kết quả thành công.
- Các trường hợp lỗi hoặc thiếu dữ liệu.
- Cách hệ thống xử lý khi không xác định được đơn hàng.

### D. Kiến trúc tổng thể

Đề xuất kiến trúc hệ thống ở mức component.

Phải thể hiện rõ luồng dữ liệu giữa:

- Vue frontend.
- FastAPI backend.
- Agent orchestrator.
- LangGraph workflow.
- PostgreSQL.
- pgvector.
- Redis nếu thực sự cần thiết.
- Internal Order API.
- Internal Payment API.
- Internal Shipping API.
- RAG ingestion pipeline.
- LLM provider.
- Email hoặc notification service.
- Approval system.
- Audit logging.

Giải thích trách nhiệm và ranh giới của từng component.

Ưu tiên modular monolith trong MVP. Chỉ đề xuất tách service khi có lý do rõ ràng.

### E. Service và module

Liệt kê các service/module dự kiến.

Với mỗi module, ghi:

- Trách nhiệm.
- Input.
- Output.
- Module được phép phụ thuộc.
- Module không nên phụ thuộc trực tiếp.
- Dữ liệu sở hữu.
- Public interface.

Ít nhất cần xem xét:

- Authentication.
- Customer.
- Order.
- Payment.
- Shipping.
- Ticket.
- Ticket message.
- Knowledge base.
- RAG.
- Agent orchestration.
- Tool registry.
- Order resolution.
- Approval.
- Notification.
- Audit log.
- Evaluation.

### F. Thiết kế PostgreSQL sơ bộ

Liệt kê các bảng chính, trường quan trọng, khóa chính, khóa ngoại và quan hệ.

Ít nhất cần xem xét:

- users
- customers
- customer_addresses
- products
- orders
- order_items
- payments
- shipments
- support_tickets
- ticket_messages
- knowledge_documents
- knowledge_chunks
- agent_runs
- tool_calls
- approval_requests
- notifications
- audit_logs

Với mỗi bảng, ghi:

- Mục đích.
- Các trường chính.
- Quan hệ.
- Unique constraints.
- Index cần thiết.
- Trường trạng thái.
- Trường thời gian.
- Những dữ liệu nhạy cảm cần bảo vệ.

Chỉ ra những thao tác cần database transaction, row locking hoặc idempotency.

### G. REST API contract

Liệt kê các endpoint cần xây dựng.

Phân nhóm:

- Authentication API.
- Customer API.
- Order API.
- Payment API.
- Shipping API.
- Ticket API.
- Knowledge base API.
- Agent execution API.
- Approval API.
- Notification API.
- Administration API.

Với mỗi endpoint quan trọng, mô tả:

- HTTP method.
- Path.
- Mục đích.
- Authentication hoặc role yêu cầu.
- Request schema.
- Response schema.
- Error responses.
- Idempotency requirement.
- Có yêu cầu approval hay không.

Không chỉ liệt kê tên endpoint.

### H. AI Agent workflow

Thiết kế LangGraph workflow và các node cần có.

Ít nhất cần xem xét:

- receive_ticket
- identify_customer
- classify_intent
- extract_entities
- resolve_order
- request_missing_information
- retrieve_business_data
- retrieve_policy
- evaluate_evidence
- generate_resolution_plan
- check_approval_requirement
- wait_for_approval
- execute_action
- verify_action
- generate_customer_response
- update_ticket
- write_audit_log
- handle_failure

Với mỗi node, ghi:

- Trách nhiệm.
- Input state.
- Output state.
- Tool được phép gọi.
- Điều kiện chuyển node.
- Retry policy.
- Failure path.

Thiết kế AgentState sơ bộ, nhưng chưa viết code.

### I. Tool registry

Liệt kê toàn bộ tool mà agent được phép gọi.

Phân loại:

1. Read-only tools.
2. Write tools requiring approval.
3. Write tools có thể thực hiện tự động.
4. Tools bị cấm trong MVP.

Với mỗi tool, ghi:

- Tên tool.
- Mục đích.
- Input schema.
- Output schema.
- Service được gọi.
- Timeout.
- Retry policy.
- Idempotency rule.
- Permission requirement.
- Audit information cần lưu.

Đặc biệt làm rõ các tool liên quan đến:

- Tìm khách hàng.
- Tìm đơn hàng khi không có order ID.
- Tìm payment gần đây.
- Match payment với order.
- Tìm shipment.
- Tìm policy.
- Tạo refund request.
- Đồng bộ trạng thái thanh toán.
- Đổi địa chỉ giao hàng.
- Tạo warranty claim.
- Tạo email draft.
- Gửi notification.

### J. Order Resolution

Thiết kế riêng module xác định đơn hàng khi khách không cung cấp mã đơn.

Phải mô tả:

- Các tín hiệu có thể sử dụng.
- Customer identity được lấy từ đâu.
- Cách tìm candidate orders.
- Cách tính match score.
- Confidence threshold.
- Trường hợp tự chọn được order.
- Trường hợp cần khách xác nhận.
- Trường hợp cần hỏi thêm thông tin.
- Cách tránh tiết lộ dữ liệu của khách hàng khác.
- Cách kiểm thử entity resolution.
- Không sử dụng RAG để truy vấn dữ liệu giao dịch.

### K. RAG pipeline

Thiết kế toàn bộ pipeline:

1. Document ingestion.
2. Document validation.
3. Text normalization.
4. Metadata extraction.
5. Chunking.
6. Embedding.
7. Lưu PostgreSQL + pgvector.
8. Retrieval.
9. Metadata filtering.
10. Reranking nếu thực sự cần.
11. Citation.
12. Versioning.
13. Re-indexing.
14. Policy expiration.
15. Evaluation.

Chỉ rõ:

- Loại tài liệu được hỗ trợ trong MVP.
- Chunk size đề xuất và lý do.
- Metadata bắt buộc.
- Embedding provider.
- Retrieval strategy.
- Top-k.
- Similarity threshold.
- Khi nào agent phải từ chối kết luận vì không tìm thấy policy đủ tin cậy.
- Cách trả citation về frontend.
- Cách xử lý hai policy mâu thuẫn hoặc khác phiên bản.

### L. Cấu trúc thư mục

Đề xuất cấu trúc repository theo dạng:

- backend/
- frontend/
- docs/
- infrastructure/
- tests/
- scripts/

Trong backend, cần thể hiện rõ:

- api
- core
- db
- models
- schemas
- repositories
- services
- agents
- tools
- rag
- integrations
- approvals
- audit
- tests

Trong frontend Vue 3, cần thể hiện rõ:

- views
- components
- layouts
- router
- stores
- services
- composables
- types
- utils

Giải thích ngắn gọn trách nhiệm từng thư mục.

### M. Biến môi trường

Liệt kê các biến môi trường cần thiết theo nhóm:

- Application.
- PostgreSQL.
- Redis.
- Authentication.
- LLM provider.
- Embedding.
- RAG.
- Email.
- Logging.
- Security.
- Mock service configuration.

Với mỗi biến, ghi:

- Ý nghĩa.
- Bắt buộc hay tùy chọn.
- Giá trị mẫu không chứa secret thật.
- Môi trường sử dụng.
- Secret có được commit hay không.

### N. Testing strategy

Thiết kế chiến lược kiểm thử gồm:

- Unit tests.
- Repository tests.
- API integration tests.
- Tool contract tests.
- LangGraph node tests.
- Agent workflow tests.
- RAG retrieval tests.
- Security tests.
- Approval tests.
- End-to-end tests.
- Regression evaluation.
- Failure injection.

Nêu cách mock:

- LLM.
- Payment service.
- Shipping service.
- Email service.
- Embedding model.

Đề xuất bộ golden test cases cho agent.

### O. Docker Compose

Đề xuất các container cho môi trường development.

Chỉ thêm container thực sự cần thiết.

Ít nhất xem xét:

- backend
- frontend
- postgres với pgvector
- redis nếu cần
- mailpit
- optional local LLM profile

Mô tả:

- Port.
- Volume.
- Health check.
- Dependency.
- Network.
- Startup order.
- Migration strategy.
- Seed data strategy.

Chưa viết file Docker Compose thật trong bước này.

### P. Observability và audit

Thiết kế sơ bộ cách lưu:

- Agent run.
- Tool call.
- Input và output đã được che dữ liệu nhạy cảm.
- Latency.
- Token usage.
- Estimated cost.
- Retrieved policy chunks.
- Approval decision.
- Final action.
- Error.
- Retry.
- Correlation ID.

Phân biệt rõ log kỹ thuật, audit log và dữ liệu hội thoại.

### Q. Security

Xác định các rủi ro và biện pháp tối thiểu:

- Authentication.
- Role-based access control.
- Customer data isolation.
- Prompt injection từ ticket hoặc document.
- Tool misuse.
- Unauthorized write action.
- Sensitive data in logs.
- Secret management.
- Rate limiting.
- File upload validation.
- SQL injection.
- Duplicate action.
- Refund abuse.

### R. Assumptions và technical decisions

Tạo hai danh sách riêng:

#### Assumptions

Các giả định tạm thời được sử dụng để xây plan.

#### Technical decisions requiring review

Các quyết định người dùng cần phê duyệt trước khi code.

Mỗi quyết định cần có:

- Các lựa chọn.
- Phương án đề xuất.
- Lý do.
- Trade-off.
- Ảnh hưởng nếu thay đổi sau này.

## 3. Vertical slice đầu tiên

Ưu tiên hoàn thành một vertical slice hoạt động end-to-end trước, thay vì xây toàn bộ database hoặc toàn bộ giao diện cùng lúc.

Vertical slice đầu tiên phải xử lý use case:

“Khách hàng báo đã thanh toán một sản phẩm nhưng đơn hàng chưa được xác nhận, kể cả khi khách không cung cấp mã đơn hàng.”

Vertical slice cần bao gồm tối thiểu:

1. Khách hàng gửi ticket từ giao diện Vue.
2. Backend lưu ticket vào PostgreSQL.
3. Agent phân loại ticket.
4. Agent trích xuất product keyword và thông tin liên quan.
5. Hệ thống xác định customer identity.
6. Order Resolution tìm candidate orders.
7. Agent gọi Order API.
8. Agent gọi Payment API.
9. RAG truy xuất payment policy.
10. Agent tổng hợp evidence.
11. Agent đề xuất hành động.
12. Nhân viên approve hoặc reject.
13. Backend đồng bộ trạng thái order nếu được approve.
14. Agent tạo customer response.
15. Ticket và audit log được cập nhật.
16. Giao diện hiển thị execution timeline, evidence, citation và approval state.

Không dùng dữ liệu khách hàng thật trong vertical slice. Hãy đề xuất seed data phù hợp.

## 4. Chia phase và task

Chia dự án thành các phase có thứ tự phụ thuộc rõ ràng.

Mỗi phase phải tạo ra một kết quả có thể chạy hoặc kiểm chứng được.

Không tạo task quá lớn. Mỗi task nên đủ nhỏ để một coding agent có thể hoàn thành trong một lần làm việc và review độc lập.

Mỗi task bắt buộc có:

- Task ID.
- Tên task.
- Phase.
- Mục tiêu.
- Phạm vi.
- Những nội dung không thuộc task.
- File hoặc module dự kiến tạo hoặc thay đổi.
- Input.
- Output.
- Điều kiện hoàn thành.
- Acceptance criteria.
- Task phụ thuộc.
- Test cần viết.
- Lệnh kiểm tra dự kiến.
- Rủi ro.
- Estimate tương đối: S, M hoặc L.

Ưu tiên thứ tự triển khai:

1. Documentation và architecture decisions.
2. Project foundation.
3. Database và migrations tối thiểu.
4. Seed data cho vertical slice.
5. Ticket creation.
6. Internal Order API.
7. Internal Payment API.
8. Order Resolution.
9. RAG ingestion và retrieval.
10. LangGraph workflow.
11. Human approval.
12. Write action và verification.
13. Vue ticket interface.
14. Execution timeline.
15. End-to-end tests.
16. Các use case tiếp theo.

## 5. Định dạng đầu ra

Trả kết quả theo đúng thứ tự:

1. Executive summary.
2. Requirements extracted from the document.
3. MVP, Post-MVP và Out of Scope.
4. Use cases.
5. Architecture.
6. Modules and responsibilities.
7. Database design.
8. API contract.
9. Agent workflow.
10. Tool registry.
11. Order Resolution design.
12. RAG design.
13. Repository structure.
14. Environment variables.
15. Testing strategy.
16. Docker Compose proposal.
17. Observability.
18. Security.
19. Assumptions.
20. Technical decisions requiring review.
21. Phase roadmap.
22. Detailed task backlog.
23. Vertical slice execution sequence.
24. Definition of Done.
25. Questions blocking implementation.

Sử dụng bảng khi giúp nội dung dễ review hơn.

Không viết code.

Không tạo file thực tế.

Không bắt đầu implementation.

Nếu có điểm mâu thuẫn trong tài liệu, hãy trích rõ phần mâu thuẫn và đề xuất cách giải quyết.

Nếu có câu hỏi chưa rõ nhưng không chặn việc lập kế hoạch, hãy ghi assumption thay vì dừng lại hỏi.

Chỉ đưa vào mục “Questions blocking implementation” những câu hỏi thực sự khiến không thể bắt đầu vertical slice.

Cuối cùng, đề xuất nội dung của các file tài liệu cần được tạo trong repository:

- docs/PROJECT_SPEC.md
- docs/ARCHITECTURE.md
- docs/DATABASE_DESIGN.md
- docs/API_CONTRACT.md
- docs/AGENT_WORKFLOW.md
- docs/RAG_DESIGN.md
- docs/SECURITY.md
- docs/ROADMAP.md
- docs/TASKS.md

Với mỗi file, ghi rõ các section dự kiến nhưng chưa tạo file ở bước này.
