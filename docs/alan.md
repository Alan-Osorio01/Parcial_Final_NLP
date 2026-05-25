# Asignación: Alan — OCR de Imágenes + Sistema RAG Core
> **Rol:** Responsable de trazabilidad de imágenes y motor RAG completo  
> **Carga estimada:** ~35% del proyecto  
> **Criterios de nota cubiertos:** Pipeline OCR (parte del 20%) + Arquitectura (20%) + RAG (10%) = **~30% directo + impacto en trazabilidad del 30%**

---

## Objetivo general

Dos responsabilidades conectadas:
1. **OCR de imágenes**: Extraer texto de imágenes dentro de los PDFs y asociarlas correctamente a su sección/tabla mediante notas de trazabilidad.
2. **Sistema RAG end-to-end**: Tomar los `.md` que genera Santiago, fragmentarlos inteligentemente, indexarlos en una vector store local y exponer un sistema de consulta con respuestas trazadas.

---

## Bloque A: OCR e Imágenes

### A1. `src/pipeline/ocr.py` — Extractor de imágenes + OCR

**Qué hace:** Extrae imágenes embebidas en los PDFs, les aplica OCR con Tesseract para obtener el texto, y determina a qué sección/tabla pertenecen por proximidad espacial.

**Herramientas:** `PyMuPDF` (extracción de imágenes), `pytesseract` (OCR local), `Pillow` (preprocesamiento).

**Pasos:**
1. Instalar dependencias:
   ```bash
   pip install pytesseract Pillow pymupdf
   sudo apt install tesseract-ocr tesseract-ocr-spa  # español
   ```
2. Con `fitz.open(pdf_path)`, iterar páginas e identificar imágenes:
   ```python
   for page_num, page in enumerate(doc):
       for img_index, img in enumerate(page.get_images(full=True)):
           xref = img[0]
           base_image = doc.extract_image(xref)
           image_bytes = base_image["image"]
   ```
3. Guardar cada imagen en `output/images/img_p{page}_{index}.png`.
4. Aplicar OCR:
   ```python
   import pytesseract
   from PIL import Image
   text = pytesseract.image_to_string(image, lang='spa')
   ```
5. Determinar la sección padre: buscar en el texto que precede a la imagen (en la misma página o página anterior) a qué sección GHS pertenece.
6. Devolver lista de objetos `ImageBlock`:
   ```python
   {
     "path": "output/images/img_p5_1.png",
     "ocr_text": "...",
     "page": 5,
     "section_num": 9,
     "related_table": "Tabla 4",
     "traceability_note": "La información numérica de esta figura se encuentra en la Tabla 4 de la Sección 9."
   }
   ```
7. Pasar esta lista a `md_writer.py` de Santiago para que inserte las imágenes con sus notas en el `.md`.

---

## Bloque B: Sistema RAG

### B1. `src/rag/chunker.py` — Fragmentador por sección

**Qué hace:** Lee los `.md` generados por Santiago y los divide en chunks semánticamente coherentes, preservando metadatos de trazabilidad.

**Estrategia de chunking:**
- **Unidad base:** 1 subsección de las 16 secciones GHS (granularidad natural para consultas FDS).
- **Si una subsección > 800 tokens:** dividir por párrafos con overlap de 100 tokens.
- **Tablas:** siempre como un chunk completo (no partir filas).
- **Imágenes OCR:** chunk independiente referenciando sección padre.

**Metadatos por chunk:**
```python
{
  "chunk_id": "corona_fds29_sec9_chunk2",
  "documento": "FDS 29 - PINTURA PRIMERA MANO",
  "fabricante": "CORONA",
  "seccion_num": 9,
  "seccion_titulo": "Propiedades físicas y químicas",
  "tipo": "texto",  # o "tabla" o "imagen_ocr"
  "pagina": 4,
  "texto": "..."
}
```

**Pasos:**
1. Cargar `.md` de `output/markdown/`.
2. Parsear secciones con el mismo regex de `sections.py` de Santiago (reutilizar).
3. Para cada sección, dividir en chunks con `langchain_text_splitters.MarkdownHeaderTextSplitter` o implementación propia.
4. Asignar metadatos y guardar en lista de dicts.

---

### B2. `src/rag/embedder.py` — Generación de embeddings

**Qué hace:** Convierte cada chunk de texto en un vector numérico para búsqueda semántica.

**Modelo:** `BAAI/bge-m3` (multilingüe, soporta español, descarga local ~2GB) o `paraphrase-multilingual-MiniLM-L12-v2` (~400MB, más liviano).

```bash
pip install sentence-transformers
```

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-m3")  # o multilingual-MiniLM

def embed_chunks(chunks: list[dict]) -> list[dict]:
    texts = [c["texto"] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=True)
    for chunk, emb in zip(chunks, embeddings):
        chunk["embedding"] = emb.tolist()
    return chunks
