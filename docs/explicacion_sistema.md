# ¿Qué construimos y cómo funciona? — Sistema RAG sobre FDS CORONA

**Curso:** NLP – Semestre 8 | **Equipo:** Alan Osorio, Santiago, Juan

---

## ¿Qué construimos?

Un **sistema RAG (Retrieval-Augmented Generation)** que permite hacerle preguntas en lenguaje natural a 17 Fichas de Datos de Seguridad (FDS) del fabricante CORONA, y recibir respuestas con citas exactas de sección y página. Todo corre **localmente**, sin APIs de pago ni internet.

---

## Fase 1: Pipeline de extracción PDF → Markdown

### ¿Por qué no usar un lector de PDF normal?

Los PDFs de FDS tienen estructura compleja: texto con jerarquía de encabezados (negrita, tamaño de fuente), tablas con celdas fusionadas, e imágenes con pictogramas GHS. Un `pdf.read()` simple devuelve texto plano sin estructura — pierde todo el contexto de "esto está en la Sección 8".

### ¿Qué hace cada herramienta?

**PyMuPDF** (`fitz`): extrae texto bloque a bloque y lee los metadatos de cada fuente (tamaño, si es negrita). Con eso inferimos jerarquía: texto grande+negrita = encabezado `##`, texto mediano = `###`, texto normal = párrafo. Esto nos da la estructura GHS de 16 secciones.

**pdfplumber**: especializado en tablas. Detecta las líneas que forman celdas y extrae el contenido de cada celda por separado. PyMuPDF no hace esto bien porque las tablas son imágenes de líneas, no texto estructurado.

**Tesseract OCR + PIL (Pillow)**: los PDFs tienen imágenes incrustadas (logos, pictogramas de peligro GHS como la llama, el cráneo, etc.). Tesseract convierte esas imágenes a texto. Aunque el resultado sea "corona" o texto ilegible para los logos, lo importante es generar una **nota de trazabilidad**: `"La información asociada a esta figura se encuentra en la Sección 2: Identificación de peligros."` Esto le permite al RAG saber que la imagen está relacionada con esa sección.

> **¿Por qué descartamos Docling?** Requiere dependencias pesadas y GPU para funcionar bien. En CPU pura no era viable.

### Resultado

17 archivos `.md` en `output/markdown/`. Cada uno tiene:

```markdown
## SECCIÓN 8: Controles de exposición/protección personal
| EPP              | Normativa          |
|------------------|--------------------|
| Máscara autofiltrante | NTC 1584      |
...
![imagen_p4](../output/images/FDS_88_p4_1.png)
> Nota de trazabilidad: esta figura está en Sección 2.
```

---

## Fase 2: Chunking semántico

### ¿Qué es un chunk?

Un "trozo" de texto que se indexa individualmente. Si indexas documentos enteros, el modelo de embeddings no puede distinguir información relevante. Si los trozos son demasiado pequeños, pierdes contexto.

### ¿Por qué chunking por sección GHS?

Las FDS siguen la norma GHS con **16 secciones estándar** siempre en el mismo orden: identificación, peligros, composición, primeros auxilios, incendios, vertidos, manipulación, EPP, propiedades físicas, estabilidad, toxicología, ecología, eliminación, transporte, regulación, información adicional.

Estas secciones son **límites semánticos naturales**. Un chunk que cruce de "Sección 8: EPP" a "Sección 9: Propiedades físicas" mezclaría "usar guantes de nitrilo" con "densidad 1371 kg/m³" — información incompatible que confundiría al modelo.

### Reglas de chunking

| Regla | Valor |
|---|---|
| Límite primario | encabezado `## SECCIÓN N:` nunca se cruza |
| Textos largos | máximo 800 palabras con overlap de 100 palabras |
| Tablas | unidades atómicas — nunca se dividen |
| **Total chunks** | **1212 (767 texto + 445 tabla)** |

El **overlap de 100 palabras** significa que las últimas 100 palabras del chunk anterior se repiten al inicio del siguiente — para no perder contexto en los bordes entre fragmentos.

### Metadatos por chunk

Cada chunk almacena: `documento`, `seccion_num`, `seccion_titulo`, `pagina`, `tipo` (texto/tabla). Esto es lo que permite decir "esta respuesta viene de FDS 88, Sección 8, página 4".

---

## Fase 3: Indexación (construir la memoria del sistema)

Se construyen **dos índices paralelos** con los 1212 chunks:

