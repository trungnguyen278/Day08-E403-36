"""
index.py - Sprint 1: Build RAG Index
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()


DOCS_DIR = Path(__file__).parent / "data" / "docs"
CHROMA_DB_DIR = Path(__file__).parent / "chroma_db"
COLLECTION_NAME = "rag_lab"

CHUNK_SIZE = 400
CHUNK_OVERLAP = 80

EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "openai").strip().lower()
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small").strip()

_OPENAI_CLIENT = None
_SENTENCE_TRANSFORMER = None


def _get_openai_client():
    global _OPENAI_CLIENT

    if _OPENAI_CLIENT is None:
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("Thiếu OPENAI_API_KEY trong .env để tạo embedding.")
        _OPENAI_CLIENT = OpenAI(api_key=api_key)
    return _OPENAI_CLIENT


def _get_sentence_transformer(model_name: str):
    global _SENTENCE_TRANSFORMER

    if _SENTENCE_TRANSFORMER is None:
        from sentence_transformers import SentenceTransformer

        _SENTENCE_TRANSFORMER = SentenceTransformer(model_name)
    return _SENTENCE_TRANSFORMER


def _normalize_text(text: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def preprocess_document(raw_text: str, filepath: str) -> Dict[str, Any]:
    """
    Extract metadata từ header và làm sạch phần body.
    """
    metadata = {
        "source": filepath,
        "section": "",
        "department": "unknown",
        "effective_date": "unknown",
        "access": "internal",
    }

    header_pattern = re.compile(r"^(Source|Department|Effective Date|Access):\s*(.+?)\s*$")
    key_map = {
        "Source": "source",
        "Department": "department",
        "Effective Date": "effective_date",
        "Access": "access",
    }

    content_lines: List[str] = []
    in_header = True

    for raw_line in raw_text.splitlines():
        line = raw_line.rstrip()

        if in_header:
            match = header_pattern.match(line)
            if match:
                metadata[key_map[match.group(1)]] = match.group(2).strip()
                continue

            if not line.strip():
                continue

            if line.strip().isupper():
                continue

            in_header = False

        content_lines.append(line)

    return {
        "text": _normalize_text("\n".join(content_lines)),
        "metadata": metadata,
    }


def chunk_document(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Chunk theo heading `=== ... ===`, sau đó split tiếp nếu section dài.
    """
    text = doc["text"]
    base_metadata = doc["metadata"].copy()
    chunks: List[Dict[str, Any]] = []

    matches = list(re.finditer(r"^===\s*(.*?)\s*===$", text, flags=re.MULTILINE))
    if not matches:
        return _split_by_size(text=text, base_metadata=base_metadata, section="General")

    first_heading_start = matches[0].start()
    preamble = text[:first_heading_start].strip()
    if preamble:
        chunks.extend(_split_by_size(preamble, base_metadata, section="General"))

    for index, match in enumerate(matches):
        section = match.group(1).strip()
        content_start = match.end()
        content_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section_text = text[content_start:content_end].strip()
        if section_text:
            chunks.extend(_split_by_size(section_text, base_metadata, section=section))

    return chunks


def _find_split_end(text: str, start: int, chunk_chars: int) -> int:
    if start + chunk_chars >= len(text):
        return len(text)

    min_end = min(len(text), start + max(int(chunk_chars * 0.55), 1))
    max_end = min(len(text), start + chunk_chars + 200)
    candidate_window = text[min_end:max_end]

    for delimiter in ("\n\n", "\n", ". ", "? ", "! ", "; ", ": "):
        position = candidate_window.rfind(delimiter)
        if position != -1:
            return min_end + position + len(delimiter)

    return min(len(text), start + chunk_chars)


def _next_chunk_start(text: str, current_end: int, overlap_chars: int) -> int:
    if current_end >= len(text):
        return len(text)

    next_start = max(0, current_end - overlap_chars)
    while next_start < current_end and not text[next_start].isspace():
        next_start += 1
    while next_start < len(text) and text[next_start].isspace():
        next_start += 1

    return min(next_start, current_end)


def _split_by_size(
    text: str,
    base_metadata: Dict[str, str],
    section: str,
    chunk_chars: int = CHUNK_SIZE * 4,
    overlap_chars: int = CHUNK_OVERLAP * 4,
) -> List[Dict[str, Any]]:
    """
    Split text dài theo ngưỡng ký tự, ưu tiên cắt ở ranh giới tự nhiên.
    """
    normalized = _normalize_text(text)
    if not normalized:
        return []

    if len(normalized) <= chunk_chars:
        return [{"text": normalized, "metadata": {**base_metadata, "section": section}}]

    chunks: List[Dict[str, Any]] = []
    start = 0

    while start < len(normalized):
        end = _find_split_end(normalized, start, chunk_chars)
        chunk_text = normalized[start:end].strip()
        if not chunk_text:
            break

        chunks.append({"text": chunk_text, "metadata": {**base_metadata, "section": section}})

        if end >= len(normalized):
            break

        next_start = _next_chunk_start(normalized, end, overlap_chars)
        if next_start <= start:
            next_start = min(start + chunk_chars, len(normalized))
        start = next_start

    return chunks


