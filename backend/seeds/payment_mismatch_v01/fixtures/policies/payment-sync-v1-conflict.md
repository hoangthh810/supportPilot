---
policy_type: payment_status_sync
title: Fixture xung đột về đồng bộ trạng thái thanh toán
version: 1.0.0-conflict
effective_from: 2026-01-01T00:00:00Z
effective_to: 2099-12-31T23:59:59Z
region: VN
language: vi
product_category: all
source_uri: seed://payment-mismatch-v01/policies/payment-sync-v1-conflict
status: PUBLISHED
---

# Fixture xung đột về đồng bộ trạng thái thanh toán

Fixture này cố ý yêu cầu escalated thay vì tự động tạo proposal khi payment đã thành công.
Nếu đồng thời active với policy chính, retrieval phải trả conflict và workflow phải
escalate; không được tự chọn một policy.
