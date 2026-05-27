import io
import re
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

SECTION_RE = re.compile(
    r"secci[oó]n\s*(\d{1,2})[:\.\s]*(.*?)(?=\n|$)",
    re.IGNORECASE,
)
TABLE_REF_RE = re.compile(r"tabla\s+(\d+)", re.IGNORECASE)


@dataclass
class ImageBlock:
    path: str
    ocr_text: str
    page: int
    section_num: int | None
    section_title: str
    related_table: str | None
    traceability_note: str


def _detect_section_from_text(text: str) -> tuple[int | None, str]:
    matches = list(SECTION_RE.finditer(text))
    if not matches:
        return None, "Sección desconocida"
    last = matches[-1]
    return int(last.group(1)), last.group(2).strip()


def _detect_related_table(text_near: str) -> str | None:
    m = TABLE_REF_RE.search(text_near)
    return f"Tabla {m.group(1)}" if m else None


def extract_images_with_ocr(
    pdf_path: str, output_dir: str = "output/images"
) -> list[ImageBlock]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    pdf_stem = Path(pdf_path).stem
    blocks: list[ImageBlock] = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_text = page.get_text()
        section_num, section_title = _detect_section_from_text(page_text)

        for img_idx, img_info in enumerate(page.get_images(full=True)):
            xref = img_info[0]
            base = doc.extract_image(xref)
            img_bytes = base["image"]
            ext = base["ext"]

            img_name = f"{pdf_stem}_p{page_num + 1}_{img_idx + 1}.{ext}"
            img_path = out / img_name
            img_path.write_bytes(img_bytes)

            try:
                pil_img = Image.open(io.BytesIO(img_bytes))
                ocr_text = pytesseract.image_to_string(pil_img, lang="spa+eng").strip()
            except Exception:
                ocr_text = ""

            related_table = _detect_related_table(page_text)
            sec_ref = f"la Sección {section_num}" if section_num else "el documento"
            table_ref = f" en {related_table}" if related_table else ""
            note = (
                f"La información asociada a esta figura se encuentra en "
                f"{sec_ref}: {section_title}{table_ref}."
            )

            blocks.append(
                ImageBlock(
                    path=str(img_path),
                    ocr_text=ocr_text,
                    page=page_num + 1,
                    section_num=section_num,
                    section_title=section_title,
                    related_table=related_table,
                    traceability_note=note,
                )
            )

    doc.close()
    return blocks
