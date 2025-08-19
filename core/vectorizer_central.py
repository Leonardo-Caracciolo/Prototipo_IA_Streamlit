# central_vectorizer.py — Índice central con Chroma (recursivo + incremental + Artículos + batching)
# Requisitos:
#   pip install chromadb langchain-community langchain-openai pandas python-docx pymupdf
#   # opcional (fallback local / modo offline):
#   pip install sentence-transformers
#
# .env recomendado:
#   CENTRAL_DOCS_ROOT=../Leyes
#   VECTORSTORE_DIR=../leyes_vectorizer
#   VECTOR_COLLECTION=central_leyes
#   DOMAIN_TAG=leyes
#   EMBEDDINGS_PROVIDER=auto        # openai | local | auto
#   OPENAI_EMBED_MODEL=text-embedding-3-small
#   # OPENAI_API_KEY=sk-xxxx        # necesario si usás openai/auto con key
#   CACHE_EMBEDDINGS=true
#   CHROMA_TELEMETRY=false
#   # Opcionales para batching:
#   # CHROMA_UPSERT_BATCH=2000
#   # CHROMA_GET_BATCH=4000
#   # CHROMA_DELETE_BATCH=4000

import os, re, json, hashlib
from typing import List, Dict, Optional, Iterable
import pandas as pd
from pathlib import Path

from dotenv import load_dotenv
from langchain.docstore.document import Document
from langchain_community.document_loaders import PyPDFLoader, UnstructuredWordDocumentLoader
# Fallback más robusto para PDF (si está instalado)
try:
    from langchain_community.document_loaders import PyMuPDFLoader
    HAS_PYMUPDF = True
except Exception:
    HAS_PYMUPDF = False

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain.embeddings import CacheBackedEmbeddings
from langchain.storage import LocalFileStore
# from langchain_community.vectorstores import Chroma
from langchain_chroma import Chroma
import unicodedata
from chromadb.config import Settings
import chromadb

# ================= Config (desde .env con defaults) =================
load_dotenv(dotenv_path="../.env")

CENTRAL_ROOT    = Path(os.getenv("CENTRAL_DOCS_ROOT", "../Leyes")).expanduser().resolve()          # carpeta central a indexar
PERSIST_DIR     = Path(os.getenv("VECTORSTORE_DIR", "../leyes_vectorizer")).expanduser().resolve() # carpeta de Chroma (NO dentro de CENTRAL_ROOT)
COLLECTION_NAME = os.getenv("VECTOR_COLLECTION", "central_leyes")
DOMAIN_TAG      = os.getenv("DOMAIN_TAG", "leyes")

# Embeddings provider + cache
EMBEDDINGS_PROVIDER = os.getenv("EMBEDDINGS_PROVIDER", "auto")  # auto | openai | local
OPENAI_EMBED_MODEL  = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
CACHE_EMBEDDINGS    = os.getenv("CACHE_EMBEDDINGS", "true").lower() == "true"

CHROMA_SETTINGS = Settings(
    anonymized_telemetry=os.getenv("CHROMA_TELEMETRY", "false").lower() == "true"
)

# Batching (evita InternalError por límite de batch del backend)
UPSERT_BATCH  = int(os.getenv("CHROMA_UPSERT_BATCH", "2000"))
GET_IDS_BATCH = int(os.getenv("CHROMA_GET_BATCH", "4000"))
DEL_IDS_BATCH = int(os.getenv("CHROMA_DELETE_BATCH", "4000"))

CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200
RE_ART = re.compile(
    r"(?im)^\s*(?:art(?:[íi]culo)?\.?)\s*"
    r"(\d+)\s*(?:º|°|o)?\s*(?:\b(bis|ter|qu(?:a|á)ter|quinquies)\b)?\s*"
    r"[-–—:\.]?\s*(.*)$"
)

# --- al tope del archivo (junto a imports) ---
import itertools

# --- debajo de RE_ART ---
RE_HEADER_FOOTER = re.compile(r'^\s*(Página\s+\d+.*|Boletín\s+Oficial.*|Dirección\s+General.*)$', re.I)
RE_HYPHEN = re.compile(r'(\w)-\n(\w)')                  # une palabras cortadas a fin de línea
RE_MULTI_NL = re.compile(r'\n{3,}')
RE_SPACES = re.compile(r'[ \t]{2,}')

