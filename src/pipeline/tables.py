"""
Extrae tablas de PDFs usando pdfplumber y las convierte a formato Markdown.
"""

from dataclasses import dataclass
from pathlib import Path

import pdfplumber


@dataclass
class TableBlock:
    markdown: str
    page: int
    raw_data: list[list[str]]


def _row_to_md(row: list) -> str:
    cells = [str(c).replace("\n", " ").strip() if c is not None else "" for c in row]
    return "| " + " | ".join(cells) + " |"


def _table_to_markdown(table: list[list]) -> str:
    if not table or not table[0]:
        return ""

    # Clean None cells
    cleaned = [[str(c).strip() if c else "" for c in row] for row in table]
    rows = [r for r in cleaned if any(r)]  # skip fully empty rows

    if not rows:
        return ""

    header = rows[0]
    md_lines = [_row_to_md(header)]
    md_lines.append("| " + " | ".join(["---"] * len(header)) + " |")

    for row in rows[1:]:
        # Pad row if fewer cells than header
        padded = row + [""] * (len(header) - len(row))
        md_lines.append(_row_to_md(padded))

    return "\n".join(md_lines)


def extract_tables(pdf_path: str) -> list[TableBlock]:
    """Extract all tables from a PDF and return as Markdown blocks with page info."""
    blocks: list[TableBlock] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            if not tables:
                continue
            for table in tables:
                md = _table_to_markdown(table)
                if md:
                    blocks.append(TableBlock(markdown=md, page=page_num, raw_data=table))

    return blocks


def tables_by_page(pdf_path: str) -> dict[int, list[TableBlock]]:
    """Group extracted tables by page number."""
    result: dict[int, list[TableBlock]] = {}
    for tb in extract_tables(pdf_path):
        result.setdefault(tb.page, []).append(tb)
    return result
