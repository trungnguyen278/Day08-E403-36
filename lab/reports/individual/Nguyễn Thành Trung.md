# Báo Cáo Cá Nhân — Lab Day 08: RAG Pipeline

**Họ và tên:** Nguyễn Thành Trung  
**Vai trò trong nhóm:** Index owner
**Ngày nộp:** 13/04/2026  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi đã làm gì trong lab này? (100-150 từ)

Tôi đảm nhiệm vai trò Index Owner, chịu trách nhiệm chính trong Sprint 1 — xây dựng toàn bộ indexing pipeline. Cụ thể, tôi đã refactor lại file `index.py` từ template có sẵn thành code chạy được end-to-end: implement hàm `get_embedding()` hỗ trợ cả OpenAI (`text-embedding-3-small`) lẫn Sentence Transformers local, viết lại `preprocess_document()` dùng regex để extract metadata từ header (source, department, effective_date, access), implement `chunk_document()` chia tài liệu theo heading `=== ... ===` rồi split tiếp theo kích thước với overlap, và hoàn thiện `build_index()` để embed + upsert vào ChromaDB. Tôi cũng implement `list_chunks()` và `inspect_metadata_coverage()` để nhóm có thể debug chất lượng index. Sau khi chạy thành công, index có 30 chunks từ 5 tài liệu với đầy đủ 5 metadata fields. Công việc này tạo nền tảng cho Sprint 2 (MinhPhuoc implement retrieval trên `rag_answer.py`) và Sprint 4 (Luong Anh chạy evaluation).

---

## 2. Điều tôi hiểu rõ hơn sau lab này (100-150 từ)

Sau lab này, tôi hiểu rõ hơn tầm quan trọng của chunking strategy đối với chất lượng retrieval. Ban đầu tôi nghĩ chỉ cần split theo kích thước cố định là đủ, nhưng thực tế cho thấy việc ưu tiên cắt tại ranh giới tự nhiên (heading, paragraph, câu) quan trọng hơn nhiều. Hàm `_find_split_end()` tôi viết phải tìm điểm cắt hợp lý (paragraph break `\n\n`, sentence boundary `. `, `? `) thay vì cắt cứng — nếu không chunk sẽ bị đứt giữa điều khoản, gây mất ngữ cảnh khi retrieve.

Tôi cũng hiểu rõ hơn vai trò của metadata trong RAG: 5 fields (source, section, department, effective_date, access) không chỉ phục vụ citation mà còn giúp debug khi pipeline trả lời sai — nhờ `inspect_metadata_coverage()` có thể nhanh chóng phát hiện chunk nào thiếu thông tin.

---

## 3. Điều tôi ngạc nhiên hoặc gặp khó khăn (100-150 từ)

Điều ngạc nhiên nhất là overlap giữa các chunk phức tạp hơn tôi tưởng. Hàm `_next_chunk_start()` phải tính toán vị trí bắt đầu chunk tiếp theo sao cho overlap không cắt giữa từ — tôi phải duyệt tìm whitespace boundary để đảm bảo chunk mới bắt đầu tại ranh giới từ hợp lệ. Nếu không cẩn thận, overlap sẽ tạo ra các chunk bắt đầu giữa chừng một câu, gây nhiễu cho embedding.

Khó khăn lớn nhất là xử lý header metadata: mỗi tài liệu có format header hơi khác nhau (có file dùng dòng trống phân cách, có file có tiêu đề in hoa). Tôi phải viết logic `in_header` với regex pattern matching để tự động phát hiện khi nào header kết thúc và body bắt đầu, thay vì hardcode số dòng. Việc này mất thời gian debug nhưng đảm bảo pipeline hoạt động đúng với cả 5 tài liệu.

---

## 4. Phân tích một câu hỏi trong scorecard (150-200 từ)

**Câu hỏi:** q07 — "Approval Matrix để cấp quyền hệ thống là tài liệu nào?"

**Phân tích:**

Ở baseline dense, pipeline retrieve đúng nguồn `it/access-control-sop.md` và trả lời đúng hướng, đạt faithfulness/relevance/recall đều 5/5. Tuy nhiên completeness chỉ đạt 3/5 — thấp nhất trong toàn bộ test set. Nguyên nhân nằm ở generation: câu trả lời vẫn dùng tên cũ "Approval Matrix for System Access" mà không nêu rõ tên hiện tại là "Access Control SOP". Đây là lỗi ở tầng generation, không phải indexing hay retrieval.

Từ góc nhìn indexing, tôi kiểm tra lại và xác nhận chunk chứa section "Phân cấp quyền truy cập" đã được index đúng với metadata `section` phù hợp. Vấn đề là trong tài liệu gốc, tên cũ và tên mới xuất hiện ở các đoạn khác nhau — chunk được retrieve chứa alias cũ nhưng không chứa mapping rõ ràng sang tên hiện tại.

Sang variant hybrid, điểm completeness không đổi cho q07. BM25 match được keyword "Approval Matrix" nhưng điều đó không giúp gì vì dense đã retrieve đúng chunk. Cải tiến thực sự cần thiết ở đây là query transform (map alias cũ sang tên mới) hoặc chỉnh prompt buộc LLM ưu tiên nêu tên tài liệu hiện hành, không phải thay đổi retrieval strategy.

---

## 5. Nếu có thêm thời gian, tôi sẽ làm gì? (50-100 từ)

Tôi sẽ cải thiện chunking bằng cách thêm cross-reference metadata: khi một section nhắc đến tài liệu khác (ví dụ "xem thêm SLA P1"), ghi lại liên kết đó vào metadata chunk. Điều này sẽ giúp retrieval cho các câu hỏi multi-hop như q06 (cross-doc) mà scorecard cho thấy baseline chỉ đạt completeness 4/5. Ngoài ra, tôi sẽ thử chunk size nhỏ hơn (300 tokens) cho các tài liệu FAQ vì chúng có cấu trúc Q&A ngắn, chunk 400 tokens có thể gộp nhiều câu hỏi khác nhau vào cùng một chunk.