### Índice denso — ChromaDB + fastembed

**fastembed** convierte cada chunk a un vector de 384 números (embedding). El modelo es `paraphrase-multilingual-MiniLM-L12-v2` de Sentence Transformers, pero ejecutado en **ONNX Runtime** — sin PyTorch, sin GPU, solo ~241 MB. Es multilingüe y funciona bien con español técnico.

**¿Qué captura un embedding?** El *significado semántico*. Si preguntas "¿qué protección necesito para los ojos?" y el chunk dice "se requiere pantalla facial", el embedding entiende que son conceptualmente similares aunque no compartan palabras exactas.

**ChromaDB** almacena los 1212 vectores con un índice **HNSW** (Hierarchical Navigable Small World) — una estructura de grafo que permite búsqueda aproximada de vecinos más cercanos muy rápido. Usa **similitud coseno**: mide el ángulo entre vectores (0 = opuesto, 1 = idéntico en dirección). Persiste en SQLite en `data/chroma_db/`.

### Índice sparse — BM25

**BM25** (Best Match 25) es el algoritmo base de motores de búsqueda tradicionales. Construye un índice invertido: para cada palabra, guarda en qué chunks aparece y cuántas veces. La fórmula pondera la frecuencia de término (TF) penalizando documentos muy largos.

**¿Por qué necesitamos BM25 si ya tenemos embeddings?**

Los embeddings no son buenos con términos exactos: números CAS (`7732-18-5`), códigos de peligro (`H226`, `H304`), nombres técnicos (`isotiazolinas`), números de sección. BM25 los encuentra exactamente porque busca coincidencias léxicas. Los embeddings son buenos con paráfrasis y sinónimos. Necesitamos los dos.

---

## Fase 4: Búsqueda híbrida (Retrieval)

Cuando el usuario hace una pregunta, se lanzan **dos búsquedas en paralelo**:

1. **Dense search**: la pregunta se convierte a embedding con fastembed → se buscan los 20 chunks más similares en ChromaDB por coseno
2. **Sparse search**: la pregunta se tokeniza → BM25 busca los 20 chunks con mayor puntuación

Luego se fusionan con **Reciprocal Rank Fusion (RRF)**:

```
score(chunk) = 1/(60 + rank_dense) + 1/(60 + rank_sparse)
```

El 60 es un parámetro de suavizado estándar. Un chunk que aparece en posición 3 en dense y posición 5 en sparse obtiene un score combinado alto. Se toman los **top 7 chunks**.

> **¿Por qué k=7 y no k=5?** Con k=5 hubo un fallo documentado: el §9 de FDS 67 (flash point de Pintura Exteriores) no aparecía en los top-5. Con k=7 sí aparecía en posición 7. El sistema con k=5 respondía "No encontrado" — correcto técnicamente (no alucinó), pero incompleto.

> **¿Por qué no simplemente sumar scores?** Sumar scores requiere que las escalas de BM25 y coseno sean comparables (no lo son — BM25 puede dar 15.3, coseno da 0.87). RRF convierte ambos a rankings ordinales antes de combinar, eliminando el problema de escala.

---

## Fase 5: Generación (el LLM)

Los 7 chunks recuperados se formatean en un contexto y se pasan a **Ollama** con **qwen2.5:7b**:

```
[1] FDS 88 | Sección 8: EPP | Pág. 4
<texto del chunk>
---
[2] FDS 29 | Sección 8: EPP | Pág. 4
<texto del chunk>
...

PREGUNTA: ¿Qué EPP necesito para Pintura Lavable?

RESPUESTA (con citas de sección y página):
```

El prompt **prohíbe explícitamente** inventar información:
> *"Si la información no está en el contexto responde: No encontrado en los documentos disponibles."*

Esto elimina alucinaciones — el LLM solo puede usar los chunks que recibió.

### ¿Por qué qwen2.5:7b?

Es el modelo con mejor desempeño en español técnico entre los disponibles localmente (mejor que llama3 y mistral en benchmarks de seguimiento de instrucciones). Temperatura 0.1 para respuestas factuales deterministas. Corre en CPU (~4.7 GB, ~2 min/pregunta en la máquina local sin GPU dedicada).

---

## Fase 6: Evaluación

### Ground truth

35 pares pregunta-respuesta construidos manualmente revisando los .md generados. 4 tipos:

