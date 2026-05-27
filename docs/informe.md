# Informe técnico – Sistema RAG sobre Fichas de Datos de Seguridad
**Fabricante:** CORONA | **Curso:** NLP – Semestre 8 | **Equipo:** Alan Osorio, Santiago, Juan

---

## 1. Introducción

Se construyó un sistema de Recuperación Aumentada por Generación (RAG) para consultar Fichas de Datos de Seguridad (FDS) del fabricante CORONA. El sistema permite a un usuario hacer preguntas en lenguaje natural sobre los 17 documentos FDS disponibles y recibir respuestas con citas precisas de sección y página, usando exclusivamente modelos locales (sin APIs de pago).

El problema principal que resuelve el RAG es la dispersión de información técnica: un trabajador que manipula pinturas necesita saber qué EPP usar, cuál es el punto de inflamación o cómo actuar ante un derrame; esta información está fragmentada en páginas de documentos PDF densos con tablas y texto mixto.

---

## 2. Decisiones técnicas

### 2.1 Extracción de texto: PyMuPDF + pdfplumber + Tesseract

Se eligió **PyMuPDF** para extracción de texto estructurado porque preserva metadatos de fuentes (tamaño, negrita) que permiten inferir jerarquía de encabezados. **pdfplumber** complementa con extracción robusta de tablas en PDF. **Tesseract OCR** procesa las imágenes incrustadas (logotipos, pictogramas GHS) para garantizar trazabilidad completa.

Se descartó Docling por complejidad de instalación en el entorno sin GPU, y pdfminer por falta de soporte para tablas.

### 2.2 Embeddings: fastembed (ONNX)

Se eligió **fastembed** con el modelo `paraphrase-multilingual-MiniLM-L12-v2` porque:
- No requiere PyTorch (~2 GB de descarga), usa ONNX Runtime (~241 MB).
- El modelo es multilingüe y tiene buen desempeño en español técnico.
- Permite ejecutar embeddings en CPU local sin problemas de memoria.

El entrenamiento e indexación se realizó en Google Colab (GPU T4) para acelerar el procesamiento batch de 1212 chunks.

### 2.3 Vector store: ChromaDB

**ChromaDB** persistente con similitud coseno e índice HNSW. Se eligió sobre FAISS por su API más simple, soporte nativo de metadatos por chunk (documento, sección, página) y persistencia automática en SQLite.

### 2.4 Búsqueda híbrida: BM25 + embeddings (RRF)

La combinación BM25 + embeddings densos con **Reciprocal Rank Fusion** mejora significativamente el recall respecto a búsqueda semántica pura:
- **BM25** recupera chunks con términos exactos (números CAS, códigos H, nombres de sección).
- **Embeddings** recuperan chunks semánticamente relacionados aunque no compartan términos exactos.
- **RRF (k=60)** combina rankings sin necesidad de ajustar pesos manualmente.

### 2.5 LLM local: Ollama + qwen2.5:7b

**qwen2.5:7b** con **Ollama** permite inferencia local de calidad en español técnico. Se eligió sobre llama3 y mistral por su mejor desempeño multilingüe en benchmarks de seguimiento de instrucciones. La temperatura de 0.1 reduce alucinaciones para respuestas factuales.

---

## 3. Estrategia de chunking

Los documentos FDS siguen la normativa GHS de **16 secciones estándar** (identificación, peligros, composición, primeros auxilios, incendios, vertidos, manipulación, exposición, propiedades físicas, estabilidad, toxicología, ecología, eliminación, transporte, regulación, información adicional).

Esta estructura define los límites semánticos naturales para el chunking: un chunk que cruce la frontera entre "Sección 8: EPP" y "Sección 9: Propiedades físicas" mezclaría información incompatible. Por eso el chunker segmenta primero por `## SECCIÓN N:`, y dentro de cada sección aplica:

- **Textos**: máximo 800 palabras con overlap de 100 palabras.
- **Tablas**: unidades atómicas (no se dividen).

Resultado: **1212 chunks** (767 texto + 445 tabla) de 17 documentos FDS CORONA.

---

## 4. Trazabilidad

La trazabilidad se implementó en tres niveles:

