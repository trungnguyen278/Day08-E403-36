"""
rag_answer.py - Sprint 2/3: Dense retrieval + hybrid tuning + grounded generation
"""

import json
import math
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from index import CHROMA_DB_DIR, COLLECTION_NAME, get_embedding

load_dotenv()


TOP_K_SEARCH = 10
TOP_K_SELECT = 3
MIN_RELEVANCE_SCORE = float(os.getenv("MIN_RELEVANCE_SCORE", "0.35"))
HYBRID_DENSE_WEIGHT = float(os.getenv("HYBRID_DENSE_WEIGHT", "0.6"))
HYBRID_SPARSE_WEIGHT = float(os.getenv("HYBRID_SPARSE_WEIGHT", "0.4"))

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").strip().lower()
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite").strip()

_OPENAI_CLIENT = None
_SPARSE_INDEX_CACHE: Optional[Dict[str, Any]] = None

_QUERY_ALIASES = {
    "approval matrix": ["access control sop", "system access"],
    "level 3": ["elevated access"],
    "p1": ["critical", "incident"],
    "refund": ["hoan tien"],
    "remote": ["lam remote", "work from home"],
}


def _get_openai_client():
    global _OPENAI_CLIENT

    if _OPENAI_CLIENT is None:
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("Thiếu OPENAI_API_KEY trong .env để gọi LLM.")
        _OPENAI_CLIENT = OpenAI(api_key=api_key)
    return _OPENAI_CLIENT


def _resolve_llm_model(provider: str) -> str:
    if provider == "gemini":
        configured = os.getenv("LLM_MODEL", "").strip()
        if configured and not configured.startswith("gpt-"):
            return configured
        return GEMINI_MODEL or "gemini-2.5-flash-lite"

    configured = os.getenv("LLM_MODEL", "").strip()
    return configured or "gpt-4o-mini"


def _call_gemini(
    prompt: str,
    model_name: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 512,
    response_mime_type: Optional[str] = None,
    retries: int = 4,
) -> str:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Thiếu GOOGLE_API_KEY trong .env để gọi Gemini.")

    resolved_model = (model_name or GEMINI_MODEL or "gemini-2.5-flash-lite").strip()
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{urllib.parse.quote(resolved_model)}:generateContent?key={urllib.parse.quote(api_key)}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if response_mime_type:
        payload["generationConfig"]["responseMimeType"] = response_mime_type
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    body = None
    last_error = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            last_error = RuntimeError(f"Gọi Gemini thất bại ({exc.code}): {detail}")
            if exc.code not in {429, 500, 503} or attempt == retries - 1:
                raise last_error from exc
            time.sleep(2 ** attempt)
        except urllib.error.URLError as exc:
            last_error = RuntimeError(f"Gọi Gemini thất bại do lỗi mạng: {exc}")
            if attempt == retries - 1:
                raise last_error from exc
            time.sleep(2 ** attempt)

    if body is None:
        raise last_error or RuntimeError("Gemini không trả về phản hồi hợp lệ.")

    candidates = body.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"Gemini không trả về candidate hợp lệ: {body}")

    parts = candidates[0].get("content", {}).get("parts", [])
    text_parts = [part.get("text", "") for part in parts if part.get("text")]
    text = "".join(text_parts).strip()
    if not text:
        raise RuntimeError(f"Gemini không trả về text hợp lệ: {body}")
    return text


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _normalize_for_search(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).lower()
    normalized = normalized.replace("đ", "d")
    return re.sub(r"\s+", " ", normalized).strip()


def _tokenize_for_search(text: str) -> List[str]:
    normalized = _normalize_for_search(text)
    stripped = _strip_accents(normalized)

    tokens: List[str] = []
    for variant in {normalized, stripped}:
        tokens.extend(re.findall(r"\w+", variant, flags=re.UNICODE))

    return [token for token in tokens if token]


def _get_collection():
    import chromadb

    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    return client.get_collection(COLLECTION_NAME)


