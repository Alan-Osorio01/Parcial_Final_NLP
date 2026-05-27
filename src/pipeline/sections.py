"""
Detecta y mapea las 16 secciones normativas GHS dentro del texto extraído.
"""

import re
from dataclasses import dataclass, field

GHS_SECTIONS: dict[int, str] = {
    1: "Identificación del producto y de la compañía",
    2: "Identificación de peligros",
    3: "Composición / información sobre los componentes",
    4: "Primeros auxilios",
    5: "Medidas de lucha contra incendios",
    6: "Medidas en caso de vertido accidental",
    7: "Manipulación y almacenamiento",
    8: "Controles de exposición / protección personal",
    9: "Propiedades físicas y químicas",
    10: "Estabilidad y reactividad",
    11: "Información toxicológica",
    12: "Información ecológica",
    13: "Información sobre la eliminación",
    14: "Información sobre el transporte",
    15: "Información sobre la reglamentación",
    16: "Otra información",
}

# Matches patterns like:
#   SECCIÓN 1, Sección 1., SECCION 1:, 1. IDENTIFICACIÓN, 1 -
_SECTION_RE = re.compile(
    r"(?:secci[oó]n\s*)?(\d{1,2})\s*[:\.\-\s]\s*(.{3,80}?)(?=\n|$)",
    re.IGNORECASE,
)

# Strict match for standalone section headers
_STRICT_RE = re.compile(
    r"^(?:secci[oó]n\s+)?(\d{1,2})\s*[\.\:\-]\s*(.*?)$",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass
class DetectedSection:
    num: int
    title: str
    content_lines: list[str] = field(default_factory=list)


def detect_sections(full_text: str) -> dict[int, DetectedSection]:
    """
    Returns a dict {section_num: DetectedSection} for all GHS sections found.
    Logs a warning for any of the 16 expected sections not found.
    """
    found: dict[int, int] = {}  # section_num -> character position

    for m in _STRICT_RE.finditer(full_text):
        num = int(m.group(1))
        if 1 <= num <= 16 and num not in found:
            found[num] = m.start()

    # Build sections by slicing text between consecutive found positions
    sorted_nums = sorted(found.keys(), key=lambda n: found[n])
    positions = [(n, found[n]) for n in sorted_nums]
    positions.append((0, len(full_text)))  # sentinel

    sections: dict[int, DetectedSection] = {}
    for i, (num, start_pos) in enumerate(positions[:-1]):
        end_pos = positions[i + 1][1]
        slice_text = full_text[start_pos:end_pos].strip()
        lines = [l.strip() for l in slice_text.splitlines() if l.strip()]
        title = GHS_SECTIONS.get(num, lines[0] if lines else f"Sección {num}")
        sections[num] = DetectedSection(num=num, title=title, content_lines=lines[1:])

    # Report missing sections
    missing = [n for n in range(1, 17) if n not in sections]
    if missing:
        import warnings
        warnings.warn(
            f"Secciones GHS no encontradas: {missing}. "
            "Revisar formato del PDF y registrar en docs/errores_extraccion.md",
            stacklevel=2,
        )

    return sections


def section_for_position(text: str, char_pos: int) -> int | None:
    """Return the GHS section number that contains a given character position."""
    best_num = None
    best_pos = -1
    for m in _STRICT_RE.finditer(text):
        num = int(m.group(1))
        if 1 <= num <= 16 and m.start() <= char_pos and m.start() > best_pos:
            best_pos = m.start()
            best_num = num
    return best_num