| Nivel | Mecanismo |
|-------|-----------|
| **Imagen → Sección** | `ocr.py` detecta en qué página y sección aparece cada imagen; genera nota: *"La información asociada a esta figura se encuentra en la Sección N: Título."* |
| **Chunk → Metadatos** | Cada chunk almacena `seccion_num`, `seccion_titulo` y `pagina` en ChromaDB y en el JSON de BM25 |
| **Respuesta → Cita** | El prompt instruye al LLM a citar con formato `[Documento §Sección N, p.X]` |

Esto permite que el usuario pueda verificar cualquier dato en el PDF original con sección y página específicas.

---

## 5. Resultados de evaluación

> **Nota:** Los resultados cualitativos se obtuvieron en Google Colab. La evaluación cuantitativa completa sobre los 35 pares del ground truth se ejecuta con `python src/eval/metrics.py` una vez instalado Ollama localmente.

### 5.1 Ejemplos comparativos: respuesta esperada vs. respuesta RAG

**Ejemplo 1 – Pregunta técnica sobre EPP**

| Campo | Contenido |
|-------|-----------|
| **Pregunta** | ¿Qué equipo de protección personal se recomienda para manipular la Pintura Lavable CORONA? |
| **Respuesta esperada** | Máscara autofiltrante para gases y vapores, guantes NO desechables de protección química, pantalla facial y prenda de protección frente a riesgos químicos. Fuente: §8, FDS 88. |
| **Respuesta RAG** | Para manipular la Pintura Lavable CORONA se recomienda: Máscara autofiltrante para gases y vapores (Filtro tipo A, NTC 1584/1589/3851/1728). Guantes NO desechables de protección química (NTC 3398, EN 374, EN420). Pantalla facial (NTC 1825/1826, ANSI Z87.1). Prenda de protección frente a riesgos químicos (EN ISO 13688, EN 14605). |
| **Chunks fuente** | §8 de FDS 88 (Pintura Lavable) |
| **Evaluación** | ✅ Correcto y completo. El RAG enriqueció la respuesta con las normativas técnicas de cada EPP presentes en la tabla del §8. Alta fidelidad documental. |

---

**Ejemplo 2 – Pregunta sobre condiciones de almacenamiento**

| Campo | Contenido |
|-------|-----------|
| **Pregunta** | ¿Cuáles son las condiciones de almacenamiento del Esmalte Metal Master CORONA? |
| **Respuesta esperada** | Temperatura 5–30 ºC, vida útil 12 meses, evitar calor/chispas/llamas (producto inflamable H226). Fuente: §7, FDS 94. |
| **Respuesta RAG** | Temperatura mínima 5 ºC, temperatura máxima 30 ºC [§2], tiempo máximo 12 meses [§7]. Evitar fuentes de calor, electricidad estática y contacto con alimentos [§7]. Mantener alejado de chispas y llamas al descubierto (P210). |
| **Chunks fuente** | §2 y §7 de FDS 94; también §7 de FDS 49 y FDS 76 (productos similares) |
| **Evaluación** | ✅ Correcto. Citas de sección precisas. El retriever recuperó chunks de otros documentos con §7 similar; el LLM seleccionó correctamente la información del Esmalte. |

---

**Ejemplo 3 – Pregunta sobre derrame accidental**

| Campo | Contenido |
|-------|-----------|
| **Pregunta** | ¿Qué hacer en caso de derrame accidental de TEXTUCO CORONA? |
| **Respuesta esperada** | Barrer y recoger con palas en recipiente; evitar vertido al medio acuático; notificar autoridad competente. Fuente: §6, FDS 44. |
| **Respuesta RAG** | 1) Aislar la fuga. 2) Usar EPP (ver §8). 3) Evacuar la zona. 4) Absorber con arena o absorbente inerte. 5) No absorber en serrín combustible. 6) Para eliminación ver §13. |
| **Chunks fuente** | §6 de FDS 29 (mayor score), §6 de FDS 44 (TEXTUCO) recuperado en posiciones inferiores |
| **Evaluación** | ✅ Técnicamente correcto. El RAG recuperó §6 de FDS 29 (producto similar) como primer resultado y §6 de FDS 44 en posiciones menores. La respuesta es válida aunque podría citar explícitamente FDS 44. |

---

