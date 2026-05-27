"""
Ensambla el archivo Markdown final combinando:
- Bloques de texto estructurado (parser.py)
- Tablas en formato Markdown (tables.py)
- Bloques de imágenes OCR con notas de trazabilidad (ocr.py)
"""

import re
from pathlib import Path

import fitz  # PyMuPDF

from src.pipeline.ocr import ImageBlock, extract_images_with_ocr
from src.pipeline.parser import ParsedDocument, TextBlock
from src.pipeline.sections import GHS_SECTIONS, DetectedSection
from src.pipeline.tables import TableBlock, tables_by_page

SECTION_HEADER_RE = re.compile(
    r"^(?:secci[oó]n\s+)?(\d{1,2})\s*[\.\:\-]\s*(.*?)$",
    re.IGNORECASE,
)


def _block_to_md(block: TextBlock) -> str:
    t = block.text.strip()
    if block.block_type == "heading1":
        return f"# {t}"
    if block.block_type == "heading2":
        return f"## {t}"
    if block.block_type == "heading3":
        return f"### {t}"
    if block.block_type == "list_item":
        clean = re.sub(r"^[•\-·◦▪\*]\s*", "", t)
        return f"- {clean}"
    return t  # paragraph


def _is_section_header(text: str) -> bool:
    return bool(SECTION_HEADER_RE.match(text.strip()))


def _image_md(img: ImageBlock) -> str:
    img_rel = Path(img.path).name
    lines = [f"![imagen_p{img.page}](../output/images/{img_rel})"]
    if img.ocr_text:
        lines.append(f"\n**Texto extraído (OCR):** {img.ocr_text[:500]}")
    lines.append(f"\n> *Nota de trazabilidad: {img.traceability_note}*")
    return "\n".join(lines)


def convert_pdf_to_markdown(
    pdf_path: str,
    output_dir: str = "output/markdown",
    images_dir: str = "output/images",
    fabricante: str = "",
) -> str:
    """
    Full conversion: PDF → Markdown.
    Returns the path to the generated .md file.
    """
    from src.pipeline.parser import parse_pdf

    pdf_path = str(pdf_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = Path(pdf_path).stem
    md_path = out_dir / f"{stem}.md"

    # 1. Parse text structure
    doc = parse_pdf(pdf_path)

    # 2. Extract tables grouped by page
    try:
        page_tables = tables_by_page(pdf_path)
    except Exception:
        page_tables = {}

    # 3. Extract images + OCR
    try:
        image_blocks = extract_images_with_ocr(pdf_path, output_dir=images_dir)
    except Exception:
        image_blocks = []

    # Group images by page
    page_images: dict[int, list[ImageBlock]] = {}
    for img in image_blocks:
        page_images.setdefault(img.page, []).append(img)

    # 4. Assemble Markdown
    lines: list[str] = []
    header_line = f"# FDS – {stem}"
    if fabricante:
        header_line += f" – {fabricante}"
    lines.append(header_line)
    lines.append("")

    # Track which tables/images have been inserted to avoid duplicates
    inserted_table_pages: set[tuple[int, int]] = set()
    inserted_img_paths: set[str] = set()

    # Get full page text from PDF (needed for section-aware insertion)
    pdf_doc = fitz.open(pdf_path)
    page_texts = {i + 1: pdf_doc[i].get_text() for i in range(len(pdf_doc))}
    pdf_doc.close()

    current_section: int | None = None
    last_page = 1

    for block in doc.blocks:
        page = block.page

        # Inject tables that appeared on previous pages not yet inserted
        for p in range(last_page, page + 1):
            if p in page_tables:
                for idx, tb in enumerate(page_tables[p]):
                    key = (p, idx)
                    if key not in inserted_table_pages:
                        lines.append("")
                        lines.append(tb.markdown)
                        lines.append("")
                        inserted_table_pages.add(key)

        last_page = page

        md_line = _block_to_md(block)

        # Detect section headers to add proper GHS markdown headers
        sec_match = SECTION_HEADER_RE.match(block.text.strip())
        if sec_match:
            num = int(sec_match.group(1))
            if 1 <= num <= 16:
                current_section = num
                title = GHS_SECTIONS.get(num, sec_match.group(2).strip())
                lines.append("")
                lines.append(f"## SECCIÓN {num}: {title}")
                lines.append("")
                continue

        lines.append(md_line)

        # Inject images for this page after their nearest text block
        if page in page_images:
            for img in page_images[page]:
                if img.path not in inserted_img_paths:
                    lines.append("")
                    lines.append(_image_md(img))
                    lines.append("")
                    inserted_img_paths.add(img.path)

    # Remaining tables on last pages
    for p in sorted(page_tables):
        for idx, tb in enumerate(page_tables[p]):
            if (p, idx) not in inserted_table_pages:
                lines.append("")
                lines.append(tb.markdown)
                lines.append("")

    md_content = "\n".join(lines)
    md_path.write_text(md_content, encoding="utf-8")
    return str(md_path)
