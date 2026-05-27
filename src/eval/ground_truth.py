"""
Helpers para cargar y filtrar el ground truth desde eval/ground_truth.json.
Los 35 pares Q-A se encuentran en eval/ground_truth.json.
"""

import json
from pathlib import Path

_GT_PATH = Path(__file__).resolve().parent.parent.parent / "eval" / "ground_truth.json"


def load_ground_truth(path: str | None = None) -> list[dict]:
    p = Path(path) if path else _GT_PATH
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def filter_by_type(ground_truth: list[dict], tipo: str) -> list[dict]:
    """tipo: 'factual' | 'tecnica' | 'trazabilidad' | 'multi_documento'"""
    return [x for x in ground_truth if x.get("tipo") == tipo]


def filter_by_doc(ground_truth: list[dict], doc_substring: str) -> list[dict]:
    return [x for x in ground_truth if doc_substring.lower() in x.get("documento", "").lower()]