def _clean_text(text: str) -> str:
    # 1) eliminar líneas típicas de header/footer por patrón
    lines = []
    for ln in text.splitlines():
        if RE_HEADER_FOOTER.match(ln.strip()):
            continue
        lines.append(ln)
    txt = "\n".join(lines)

    # 2) unir guiones de fin de línea (corte de palabra)
    txt = RE_HYPHEN.sub(r'\1\2', txt)

    # 3) normalizar saltos de línea y espacios
    txt = RE_MULTI_NL.sub('\n\n', txt)
    txt = RE_SPACES.sub(' ', txt)

    return txt.strip()


def _merge_pdf_pages(pages_docs: list) -> str:
    """Une el contenido de TODAS las páginas de un PDF en un solo string limpio."""
    raw = "\n\n".join(d.page_content or "" for d in pages_docs)
    return _clean_text(raw)


def _infer_root_province(file_path: str) -> tuple[str | None, str | None, str]:
    parts = (file_path or "").split("/")
    root = parts[0].strip().upper() if len(parts) >= 1 else None
    province = parts[1].strip().upper() if (root == "IIBB" and len(parts) >= 2) else None
    jurisdiction = "PROVINCIAL" if root == "IIBB" else "NACIONAL"
    return root, province, jurisdiction

_DOCTYPE_RE = re.compile(r'(?i)\b(ley|decreto|resoluci[oó]n(?:\s+general)?|cf|disposici[oó]n)\b')
_NUMYEAR_RE = re.compile(r'(?i)\b(\d{1,4})[-_/](\d{4})\b')  # ej. 316-2023, 316/2023
_ISSUER_RE  = re.compile(r'(?i)\b(afip|agip|arba|p\.?e\.?n\.?|dgr|comisi[oó]n\s+arbitral)\b')

def _parse_doc_identity(file_name: str) -> dict:
    name = (file_name or "").replace(".pdf","").replace(".docx","")
    md = {}
    m = _DOCTYPE_RE.search(name)
    if m:
        md["doc_type"] = m.group(1).upper()
    n = _NUMYEAR_RE.search(name)
    if n:
        md["doc_number"] = f"{n.group(1)}/{n.group(2)}"
        md["doc_year"] = n.group(2)
    i = _ISSUER_RE.search(name)
    if i:
        md["issuer"] = i.group(1).upper().replace(".", "")
    return md

def _norm_art_num(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s*(?:º|°|o)\s*$", "", s)
    s = re.sub(r"\s+", " ", s)
    s = (s
         .replace("quáter", "quater")
         .replace("quínties", "quinquies"))
    return s

def split_por_articulos(doc: Document) -> List[Document]:
    t = doc.page_content or ""
    ms = list(RE_ART.finditer(t))
    if not ms:
        return [doc]
    res = []
    starts = [m.start() for m in ms] + [len(t)]
    for i in range(len(starts) - 1):
        piece = t[starts[i]:starts[i+1]].strip()
        if not piece:
            continue
        m = RE_ART.search(piece.splitlines()[0]) or RE_ART.search(piece)
        md = {**doc.metadata}
        if m:
            num = m.group(1) or ""
            suf = (m.group(2) or "").strip().lower()
            article_num = _norm_art_num(f"{num} {suf}".strip())
            title_rest  = (m.group(3) or "").strip()
            md["article"] = f"Artículo {num}{(' ' + suf) if suf else ''} {('- ' + title_rest) if title_rest else ''}".strip()
            md["article_num"] = article_num
        res.append(Document(page_content=piece, metadata=md))
    return res

def _normalize_text(text: str) -> str:
    if not text:
        return ""
    # une palabras cortadas por guion de fin de línea: "percep-\nción" -> "percepción"
    text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)
    # normaliza espacios
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _where_and(**kv) -> dict:
    """Convierte pares clave=valor a filtro Chroma con un único operador $and."""
    clauses = []
    for k, v in kv.items():
        if v is None:
            continue
        clauses.append({k: {"$eq": v}})
    return {"$and": clauses} if clauses else {}


def _build_base_embedder():
    use_openai = (EMBEDDINGS_PROVIDER == "openai") or (
        EMBEDDINGS_PROVIDER == "auto" and os.getenv("OPENAI_API_KEY")
    )
    if use_openai:
        return OpenAIEmbeddings(model=OPENAI_EMBED_MODEL)
    else:
        # Local (sin tokens) — requiere sentence-transformers
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("intfloat/multilingual-e5-small")
        class _LocalEmbedder:
            def embed_documents(self, texts: List[str]) -> List[List[float]]:
                return model.encode(texts, normalize_embeddings=True).tolist()
            def embed_query(self, text: str) -> List[float]:
                return self.embed_documents([text])[0]
        return _LocalEmbedder()

