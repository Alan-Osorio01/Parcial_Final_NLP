import ollama

from src.rag.retriever import hybrid_search

MODEL = "qwen2.5:7b"

_PROMPT = """\
Eres un experto en Fichas de Datos de Seguridad (FDS) de productos de pintura.
Responde la pregunta usando ÚNICAMENTE la información del contexto proporcionado.
Para cada dato importante cita la fuente con el formato: [Documento §Sección N, p.X].
Si la información no está en el contexto responde: "No encontrado en los documentos disponibles."

CONTEXTO:
{context}

PREGUNTA: {query}

RESPUESTA (con citas de sección y página):"""


def _build_context(chunks: list[dict]) -> str:
    parts = []
    for i, c in enumerate(chunks, 1):
        sec = c.get("seccion_num", "?")
        sec_title = c.get("seccion_titulo", "")
        doc = c.get("documento", "")
        page = c.get("pagina") or "?"
        parts.append(f"[{i}] {doc} | Sección {sec}: {sec_title} | Pág. {page}\n{c['texto']}")
    return "\n\n---\n\n".join(parts)


def generate_answer(
    query: str,
    fabricante: str,
    k: int = 7,
    model: str = MODEL,
    num_predict: int = 1024,
) -> tuple[str, list[dict]]:
    chunks = hybrid_search(query, fabricante, k=k)

    if not chunks:
        return "No se encontraron documentos indexados para este fabricante.", []

    context = _build_context(chunks)
    prompt = _PROMPT.format(context=context, query=query)

    response = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.1, "num_predict": num_predict},
    )
    return response["message"]["content"], chunks
