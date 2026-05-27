#!/usr/bin/env python3
"""CLI interactivo para consultar el sistema RAG de Fichas de Datos de Seguridad."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.rag.generator import generate_answer
from src.rag.vectorstore import collection_count


def _print_sources(sources: list[dict]) -> None:
    print("\nFragmentos recuperados:")
    for s in sources:
        score = s.get("rrf_score", s.get("dense_score", 0))
        doc = s.get("documento", "")
        sec = s.get("seccion_num", "?")
        sec_t = s.get("seccion_titulo", "")
        page = s.get("pagina") or "?"
        print(f"  [{score:.4f}] {doc} §{sec} {sec_t} | p.{page}")


def main() -> None:
    print("=" * 55)
    print("  RAG – Fichas de Datos de Seguridad")
    print("=" * 55)

    fabricante = input("Fabricante (CORONA / Pintuco / Pintuland / SIKA): ").strip()
    if not fabricante:
        fabricante = "CORONA"

    count = collection_count(fabricante)
    if count == 0:
        print(
            f"\n[!] No hay documentos indexados para '{fabricante}'.\n"
            f"    Ejecuta primero:\n"
            f"    python src/rag/index.py --fabricante {fabricante}\n"
        )
        sys.exit(1)

    print(f"\nSistema listo — {count} chunks indexados para {fabricante}.")
    print("Escribe 'salir' para terminar.\n")

    while True:
        try:
            query = input("Pregunta: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not query or query.lower() in {"salir", "exit", "quit"}:
            break

        print("\nBuscando...\n")
        answer, sources = generate_answer(query, fabricante)
        print(f"Respuesta:\n{answer}")
        _print_sources(sources)
        print("-" * 55 + "\n")


if __name__ == "__main__":
    main()
