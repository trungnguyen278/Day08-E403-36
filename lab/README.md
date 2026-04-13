# Lab Day 08 — RAG Pipeline

Repo này là bài lab RAG cho nhóm CS + IT Helpdesk. Hệ thống hiện tại đã có đủ các phần chính:
- build index từ tài liệu nội bộ
- truy vấn RAG bằng CLI
- giao diện web local để hỏi đáp
- evaluation và scorecard kết quả

## Thành phần chính

| File | Vai trò |
|---|---|
| `index.py` | Tiền xử lý tài liệu, chunking, embedding, upsert vào ChromaDB |
| `rag_answer.py` | Retrieve, rerank tùy chọn, sinh câu trả lời, chạy CLI và web server |
| `eval.py` | Chạy scorecard và lưu kết quả evaluation |
| `ui/index.html` | Giao diện web một file duy nhất, gồm HTML + CSS + JavaScript |
| `.env.example` | Mẫu cấu hình provider, model và API key |

## Dữ liệu và đầu ra

- Tài liệu nguồn: [`data/docs/`](data/docs/)
- Bộ câu hỏi test: [`data/test_questions.json`](data/test_questions.json)
- Tài liệu kiến trúc và tuning: [`docs/`](docs/)
- Báo cáo cá nhân: [`reports/individual/`](reports/individual/)
- Kết quả đánh giá: [`results/`](results/)
- Tiêu chí chấm điểm: [`SCORING.md`](SCORING.md)

## Tài liệu đang có

### Docs
- [`docs/architecture.md`](docs/architecture.md)
- [`docs/tuning-log.md`](docs/tuning-log.md)
- [`docs/rag-architecture-sprint1-2.md`](docs/rag-architecture-sprint1-2.md)

### Reports cá nhân
- [`reports/individual/template.md`](reports/individual/template.md)
- [`reports/individual/TruongMinhPhuoc.md`](reports/individual/TruongMinhPhuoc.md)
- [`reports/individual/pham_quoc_vuong.md`](reports/individual/pham_quoc_vuong.md)
- [`reports/individual/nguyen_huy_tu.md`](reports/individual/nguyen_huy_tu.md)
- [`reports/individual/LươngHoàngAnh.md`](<reports/individual/LươngHoàngAnh.md>)

### Results
- [`results/scorecard_baseline.md`](results/scorecard_baseline.md)
- [`results/scorecard_variant.md`](results/scorecard_variant.md)
- [`results/ab_comparison.csv`](results/ab_comparison.csv)
- [`results/ab_summary.md`](results/ab_summary.md)
- [`results/judge_cache.json`](results/judge_cache.json)

## Yêu cầu môi trường

- Windows PowerShell
- Python 3.10+ khuyến nghị
- API key cho ít nhất một LLM provider

Mẫu `.env` hiện tại hỗ trợ:
- `LLM_PROVIDER=openai` hoặc `gemini`
- `EMBEDDING_PROVIDER=openai` hoặc `local`

Xem mẫu tại [`.env.example`](.env.example).

## Cài đặt

### 1. Vào thư mục lab
```powershell
cd F:\vin\Day08-E403-36\lab
```

### 2. Tạo virtual environment
```powershell
python -m venv .venv
```

### 3. Kích hoạt `.venv`
```powershell
.\.venv\Scripts\Activate.ps1
```

Nếu PowerShell chặn script:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 4. Cài thư viện
```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 5. Tạo file `.env`
```powershell
Copy-Item .env.example .env
```

Sau đó điền API key phù hợp:
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=...
LLM_MODEL=gpt-4o-mini
EMBEDDING_PROVIDER=openai
```

## Cách chạy

### 1. Build index
```powershell
python index.py
```

Script này sẽ:
- đọc các file trong `data/docs/`
- preprocess và chia chunk
- tạo embedding
- ghi dữ liệu vào ChromaDB
- in preview chunk và metadata coverage

### 2. Chạy một query bằng CLI
```powershell
python rag_answer.py --query "SLA xử lý ticket P1 là bao lâu?"
```

Ví dụ với cấu hình cụ thể:
```powershell
python rag_answer.py --query "Ai phải phê duyệt để cấp quyền Level 3?" --mode hybrid --rerank --verbose
```

Các tùy chọn chính:
- `--mode dense|sparse|hybrid`
- `--rerank`
- `--verbose`

### 3. Chạy web UI
```powershell
python rag_answer.py --serve
```

Mặc định server chạy tại:
```text
http://127.0.0.1:8000
```

UI hiện tại:
- dùng duy nhất file [`ui/index.html`](ui/index.html)
- có trạng thái health check
- gửi câu hỏi qua `POST /api/ask`
- hỗ trợ chọn retrieval mode, top-k và rerank
- hiển thị answer kèm evidence chunks

### 4. Chạy evaluation
```powershell
python eval.py
```

Kết quả sẽ được ghi vào thư mục [`results/`](results/).

## Luồng chạy đề xuất

```powershell
cd F:\vin\Day08-E403-36\lab
.\.venv\Scripts\Activate.ps1
python index.py
python rag_answer.py --serve
```

Sau đó mở trình duyệt tại `http://127.0.0.1:8000`.

## Chạy không cần activate `.venv`

```powershell
.\.venv\Scripts\python.exe index.py
.\.venv\Scripts\python.exe rag_answer.py --serve
.\.venv\Scripts\python.exe eval.py
```

## Gợi ý kiểm tra nhanh

### Backend
```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/health
```

### Query mẫu
- `SLA xử lý ticket P1 là bao lâu?`
- `Ai phải phê duyệt để cấp quyền Level 3?`
- `Approval Matrix để cấp quyền hệ thống là tài liệu nào?`

## Lưu ý

- Cần chạy `index.py` trước khi kỳ vọng RAG trả lời đúng.
- Nếu thiếu API key, phần generation sẽ không hoạt động đúng.
- `favicon.ico` chưa được cấu hình, nên trình duyệt có thể log `404 /favicon.ico`; điều này không ảnh hưởng chức năng chính.
- `eval.py` hiện lưu scorecard vào [`results/`](results/) và dùng dữ liệu từ [`data/test_questions.json`](data/test_questions.json).
