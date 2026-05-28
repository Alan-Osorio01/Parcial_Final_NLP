from pathlib import Path

import chromadb

from src.rag.embedder import embed_query, embed_texts

CHROMA_DIR = "data/chroma_db"
BATCH_SIZE = 400  # safe ChromaDB upsert batch limit


def _collection_name(fabricante: str) -> str:
    return f"fds_{fabricante.lower().replace(' ', '_').replace('-', '_')}"


def get_collection(fabricante: str) -> chromadb.Collection:
    Path(CHROMA_DIR).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    return client.get_or_create_collection(
        name=_collection_name(fabricante),
        metadata={"hnsw:space": "cosine"},
    )


def index_chunks(chunks: list[dict], fabricante: str) -> None:
    if not chunks:
        return

    collection = get_collection(fabricante)
    texts = [c["texto"] for c in chunks]
    ids = [c["chunk_id"] for c in chunks]
    # ChromaDB requires string values in metadata
    metadatas = [
        {k: (str(v) if v is not None else "") for k, v in c.items() if k not in ("texto", "chunk_id")}
        for c in chunks
    ]

    print(f"Generando embeddings para {len(chunks)} chunks...")
    embeddings = embed_texts(texts)

    for i in range(0, len(chunks), BATCH_SIZE):
        collection.upsert(
            ids=ids[i : i + BATCH_SIZE],
            embeddings=embeddings[i : i + BATCH_SIZE].tolist(),
            documents=texts[i : i + BATCH_SIZE],
            metadatas=metadatas[i : i + BATCH_SIZE],
        )

    print(f"Colección '{collection.name}': {collection.count()} documentos indexados.")


def dense_search(query: str, fabricante: str, n_results: int = 10) -> list[dict]:
    collection = get_collection(fabricante)
    total = collection.count()
    if total == 0:
        return []

    q_emb = embed_query(query)
    results = collection.query(
        query_embeddings=[q_emb.tolist()],
        n_results=min(n_results, total),
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    for doc, meta, dist, cid in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
        results["ids"][0],
    ):
        hits.append({"texto": doc, "dense_score": float(1 - dist), "chunk_id": cid, **meta})
    return hits


def collection_count(fabricante: str) -> int:
    return get_collection(fabricante).count()
