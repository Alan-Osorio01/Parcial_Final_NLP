"""
Embeddings con fastembed (ONNX, sin PyTorch).
Instala con: pip install fastembed
El modelo se descarga automáticamente en data/fastembed_cache/ (~240 MB, una sola vez).
"""

import os
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Cache en el proyecto para que persista entre reinicios
_CACHE_DIR = str(Path(__file__).resolve().parent.parent.parent / "data" / "fastembed_cache")
os.environ["FASTEMBED_CACHE_PATH"] = _CACHE_DIR

_model: TextEmbedding | None = None


def get_model() -> TextEmbedding:
    global _model
    if _model is None:
        Path(_CACHE_DIR).mkdir(parents=True, exist_ok=True)
        print(f"Cargando modelo: {MODEL_NAME}")
        _model = TextEmbedding(model_name=MODEL_NAME, cache_dir=_CACHE_DIR)
    return _model


def embed_texts(texts: list[str], batch_size: int = 64) -> np.ndarray:
    model = get_model()
    arr = np.array(list(model.embed(texts, batch_size=batch_size)), dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    return arr / np.where(norms == 0, 1, norms)


def embed_query(query: str) -> np.ndarray:
    model = get_model()
    arr = np.array(list(model.embed([query])), dtype=np.float32)[0]
    norm = np.linalg.norm(arr)
    return arr / (norm if norm > 0 else 1)
