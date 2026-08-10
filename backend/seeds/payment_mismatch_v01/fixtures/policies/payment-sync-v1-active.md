---
policy_type: payment_status_sync
title: Đồng bộ trạng thái thanh toán thành công
version: 1.0.0
effective_from: 2026-01-01T00:00:00Z
effective_to: 2099-12-31T23:59:59Z
region: VN
language: vi
product_category: all
source_uri: seed://payment-mismatch-v01/policies/payment-sync-v1-active
status: PUBLISHED
---

# Đồng bộ trạng thái thanh toán thành công

## Điều kiện áp dụng

Chỉ đề xuất `sync_payment_status` khi payment thuộc đúng customer và order, payment có
trạng thái `SUCCEEDED`, order vẫn có `payment_status=PENDING`, số tiền và currency khớp.

## Kiểm soát

Support Agent phải phê duyệt proposal còn hạn và đúng version/hash. Backend phải đọc lại
order sau thao tác; Ticket chỉ được resolve khi Action Execution là `VERIFIED`.