def _get_sparse_index() -> Dict[str, Any]:
    global _SPARSE_INDEX_CACHE

    collection = _get_collection()
    collection_count = collection.count()
    if _SPARSE_INDEX_CACHE and _SPARSE_INDEX_CACHE.get("count") == collection_count:
        return _SPARSE_INDEX_CACHE

    from rank_bm25 import BM25Okapi

    results = collection.get(include=["documents", "metadatas", "embeddings"])
    ids = results.get("ids", [])
    documents = results.get("documents", [])
    metadatas = results.get("metadatas", [])
    embeddings = results.get("embeddings", [])

    records: List[Dict[str, Any]] = []
    tokenized_documents: List[List[str]] = []

    for idx, (doc_id, document, metadata, embedding) in enumerate(zip(ids, documents, metadatas, embeddings)):
        metadata = metadata or {}
        searchable_text = "\n".join(
            [
                document or "",
                metadata.get("source", ""),
                metadata.get("section", ""),
                metadata.get("department", ""),
            ]
        )
        records.append(
            {
                "id": doc_id or f"chunk_{idx}",
                "text": document or "",
                "metadata": metadata,
                "embedding": embedding,
            }
        )
        tokenized_documents.append(_tokenize_for_search(searchable_text))

    _SPARSE_INDEX_CACHE = {
        "count": collection_count,
        "records": records,
        "bm25": BM25Okapi(tokenized_documents or [["empty"]]),
    }
    return _SPARSE_INDEX_CACHE


def _cosine_similarity(left: List[float], right: List[float]) -> float:
    if left is None or right is None:
        return 0.0

    if len(left) == 0 or len(right) == 0 or len(left) != len(right):
        return 0.0

    dot_product = sum(float(l) * float(r) for l, r in zip(left, right))
    left_norm = math.sqrt(sum(float(value) * float(value) for value in left))
    right_norm = math.sqrt(sum(float(value) * float(value) for value in right))

    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0

    return dot_product / (left_norm * right_norm)


def _normalize_sparse_scores(scores: List[float]) -> List[float]:
    positive_scores = [score for score in scores if score > 0]
    if not positive_scores:
        return [0.0 for _ in scores]

    max_score = max(positive_scores)
    return [max(0.0, float(score)) / max_score for score in scores]


def retrieve_dense(query: str, top_k: int = TOP_K_SEARCH) -> List[Dict[str, Any]]:
    """
    Dense retrieval từ ChromaDB bằng cùng embedding model đã dùng khi index.
    """
    if not query.strip():
        return []

    collection = _get_collection()
    query_embedding = get_embedding(query)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    retrieved: List[Dict[str, Any]] = []
    for document, metadata, distance in zip(documents, metadatas, distances):
        score = max(0.0, 1.0 - float(distance))
        retrieved.append(
            {
                "text": document,
                "metadata": metadata or {},
                "score": score,
                "dense_score": score,
                "sparse_score": 0.0,
            }
        )

    return retrieved


def retrieve_sparse(query: str, top_k: int = TOP_K_SEARCH) -> List[Dict[str, Any]]:
    """
    Sparse retrieval bằng BM25 trên toàn bộ chunks đã index.
    """
    if not query.strip():
        return []

    index_data = _get_sparse_index()
    query_tokens = _tokenize_for_search(query)
    if not query_tokens:
        return []

    bm25_scores = index_data["bm25"].get_scores(query_tokens)
    sparse_scores = _normalize_sparse_scores(list(bm25_scores))

    ranked_items = sorted(
        zip(index_data["records"], sparse_scores, bm25_scores),
        key=lambda item: item[1],
        reverse=True,
    )

    retrieved: List[Dict[str, Any]] = []
    for record, normalized_score, raw_score in ranked_items[:top_k]:
        if normalized_score <= 0:
            continue
        retrieved.append(
            {
                "text": record["text"],
                "metadata": record["metadata"],
                "score": float(normalized_score),
                "dense_score": 0.0,
                "sparse_score": float(normalized_score),
                "sparse_score_raw": float(raw_score),
            }
        )

    return retrieved


def retrieve_hybrid(
    query: str,
    top_k: int = TOP_K_SEARCH,
    dense_weight: float = HYBRID_DENSE_WEIGHT,
    sparse_weight: float = HYBRID_SPARSE_WEIGHT,
) -> List[Dict[str, Any]]:
    """
    Hybrid retrieval: dense cosine similarity + sparse BM25 score.
    """
    if not query.strip():
        return []

    index_data = _get_sparse_index()
    query_tokens = _tokenize_for_search(query)
    if not query_tokens:
        return []

    query_embedding = get_embedding(query)
    bm25_scores = list(index_data["bm25"].get_scores(query_tokens))
    sparse_scores = _normalize_sparse_scores(bm25_scores)

    ranked_items = []
    for record, sparse_score, raw_sparse_score in zip(index_data["records"], sparse_scores, bm25_scores):
        dense_score = max(0.0, _cosine_similarity(query_embedding, record["embedding"]))
        combined_score = (dense_weight * dense_score) + (sparse_weight * sparse_score)
        ranked_items.append(
            {
                "text": record["text"],
                "metadata": record["metadata"],
                "score": combined_score,
                "dense_score": dense_score,
                "sparse_score": float(sparse_score),
                "sparse_score_raw": float(raw_sparse_score),
            }
        )

    ranked_items.sort(key=lambda item: item["score"], reverse=True)
    return ranked_items[:top_k]


