# Documentación del Pipeline PDF → Markdown

## Descripción general

El pipeline convierte los PDFs de Fichas de Datos de Seguridad (FDS) a Markdown estructurado, preservando la organización en 16 secciones GHS y la trazabilidad de tablas e imágenes.

## Herramientas elegidas

| Tarea | Herramienta | Alternativa descartada | Razón de la elección |
|-------|-------------|----------------------|----------------------|
| Extracción de texto y estructura | PyMuPDF (fitz) | Docling, pdfminer | Preserva metadatos de fuentes (tamaño, negrita) para inferir jerarquía |
| Extracción de tablas | pdfplumber | Camelot, tabula-py | Robusto en tablas sin bordes explícitos, API simple |
| OCR de imágenes | Tesseract (`spa+eng`) | EasyOCR, PaddleOCR | Soporte oficial de español, sin GPU requerida |
| Detección de secciones | Regex (`SECCIÓN \d+`) | Heurísticas de formato | Las FDS CORONA siguen la normativa GHS consistentemente |

## Flujo de procesamiento

```
PDF
 ├─→ parser.py         Extrae bloques de texto (PyMuPDF)
 │                     Clasifica: heading1/2/3, paragraph, list_item
 │                     Criterio: tamaño de fuente vs. mediana de página
 │
 ├─→ sections.py       Detecta "SECCIÓN N:" con regex _STRICT_RE
 │                     Mapea a 16 títulos estándar GHS en español
 │                     Reporta secciones faltantes como advertencias
 │
 ├─→ tables.py         Extrae tablas con pdfplumber
 │                     Convierte a formato Markdown (| col | col |)
 │                     Genera fila de separadores (| --- | --- |)
 │
 ├─→ ocr.py            Extrae imágenes con page.get_images(full=True)
 │                     Convierte a PNG en memoria
 │                     Ejecuta Tesseract (lang="spa+eng")
 │                     Detecta sección de contexto desde texto de página
 │                     Genera nota: "La información asociada a esta figura
 │                                   se encuentra en la Sección N: Título."
 │
 └─→ md_writer.py      Ensambla el .md final por orden de página
                       Escribe encabezados ## SECCIÓN N: Título
                       Intercala tablas y notas OCR en posición correcta
                       Guarda en output/markdown/
```

## Preservación de las 16 secciones GHS

El módulo `sections.py` define `GHS_SECTIONS` (dict 1..16) con los títulos estándar en español, y usa `_STRICT_RE = re.compile(r"SECCI[OÓ]N\s+(\d+)", re.IGNORECASE)` para detectar encabezados de sección en el texto extraído.

Si una sección no se detecta en el documento, se registra como advertencia y el documento continúa procesándose. En los 17 FDS de CORONA, las 16 secciones se detectaron en todos los documentos.

## Tratamiento de tablas

- pdfplumber extrae tablas con sus celdas y detecta automáticamente filas de encabezado.
- Las celdas `None` se sustituyen por cadena vacía para mantener alineación Markdown.
- El chunker posterior trata cada tabla como **unidad atómica** (no se divide entre chunks).

## Tratamiento de imágenes y OCR

1. PyMuPDF extrae imágenes de cada página (`page.get_images(full=True)`).
2. Cada imagen se renderiza a PNG en memoria (sin escritura a disco en esta etapa).
3. Tesseract procesa el PNG con `lang="spa+eng"` y retorna el texto extraído.
4. Se determina la sección de contexto buscando el último encabezado `## SECCIÓN N:` antes de la posición de la imagen en la página.
5. Se genera la nota de trazabilidad y se guarda la imagen en `output/images/`.

## Resultado del pipeline en CORONA

- **17/17 PDFs** convertidos exitosamente.
- **626 imágenes** extraídas con notas de trazabilidad.
- **16/16 secciones** detectadas en todos los documentos.
- Tiempo de ejecución: ~3-5 minutos en CPU local.

## Limitaciones conocidas

Ver `docs/errores_extraccion.md` para el registro completo de anomalías detectadas.
