import re
from pathlib import Path

from rank_bm25 import BM25Okapi

from src.rag.chunker import load_chunks
from src.rag.vectorstore import dense_search

# In-memory cache: fabricante -> (BM25Okapi, list[dict])
_bm25_cache: dict[str, tuple[BM25Okapi, list[dict]]] = {}


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def _chunks_path(fabricante: str) -> str:
    return f"data/chunks_{fabricante.lower()}.json"


def build_bm25_index(chunks: list[dict], fabricante: str) -> None:
    corpus = [_tokenize(c["texto"]) for c in chunks]
    _bm25_cache[fabricante] = (BM25Okapi(corpus), chunks)


def _ensure_bm25(fabricante: str) -> bool:
    if fabricante in _bm25_cache:
        return True
    path = _chunks_path(fabricante)
    if Path(path).exists():
        build_bm25_index(load_chunks(path), fabricante)
        return True
    return False


def bm25_search(query: str, fabricante: str, n: int = 10) -> list[dict]:
    if not _ensure_bm25(fabricante):
        return []
    bm25, chunks = _bm25_cache[fabricante]
    scores = bm25.get_scores(_tokenize(query))
    top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n]
    return [{"bm25_score": float(scores[i]), **chunks[i]} for i in top_idx if scores[i] > 0]


def _rrf(rankings: list[list[dict]], k: int = 60) -> list[dict]:
    """Reciprocal Rank Fusion — merges multiple ranked lists."""
    scores: dict[str, float] = {}
    docs: dict[str, dict] = {}

    for ranking in rankings:
        for rank, doc in enumerate(ranking):
            cid = doc.get("chunk_id") or doc.get("texto", "")[:60]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
            docs[cid] = doc

    result = []
    for cid in sorted(scores, key=scores.__getitem__, reverse=True):
        entry = dict(docs[cid])
        entry["rrf_score"] = round(scores[cid], 6)
        result.append(entry)
    return result


def hybrid_search(query: str, fabricante: str, k: int = 5) -> list[dict]:
    dense = dense_search(query, fabricante, n_results=k * 2)
    bm25 = bm25_search(query, fabricante, n=k * 2)

    if not bm25:
        return dense[:k]

    return _rrf([dense, bm25])[:k]
