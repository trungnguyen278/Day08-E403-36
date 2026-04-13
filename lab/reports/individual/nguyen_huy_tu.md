# Báo Cáo Cá Nhân — Lab Day 08: RAG Pipeline

**Họ và tên:** Nguyễn Huy Tú  
**Vai trò trong nhóm:** Tech Lead  
**Ngày nộp:** 13/04/2026  

---

## 1. Tôi đã làm gì trong lab này? (100-150 từ)

Trong lab Day 08, tôi giữ vai trò Tech Lead nên phần việc chính là chốt hướng thiết kế, chia sprint và giữ cho pipeline RAG đi đúng giả thuyết kiểm thử. Tôi cùng nhóm thống nhất kiến trúc end-to-end gồm `index.py` cho indexing, `rag_answer.py` cho retrieval + generation và `eval.py` cho scorecard/A/B. Ở Sprint 1 và 2, tôi ưu tiên khóa baseline rõ ràng: chunk size `400`, overlap `80`, dense retrieval trên ChromaDB, top-k search `10`, top-k select `3`, grounded prompt với citation và abstain khi thiếu context. Ngoài phần pipeline, tôi làm thêm web UI tại `ui/index.html` và nối với backend qua `GET /api/health`, `POST /api/ask` để nhóm có thể demo trực tiếp, đổi retrieval mode, bật/tắt rerank và xem các chunk/sources được dùng để sinh đáp án. Sang Sprint 3, tôi quyết định cho nhóm chỉ thử đúng một biến là `hybrid retrieval` để tuân thủ A/B rule.

---

## 2. Điều tôi hiểu rõ hơn sau lab này (100-150 từ)

Sau lab này, tôi hiểu rõ hơn rằng tối ưu RAG phải nhìn như một chuỗi ràng buộc, không thể gom mọi lỗi về “retrieval chưa đủ tốt”. Trước đó, tôi có xu hướng nghĩ rằng chỉ cần tăng recall hoặc thêm hybrid search là chất lượng answer sẽ tăng. Nhưng khi nhìn vào scorecard, baseline đã đạt `5.0` ở faithfulness, relevance và context recall; điểm còn mất chủ yếu nằm ở completeness. Điều đó có nghĩa là retrieval đúng tài liệu chưa chắc kéo theo answer đủ ý. Tôi cũng hiểu rõ hơn rằng UI trong bài toán RAG không chỉ để demo đẹp hơn. Khi giao diện hiển thị rõ answer, source, config và các chunk dùng thật, việc debug retrieval/generation trở nên cụ thể hơn rất nhiều. Với vai trò tech lead, bài học lớn nhất là phải xác định đúng bottleneck trước khi tối ưu.

---

## 3. Điều tôi ngạc nhiên hoặc gặp khó khăn (100-150 từ)

Điều làm tôi ngạc nhiên nhất là biến thể hybrid chạy đúng về mặt kỹ thuật nhưng lại không thắng baseline. Giả thuyết ban đầu của tôi là corpus có cả ngôn ngữ tự nhiên lẫn alias/keyword như `Approval Matrix`, `P1`, `ERR-403-AUTH`, nên thêm BM25 vào dense retrieval có thể giúp bắt đúng hơn các truy vấn chứa từ khóa đặc thù. Thực tế, metric tổng cho thấy faithfulness, relevance và context recall đều không đổi, còn completeness lại giảm từ `4.50` xuống `4.30`. Khó khăn lớn nhất là phân biệt rõ lỗi nằm ở retrieval hay generation, đồng thời giữ cho UI mỏng nhưng đủ hữu ích để soi lỗi. Tôi phải đồng bộ payload giữa form và backend, xử lý loading/error state và render các score/chunk sao cho nhóm nhìn vào là thấy ngay vì sao query bị lệch domain. Trường hợp `q06` là ví dụ rõ nhất về lexical overlap trong retrieval.

---

## 4. Phân tích một câu hỏi trong scorecard (150-200 từ)

**Câu hỏi:** `q06` - "Escalation trong sự cố P1 diễn ra như thế nào?"

**Phân tích:**

Đây là câu hỏi tôi thấy có giá trị để ra quyết định kỹ thuật vì nó cho thấy sự khác nhau giữa baseline và variant. Ở baseline dense, hệ thống retrieve đúng nguồn `support/sla-p1-2026.pdf`, nên answer giữ được logic chính của quy trình P1. Faithfulness, relevance và context recall đều đạt `5/5`; completeness đạt `4/5` vì câu trả lời chưa nhấn đủ chi tiết “auto escalate lên Senior Engineer sau 10 phút”. Với baseline, lỗi chính nằm ở generation.

Sang variant hybrid, completeness giảm tiếp xuống `3/5`. Điểm quan trọng là nguồn trả về đã lệch sang `it/access-control-sop.md`, cụ thể là section có chữ “Escalation” nhưng nói về thay đổi quyền hệ thống chứ không phải xử lý sự cố P1. Như vậy, ở variant, lỗi gốc đã chuyển sang retrieval. Generation vẫn grounded, không bịa, nhưng nó grounded trên bằng chứng sai domain nên output không thể đủ ý. Với góc nhìn tech lead, đây là case đủ mạnh để bác bỏ giả thuyết “hybrid lúc nào cũng tốt hơn”.

---

## 5. Nếu có thêm thời gian, tôi sẽ làm gì? (50-100 từ)

Nếu có thêm thời gian, tôi sẽ không bật thêm nhiều biến cùng lúc mà tiếp tục tune có kiểm soát. Ưu tiên đầu tiên là thử `query transform` cho alias như `Approval Matrix` -> `Access Control SOP`, vì đây là nhu cầu thật nhưng không cần hybrid toàn cục. Ưu tiên thứ hai là thêm domain-aware rerank hoặc filter nhẹ cho các query kiểu `P1`, `SLA`, `escalation`, vì kết quả eval đã chỉ ra lexical overlap là nguyên nhân trực tiếp làm retrieval lệch domain ở `q06`. Về UI, tôi muốn bổ sung chế độ so sánh baseline/variant ngay trên cùng một màn hình để nhóm nhìn được delta về source và chunk mà không phải đọc log thủ công.