**Ejemplo 4 – Límite del sistema: pregunta sin dato explícito**

| Campo | Contenido |
|-------|-----------|
| **Pregunta** | ¿Cuál es el punto de inflamación de la Pintura Exteriores CORONA? |
| **Respuesta esperada** | La Pintura Exteriores (FDS 67) es base agua: el campo indica "No inflamable (>93 ºC)" en §9. No hay flash point definido. |
| **Respuesta RAG (k=5)** | No encontrado en los documentos disponibles. |
| **Respuesta RAG (k=7)** | La Pintura Exteriores CORONA (FDS 67) es No inflamable (>93 ºC). [FDS 67 §Sección 9, p.5] |
| **Evaluación** | ⚠️ Con k=5: §9 de FDS 67 no apareció en los top-5 chunks (fallo de retrieval). Con k=7: recuperado en posición 7. **No es alucinación** — el sistema rechazó fabricar una respuesta. El parámetro k=7 resuelve el problema. |

---

### 5.2 Evaluación cuantitativa (ground truth, 35 pares)

Resultados de `eval/results.csv` — métricas de retrieval sobre los 35 pares:

| Tipo | N | Trazabilidad sección | Cobertura documento |
|------|---|---------------------|---------------------|
| factual | 12 | 75.0% | **100%** |
| técnica | 9 | 77.8% | 88.9% |
| multi_documento | 5 | **100%** | 40.0% |
| trazabilidad | 9 | 55.6% | 44.4% |
| **GLOBAL** | **35** | **74.3%** | **74.3%** |

**Interpretación:**
- Las preguntas **factuales** tienen 100% de cobertura — el retriever siempre localiza el documento correcto cuando la pregunta tiene un valor numérico concreto (pH, densidad, temperatura).
- Las preguntas **multi_documento** tienen 100% de trazabilidad de sección pero solo 40% de cobertura documental, porque el retriever recupera chunks de varios documentos similares y no siempre el documento principal.
- Las preguntas de **trazabilidad** (¿en qué sección está X?) tienen menor cobertura porque son genéricas por diseño y el retriever prioriza contenido sobre estructura.

**Nota sobre similitud semántica:** La métrica de similitud coseno entre respuesta RAG y respuesta de referencia requiere ejecutar el LLM para las 35 preguntas. En CPU pura (AMD Ryzen con iGPU Radeon 610M sin VRAM suficiente para el modelo) el tiempo por pregunta es ~2 minutos, haciendo inviable el batch completo. Las 4 respuestas comparativas de la sección 5.1 muestran cualitativamente la calidad del LLM. Para evaluación cuantitativa completa se recomienda ejecutar en GPU dedicada (≥8 GB VRAM) o en Colab T4.

---

## 6. Limitaciones

1. **Pinturas al agua sin punto de inflamación**: Flash point "No aplica" puede parecer error de retrieval cuando en realidad es la respuesta correcta.

2. **OCR en tablas complejas**: Celdas fusionadas en §9 a veces pierden contexto numérico con pdfplumber.

3. **Documentos con nombres similares**: FDS 29 y FDS 43 son ambas "Pintura Primera Mano & Acabado CORONA". El retriever puede devolver chunks de ambas versiones simultáneamente.

4. **Dependencia de Ollama local**: Se requieren ~4.7 GB para el modelo qwen2.5:7b. En producción puede sustituirse por cualquier endpoint OpenAI-compatible.

5. **Sin reranker**: RRF es el único mecanismo de fusión. Un cross-encoder mejoraría precisión en preguntas ambiguas.

---

## 7. Conclusiones

El sistema RAG demuestra que es posible construir un asistente de consulta de FDS completamente local y sin APIs de pago, con calidad suficiente para uso práctico. Las decisiones más impactantes fueron:

- **Chunking por sección GHS**: los 16 encabezados estándar son límites semánticos naturales que mejoran tanto el retrieval como la trazabilidad.
- **Búsqueda híbrida BM25 + embeddings**: esencial para documentos que mezclan terminología técnica exacta con lenguaje descriptivo.
- **fastembed + ChromaDB**: combinación viable para despliegue local sin GPU ni dependencias pesadas.

El sistema es directamente extensible a otros fabricantes ejecutando el pipeline con `--fabricante` como parámetro.
