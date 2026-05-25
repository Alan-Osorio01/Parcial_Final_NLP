# Asignación: Santiago — Pipeline PDF → Markdown
> **Rol:** Líder del pipeline de extracción documental  
> **Carga estimada:** ~35% del proyecto  
> **Criterios de nota cubiertos:** Calidad del pipeline (20%) + Fidelidad estructural del .md (30%) = **50% de la nota total**

---

## Objetivo general

Construir el pipeline que convierte los PDFs de Fichas de Datos de Seguridad (FDS) en archivos Markdown (`.md`) con fidelidad estructural completa. Este módulo es la base de todo el sistema: si el `.md` es de mala calidad, el RAG también lo será.

---

## Módulos a implementar

### 1. `src/pipeline/parser.py` — Extractor base de PDF

**Qué hace:** Lee el PDF e identifica bloques de texto, tablas e imágenes con sus coordenadas y posición de página.

**Herramienta principal:** `Docling` (IBM) — parsea PDF preservando layout.  
**Fallback:** `PyMuPDF` (`fitz`) + `pdfplumber` si Docling no maneja bien un PDF.

**Pasos:**
1. Instalar y configurar Docling: `pip install docling`
2. Cargar un PDF con `DocumentConverter` de Docling.
3. Exportar a Markdown usando el exportador nativo de Docling (`doc.export_to_markdown()`).
4. Si Docling falla en algún documento, usar PyMuPDF como backup:
   - `fitz.open(path)` → iterar páginas → extraer bloques de texto con `page.get_text("dict")`.
5. Guardar el resultado crudo antes de postprocesarlo.

```python
# src/pipeline/parser.py  (esquema básico)
from docling.document_converter import DocumentConverter

def parse_pdf(pdf_path: str) -> str:
    converter = DocumentConverter()
    result = converter.convert(pdf_path)
    return result.document.export_to_markdown()
```

---

### 2. `src/pipeline/sections.py` — Detector de las 16 secciones GHS

**Qué hace:** Detecta y etiqueta las 16 secciones normativas dentro del Markdown extraído para asegurar cobertura completa.

**Las 16 secciones GHS:**
1. Identificación del producto
2. Identificación de peligros
3. Composición / información sobre los componentes
4. Primeros auxilios
5. Medidas de lucha contra incendios
6. Medidas en caso de vertido accidental
7. Manipulación y almacenamiento
8. Controles de exposición / protección personal
9. Propiedades físicas y químicas
10. Estabilidad y reactividad
11. Información toxicológica
12. Información ecológica
13. Información sobre la eliminación
14. Información sobre el transporte
15. Información sobre la reglamentación
16. Otra información

**Pasos:**
1. Definir patrones regex para detectar encabezados de sección (ej: `SECCIÓN 1`, `Sección 1.`, `1.`, etc.).
2. Parsear el Markdown e identificar qué partes corresponden a cada sección.
3. Si alguna sección no se detecta → loguear en `docs/errores_extraccion.md` con estrategia de mitigación.
4. Devolver un diccionario `{num_seccion: {titulo, contenido_md}}`.

```python
# src/pipeline/sections.py  (esquema básico)
import re

SECTION_PATTERN = re.compile(
    r'(?i)(secci[oó]n\s*(\d{1,2})[:\.]?\s*(.+))', re.MULTILINE
)

def extract_sections(markdown_text: str) -> dict:
    # detectar y mapear las 16 secciones
    ...
```

---

### 3. `src/pipeline/tables.py` — Extractor de tablas

**Qué hace:** Extrae tablas del PDF y las convierte a formato Markdown con estructura de celdas intacta.

**Herramienta:** `pdfplumber` (mejor para tablas de texto) o `Camelot` (para tablas con bordes).

**Pasos:**
1. Instalar: `pip install pdfplumber camelot-py[cv]`
2. Detectar páginas con tablas usando `pdfplumber.open(path)`.
3. Para cada tabla, extraer celdas con `page.extract_table()`.
4. Convertir a Markdown table:
   ```
   | col1 | col2 | col3 |
   |------|------|------|
   | val1 | val2 | val3 |
   ```
5. Reemplazar la tabla en el Markdown final con la versión bien formateada.
6. Preservar el número de sección donde aparece la tabla (para trazabilidad).

---

### 4. `src/pipeline/md_writer.py` — Escritor final de Markdown

**Qué hace:** Ensambla el `.md` final con toda la estructura: secciones, tablas, bloques de imágenes (con notas de trazabilidad), respetando el formato requerido por el enunciado.

**Pasos:**
1. Tomar el dict de secciones + tablas + imágenes OCR (que entrega Alan).
2. Escribir el `.md` con encabezados jerárquicos:
   ```markdown
   # FDS – [Nombre del Producto] – [Fabricante]
   
   ## SECCIÓN 1: Identificación del producto
   ...contenido...
   
   ## SECCIÓN 9: Propiedades físicas y químicas
   ...
   | Propiedad | Valor |
   |-----------|-------|
   | ...       | ...   |
   
   ![imagen_seccion9_tabla4](../output/images/img_p5_fig1.png)
   > *Nota de trazabilidad: La información numérica asociada a esta figura se encuentra en la Tabla 4 de la Sección 9.*
   ```
3. Guardar en `output/markdown/<nombre_producto>.md`.
4. Correr validación final: verificar que las 16 secciones estén presentes y que no haya tablas vacías.

---

### 5. `docs/errores_extraccion.md` — Log de errores y mitigaciones

**Qué hace:** Documenta honestamente qué no se extrajo bien y cómo se compensó.

**Pasos:**
1. Registrar cada PDF que presentó problemas (secciones faltantes, tablas mal parseadas, imágenes sin OCR usable).
2. Para cada error indicar:
   - Tipo de error
   - PDF afectado
   - Sección afectada
   - Estrategia de mitigación aplicada
3. Este documento va directo al informe final.

---

## Orden de ejecución sugerido

```
Día 1: Instalar Docling + PyMuPDF, probar en 1-2 PDFs, ver calidad raw
Día 2: Implementar sections.py + verificar las 16 secciones en todos los docs
Día 3: Implementar tables.py, reemplazar tablas en el MD
Día 4: Implementar md_writer.py, generar .md completos para todos los PDFs del fabricante
Día 5: Revisar calidad, completar log de errores
```

---

## Dependencias que Santiago entrega a Alan

- Archivos `.md` completos en `output/markdown/` (uno por PDF).
- Dict/JSON de metadatos por sección: `output/metadata/secciones.json`.
- Log de errores: `docs/errores_extraccion.md`.

---

## Checklist de entrega

- [ ] Todos los PDFs del fabricante convertidos a `.md`
- [ ] Las 16 secciones detectadas en cada documento
- [ ] Tablas en formato Markdown correcto
- [ ] Espacio para imágenes OCR con nota de trazabilidad (placeholder si Alan aún no terminó)
- [ ] `docs/errores_extraccion.md` completado
- [ ] `src/pipeline/` con código limpio y comentado
- [ ] Al menos 1 `.md` de ejemplo en el README

---

## Instalación de dependencias

```bash
pip install docling pymupdf pdfplumber camelot-py[cv] python-dotenv
```

> **Nota:** Si `camelot` da problemas de instalación (necesita ghostscript), usar solo `pdfplumber` que es más ligero.