def get_embedding(text: str) -> List[float]:
    """
    Tạo embedding cho chunk hoặc query bằng provider cấu hình trong `.env`.
    """
    payload = text.strip()
    if not payload:
        raise ValueError("Không thể tạo embedding cho chuỗi rỗng.")

    if EMBEDDING_PROVIDER == "openai":
        client = _get_openai_client()
        response = client.embeddings.create(input=payload, model=EMBEDDING_MODEL)
        return response.data[0].embedding

    if EMBEDDING_PROVIDER in {"sentence-transformers", "sentence_transformers", "local"}:
        model_name = EMBEDDING_MODEL or "paraphrase-multilingual-MiniLM-L12-v2"
        model = _get_sentence_transformer(model_name)
        return model.encode(payload).tolist()

    raise ValueError(f"EMBEDDING_PROVIDER không hỗ trợ: {EMBEDDING_PROVIDER}")


def build_index(docs_dir: Path = DOCS_DIR, db_dir: Path = CHROMA_DB_DIR) -> None:
    """
    Đọc docs -> preprocess -> chunk -> embed -> upsert vào ChromaDB.
    """
    import chromadb

    try:
        from tqdm import tqdm
    except ImportError:
        tqdm = None

    print(f"Đang build index từ: {docs_dir}")
    db_dir.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(db_dir))
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    doc_files = sorted(docs_dir.glob("*.txt"))
    if not doc_files:
        raise FileNotFoundError(f"Không tìm thấy file .txt trong {docs_dir}")

    total_chunks = 0
    iterator = tqdm(doc_files, desc="Indexing docs") if tqdm else doc_files

    for filepath in iterator:
        raw_text = filepath.read_text(encoding="utf-8")
        doc = preprocess_document(raw_text, filepath.as_posix())
        chunks = chunk_document(doc)

        ids: List[str] = []
        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        embeddings: List[List[float]] = []

        for chunk_index, chunk in enumerate(chunks):
            ids.append(f"{filepath.stem}_{chunk_index}")
            documents.append(chunk["text"])
            metadatas.append(chunk["metadata"])
            embeddings.append(get_embedding(chunk["text"]))

        if ids:
            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )

        total_chunks += len(chunks)
        if not tqdm:
            print(f"  {filepath.name}: {len(chunks)} chunks")

    print(f"Hoàn thành build index. Tổng số chunks: {total_chunks}")


def list_chunks(db_dir: Path = CHROMA_DB_DIR, n: int = 5) -> None:
    """
    In preview một số chunk đầu để kiểm tra chất lượng index.
    """
    import chromadb

    client = chromadb.PersistentClient(path=str(db_dir))
    collection = client.get_collection(COLLECTION_NAME)
    results = collection.get(limit=n, include=["documents", "metadatas"])

    print(f"\n=== Top {n} chunks trong index ===\n")
    for idx, (document, metadata) in enumerate(zip(results["documents"], results["metadatas"]), start=1):
        print(f"[Chunk {idx}]")
        print(f"  Source: {metadata.get('source', 'N/A')}")
        print(f"  Department: {metadata.get('department', 'N/A')}")
        print(f"  Effective Date: {metadata.get('effective_date', 'N/A')}")
        print(f"  Access: {metadata.get('access', 'N/A')}")
        print(f"  Section: {metadata.get('section', 'N/A')}")
        print(f"  Text preview: {document[:180]}...")
        print()


def inspect_metadata_coverage(db_dir: Path = CHROMA_DB_DIR) -> None:
    """
    Kiểm tra coverage của metadata trên toàn bộ collection.
    """
    import chromadb

    client = chromadb.PersistentClient(path=str(db_dir))
    collection = client.get_collection(COLLECTION_NAME)
    results = collection.get(include=["metadatas"])
    metadatas: List[Dict[str, Any]] = results["metadatas"]

    required_keys = ["source", "section", "department", "effective_date", "access"]
    missing_counts = {key: 0 for key in required_keys}
    department_counts: Dict[str, int] = {}

    for metadata in metadatas:
        for key in required_keys:
            if not metadata.get(key):
                missing_counts[key] += 1

        department = metadata.get("department", "unknown")
        department_counts[department] = department_counts.get(department, 0) + 1

    print("\n=== Metadata coverage ===")
    print(f"Tổng chunks: {len(metadatas)}")
    print("Phân bố theo department:")
    for department, count in sorted(department_counts.items()):
        print(f"  - {department}: {count}")
    print("Thiếu metadata:")
    for key, count in missing_counts.items():
        print(f"  - {key}: {count}")


if __name__ == "__main__":
    print("=" * 60)
    print("Sprint 1: Build RAG Index")
    print("=" * 60)

    doc_files = sorted(DOCS_DIR.glob("*.txt"))
    print(f"\nTìm thấy {len(doc_files)} tài liệu:")
    for file in doc_files:
        print(f"  - {file.name}")

    if doc_files:
        sample = doc_files[0]
        sample_doc = preprocess_document(sample.read_text(encoding="utf-8"), sample.as_posix())
        sample_chunks = chunk_document(sample_doc)
        print(f"\nPreview preprocess/chunking cho {sample.name}:")
        print(f"  Metadata: {sample_doc['metadata']}")
        print(f"  Số chunks: {len(sample_chunks)}")
        for idx, chunk in enumerate(sample_chunks[:3], start=1):
            print(f"  [Chunk {idx}] {chunk['metadata']['section']}")
            print(f"    {chunk['text'][:140]}...")

    print("\n--- Build Full Index ---")
    build_index()
    list_chunks()
    inspect_metadata_coverage()