# Construcción de embedder + cache opcional
_base_emb = _build_base_embedder()
if CACHE_EMBEDDINGS:
    cache_dir = PERSIST_DIR / "embed_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_store = LocalFileStore(str(cache_dir))
    try:
        EMB = CacheBackedEmbeddings.from_bytes_store(_base_emb, cache_store)
    except Exception:
        EMB = _base_emb
else:
    EMB = _base_emb

print(f"[vectorizer] provider={EMBEDDINGS_PROVIDER} "
      f"model={OPENAI_EMBED_MODEL if isinstance(_base_emb, OpenAIEmbeddings) else 'local-e5-small'} "
      f"cache={'on' if CACHE_EMBEDDINGS else 'off'} "
      f"batches(upsert/get/del)=({UPSERT_BATCH}/{GET_IDS_BATCH}/{DEL_IDS_BATCH})")

# ================= Helpers de batching =================
def batched(seq: Iterable, size: int):
    seq = list(seq)
    for i in range(0, len(seq), size):
        yield seq[i:i+size]

def col_get_ids_in_batches(col, ids: List[str]) -> List[str]:
    found: List[str] = []
    for part in batched(ids, GET_IDS_BATCH):
        res = col.get(ids=part)  # devuelve "ids" siempre
        if res and res.get("ids"):
            found.extend(res["ids"])
    return found


def col_delete_ids_in_batches(col, ids: List[str]):
    for part in batched(ids, DEL_IDS_BATCH):
        if part:
            col.delete(ids=list(part))

def add_documents_in_batches(vs: Chroma, docs: List[Document]):
    for part in batched(docs, UPSERT_BATCH):
        part_ids = [d.metadata["id_hash"] for d in part]
        vs.add_documents(part, ids=part_ids)

# ================= Utilidades de archivos =================
def iter_files(root: Path):
    allowed = {".pdf", ".docx", ".xls", ".xlsx", ".xlsm"}
    root = Path(root).resolve()
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in allowed:
            yield p.resolve()

def rel_path(path: Path) -> str:
    path = Path(path).resolve()
    try:
        return path.relative_to(CENTRAL_ROOT).as_posix()
    except Exception:
        return os.path.relpath(str(path), str(CENTRAL_ROOT)).replace("\\", "/")

