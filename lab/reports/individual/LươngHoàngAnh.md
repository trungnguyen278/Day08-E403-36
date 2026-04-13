# Báo Cáo Cá Nhân — Lab Day 08: RAG Pipeline

**Họ và tên:** Anh Luong  
**Vai trò trong nhóm:** Eval Owner  
**Ngày nộp:** 13/04/2026  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi đã làm gì trong lab này? (100-150 từ)

Với vai trò là Eval Owner trong quy trình xây dựng RAG Pipeline, tôi chủ yếu tham gia vào Sprint đánh giá và đo lường (Evaluation Loop). Nhiệm vụ cụ thể của tôi tập trung vào việc định thiết lập và kích hoạt script đánh giá hiệu năng hệ thống nhằm trích xuất các chỉ số định lượng về Faithfulness, Relevance, Context Recall và Completeness thông qua bộ dữ liệu `test_questions.json` đa dạng độ khó. Thông qua việc thực hiện A/B test giữa hệ thống `baseline_dense` và hệ thống được cải tiến `variant_hybrid` và phân tích kết quả dữ liệu trong các file `scorecard_baseline.md` và `scorecard_variant.md`, tôi đã cung cấp những insight, biểu đồ feedback quan trọng cho Retrieval Owner và Generation Owner về các câu hỏi hệ thống trả lời còn yếu (đặc biệt là lỗi giảm Completeness ở Variant), từ đó giúp nhóm đưa ra căn cứ nhằm tinh chỉnh mô hình và bộ prompt cải thiện.

---

## 2. Điều tôi hiểu rõ hơn sau lab này (100-150 từ)

Sau lab này, tôi đã thực sự hiểu sâu sắc về khái niệm **Evaluation Loop** và cách định lượng hiệu suất của công nghệ RAG thông qua thiết kế đo lường tự động. Trước đây, tôi chỉ đánh giá AI "đúng/sai" một cách cảm tính và khá phiến diện. Nhưng thông qua phương pháp đánh giá hiện đại, tôi hiểu rằng hệ thống đòi hỏi bóc tách rõ rệt: Faithfulness (đảm bảo không bịa đặt sai sự thật dựa trên context), Relevance (bám sát truy vấn mong muốn), Context Recall (truy xuất đúng/đủ tài liệu khớp ngữ nghĩa từ vector database) và Completeness (đảm bảo đáp án bao phủ trọn vẹn ngữ nghĩa đầy đủ). Tôi nhận thức rõ ràng hơn rằng Grounded Prompt có sức tác động phi thường để cản bước hallucination — thể hiện mạnh nhất qua việc mô hình dứt khoát "Abstain" (kết luận rằng không có cơ sở dữ kiện) trong những trường hợp không có dữ liệu gốc để trả lời.

---

## 3. Điều tôi ngạc nhiên hoặc gặp khó khăn (100-150 từ)

Điều khiến tôi ngạc nhiên nhất là việc áp dụng chiến lược cấu hình `variant_hybrid` (kết hợp vector và keyword search) không mang lại sự cải thiện hoàn hảo trên mọi khía cạnh. Cụ thể, khi nhìn vào báo cáo `ab_summary.md`, dễ dàng thấy các chỉ số cốt lõi là Faithfulness, Relevance và Context Recall đều duy trì mức chạm trần (5.0), nhưng điểm Completeness thực lại đối mặt với biến động giảm từ 4.50 xuống chỉ còn 4.30. Ban đầu, tôi thiết lập giả thuyết hybrid search là lá chắn thép giúp mở rộng ngữ cảnh, đẩy Completeness cao hơn. Thực tế chứng minh lượng context đồ sộ (khi chứa thêm những cụm từ không trọng tâm) đôi khi gây xao nhãng LLM, khiến câu trả lời rơi rụng một số chi tiết và mất tính trọn vẹn. Khó khăn nhức nhối nhất lúc đầu là liên tục gặp lỗi giá trị Context Recall báo `None` với một số câu hỏi bẫy, buộc tôi phải tìm lại thuật toán để hiểu do `expected_sources` đang không có phần tử nào.

---

## 4. Phân tích một câu hỏi trong scorecard (150-200 từ)

**Câu hỏi:** q09 - "ERR-403-AUTH là lỗi gì và cách xử lý?"

**Phân tích:**
Đây là một dạng câu hỏi "Insufficient Context" trong tập `test_questions.json`, được tích hợp một cách có chủ đích với dàn tài liệu cho trước rỗng, dùng để thẩm định khả năng tránh bịa đặt của mô hình Generator.
Ở bài test Baseline, hệ thống phản ứng rất chuẩn mực, nhận diện rõ viễn cảnh trống thông tin và báo cáo trả lời từ chối an toàn. Các chỉ tiêu Faithfulness, Relevance và Completeness duy trì ổn định. Điều lạ ở mặt thống kê là Context Recall bị hạ gục thành `None`. Về mặt cấu trúc, khi chia số tài liệu hợp lệ cho tổng số liệu kỳ vọng `expected_sources` bằng 0, phép tính tạo giá trị bất định.
Tương tự, nhảy sang Variant Hybrid, thuật toán lôi thêm 3 tài liệu mờ nhạt (như `access-control-sop.md`, `refund-v4.pdf`...) nhưng Generation Prompt đã kìm cương mô hình an toàn mà không sinh hallucination. Tổng quan, điểm yếu không nằm ở retrieval hay generation, mà nằm ở công cụ evaluation: Công thức Context Recall còn yếu kém và không thể phân loại logic chấm điểm an toàn cho hành vi “chủ đích không cần tài liệu”. Nó là giới hạn về triết lý chấm điểm hơn là yếu điểm của bot.

---

## 5. Nếu có thêm thời gian, tôi sẽ làm gì? (50-100 từ)

Xác định được nút thắt đánh giá, tôi ưu tiên hàng đầu vào phát triển cập nhật script `eval.py`: bổ sung luật logic xử lý riêng hàm **Context Recall** để gán điểm trọn vẹn 5.0 khi phát hiện query có mảng `expected_sources` là Rỗng mà chatbot vẫn duy trì Faithfulness. Đồng thời, tôi dành thời gian đào sâu nhóm câu hỏi hổng điểm (như q06, q07) và làm việc với team Retrieval nhằm thay đổi thông số "Alpha ratio" điều áp tỉ trọng kết quả trả về của Hybrid Search, giảm độ nhiễu context và phục hồi lại điểm Completeness.