| Tipo | N | Descripción |
|---|---|---|
| Factual | 12 | Valor numérico concreto (pH, densidad, temperatura) |
| Técnica | 9 | Procedimientos (EPP, primeros auxilios, incendio) |
| Trazabilidad | 9 | ¿En qué sección está X? |
| Multi_documento | 5 | ¿Qué productos tienen Y? (compara varios FDS) |

### Métricas calculadas

**Trazabilidad de sección**: ¿apareció la sección correcta entre los 7 chunks recuperados?

**Cobertura documental**: ¿apareció el documento correcto entre los 7 chunks?

**Similitud semántica coseno**: `embed(respuesta_RAG) · embed(respuesta_referencia)`. Requiere correr el LLM para las 35 preguntas (~70 min en CPU). Se ejecutó en Google Colab T4 para los ejemplos cualitativos.

### Resultados

| Tipo | N | Trazabilidad sección | Cobertura documento |
|---|---|---|---|
| Factual | 12 | 75.0% | **100%** |
| Técnica | 9 | 77.8% | 88.9% |
| Multi_documento | 5 | **100%** | 40.0% |
| Trazabilidad | 9 | 55.6% | 44.4% |
| **GLOBAL** | **35** | **74.3%** | **74.3%** |

**Interpretación:**
- Factual 100% de cobertura: cuando la pregunta tiene un número (densidad, pH), el retriever siempre encuentra el documento correcto
- Multi_documento 100% de trazabilidad pero 40% de cobertura: recupera la sección correcta de varios documentos pero no siempre el documento principal entre los top-7
- Trazabilidad baja cobertura: preguntas genéricas como "¿en qué sección está X?" compiten con chunks de contenido de varios documentos similares

---

## ¿Por qué todo local? ¿No tiene sentido conectarse a internet?

Tiene todo el sentido. Las FDS contienen información confidencial de formulaciones químicas. En contextos industriales reales, estos documentos no pueden enviarse a APIs externas (OpenAI, Anthropic, etc.) por:
- Confidencialidad comercial (composición de productos)
- Cumplimiento normativo (Decreto 1496/2018, GDPR equivalente)
- Disponibilidad offline (plantas industriales sin internet confiable)

El sistema funciona completamente sin conexión una vez instalado.

---

## Preguntas frecuentes

**¿Qué es HNSW?**
Hierarchical Navigable Small World. Una estructura de grafo que organiza los vectores en capas jerárquicas. Para buscar el vecino más cercano no revisa los 1212 vectores uno a uno (O(n)) sino que navega el grafo saltando entre capas (O(log n)). Permite búsqueda aproximada muy rápida con pérdida mínima de precisión.

**¿Qué es un embedding?**
Una representación numérica de texto como vector en un espacio de alta dimensión (aquí, 384 dimensiones). El modelo fue entrenado para que textos con significado similar queden cerca en ese espacio (distancia coseno pequeña). "Guantes de protección química" y "EPP para manos" quedarían cerca aunque no compartan palabras.

**¿Por qué overlap en los chunks?**
Si un dato importante cae justo en el borde entre dos chunks (por ejemplo, una tabla que empieza al final de un chunk), sin overlap ese dato se pierde o queda partido. Las 100 palabras repetidas garantizan que el contexto fronterizo esté representado en ambos chunks.

**¿Qué pasa si el RAG no encuentra la respuesta?**
El prompt instruye al LLM a responder "No encontrado en los documentos disponibles." en lugar de inventar. Esto se verificó en la evaluación: 0 de 35 preguntas tuvieron respuesta fabricada (flag `sin_respuesta`). El sistema prefiere admitir que no sabe antes que alucinar.

**¿Por qué fastembed y no sentence-transformers?**
`sentence-transformers` requiere PyTorch (~2 GB). `fastembed` usa el mismo modelo pero en formato ONNX (~241 MB total), corre en CPU sin dependencias pesadas, y la diferencia de calidad es mínima para este caso de uso.

**¿El sistema es extensible a otros fabricantes?**
Sí. El pipeline acepta `--fabricante` como parámetro. Para indexar Pintuco o SIKA se ejecuta `run_pipeline.py` con los PDFs del nuevo fabricante y se crea una colección nueva en ChromaDB. El código de retrieval y generación es idéntico.

**¿Cuál es la mayor limitación?**
La velocidad del LLM en CPU (~2 min/pregunta). En producción se resuelve con GPU dedicada (≥8 GB VRAM) o sustituyendo Ollama por cualquier endpoint OpenAI-compatible. El retrieval, los embeddings y el chunking son instantáneos.