def file_sha1(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

# ================= Loaders =================
def load_doc(path: str | Path) -> List[Document]:
    p = Path(path).resolve()
    r = rel_path(p)
    if not p.is_file():
        print(f"❌ No existe el archivo: {p}")
        return []

    suffix = p.suffix.lower()

    if suffix == ".pdf":
        # 1) cargar páginas (PyPDF -> fallback PyMuPDF)
        try:
            pages = PyPDFLoader(str(p)).load()
        except Exception as e:
            if HAS_PYMUPDF:
                try:
                    pages = PyMuPDFLoader(str(p)).load()
                except Exception as e2:
                    print(f"❌ Error cargando PDF (PyPDF/PyMuPDF): {p}\n  - {e}\n  - {e2}")
                    return []
            else:
                print(f"❌ Error cargando PDF con PyPDFLoader: {p}\n  - {e}\n(Instalá 'pymupdf' para fallback opcional)")
                return []

        # 2) fusionar TODAS las páginas + limpieza básica
        merged = _merge_pdf_pages(pages)

        # 3) devolver UN solo Document por archivo
        return [Document(
            page_content=merged,
            metadata={"file_path": r, "file_name": p.name, "source": str(p)}
        )]

    if suffix == ".docx":
        try:
            docs = UnstructuredWordDocumentLoader(str(p)).load()
        except Exception:
            import docx
            dx = docx.Document(str(p))
            text = "\n".join(par.text for par in dx.paragraphs)
            docs = [Document(page_content=text, metadata={})]
        for d in docs:
            d.metadata = {**d.metadata, "source": str(p), "file_path": r, "file_name": p.name}
        return docs

    if suffix in {".xls", ".xlsx", ".xlsm"}:
        out: List[Document] = []
        try:
            xls = pd.ExcelFile(str(p))
            for sheet in xls.sheet_names:
                df = xls.parse(sheet)
                df = df.loc[:, ~df.columns.astype(str).str.contains(r"^Unnamed", na=False)]
                text = df.astype(str).to_string(index=False)
                out.append(Document(
                    page_content=text,
                    metadata={"source": str(p), "file_path": r, "file_name": p.name, "sheet": sheet}
                ))
        except Exception as e:
            print(f"❌ Error cargando Excel {p}: {e}")
        return out

    return []


def load_doc_for_path(path: str | Path) -> List[Document]:
    return load_doc(path)

# ================= Chunking (Artículo + tamaño) =================
def split_por_articulos(doc: Document) -> List[Document]:
    t = doc.page_content or ""
    ms = list(RE_ART.finditer(t))
    if not ms:
        return [doc]
    res: List[Document] = []
    starts = [m.start() for m in ms] + [len(t)]
    for i in range(len(starts) - 1):
        piece = t[starts[i]:starts[i+1]].strip()
        if not piece:
            continue
        m = RE_ART.search(piece)
        art = m.group(1).strip() if m else None
        md = {**doc.metadata}
        if art:
            md["article"] = art
        res.append(Document(page_content=piece, metadata=md))
    return res

def chunk_document(doc: Document) -> List[Document]:
    # 1) separo por artículos primero (sobre el DOC COMPLETO)
    parts: List[Document] = []
    parts.extend(split_por_articulos(doc))

    # 2) troceo cada parte por tamaño (respetando que cada parte ya es un Artículo)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", "; ", " "],
    )
    chunks: List[Document] = []
    for part in parts:
        chunks.extend(splitter.split_documents([part]))

    out: List[Document] = []
    for idx, c in enumerate(chunks):
        md = {**c.metadata}

        # --- ley y ruta normalizada ---
        doc_path_no_ext = os.path.splitext(md.get("file_path", "desconocido"))[0]
        law_norm = unicodedata.normalize("NFC", doc_path_no_ext).rstrip()
        md["domain"] = DOMAIN_TAG
        md["law"] = law_norm
        md["chunk_index"] = idx

        # --- root y province (para IIBB) ---
        parts_path = law_norm.split("/")
        root = parts_path[0].upper() if parts_path else None
        province = parts_path[1].upper() if (root == "IIBB" and len(parts_path) > 1) else None
        if root:     md["root"] = root
        if province: md["province"] = province

        # --- article y article_num normalizados (si existe) ---
        art_label = md.get("article")
        if art_label:
            mnum = re.search(r'(?i)art[íi]culo\s+(\d+[a-zº°]?)', art_label)
            if mnum:
                num_norm = mnum.group(1).lower()
                num_norm = num_norm.replace('º', '').replace('°', '')
                md["article_num"] = num_norm  # ej: "4", "12bis"

        # --- id estable ---
        h = hashlib.sha1()
        h.update((md["law"] + "|" + md.get("article", "") + "|" + str(md["chunk_index"])).encode("utf-8"))
        h.update((c.page_content or "").encode("utf-8"))
        md["id_hash"] = h.hexdigest()

        out.append(Document(page_content=c.page_content, metadata=md))
    return out




# ================= Manifest (para updates incrementales) =================
def manifest_path() -> Path:
    return PERSIST_DIR / "_manifest.json"

