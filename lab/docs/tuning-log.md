# Tuning Log - RAG Pipeline (Day 08 Lab)

> A/B Rule: chỉ đổi MỘT biến mỗi lần để biết điều gì thật sự tạo ra cải thiện.

---

## Baseline (Sprint 2)

**Ngày:** 2026-04-13  
**Config:**

```text
retrieval_mode = "dense"
chunk_size = 400 tokens
overlap = 80 tokens
top_k_search = 10
top_k_select = 3
use_rerank = False
llm_model = gpt-4o-mini
judge_model = gemini-2.5-flash-lite
```

**Scorecard Baseline:**

| Metric | Average Score |
|--------|---------------|
| Faithfulness | 5.00 / 5 |
| Answer Relevance | 5.00 / 5 |
| Context Recall | 5.00 / 5 |
| Completeness | 4.50 / 5 |

**Câu hỏi yếu nhất:**

- `q07` - completeness = `3/5`  
  Câu trả lời đúng nguồn nhưng vẫn nêu tên cũ "Approval Matrix for System Access", chưa nói rõ tên hiện tại là `Access Control SOP`.
- `q05` - completeness = `4/5`  
  Câu trả lời đúng "5 lần" nhưng không nhắc thêm cách mở khóa qua helpdesk/SSO.
- `q06` - completeness = `4/5`  
  Câu trả lời mô tả đúng quy trình xử lý P1 nhưng không nhấn mạnh dòng "auto escalate lên Senior Engineer sau 10 phút" như expected answer.

**Giả thuyết nguyên nhân (Error Tree):**

- [x] Retrieval dense đã đủ tốt cho test set này.
- [ ] Indexing lỗi hoặc metadata thiếu.
- [ ] Top-k quá ít.
- [x] Vấn đề còn lại chủ yếu nằm ở generation/completeness, không phải recall.
- [x] Query alias vẫn lấy được đúng chunk nhưng answer chưa diễn đạt đúng tên tài liệu hiện tại.

---

## Variant 1 (Sprint 3) - Hybrid Retrieval

**Ngày:** 2026-04-13  
**Biến thay đổi:** thêm sparse BM25 score vào dense retrieval.

**Lý do chọn biến này:**

Corpus có cả query tự nhiên và query keyword/alias. Trước khi test, giả thuyết là hybrid sẽ giúp:

- `q07` tìm alias cũ "Approval Matrix"
- query có token kỹ thuật như `P1`, `Level 3`, `ERR-403-AUTH`

**Config thay đổi:**

```text
retrieval_mode = "hybrid"
dense_weight = 0.6
sparse_weight = 0.4
top_k_search = 10
top_k_select = 3
use_rerank = False
```

**Scorecard Variant 1:**

| Metric | Baseline | Variant 1 | Delta |
|--------|----------|-----------|-------|
| Faithfulness | 5.00/5 | 5.00/5 | +0.00 |
| Answer Relevance | 5.00/5 | 5.00/5 | +0.00 |
| Context Recall | 5.00/5 | 5.00/5 | +0.00 |
| Completeness | 4.50/5 | 4.30/5 | -0.20 |

**Nhận xét:**

- Cải thiện:  
  `q05` tăng từ `4/5` lên `5/5`, nhưng đây chỉ là cải thiện nhỏ ở generation output.
- Không đổi:  
  `q01`, `q03`, `q07`, `q08`, `q09`, `q10`.
- Kém hơn:  
  `q02` và `q04` giảm `1 điểm completeness`.  
  `q06` giảm từ `4/5` xuống `3/5`.

**Tại sao hybrid kém hơn ở q06:**

Query chứa token "escalation" và "P1". BM25 ưu tiên chunk `Section 4: Escalation khi cần thay đổi quyền hệ thống` trong `access-control-sop.md`, trong khi expected source đúng phải là `support/sla-p1-2026.pdf`. Dense baseline giữ đúng domain SLA tốt hơn.

**Kết luận:**

Variant hybrid **không tốt hơn baseline** trên test set hiện tại. Nó thành công về mặt kỹ thuật, có score và compare đầy đủ, nhưng không được chọn làm cấu hình đề xuất cuối cùng. Cấu hình được giữ lại sau Sprint 4 là:

```text
retrieval_mode = "dense"
top_k_search = 10
top_k_select = 3
use_rerank = False
```

---

## Nếu có thêm thời gian

Nếu có thêm 1 giờ, hướng tune hợp lý hơn là:

1. Query transform riêng cho alias (`Approval Matrix` -> `Access Control SOP`) thay vì bật sparse cho mọi query.
2. Domain-aware rerank để phân biệt `escalation P1` của SLA với `escalation quyền hệ thống`.
3. Prompt fix cho câu hỏi identify-document, ưu tiên nêu tên hiện tại của tài liệu thay vì chỉ lặp lại alias cũ.

---

## Tóm tắt học được

1. **Lỗi phổ biến nhất trong pipeline này là gì?**  
   Retrieval không phải điểm nghẽn lớn nhất; điểm mất nhiều nhất nằm ở `completeness`, khi answer đúng nguồn nhưng thiếu chi tiết hoặc diễn đạt chưa sát expected answer.

2. **Biến nào có tác động lớn nhất tới chất lượng?**  
   Trong test set này, việc thêm sparse score có tác động lớn nhất theo hướng xấu: nó không cải thiện recall nhưng có thể kéo query sang sai domain vì overlap từ khóa.

3. **Nếu có thêm 1 giờ, nhóm sẽ thử gì tiếp theo?**  
   Thử `query transform` cho alias và fallback abstain/domain filter, thay vì hybrid toàn cục.
