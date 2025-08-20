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

# --- SVG ---
SVG_LOGO = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 182 34" style="max-width:100%; height:auto;">
<style type="text/css">
    .st0{fill:#86BC25;}
    .st1{fill:#FFFFFF;}
</style>
<g>
    <path class="st0" d="M171.8,29c0-2.7,2.2-4.8,4.8-4.8c2.7,0,4.8,2.2,4.8,4.8s-2.2,4.8-4.8,4.8S171.8,31.7,171.8,29"/>
    <path class="st1" d="M27.6,16.1c0,5.6-1.4,9.8-4.4,12.8s-7.2,4.5-12.6,4.5H0V0.1h11.2c5.3,0,9.3,1.3,12.1,4.1
            C26.2,6.9,27.6,10.9,27.6,16.1 M18.4,16.4c0-3.1-0.6-5.3-1.8-6.8c-1.1-1.4-3-2.2-5.4-2.2H8.8v18.6h2c2.7,0,4.6-0.8,5.9-2.4
            C17.8,22,18.4,19.6,18.4,16.4"/>
    <rect x="56.7" class="st1" width="8.3" height="33.4"/>
    <path class="st1" d="M92.4,20.9c0,4-1,7.2-3.2,9.5s-5.2,3.4-9,3.4c-3.7,0-6.6-1.1-8.8-3.5c-2.2-2.4-3.3-5.5-3.3-9.4
            c0-4,1-7.2,3.2-9.4c2.2-2.3,5.2-3.4,9-3.4c2.4,0,4.5,0.5,6.3,1.5c1.9,1,3.2,2.5,4.2,4.4C92,16.1,92.4,18.3,92.4,20.9 M76.7,20.9
            c0,2.2,0.3,3.7,0.8,4.8c0.5,1.1,1.4,1.6,2.8,1.6s2.2-0.5,2.8-1.6c0.5-1.1,0.8-2.8,0.8-4.8c0-2.2-0.3-3.7-0.8-4.8       
            c-0.5-1-1.4-1.6-2.8-1.6c-1.2,0-2.2,0.5-2.8,1.6C77,17.2,76.7,18.7,76.7,20.9"/>
    <rect x="95.8" y="8.5" class="st1" width="8.3" height="24.8"/>
    <rect x="95.8" class="st1" width="8.3" height="5.6"/>
    <path class="st1" d="M121,27c1.1,0,2.5-0.3,4-0.8v6.3c-1.1,0.5-2.2,0.8-3.2,1c-1,0.2-2.2,0.3-3.6,0.3c-2.8,0-4.8-0.7-6.1-2.2  
            c-1.2-1.4-1.9-3.6-1.9-6.5V14.9h-2.9V8.5h2.9V2.3l8.4-1.4v7.8h5.4V15h-5.4v9.6C118.8,26.3,119.5,27,121,27"/>
    <path class="st1" d="M140.4,27c1.1,0,2.5-0.3,4-0.8v6.3c-1.1,0.5-2.2,0.8-3.2,1c-1,0.2-2.2,0.3-3.6,0.3c-2.8,0-4.8-0.7-6.1-2.2
            c-1.2-1.4-1.9-3.6-1.9-6.5V14.9h-2.9V8.5h2.9V2.2l8.4-1.3v7.8h5.4V15h-5.4v9.6C138.1,26.3,138.9,27,140.4,27"/>        
    <path class="st1" d="M166.8,11c-2-2-4.8-2.9-8.4-2.9c-3.8,0-6.8,1.1-8.9,3.4c-2.1,2.3-3.1,5.5-3.1,9.7c0,4,1.1,7.2,3.3,9.4    
            c2.3,2.2,5.4,3.3,9.4,3.3c2,0,3.6-0.1,5-0.4c1.3-0.3,2.8-0.7,4-1.4l-1.2-5.6c-0.9,0.4-1.9,0.7-2.7,0.9c-1.2,0.3-2.6,0.4-4,0.4
            c-1.6,0-2.9-0.4-3.8-1.1c-0.9-0.8-1.4-1.9-1.4-3.3h14.9v-3.9C169.8,15.8,168.7,13,166.8,11 M155,17.9c0.1-1.3,0.5-2.4,1.1-3
            c0.6-0.6,1.4-0.9,2.5-0.9c1,0,2,0.3,2.6,1c0.6,0.7,0.9,1.6,1,2.9H155z"/>
    <path class="st1" d="M50.5,11c-2.1-2-4.8-2.9-8.4-2.9c-3.8,0-6.8,1.1-8.9,3.4s-3.1,5.5-3.1,9.7c0,4,1.1,7.2,3.3,9.4
            c2.3,2.2,5.4,3.3,9.4,3.3c2,0,3.6-0.1,5-0.4c1.3-0.3,2.8-0.7,4-1.4l-1.2-5.7c-0.9,0.4-1.9,0.7-2.7,0.9c-1.2,0.3-2.6,0.4-4,0.4
            c-1.6,0-2.9-0.4-3.8-1.1c-0.9-0.8-1.4-1.9-1.4-3.3h14.9v-3.8C53.5,15.8,52.4,13,50.5,11 M38.6,17.9c0.1-1.3,0.5-2.4,1.1-3
            s1.4-0.9,2.5-0.9s2,0.3,2.6,1c0.6,0.7,0.9,1.6,1,2.9H38.6z"/>
</g>
</svg>
"""

def sidebar():
    # Leer el SVG y embeberlo centrado
    st.sidebar.markdown(SVG_LOGO, unsafe_allow_html=True)
    st.sidebar.title("TaxMiner")

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