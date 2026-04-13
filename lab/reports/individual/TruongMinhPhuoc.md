# Báo Cáo Cá Nhân — Lab Day 08: RAG Pipeline

**Họ và tên:** Trương Minh Phước  
**Vai trò trong nhóm:** Retrieval Owner  
**Ngày nộp:** 13/04/2026  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi đã làm gì trong lab này? (100-150 từ)

Trong dự án xây dựng RAG Pipeline này, tôi đảm nhận vai trò **Retrieval Owner**, chịu trách nhiệm chính trong việc thiết kế và tối ưu hóa quy trình truy xuất dữ liệu. Tôi tập trung vào Sprint 2 và 3, cụ thể là xây dựng hệ thống **Hybrid Retrieval** kết hợp giữa Dense Search (Cosine Similarity trên vector embeddings của ChromaDB) và Sparse Search (thuật toán BM25 dùng Rank-BM25). 

Tôi đã thực hiện implement hàm `retrieve_hybrid` với cơ chế trọng số tùy chỉnh (0.6 cho Dense và 0.4 cho Sparse) để tận dụng thế mạnh của cả hai phương pháp. Ngoài ra, tôi còn tích hợp thêm kỹ thuật **Query Expansion** (mở rộng truy vấn dựa trên từ điển alias) và **Lexical Rerank** để ưu tiên các đoạn văn bản có mức độ overlap từ khóa cao với câu hỏi. Những đóng góp của tôi đóng vai trò là "xương sống" cung cấp ngữ cảnh chính xác cho Generation Owner, giúp hệ thống giảm thiểu hiện tượng ảo giác (hallucination) do thiếu thông tin.

---

## 2. Điều tôi hiểu rõ hơn sau lab này (100-150 từ)

Sau lab này, tôi đã hiểu sâu sắc hơn về sự khác biệt thực tiễn giữa **Dense Retrieval** và **Sparse Retrieval**. Trước đây, tôi thường nghĩ Vector Search (Dense) là giải pháp vạn năng vì nó hiểu ngữ nghĩa. Tuy nhiên, khi đối mặt với các truy vấn chứa thuật ngữ kỹ thuật chính xác hoặc tên riêng (ví dụ: "ERR-403-AUTH" hay "Approval Matrix"), Vector Search đôi khi trả về các kết quả có "vẻ ngoài" giống nhau về ngữ cảnh nhưng lại sai lệch hoàn toàn về thực thể. 

BM25 (Sparse Search) đã lấp đầy khoảng trống đó bằng cách bám sát các keyword cốt lõi. Tôi cũng hiểu rõ hơn về tầm quan trọng của việc **Score Normalization** — làm thế nào để kết hợp hai loại điểm số có thang đo khác nhau (cosine similarity từ 0-1 và BM25 score không giới hạn) về một hệ quy chiếu chung trước khi cộng dồn trọng số. Concept về **Retrieval-Augmented Generation** lúc này không còn là lý thuyết mà là một bài toán cân bằng giữa độ phủ (Recall) và độ chính xác (Precision).

---

## 3. Điều tôi ngạc nhiên hoặc gặp khó khăn (100-150 từ)

Điều khiến tôi ngạc nhiên nhất là việc tăng thêm dữ liệu truy xuất không phải lúc nào cũng tốt. Ban đầu, tôi giả thuyết rằng nếu mình lấy `top_k` lớn hơn và dùng nhiều phương pháp tìm kiếm hơn thì LLM sẽ trả lời đầy đủ hơn. Thực tế khi chuyển sang `variant_hybrid`, dù điểm Faithfulness và Relevance vẫn đạt tuyệt đối (5.0), nhưng điểm **Completeness** lại có xu hướng giảm nhẹ (từ 4.50 xuống 4.30). 

Khó khăn lớn nhất tôi gặp phải là việc debug hiện tượng xao nhãng ngữ cảnh (Context Noise). Khi Hybrid Search mang lại quá nhiều đoạn văn bản từ các nguồn khác nhau, LLM có thể bị "ngợp" và bỏ lỡ một số chi tiết nhỏ nhưng quan trọng trong yêu cầu của người dùng. Việc điều chỉnh tham số `MIN_RELEVANCE_SCORE` để loại bỏ các "nhiễu" này tiêu tốn khá nhiều thời gian vì nếu đặt quá cao sẽ mất thông tin, đặt quá thấp lại làm giảm chất lượng câu trả lời.

---

## 4. Phân tích một câu hỏi trong scorecard (150-200 từ)

**Câu hỏi:** q07 - "Approval Matrix để cấp quyền hệ thống là tài liệu nào?"

**Phân tích:**
Đây là một câu hỏi thuộc dạng "Hard" vì nó sử dụng một thuật ngữ cũ ("Approval Matrix") vốn không còn là tiêu đề chính trong bộ tài liệu mới (đã đổi tên thành "Access Control SOP"). 

- **Baseline (Dense Search):** Thường gặp khó khăn nếu embedding model không nhận diện được mối quan hệ chặt chẽ giữa cụm "Approval Matrix" và "Access Control SOP" trong không gian vector hẹp của dataset này.
- **Variant (Hybrid Retrieval):** Kết quả đạt điểm tối đa về Context Recall (5.0). Nhờ có cơ chế **Query Expansion** mà tôi cài đặt, hệ thống tự động ánh xạ "approval matrix" sang "access control sop". Đồng thời, BM25 đã bắt được từ khóa "Approval" và "Access Control" trong phần metadata và nội dung text, giúp đẩy đoạn chunk từ file `it/access-control-sop.md` lên vị trí top đầu với điểm số vượt trội.
- **Lỗi:** Tuy nhiên, điểm Completeness ở câu này trong Variant chỉ đạt 3.0. Nguyên nhân là do Hybrid Search cũng kéo về một số tài liệu khác liên quan đến "Access" nhưng không trực tiếp trả lời về "tên tài liệu", khiến câu trả lời của LLM bị dàn trải. Đây là minh chứng cho việc retrieval quá tốt về mặt Recall đôi khi gây tác dụng ngược cho khâu Generation nếu không có bước lọc/rerank đủ mạnh.

---

## 5. Nếu có thêm thời gian, tôi sẽ làm gì? (50-100 từ)

Nếu có thêm thời gian, tôi sẽ triển khai một lớp **Neural Re-ranker** (như Cohere Rerank hoặc một mô hình Cross-Encoder nhỏ) thay thế cho hàm `rerank` thủ công hiện tại. Tôi tin rằng việc chấm điểm lại mối quan hệ giữa Query và Content ở cấp độ câu (sentence-level) sau khi đã có kết quả từ Hybrid Search sẽ giúp loại bỏ hoàn toàn các context nhiễu, từ đó phục hồi lại điểm **Completeness** đang bị sụt giảm mà vẫn duy trì được Recall cao.

---