```

---

### B3. `src/rag/vectorstore.py` — Índice vectorial local

**Qué hace:** Almacena los chunks y sus embeddings en ChromaDB local (persistente, sin servidor).

```bash
pip install chromadb
```

**Pasos:**
1. Crear cliente ChromaDB persistente en `data/chroma_db/`.
2. Crear colección por fabricante (`corona_fds`, etc.).
3. Insertar chunks con embeddings y metadatos.
4. Función de búsqueda por similitud:
   ```python
   def search(query: str, n_results: int = 5) -> list[dict]:
       query_emb = model.encode([query])[0]
       results = collection.query(
           query_embeddings=[query_emb.tolist()],
           n_results=n_results,
           include=["documents", "metadatas", "distances"]
       )
       return results
   ```

---

### B4. `src/rag/retriever.py` — Retriever híbrido

**Qué hace:** Combina búsqueda densa (embeddings) con BM25 (keyword) para mayor recall, y re-rankea los top-k resultados.

```bash
pip install rank-bm25
```

**Pasos:**
1. Indexar todos los textos de chunks en BM25.
2. Al recibir una query: correr búsqueda densa Y BM25 en paralelo.
3. Combinar resultados con Reciprocal Rank Fusion (RRF).
4. Devolver top-5 chunks con sus metadatos completos.

```python
def hybrid_search(query: str, k: int = 5) -> list[dict]:
    dense_results = vector_search(query, k=k*2)
    bm25_results = bm25_search(query, k=k*2)
    return reciprocal_rank_fusion(dense_results, bm25_results, k=k)
```

---

### B5. `src/rag/generator.py` — Generador con Ollama

**Qué hace:** Toma los chunks recuperados, construye un prompt y llama al LLM local (Ollama) para generar la respuesta con citas.

**Modelo recomendado:** `qwen2.5:7b` (buen español) o `llama3.1:8b`.

```bash
# Instalar Ollama
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull qwen2.5:7b
pip install ollama
```

**Prompt template:**
```
Eres un experto en Fichas de Datos de Seguridad (FDS). 
Responde la pregunta usando ÚNICAMENTE la información del contexto proporcionado.
Para cada dato cita la fuente: [Documento, Sección N, pág. X].
Si la información no está en el contexto, di "No encontrado en los documentos disponibles."

CONTEXTO:
{context}

PREGUNTA: {query}

RESPUESTA (con citas):
```

**Pasos:**
1. Recibir query del usuario.
2. Recuperar chunks con `retriever.py`.
3. Construir contexto concatenando textos + metadatos de cada chunk.
4. Llamar a Ollama:
   ```python
   import ollama
   response = ollama.chat(model="qwen2.5:7b", messages=[
       {"role": "user", "content": prompt}
   ])
   ```
5. Devolver respuesta + lista de chunks fuente.

---

### B6. CLI de consulta `src/rag/query_cli.py`

**Qué hace:** Interfaz mínima para demostrar el sistema funcionando.

```python
# Uso: python src/rag/query_cli.py
query = input("Pregunta: ")
answer, sources = rag_chain(query)
print(f"\nRespuesta:\n{answer}\n")
print("Fuentes:")
for s in sources:
    print(f"  - {s['documento']} §{s['seccion_num']}, p.{s['pagina']}")
```

---

## Orden de ejecución sugerido

```
Día 1: Configurar entorno (Ollama + modelos), probar OCR en 1-2 PDFs
Día 2: Completar ocr.py, entregar ImageBlocks a Santiago para el md_writer
Día 3: chunker.py + embedder.py sobre los primeros .md de Santiago
Día 4: vectorstore.py + retriever.py + generator.py
Día 5: query_cli.py, pruebas end-to-end, ajuste de prompts
```

---

## Lo que Alan necesita de Santiago

- `.md` completos en `output/markdown/` (mínimo 2-3 para empezar a probar).
- Estructura de secciones para reutilizar en el chunker.

## Lo que Alan entrega a Juan

- Sistema RAG funcional con trazabilidad.
- `query_cli.py` corriendo.
- Respuestas de ejemplo para el ground truth evaluation.

---

## Checklist de entrega

- [ ] `ocr.py` extrae imágenes con OCR y notas de trazabilidad
- [ ] `chunker.py` con metadatos por sección completos
- [ ] `embedder.py` usando modelo local multilingüe
- [ ] `vectorstore.py` con ChromaDB persistente
- [ ] `retriever.py` híbrido BM25 + denso
- [ ] `generator.py` con Ollama y prompt con citas
- [ ] `query_cli.py` funcional
- [ ] Al menos 3 consultas de ejemplo guardadas en `eval/sample_queries.txt`

---

## Dependencias completas

```bash
pip install sentence-transformers chromadb rank-bm25 ollama \
            langchain langchain-text-splitters pytesseract \
            Pillow pymupdf python-dotenv
sudo apt install tesseract-ocr tesseract-ocr-spa
# Ollama
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull qwen2.5:7b
```
