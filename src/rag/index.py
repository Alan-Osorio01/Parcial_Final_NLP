#!/usr/bin/env python3
"""Indexa los documentos .md en ChromaDB y guarda los chunks para BM25."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.rag.chunker import chunk_all_markdowns, save_chunks
from src.rag.retriever import build_bm25_index
from src.rag.vectorstore import index_chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="Indexar documentos .md en ChromaDB")
    parser.add_argument(
        "--md-dir", default="output/markdown", help="Directorio con archivos .md"
    )
    parser.add_argument("--fabricante", required=True, help="Nombre del fabricante")
    args = parser.parse_args()

    md_dir = Path(args.md_dir)
    if not md_dir.exists():
        print(f"[!] El directorio '{md_dir}' no existe.")
        sys.exit(1)

    md_files = list(md_dir.glob("*.md"))
    if not md_files:
        print(f"[!] No se encontraron archivos .md en '{md_dir}'.")
        sys.exit(1)

    print(f"Encontrados {len(md_files)} archivos .md en '{md_dir}'.")
    print(f"Fabricante: {args.fabricante}\n")

    print("Fragmentando documentos...")
    chunks = chunk_all_markdowns(str(md_dir), fabricante=args.fabricante)
    print(f"Total: {len(chunks)} chunks generados.\n")

    chunks_path = f"data/chunks_{args.fabricante.lower()}.json"
    save_chunks(chunks, chunks_path)
    print(f"Chunks guardados en '{chunks_path}' (usado por BM25).\n")

    print("Indexando en ChromaDB...")
    index_chunks(chunks, fabricante=args.fabricante)

    print("Construyendo índice BM25 en memoria...")
    build_bm25_index(chunks, fabricante=args.fabricante)

    print("\nIndexación completada.")
    print(f"Para consultar: python src/rag/query_cli.py")


if __name__ == "__main__":
    main()
