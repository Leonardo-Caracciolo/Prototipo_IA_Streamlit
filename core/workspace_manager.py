# core/workspace_manager.py
import re
import json
import unicodedata
from pathlib import Path
from datetime import datetime

BASE_PATH = Path("storage/workspaces")
BASE_PATH.mkdir(parents=True, exist_ok=True)

ILLEGAL_FS = r'[/\\:*?"<>|]'  # Windows/FS inválidos
SEP = "-"  # separador canónico para slugs


def slugify(name: str) -> str:
    if not isinstance(name, str):
        name = str(name or "")
    # Normaliza acentos: "Facturación Ñ" -> "Facturacion N"
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = name.lower()
    # Reemplaza caracteres de FS inválidos por espacio
    name = re.sub(ILLEGAL_FS, " ", name)
    # Cualquier bloque no alfanumérico -> separador
    name = re.sub(r"[^a-z0-9]+", SEP, name)
    # Colapsa separadores múltiples y recorta
    name = re.sub(rf"{SEP}+", SEP, name).strip(SEP)
    return name or "workspace"


def ensure_unique_slug(slug: str) -> str:
    candidate = slug
    i = 2
    while (BASE_PATH / candidate).exists():
        candidate = f"{slug}-{i}"
        i += 1
    return candidate


def _meta_path(slug: str) -> Path:
    return BASE_PATH / slug / "meta.json"


def get_all_workspaces() -> list[str]:
    return sorted([p.name for p in BASE_PATH.iterdir() if p.is_dir()])


def get_meta(slug: str) -> dict:
    p = _meta_path(slug)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def set_meta(slug: str, **kwargs):
    p = _meta_path(slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    meta = get_meta(slug)
    meta.update(kwargs)
    meta.setdefault("slug", slug)
    meta.setdefault("created_at", datetime.utcnow().isoformat() + "Z")
    meta["updated_at"] = datetime.utcnow().isoformat() + "Z"
    p.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def get_display_name(slug: str) -> str:
    return get_meta(slug).get("display_name", slug)


def get_type(slug: str) -> str | None:
    return get_meta(slug).get("type")

def get_table_db(slug: str) -> str | None:
    return get_meta(slug).get("table")

def create_workspace(display_name: str, ws_type: str = "Analisis de facturas") -> str:
    raw_slug = slugify(display_name)
    slug = ensure_unique_slug(raw_slug)
    root = BASE_PATH / slug

    # carpetas estándar
    for sub in ("documents", "knowledge", "threads"):
        (root / sub).mkdir(parents=True, exist_ok=True)

    hist = root / "history.json"
    if not hist.exists():
        hist.write_text("[]", encoding="utf-8")

    if ws_type == "Analisis de facturas":
        table_db = "facturas"
    else:
        table_db = "general"

    # metadatos
    set_meta(
        slug,
        display_name=display_name,
        type=ws_type,
        table=table_db,
    )
    return slug


def delete_workspace(slug: str) -> bool:
    import shutil
    path = BASE_PATH / slug
    if path.exists():
        shutil.rmtree(path)
        return True
    return False


# ───── Diagnóstico/limpieza opcional ───── #

def _canonical_key(slug: str) -> str:
    # Unifica '_' y '-' para detectar “duplicados visuales”: mi-workspace vs mi_workspace
    return re.sub(r"[_-]+", "-", slug)


def find_potential_duplicates() -> dict[str, list[str]]:
    groups = {}
    for slug in get_all_workspaces():
        k = _canonical_key(slug)
        groups.setdefault(k, []).append(slug)
    # Devuelve solo grupos con más de 1 variante
    return {k: v for k, v in groups.items() if len(v) > 1}
