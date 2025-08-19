# ──────────────────────────────────────────────────────────────────────────────
# FILE: sidebar.py (refactor)
# ──────────────────────────────────────────────────────────────────────────────
import json
from pathlib import Path
import streamlit as st
from core.workspace_manager import get_all_workspaces, create_workspace  # , delete_workspace (opcional)

# ─────────── Helpers Query Params ─────────── #

def _get_qp(key: str, default=None):
    try:
        return st.query_params.get(key, default)
    except Exception:
        return st.experimental_get_query_params().get(key, [default])[0]


def _set_qp(params: dict):
    try:
        st.query_params.clear()
        for k, v in params.items():
            if v is None:
                continue
            st.query_params[k] = v
    except Exception:
        st.experimental_set_query_params(**{k: v for k, v in params.items() if v is not None})


# ─────────── Helpers de metadatos por workspace ─────────── #
_WS_ROOT = Path("storage/workspaces")


def _meta_path(name: str) -> Path:
    return _WS_ROOT / name / "meta.json"


def get_workspace_type(name: str) -> str | None:
    try:
        p = _meta_path(name)
        if not p.exists():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("type")
    except Exception:
        return None


def set_workspace_type(name: str, ws_type: str, overwrite: bool = False):
    """Guarda el tipo de workspace una sola vez por defecto.
    Si `overwrite=True`, permite cambiarlo (no recomendado)."""
    p = _meta_path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    # Evitar cambios posteriores salvo que se fuerce
    if not overwrite and data.get("type"):
        return  # no modifica
    data["type"] = ws_type
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def set_workspace_display_name(name: str, display_name: str, overwrite: bool = False):
    """Guarda display_name; por defecto no sobrescribe si ya existe."""
    p = _meta_path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    if not overwrite and data.get("display_name"):
        return
    data["display_name"] = display_name
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ─────────── Sidebar principal ─────────── #

def _emoji_for(ws_type: str | None) -> str:
    return "🧾" if (ws_type or "Analisis de facturas").lower().startswith("analisis") else "⚖️"


def _active_ws() -> str | None:
    if st.session_state.get("active_workspace"):
        return st.session_state["active_workspace"]
    qp = _get_qp("workspace")
    if isinstance(qp, list):
        qp = qp[0] if qp else None
    return qp


def sidebar():
    st.sidebar.title("🧠 TaxMiner")

    workspaces = sorted(get_all_workspaces())  # orden alfabético por slug

    # ── Crear nuevo (arriba de todo) ──
    with st.sidebar.expander("➕ Crear nuevo", expanded=False):
        with st.form("create_ws_form", clear_on_submit=True):
            new_name = st.text_input("Nombre", placeholder="p.ej. Facturas 2024")
            ws_type = st.selectbox("Tipo", ["Analisis de facturas", "Conocimiento de leyes"]) 
            c1, c2 = st.columns(2)
            submit = c1.form_submit_button("Crear", use_container_width=True)
            cancel = c2.form_submit_button("Cancelar", use_container_width=True)
        if submit:
            name = (new_name or "").strip()
            if not name:
                st.warning("Ingresá un nombre válido.")
            elif name in workspaces:
                # OJO: workspaces es por slug; si coincide texto exacto puede que no detecte duplicados de display_name
                st.info("Ya existe un workspace con ese nombre.")
            else:
                try:
                    slug = create_workspace(name, ws_type)
                    # Persistir tipo + display_name en meta.json de *ese slug*
                    set_workspace_type(slug, ws_type)
                    set_workspace_display_name(slug, name)
                    st.success(f"Workspace '{name}' creado como '{ws_type}'.")
                    st.session_state["active_workspace"] = slug
                    _set_qp({"workspace": slug})
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo crear el workspace: {e}")
        if cancel:
            st.experimental_rerun() if hasattr(st, "experimental_rerun") else st.rerun()

    # ── Listado de chats ──
    st.sidebar.markdown("---")
    st.sidebar.subheader("Chats")
    q = st.sidebar.text_input("Buscar…", placeholder="Nombre del workspace")

    def _get_display_name(slug: str) -> str:
        p = _meta_path(slug)
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if data.get("display_name"):
                    return data["display_name"]
            except Exception:
                pass
        # Fallback legible: 'facturas-2024' -> 'Facturas 2024'
        return slug.replace("-", " ").replace("_", " ").title()

    filtered = [w for w in workspaces if (not q or q.lower() in _get_display_name(w).lower())]

    label_map = {}
    # ordenar por display_name para UX
    filtered_sorted = sorted(filtered, key=lambda s: _get_display_name(s).lower())
    for w in filtered_sorted:
        t = get_workspace_type(w) or "Analisis de facturas"
        nice = _get_display_name(w)
        label = f"{_emoji_for(t)}  {nice}"
        label_map[label] = w

    current = _active_ws()
    if label_map:
        labels = list(label_map.keys())
        try:
            # match por slug actual -> label
            idx = labels.index(next(k for k, v in label_map.items() if v == current)) if current in label_map.values() else 0
        except StopIteration:
            idx = 0
        chosen_label = st.sidebar.radio("Seleccioná un chat", options=labels, index=idx)
        chosen_ws = label_map[chosen_label]
        if chosen_ws != current:
            st.session_state["active_workspace"] = chosen_ws
            _set_qp({"workspace": chosen_ws})
            st.rerun()
    else:
        st.sidebar.info("No hay workspaces.")
        chosen_ws = current

    # ── Acciones y detalles (tipo solo lectura) ──
    if chosen_ws:
        st.sidebar.markdown("---")
        st.sidebar.subheader("⚙️ Acciones")
        # Mostrar tipo (solo lectura)
        current_type = get_workspace_type(chosen_ws)
        st.sidebar.caption(f"Tipo: {_emoji_for(current_type)} {current_type}")

        col1, col2 = st.sidebar.columns(2)
        if col1.button("🧹 Limpiar", use_container_width=True, key="sb_clear"):
            st.session_state[f"action:clear:{chosen_ws}"] = True
            st.rerun()
        if col2.button("📚 Actualizar base", use_container_width=True, key="sb_update"):
            st.session_state[f"action:update:{chosen_ws}"] = True
            st.rerun()
        if st.sidebar.button("🎙️ Voz → Texto", use_container_width=True, key="sb_voice"):
            st.session_state[f"action:voice:{chosen_ws}"] = True
            st.rerun()