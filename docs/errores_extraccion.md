# Errores y anomalías de extracción – CORONA

Registro de problemas detectados durante el pipeline PDF→MD sobre los 17 FDS de CORONA.

## Problemas encontrados

### 1. Celdas fusionadas en tablas de §9 (Propiedades físicas)

**Documentos afectados:** FDS 29, 43, 44, 88, 89, 91, 92, 93  
**Descripción:** Las tablas de propiedades físicas en la Sección 9 contienen celdas fusionadas horizontalmente para agrupar propiedades (ej. "Aspecto físico:", "Inflamabilidad:"). pdfplumber no reconstruye correctamente el contexto de estas celdas fusionadas.  
**Impacto:** Algunos valores numéricos (densidad, temperatura de ebullición) pueden perder su etiqueta de propiedad en la representación Markdown.  
**Mitigación:** El texto de sección 9 también aparece como párrafo en la extracción base de PyMuPDF, por lo que el chunker tiene texto redundante con el valor correcto.

### 2. Nombre de productos duplicados (FDS 29 y FDS 43)

**Documentos afectados:** FDS 29 y FDS 43  
**Descripción:** Ambas FDS llevan el mismo nombre de producto: "PINTURA PRIMERA MANO & ACABADO - CORONA". Se trata de versiones/formulaciones distintas con densidades levemente diferentes (1371.4 vs. valor de FDS 43).  
**Impacto:** Al consultar por nombre de producto, el retriever puede devolver chunks de ambos documentos. El LLM puede mezclar propiedades de ambas versiones.  
**Mitigación:** Usar el número de FDS (29 ó 43) en la consulta para discriminar.

### 3. OCR de logotipos e imágenes decorativas

**Documentos afectados:** Todos (626 imágenes en total)  
**Descripción:** Muchas imágenes son el logotipo de CORONA, pictogramas GHS o imágenes decorativas. Tesseract extrae texto mínimo o incorrecto de estas imágenes (ej. "corona", caracteres aislados).  
**Impacto:** Las notas de trazabilidad OCR para estas imágenes tienen poco valor informativo.  
**Mitigación:** Aceptable — la nota de trazabilidad sigue siendo útil para mapear la imagen a su sección de contexto, aunque el texto OCR sea escaso.

### 4. Codificación de nombres de archivo con caracteres especiales

**Documentos afectados:** FDS 61 (SEÑALIZACIÓN Y DEMARCACIÓN)  
**Descripción:** El nombre del archivo contiene caracteres Unicode de composición (Ñ como N + combinando tilde), lo que produce nombres de archivo inconsistentes en el sistema de archivos.  
**Impacto:** El nombre aparece como `FDS 61 - PINTURA SEN╠âALIZACIO╠üN Y DEMARCACIO╠üN - CORONA` en algunos contextos.  
**Mitigación:** El campo `documento` en los metadatos del chunk usa el stem del nombre de archivo, por lo que las consultas por nombre pueden no coincidir exactamente. Consultar por número de FDS (61) es más robusto.

### 5. Páginas con solo imágenes (sin texto extraíble)

**Documentos afectados:** Varios (principalmente páginas de portada)  
**Descripción:** Algunas páginas contienen únicamente imágenes sin texto digital subyacente. PyMuPDF no extrae bloques de texto de estas páginas.  
**Impacto:** La portada de los documentos no tiene texto indexado. Las imágenes de portada sí se procesan con OCR.  
**Mitigación:** La portada generalmente no contiene información de seguridad relevante para las consultas.

## Estadísticas del pipeline

| Métrica | Valor |
|---------|-------|
| PDFs procesados | 17 / 17 |
| PDFs con errores fatales | 0 |
| Imágenes extraídas (total) | 626 |
| Secciones detectadas | 16 / 16 en todos los documentos |
| Chunks generados | 1212 (767 texto + 445 tabla) |
| Tiempo de procesamiento | ~3-5 min (CPU local) |
