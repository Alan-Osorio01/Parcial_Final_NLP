"""
Extrae texto y estructura de PDFs usando PyMuPDF.
Detecta encabezados por tamaño de fuente, listas, párrafos y bloques de texto.
"""

from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF


@dataclass
class TextBlock:
    text: str
    block_type: str  # heading1 | heading2 | heading3 | paragraph | list_item | caption
    page: int
    font_size: float
    bold: bool


@dataclass
class ParsedDocument:
    title: str
    pdf_path: str
    pages: int
    blocks: list[TextBlock] = field(default_factory=list)


def _classify_block(text: str, font_size: float, flags: int, avg_size: float) -> str:
    """Classify a text block based on font size and formatting."""
    text = text.strip()
    is_bold = bool(flags & 2**4)

    if font_size >= avg_size * 1.6:
        return "heading1"
    if font_size >= avg_size * 1.3:
        return "heading2"
    if font_size >= avg_size * 1.1 or (is_bold and font_size >= avg_size):
        return "heading3"
    if text.startswith(("•", "-", "·", "◦", "▪", "*")) or (
        len(text) < 120 and text[:2] in {"- ", "· ", "• "}
    ):
        return "list_item"
    return "paragraph"


def parse_pdf(pdf_path: str) -> ParsedDocument:
    doc = fitz.open(pdf_path)
    path = Path(pdf_path)

    # First pass: collect all font sizes to compute average body size
    all_sizes: list[float] = []
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span.get("size"):
                        all_sizes.append(span["size"])

    avg_size = sorted(all_sizes)[len(all_sizes) // 2] if all_sizes else 10.0

    # Second pass: extract structured blocks
    blocks: list[TextBlock] = []
    for page_num, page in enumerate(doc):
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0:  # 0 = text, 1 = image
                continue

            # Aggregate spans into a single block text
            block_text_parts: list[str] = []
            dominant_size = avg_size
            dominant_flags = 0

            for line in block.get("lines", []):
                line_parts = []
                for span in line.get("spans", []):
                    t = span.get("text", "").strip()
                    if t:
                        line_parts.append(t)
                        if span.get("size", 0) > dominant_size:
                            dominant_size = span["size"]
                        dominant_flags |= span.get("flags", 0)
                if line_parts:
                    block_text_parts.append(" ".join(line_parts))

            full_text = "\n".join(block_text_parts).strip()
            if not full_text or len(full_text) < 2:
                continue

            btype = _classify_block(full_text, dominant_size, dominant_flags, avg_size)
            blocks.append(
                TextBlock(
                    text=full_text,
                    block_type=btype,
                    page=page_num + 1,
                    font_size=round(dominant_size, 1),
                    bold=bool(dominant_flags & 2**4),
                )
            )

    num_pages = len(doc)
    doc.close()

    title = path.stem
    return ParsedDocument(
        title=title,
        pdf_path=pdf_path,
        pages=num_pages,
        blocks=blocks,
    )