def rerank(query: str, candidates: List[Dict[str, Any]], top_k: int = TOP_K_SELECT) -> List[Dict[str, Any]]:
    """
    Lexical rerank nhẹ để ưu tiên candidates có overlap token cao hơn với query.
    """
    query_tokens = set(_tokenize_for_search(query))
    if not query_tokens:
        return candidates[:top_k]

    reranked = []
    for candidate in candidates:
        candidate_tokens = set(
            _tokenize_for_search(
                " ".join(
                    [
                        candidate.get("text", ""),
                        candidate.get("metadata", {}).get("source", ""),
                        candidate.get("metadata", {}).get("section", ""),
                    ]
                )
            )
        )
        overlap = len(query_tokens & candidate_tokens) / max(len(query_tokens), 1)
        rerank_score = (0.7 * candidate.get("score", 0.0)) + (0.3 * overlap)
        reranked.append({**candidate, "rerank_score": rerank_score})

    reranked.sort(key=lambda item: item.get("rerank_score", item.get("score", 0.0)), reverse=True)
    return reranked[:top_k]


def transform_query(query: str, strategy: str = "expansion") -> List[str]:
    """
    Query transform đơn giản cho alias cũ / từ khóa đồng nghĩa.
    """
    normalized_query = _normalize_for_search(query)
    expanded_queries = [query.strip()]

    if strategy != "expansion":
        return expanded_queries

    for trigger, aliases in _QUERY_ALIASES.items():
        if trigger in normalized_query:
            for alias in aliases:
                expanded_queries.append(f"{query.strip()} {alias}".strip())

    unique_queries: List[str] = []
    for item in expanded_queries:
        if item and item not in unique_queries:
            unique_queries.append(item)

    return unique_queries


def build_context_block(chunks: List[Dict[str, Any]]) -> str:
    context_parts: List[str] = []
    for index, chunk in enumerate(chunks, start=1):
        metadata = chunk.get("metadata", {})
        source = metadata.get("source", "unknown")
        section = metadata.get("section", "")
        effective_date = metadata.get("effective_date", "")
        score = chunk.get("score", 0.0)
        dense_score = chunk.get("dense_score")
        sparse_score = chunk.get("sparse_score")

        header_parts = [f"[{index}] {source}"]
        if section:
            header_parts.append(section)
        if effective_date:
            header_parts.append(f"effective_date={effective_date}")
        header_parts.append(f"score={score:.2f}")
        if dense_score is not None:
            header_parts.append(f"dense={dense_score:.2f}")
        if sparse_score is not None:
            header_parts.append(f"sparse={sparse_score:.2f}")

        context_parts.append(" | ".join(header_parts) + "\n" + chunk.get("text", ""))

    return "\n\n".join(context_parts)


def build_grounded_prompt(query: str, context_block: str) -> str:
    return f"""You are answering questions using only the retrieved internal documents.
Rules:
- Answer only from the provided context.
- If the context is insufficient, reply exactly "Không đủ dữ liệu trong tài liệu được cung cấp.".
- Cite evidence with snippet numbers such as [1] or [2].
- Keep the answer short, factual, and in the same language as the question.
- Do not mention any information that is not present in the context.

Question:
{query}

Context:
{context_block}

Answer:"""


def call_llm(prompt: str) -> str:
    """
    Gọi LLM theo provider cấu hình trong `.env`.
    """
    resolved_model = _resolve_llm_model(LLM_PROVIDER)

    if LLM_PROVIDER == "openai":
        client = _get_openai_client()
        response = client.chat.completions.create(
            model=resolved_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=512,
        )
        return (response.choices[0].message.content or "").strip()

    if LLM_PROVIDER == "gemini":
        return _call_gemini(prompt, model_name=resolved_model, temperature=0.0, max_tokens=512)

    raise ValueError(f"LLM_PROVIDER hiện tại chưa được hỗ trợ trong code này: {LLM_PROVIDER}")


def _abstain_answer() -> str:
    return "Không đủ dữ liệu trong tài liệu được cung cấp."