def load_manifest() -> Dict[str, str]:
    try:
        with open(manifest_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_manifest(m: Dict[str, str]):
    PERSIST_DIR.mkdir(parents=True, exist_ok=True)
    with open(manifest_path(), "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)

# ================= Chroma helpers =================
def get_collection(recreate: bool = False) -> Chroma:
    PERSIST_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(PERSIST_DIR), settings=CHROMA_SETTINGS)
    if recreate:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
    return Chroma(
        client=client,
        collection_name=COLLECTION_NAME,
        persist_directory=str(PERSIST_DIR),
        embedding_function=EMB,
    )

# ================= Indexado completo =================
def reindex_all():
    vs = get_collection(recreate=True)
    ids: List[str] = []
    docs: List[Document] = []

    for path in iter_files(CENTRAL_ROOT):
        loaded = load_doc(path)
        loaded = [d for d in loaded if d.page_content and d.page_content.strip()]
        for d in loaded:
            for c in chunk_document(d):
                ids.append(c.metadata["id_hash"])
                docs.append(c)
        print(f"Indexando: {rel_path(path)} (chunks acumulados: {len(docs)})")

    if ids:
        # Dedupe ids para .get()
        unique_ids = list(dict.fromkeys(ids))
        existing_list = col_get_ids_in_batches(vs._collection, unique_ids)
        existing = set(existing_list)

        # Dedupe intra-batch por id_hash
        uniq_docs: Dict[str, Document] = {}
        for d in docs:
            _id = d.metadata["id_hash"]
            if _id not in uniq_docs:
                uniq_docs[_id] = d

        docs_clean = list(uniq_docs.values())
        ids_clean  = [d.metadata["id_hash"] for d in docs_clean]

        # Borrar colisiones existentes y agregar en lotes
        if existing:
            col_delete_ids_in_batches(vs._collection, list(existing))
        add_documents_in_batches(vs, docs_clean)
        # vs.persist()

    save_manifest({rel_path(p): file_sha1(p) for p in iter_files(CENTRAL_ROOT)})
    print(f"✅ Reindex completo. Persistencia en: {PERSIST_DIR}  (colección: {COLLECTION_NAME})")

# ================= Update incremental (a demanda) =================
def update_index():
    vs = get_collection(recreate=False)
    prev = load_manifest()
    now_files = {rel_path(p): p for p in iter_files(CENTRAL_ROOT)}
    now_hash = {rel: file_sha1(path) for rel, path in now_files.items()}

    added   = [rel for rel in now_hash if rel not in prev]
    changed = [rel for rel in now_hash if rel in prev and now_hash[rel] != prev[rel]]
    deleted = [rel for rel in prev     if rel not in now_hash]

    print(f"➕ nuevos: {len(added)} | ✏️ cambiados: {len(changed)} | 🗑️ eliminados: {len(deleted)}")

    # 1) Eliminar del índice lo que ya no existe
    for rel in deleted:
        vs._collection.delete(where={"file_path": rel})

    # 2) Upsert de nuevos/cambiados (limpiamos por file_path antes de insertar)
    to_docs: List[Document] = []
    ids: List[str] = []
    for rel in added + changed:
        path = now_files[rel]
        vs._collection.delete(where={"file_path": rel})
        loaded = load_doc_for_path(path)
        for d in loaded:
            for c in chunk_document(d):
                to_docs.append(c)
                ids.append(c.metadata["id_hash"])

    if ids:
        unique_ids = list(dict.fromkeys(ids))
        existing_list = col_get_ids_in_batches(vs._collection, unique_ids)
        existing = set(existing_list)

        uniq_docs: Dict[str, Document] = {}
        for d in to_docs:
            _id = d.metadata["id_hash"]
            if _id not in uniq_docs:
                uniq_docs[_id] = d

        docs_clean = list(uniq_docs.values())
        ids_clean  = [d.metadata["id_hash"] for d in docs_clean]

        if existing:
            col_delete_ids_in_batches(vs._collection, list(existing))
        add_documents_in_batches(vs, docs_clean)
        # vs.persist()

    save_manifest(now_hash)
    print("✅ Update incremental listo.")

# ================= Búsqueda (para tu agente) =================
def search(query: str, k: int = 5, law: Optional[str] = None, article: Optional[str] = None, expand_article: bool = False):
    vs = get_collection(recreate=False)
    # Para similarity_search, el filtro dict plano sigue funcionando en LangChain
    filt = {"domain": DOMAIN_TAG}
    if law:     filt["law"] = law
    if article: filt["article"] = article

    docs = vs.similarity_search(query, k=k, filter=filt)
    if not docs:
        return []

    if not expand_article:
        return [{"text": d.page_content, "meta": d.metadata} for d in docs]

    # Expandimos al artículo completo del top-1 (usar where con $and en Chroma 0.4+)
    top = docs[0].metadata
    where = _where_and(domain=DOMAIN_TAG, law=top.get("law"), article=top.get("article"))
    got = vs._collection.get(where=where, include=["documents", "metadatas"])
    full = "\n\n".join(got["documents"]) if got and got.get("documents") else docs[0].page_content
    return [{"text": full, "meta": where}]


# ================= CLI opcional =================
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Índice central Chroma")
    ap.add_argument("cmd", choices=["reindex", "update", "search"], help="Comando")
    ap.add_argument("--query", help="Texto a buscar (para cmd=search)")
    ap.add_argument("--k", type=int, default=5, help="Top K resultados (search)")
    ap.add_argument("--law", help="Filtro exacto por 'law' (ruta relativa sin extensión)")
    ap.add_argument("--article", help="Filtro exacto por 'Artículo ...'")
    ap.add_argument("--expand_article", action="store_true", help="Expandir al artículo completo")
    args = ap.parse_args()

    if args.cmd == "reindex":
        reindex_all()
    elif args.cmd == "update":
        update_index()
    elif args.cmd == "search":
        if not args.query:
            raise SystemExit("Falta --query para cmd=search")
        res = search(args.query, k=args.k, law=args.law, article=args.article, expand_article=args.expand_article)
        for i, r in enumerate(res, 1):
            print(f"\n#{i}  meta={r['meta']}")
            print("-"*80)
            print(r["text"][:2000])
            if len(r["text"]) > 2000:
                print("…")
