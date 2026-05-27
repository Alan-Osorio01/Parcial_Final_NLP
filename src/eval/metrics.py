"""
Evaluación del sistema RAG sobre el ground truth de CORONA.

Uso:
    python src/eval/metrics.py [--fabricante CORONA] [--gt eval/ground_truth.json] [--out eval/results.csv]

Métricas calculadas:
  - Similitud semántica coseno entre respuesta RAG y respuesta de referencia
  - Trazabilidad: si la sección fuente correcta apareció en los chunks recuperados
  - Cobertura: si el documento correcto fue recuperado
"""

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Asegura que el proyecto esté en el path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.rag.embedder import embed_query, embed_texts
from src.rag.generator import generate_answer


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom > 0 else 0.0


def _section_num(seccion_fuente: str) -> str:
    """Extrae el número de sección: 'Sección 9 – ...' → '9'"""
    m = re.search(r"Sección\s+(\d+)", seccion_fuente, re.IGNORECASE)
    return m.group(1) if m else ""


def evaluate(
    ground_truth_path: str = "eval/ground_truth.json",
    fabricante: str = "CORONA",
    output_path: str = "eval/results.csv",
    k: int = 7,
) -> pd.DataFrame:
    with open(ground_truth_path, encoding="utf-8") as f:
        ground_truth = json.load(f)

    print(f"Evaluando {len(ground_truth)} preguntas contra el RAG ({fabricante}, k={k})…\n", flush=True)

    # Embeddings de referencia en batch para eficiencia
    print("Generando embeddings de referencia…", flush=True)
    ref_texts = [item["respuesta_referencia"] for item in ground_truth]
    ref_embeddings = embed_texts(ref_texts)
    print(f"Embeddings listos: {ref_embeddings.shape}\n", flush=True)

    results = []
    for i, item in enumerate(ground_truth):
        print(f"  [{i+1}/{len(ground_truth)}] {item['id']}: {item['pregunta'][:60]}…", flush=True)

        rag_answer, chunks = generate_answer(item["pregunta"], fabricante, k=k, num_predict=150)

        # Similitud semántica coseno
        gen_emb = embed_query(rag_answer)
        sem_score = _cosine(ref_embeddings[i], gen_emb)

        # Trazabilidad: ¿recuperó la sección correcta?
        expected_sec = _section_num(item["seccion_fuente"])
        traceability_ok = any(
            str(c.get("seccion_num", "")) == expected_sec for c in chunks
        )

        # Cobertura documental: ¿recuperó el documento correcto?
        expected_doc_stem = Path(item["documento"]).stem.strip()
        doc_ok = any(
            c.get("documento", "").strip() == expected_doc_stem for c in chunks
        )

        # ¿La respuesta indica "no encontrado"?
        no_answer = "no encontrado" in rag_answer.lower() or "no se encontr" in rag_answer.lower()

        results.append(
            {
                "id": item["id"],
                "tipo": item["tipo"],
                "pregunta": item["pregunta"],
                "respuesta_referencia": item["respuesta_referencia"],
                "respuesta_rag": rag_answer,
                "similitud_semantica": round(sem_score, 4),
                "trazabilidad_seccion": traceability_ok,
                "cobertura_documento": doc_ok,
                "sin_respuesta": no_answer,
                "chunks_recuperados": len(chunks),
            }
        )

    df = pd.DataFrame(results)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8")

    _print_summary(df)
    return df


def _print_summary(df: pd.DataFrame) -> None:
    print("\n" + "=" * 60)
    print("RESUMEN DE EVALUACIÓN")
    print("=" * 60)
    print(f"Total preguntas evaluadas: {len(df)}")
    print(f"\nSimilitud semántica promedio: {df['similitud_semantica'].mean():.3f}")
    print(f"  Por tipo:")
    for tipo, grp in df.groupby("tipo"):
        print(f"    {tipo:20s}: {grp['similitud_semantica'].mean():.3f}  (n={len(grp)})")

    print(f"\nTrazabilidad sección correcta: {df['trazabilidad_seccion'].mean() * 100:.1f}%")
    print(f"Cobertura documento correcto:   {df['cobertura_documento'].mean() * 100:.1f}%")
    print(f"Respuestas 'no encontrado':     {df['sin_respuesta'].sum()} / {len(df)}")

    print("\nTop 5 peores por similitud semántica:")
    worst = df.nsmallest(5, "similitud_semantica")[["id", "tipo", "similitud_semantica", "trazabilidad_seccion"]]
    print(worst.to_string(index=False))

    print("\nTop 5 mejores por similitud semántica:")
    best = df.nlargest(5, "similitud_semantica")[["id", "tipo", "similitud_semantica", "trazabilidad_seccion"]]
    print(best.to_string(index=False))
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evalúa el RAG contra ground truth")
    parser.add_argument("--fabricante", default="CORONA")
    parser.add_argument("--gt", default="eval/ground_truth.json")
    parser.add_argument("--out", default="eval/results.csv")
    parser.add_argument("--k", type=int, default=7)
    args = parser.parse_args()

    evaluate(
        ground_truth_path=args.gt,
        fabricante=args.fabricante,
        output_path=args.out,
        k=args.k,
    )