def rag_answer(
    query: str,
    retrieval_mode: str = "dense",
    top_k_search: int = TOP_K_SEARCH,
    top_k_select: int = TOP_K_SELECT,
    use_rerank: bool = False,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Pipeline RAG baseline: retrieve -> select -> grounded prompt -> generate.
    """
    config = {
        "retrieval_mode": retrieval_mode,
        "top_k_search": top_k_search,
        "top_k_select": top_k_select,
        "use_rerank": use_rerank,
        "llm_provider": LLM_PROVIDER,
        "llm_model": _resolve_llm_model(LLM_PROVIDER),
        "min_relevance_score": MIN_RELEVANCE_SCORE,
    }

    if retrieval_mode == "dense":
        candidates = retrieve_dense(query, top_k=top_k_search)
    elif retrieval_mode == "sparse":
        candidates = retrieve_sparse(query, top_k=top_k_search)
    elif retrieval_mode == "hybrid":
        candidates = retrieve_hybrid(query, top_k=top_k_search)
    else:
        raise ValueError(f"retrieval_mode không hợp lệ: {retrieval_mode}")

    if verbose:
        print(f"\n[RAG] Query: {query}")
        print(f"[RAG] Retrieved {len(candidates)} candidates")
        for index, candidate in enumerate(candidates[:5], start=1):
            print(
                f"  [{index}] score={candidate.get('score', 0):.3f} | "
                f"dense={candidate.get('dense_score', 0):.3f} | "
                f"sparse={candidate.get('sparse_score', 0):.3f} | "
                f"{candidate.get('metadata', {}).get('source', '?')} | "
                f"{candidate.get('metadata', {}).get('section', '?')}"
            )

    filtered_candidates = [candidate for candidate in candidates if candidate.get("score", 0.0) >= MIN_RELEVANCE_SCORE]

    if use_rerank:
        selected_chunks = rerank(query, filtered_candidates, top_k=top_k_select)
    else:
        selected_chunks = filtered_candidates[:top_k_select]

    if verbose:
        print(f"[RAG] Candidates above threshold {MIN_RELEVANCE_SCORE:.2f}: {len(filtered_candidates)}")
        print(f"[RAG] Selected chunks: {len(selected_chunks)}")

    if not selected_chunks:
        return {
            "query": query,
            "answer": _abstain_answer(),
            "sources": [],
            "chunks_used": [],
            "config": config,
        }

    context_block = build_context_block(selected_chunks)
    prompt = build_grounded_prompt(query, context_block)

    if verbose:
        print(f"\n[RAG] Context block:\n{context_block[:1200]}\n")

    answer = call_llm(prompt)

    cited_indices = [int(match) for match in re.findall(r"\[(\d+)\]", answer)]
    if cited_indices:
        sources = list(
            dict.fromkeys(
                selected_chunks[index - 1]["metadata"].get("source", "unknown")
                for index in cited_indices
                if 1 <= index <= len(selected_chunks)
            )
        )
    else:
        sources = list(dict.fromkeys(chunk["metadata"].get("source", "unknown") for chunk in selected_chunks))

    return {
        "query": query,
        "answer": answer,
        "sources": sources,
        "chunks_used": selected_chunks,
        "config": config,
    }


def compare_retrieval_strategies(query: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"Query: {query}")
    print("=" * 60)

    for strategy in ["dense", "hybrid"]:
        print(f"\n--- Strategy: {strategy} ---")
        try:
            result = rag_answer(query, retrieval_mode=strategy, verbose=False)
            print(f"Answer: {result['answer']}")
            print(f"Sources: {result['sources']}")
            for index, chunk in enumerate(result["chunks_used"], start=1):
                metadata = chunk.get("metadata", {})
                print(
                    f"  [{index}] score={chunk.get('score', 0):.3f} "
                    f"dense={chunk.get('dense_score', 0):.3f} "
                    f"sparse={chunk.get('sparse_score', 0):.3f} "
                    f"{metadata.get('source', '?')} | {metadata.get('section', '?')}"
                )
        except Exception as exc:
            print(f"Lỗi: {exc}")


if __name__ == "__main__":
    print("=" * 60)
    print("Sprint 2/3: RAG Answer Pipeline")
    print("=" * 60)

    test_queries = [
        "SLA xử lý ticket P1 là bao lâu?",
        "Khách hàng có thể yêu cầu hoàn tiền trong bao nhiêu ngày?",
        "Ai phải phê duyệt để cấp quyền Level 3?",
        "Approval Matrix để cấp quyền hệ thống là tài liệu nào?",
        "ERR-403-AUTH là lỗi gì?",
    ]

    for query in test_queries:
        print(f"\nQuery: {query}")
        try:
            result = rag_answer(query, retrieval_mode="hybrid", verbose=True)
            print(f"Answer: {result['answer']}")
            print(f"Sources: {result['sources']}")
        except Exception as exc:
            print(f"Lỗi: {exc}")
