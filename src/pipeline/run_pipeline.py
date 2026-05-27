#!/usr/bin/env python3
"""
Orquesta la conversión de todos los PDFs de un fabricante a Markdown.

Uso:
    python src/pipeline/run_pipeline.py --input "Documentos - Parcial final/Documentos - Parcial final/CORONA" \
                                         --fabricante CORONA
"""

import argparse
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.pipeline.md_writer import convert_pdf_to_markdown


def main() -> None:
    parser = argparse.ArgumentParser(description="Convertir PDFs de FDS a Markdown")
    parser.add_argument("--input", required=True, help="Carpeta con PDFs del fabricante")
    parser.add_argument("--fabricante", required=True, help="Nombre del fabricante")
    parser.add_argument("--output", default="output/markdown", help="Carpeta de salida .md")
    parser.add_argument("--images", default="output/images", help="Carpeta de salida imágenes")
    args = parser.parse_args()

    input_dir = Path(args.input)
    if not input_dir.exists():
        print(f"[!] No existe el directorio: {input_dir}")
        sys.exit(1)

    pdfs = sorted(input_dir.glob("*.pdf"))
    if not pdfs:
        print(f"[!] No se encontraron PDFs en: {input_dir}")
        sys.exit(1)

    print(f"Fabricante : {args.fabricante}")
    print(f"PDFs encontrados: {len(pdfs)}")
    print(f"Salida .md : {args.output}")
    print("-" * 50)

    errors: list[tuple[str, str]] = []

    for pdf in pdfs:
        print(f"  Procesando: {pdf.name} ...", end=" ", flush=True)
        try:
            md_path = convert_pdf_to_markdown(
                str(pdf),
                output_dir=args.output,
                images_dir=args.images,
                fabricante=args.fabricante,
            )
            size_kb = Path(md_path).stat().st_size // 1024
            print(f"OK → {Path(md_path).name} ({size_kb} KB)")
        except Exception as e:
            print(f"ERROR")
            errors.append((pdf.name, str(e)))
            traceback.print_exc()

    print("-" * 50)
    print(f"Completados: {len(pdfs) - len(errors)}/{len(pdfs)}")

    if errors:
        print("\nErrores:")
        for name, err in errors:
            print(f"  {name}: {err}")
        _log_errors(errors, args.fabricante)

    print(f"\nArchivos .md generados en: {args.output}")


def _log_errors(errors: list[tuple[str, str]], fabricante: str) -> None:
    log_path = Path("docs/errores_extraccion.md")
    lines = [f"## Errores de extracción – {fabricante}\n"]
    for name, err in errors:
        lines.append(f"- **{name}**: `{err}`")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
