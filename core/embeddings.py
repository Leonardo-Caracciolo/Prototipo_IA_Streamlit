# FILE: core/embeddings.py

import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain.embeddings import CacheBackedEmbeddings
from langchain.storage import LocalFileStore

# Carga las variables de entorno desde el .env en la raíz del proyecto
load_dotenv()

# Configuración leída del entorno
EMBEDDINGS_PROVIDER = os.getenv("EMBEDDINGS_PROVIDER", "auto")
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
CACHE_EMBEDDINGS = os.getenv("CACHE_EMBEDDINGS", "true").lower() == "true"
# Asegúrate que la ruta al vectorstore sea correcta desde la app
PERSIST_DIR = Path(os.getenv("VECTORSTORE_DIR", "leyes_vectorizer")).resolve()

def _build_base_embedder():
    """Construye el embedder base (OpenAI o local) según la configuración."""
    use_openai = (EMBEDDINGS_PROVIDER == "openai") or (
        EMBEDDINGS_PROVIDER == "auto" and os.getenv("OPENAI_API_KEY")
    )
    if use_openai:
        print("[Embedder] Usando OpenAI Embeddings")
        return OpenAIEmbeddings(model=OPENAI_EMBED_MODEL)
    else:
        print("[Embedder] Usando modelo local (requiere sentence-transformers)")
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("intfloat/multilingual-e5-small")
        class _LocalEmbedder:
            def embed_documents(self, texts: list[str]) -> list[list[float]]:
                return model.encode(texts, normalize_embeddings=True).tolist()
            def embed_query(self, text: str) -> list[float]:
                return self.embed_documents([text])[0]
        return _LocalEmbedder()

def get_embedder():
    """
    Obtiene el embedder, aplicando el caché si está activado.
    Esta es la función que usarás en todas partes.
    """
    base_emb = _build_base_embedder()
    if CACHE_EMBEDDINGS:
        cache_dir = PERSIST_DIR / "embed_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        store = LocalFileStore(str(cache_dir))
        return CacheBackedEmbeddings.from_bytes_store(base_emb, store)
    return base_emb

# Instancia global para ser importada
EMBEDDINGS = get_embedder()