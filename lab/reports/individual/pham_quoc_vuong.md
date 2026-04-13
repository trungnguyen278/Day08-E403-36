# Báo Cáo Cá Nhân — Lab Day 08: RAG Pipeline

**Họ và tên:** Phạm Quốc Vương  
**Vai trò trong nhóm:** Documentation Owner  
**Ngày nộp:** 13/4/2026  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi đã làm gì trong lab này? (100-150 từ)

Trong lab Day 08, mình đảm nhiệm vai trò Documentation Owner, chịu trách nhiệm tổng hợp và chuẩn hóa tài liệu kỹ thuật của pipeline RAG theo tiến độ sprint. Cụ thể, mình viết và hoàn thiện `docs/architecture.md` để mô tả end-to-end flow từ indexing (preprocess → chunk → embed → store) đến retrieval/generation và evaluation (LLM-as-Judge). Đồng thời, mình ghi lại `docs/tuning-log.md` theo đúng A/B rule (mỗi lần chỉ đổi một biến) để trace được nguyên nhân thay đổi điểm số. Công việc của mình kết nối trực tiếp với Retrieval Owner và Eval Owner: mình cập nhật cấu hình baseline/variant, diễn giải kết quả scorecard/so sánh A/B, và chốt lại “cấu hình đề xuất” để nhóm demo/benchmark thống nhất.

---

## 2. Điều tôi hiểu rõ hơn sau lab này (100-150 từ)

Sau lab này, mình hiểu rõ hơn ranh giới giữa “retrieval tốt” và “answer tốt”. Trên test set hiện tại, dense retrieval đã đạt context recall cao, nhưng completeness vẫn bị mất điểm do generation không nhấn đúng các chi tiết kỳ vọng (ví dụ: thời gian auto-escalate). Điều này giúp mình nhìn pipeline theo tư duy “error budgeting”: khi faithfulness/relevance/recall đều cao, tối ưu retrieval thêm đôi khi không còn mang lại lợi ích, thậm chí gây lệch domain. Mình cũng hiểu rõ hơn cách dùng A/B rule trong RAG: nếu không khóa các biến còn lại (top-k, rerank, prompt), rất khó kết luận điều gì thật sự làm điểm số đổi.

---

## 3. Điều tôi ngạc nhiên hoặc gặp khó khăn (100-150 từ)

Điều ngạc nhiên nhất là hybrid retrieval (dense + BM25) không cải thiện baseline trong khi giả thuyết ban đầu khá hợp lý (corpus có keyword/alias như “Approval Matrix”, “P1”, “ERR-403-AUTH”). Khó khăn nằm ở việc giải thích “tại sao điểm completeness giảm” dù context recall không đổi. Khi đọc các case giảm (đặc biệt `q06`), mình nhận ra sparse BM25 có thể “overfit” theo từ khóa trùng nhau nhưng khác domain: query có “escalation” vừa xuất hiện trong SOP access control lẫn SLA P1. Dense baseline giữ domain tốt hơn, còn hybrid lại bị kéo sang chunk không phù hợp, khiến câu trả lời thiếu đúng trọng tâm expected answer. Đây là bài học quan trọng về lexical overlap trong retrieval.

---

## 4. Phân tích một câu hỏi trong scorecard (150-200 từ)

**Câu hỏi:** `q06` (escalation trong xử lý P1)

**Phân tích:**

Ở baseline dense, câu trả lời bám đúng nguồn SLA P1 và mô tả đúng quy trình chính nên điểm faithfulness/relevance/recall đều tốt. Tuy nhiên completeness chỉ đạt 4/5 vì thiếu một ý “đinh” trong expected answer: nhấn mạnh hành vi auto escalate lên Senior Engineer sau 10 phút. Lỗi ở đây nghiêng về generation: context có thể đã chứa thông tin, nhưng prompt/format trả lời chưa “ưu tiên” các ràng buộc định lượng (10 phút) nên output bị thiếu chi tiết quan trọng.

Sang Variant 1 (hybrid), completeness giảm thêm (tới 3/5) dù các metric khác không tăng. Nguyên nhân là retrieval bắt đầu lệch: vì query có token “escalation” và “P1”, BM25 ưu tiên đoạn “Escalation” trong `access-control-sop.md` (liên quan escalation khi thay đổi quyền), trong khi expected source đúng là `support/sla-p1-2026.pdf`. Khi context bị kéo sang sai domain, generation vẫn “grounded” nhưng grounded vào bằng chứng không đúng bài toán, làm completeness giảm. Trường hợp này cho thấy hybrid không phải “mặc định tốt hơn” nếu không có domain control.

---

## 5. Nếu có thêm thời gian, tôi sẽ làm gì? (50-100 từ)

Mình sẽ ưu tiên các cải tiến “có mục tiêu” thay vì bật hybrid toàn cục. Thứ nhất, thêm query transform cho alias (ví dụ map “Approval Matrix” → “Access Control SOP”) để xử lý truy vấn kiểu tên cũ/tên mới. Thứ hai, thêm domain-aware filter hoặc rerank nhẹ để phân biệt “escalation P1” (SLA) với “escalation quyền hệ thống” (SOP), vì eval cho thấy lexical overlap làm hybrid dễ lệch domain. Thứ ba, chỉnh grounded prompt để bắt buộc trả lời các mốc định lượng (như “10 phút”) khi câu hỏi có dấu hiệu SLA/timing.

