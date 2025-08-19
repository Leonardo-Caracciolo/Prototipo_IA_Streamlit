# core/rag_leyes.py
import os, re, json
from typing import Optional, List, Dict
from pathlib import Path

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.embeddings import CacheBackedEmbeddings
from langchain.storage import LocalFileStore

import chromadb
from chromadb.config import Settings

# ========= Config desde .env (mismos nombres que tu vectorizador) =========
CENTRAL_ROOT    = Path(os.getenv("CENTRAL_DOCS_ROOT", "../Leyes")).resolve()
PERSIST_DIR     = Path(os.getenv("VECTORSTORE_DIR", "../leyes_vectorizer")).resolve()
COLLECTION_NAME = os.getenv("VECTOR_COLLECTION", "central_leyes")
DOMAIN_TAG      = os.getenv("DOMAIN_TAG", "leyes")

EMBEDDINGS_PROVIDER = os.getenv("EMBEDDINGS_PROVIDER", "auto")  # auto | openai | local
OPENAI_EMBED_MODEL  = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
CACHE_EMBEDDINGS    = os.getenv("CACHE_EMBEDDINGS", "true").lower() == "true"

CHROMA_SETTINGS = Settings(
    anonymized_telemetry=os.getenv("CHROMA_TELEMETRY", "false").lower() == "true"
)

_ART_RE = re.compile(r"(?i)\b(?:art(?:[íi]culo)?\.?\s*)(\d+[a-z]?)\b")

def _build_embedder():
    """Usa el mismo proveedor/modelo que el indexado para evitar mismatch de dimensiones."""
    use_openai = (EMBEDDINGS_PROVIDER == "openai") or (
        EMBEDDINGS_PROVIDER == "auto" and os.getenv("OPENAI_API_KEY")
    )
    if use_openai:
        base = OpenAIEmbeddings(model=OPENAI_EMBED_MODEL)
    else:
        # Local sin tokens (requiere sentence-transformers instalado)
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("intfloat/multilingual-e5-small")
        class _Local:
            def embed_documents(self, texts: List[str]): 
                return model.encode(texts, normalize_embeddings=True).tolist()
            def embed_query(self, text: str): 
                return self.embed_documents([text])[0]
        base = _Local()

    if CACHE_EMBEDDINGS:
        cache_dir = PERSIST_DIR / "embed_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            return CacheBackedEmbeddings.from_bytes_store(base, LocalFileStore(str(cache_dir)))
        except Exception:
            return base
    return base

_EMB = _build_embedder()

def _open_vectorstore() -> Chroma:
    PERSIST_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(PERSIST_DIR), settings=CHROMA_SETTINGS)
    return Chroma(
        client=client,
        collection_name=COLLECTION_NAME,
        persist_directory=str(PERSIST_DIR),
        embedding_function=_EMB,
    )

def _extract_article_hint(q: str) -> Optional[str]:
    m = _ART_RE.search(q or "")
    return f"Artículo {m.group(1)}" if m else None

def _where_and(**kv) -> dict:
    clauses = []
    for k, v in kv.items():
        if v is not None:
            clauses.append({k: {"$eq": v}})
    return {"$and": clauses} if clauses else {}

def _trim(txt: str, max_chars: int = 2000) -> str:
    if len(txt) <= max_chars: 
        return txt
    return txt[:max_chars] + " …"

# =============== FUNCIÓN PRINCIPAL (se expondrá como herramienta) ===============
def buscar_leyes(query: str,
                 k: int = 5,
                 expand_article: bool = True,
                 law: Optional[str] = None,
                 article: Optional[str] = None,
                 workspace: Optional[str] = None) -> str:
    """
    Busca contexto en el índice central de leyes/jurisprudencia.

    Args:
      - query: consulta del usuario.
      - k: top-k para similarity.
      - expand_article: si True, y el top-1 tiene 'article', devuelve el artículo completo.
      - law: filtro exacto por 'law' (ruta relativa sin extensión) si lo conocés.
      - article: filtro exacto por 'Artículo ...' si lo conocés.
      - workspace: ignorado aquí (se acepta para compatibilidad con tu ejecutor de herramientas).

    Return:
      - Cadena JSON (para que el LLM la procese) con resultados o artículo expandido.
    """
    vs = _open_vectorstore()

    # Filtro base por dominio
    filt: Dict[str, str] = {"domain": DOMAIN_TAG}
    if law:     filt["law"] = law
    if article: filt["article"] = article

    # Ayuda automática: si no llega article, intento extraerlo de la query
    auto_article = _extract_article_hint(query)
    if not article and auto_article:
        filt["article"] = auto_article

    docs = vs.similarity_search(query, k=k, filter=filt)

    if not docs:
        return json.dumps({
            "query": query,
            "used_filters": filt,
            "results": [],
            "note": "Sin coincidencias."
        }, ensure_ascii=False)

    # Si piden expandir artículo, traigo todo el artículo del top-1
    if expand_article and (docs[0].metadata.get("article")):
        top = docs[0].metadata
        where = _where_and(domain=DOMAIN_TAG, law=top.get("law"), article=top.get("article"))
        got = vs._collection.get(where=where, include=["documents", "metadatas", "ids"])
        full_text = "\n\n".join(got["documents"]) if got and got.get("documents") else docs[0].page_content

        return json.dumps({
            "query": query,
            "expanded_article": True,
            "article": top.get("article"),
            "law": top.get("law"),
            "chunks_count": len(got["documents"]) if got and got.get("documents") else 1,
            "full_text": _trim(full_text, 12000),   # protege el contexto
            "citations": [
                {
                    "file_path": md.get("file_path"),
                    "file_name": md.get("file_name"),
                    "chunk_index": md.get("chunk_index")
                } for md in (got.get("metadatas") or [])
            ]
        }, ensure_ascii=False)

    # Caso normal: devuelvo top-k chunks con metadatos
    results = []
    for d in docs:
        md = d.metadata or {}
        results.append({
            "text": _trim(d.page_content, 3000),
            "law": md.get("law"),
            "article": md.get("article"),
            "file_path": md.get("file_path"),
            "file_name": md.get("file_name"),
            "chunk_index": md.get("chunk_index")
        })

    return json.dumps({
        "query": query,
        "expanded_article": False,
        "used_filters": filt,
        "top_k": k,
        "results": results
    }, ensure_ascii=False)
