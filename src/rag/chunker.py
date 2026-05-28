import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

MAX_WORDS = 800
OVERLAP_WORDS = 100

SECTION_HEADER_RE = re.compile(
    r"^#{1,3}\s+SECCI[ÓO]N\s+(\d{1,2})[:\.\s]*(.*?)$",
    re.MULTILINE | re.IGNORECASE,
)
# Markdown table: header + separator + at least one data row
TABLE_RE = re.compile(
    r"(\|[^\n]+\|\n\|[-:| ]+\|\n(?:\|[^\n]+\|\n)+)",
    re.MULTILINE,
)


@dataclass
class Chunk:
    chunk_id: str
    documento: str
    fabricante: str
    seccion_num: int | None
    seccion_titulo: str
    tipo: str  # texto | tabla | imagen_ocr
    pagina: int | None
    texto: str


def _split_with_overlap(text: str, max_w: int, overlap: int) -> list[str]:
    words = text.split()
    result: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + max_w, len(words))
        result.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - overlap
    return result


def chunk_markdown(md_path: str, fabricante: str = "unknown") -> list[dict]:
    path = Path(md_path)
    text = path.read_text(encoding="utf-8")
    doc_name = path.stem
    counter = 0

    def _make(sec_num, sec_title, content: str, tipo: str = "texto") -> dict | None:
        nonlocal counter
        content = content.strip()
        if not content:
            return None
        counter += 1
        cid = f"{doc_name}_sec{sec_num or 0}_{tipo}_{counter}"
        if sec_num is not None and sec_title:
            texto = f"Sección {sec_num}: {sec_title}\n{content}"
        else:
            texto = content
        return asdict(
            Chunk(
                chunk_id=cid,
                documento=doc_name,
                fabricante=fabricante,
                seccion_num=sec_num,
                seccion_titulo=sec_title,
                tipo=tipo,
                pagina=None,
                texto=texto,
            )
        )

    # Build list of (position, sec_num, sec_title) for all section headers
    headers = [
        (m.start(), int(m.group(1)), m.group(2).strip())
        for m in SECTION_HEADER_RE.finditer(text)
    ]
    headers.append((len(text), None, None))  # sentinel

    chunks: list[dict] = []

    # Content before first section header
    preamble_end = headers[0][0] if headers else len(text)
    if preamble_end > 0:
        c = _make(None, "Encabezado del documento", text[:preamble_end])
        if c:
            chunks.append(c)

    for idx in range(len(headers) - 1):
        pos, sec_num, sec_title = headers[idx]
        next_pos = headers[idx + 1][0]

        # Skip the header line itself, grab the body
        newline = text.find("\n", pos)
        body_start = (newline + 1) if newline != -1 else pos
        body = text[body_start:next_pos]

        # Pull out tables as atomic chunks
        table_spans = [(m.start(), m.end(), m.group(0)) for m in TABLE_RE.finditer(body)]
        last = 0
        segments: list[tuple[str, str]] = []

        for t_start, t_end, table_text in table_spans:
            before = body[last:t_start].strip()
            if before:
                segments.append(("texto", before))
            segments.append(("tabla", table_text.strip()))
            last = t_end

        tail = body[last:].strip()
        if tail:
            segments.append(("texto", tail))

        for tipo, seg in segments:
            if tipo == "tabla":
                c = _make(sec_num, sec_title, seg, tipo="tabla")
                if c:
                    chunks.append(c)
            else:
                if len(seg.split()) <= MAX_WORDS:
                    c = _make(sec_num, sec_title, seg, tipo="texto")
                    if c:
                        chunks.append(c)
                else:
                    for sub in _split_with_overlap(seg, MAX_WORDS, OVERLAP_WORDS):
                        c = _make(sec_num, sec_title, sub, tipo="texto")
                        if c:
                            chunks.append(c)

    return chunks


def chunk_all_markdowns(md_dir: str, fabricante: str) -> list[dict]:
    all_chunks: list[dict] = []
    for md_file in sorted(Path(md_dir).glob("*.md")):
        file_chunks = chunk_markdown(str(md_file), fabricante=fabricante)
        all_chunks.extend(file_chunks)
        print(f"  {md_file.name}: {len(file_chunks)} chunks")
    return all_chunks


def save_chunks(chunks: list[dict], output_path: str) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)


def load_chunks(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
