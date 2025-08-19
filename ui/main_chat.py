# ──────────────────────────────────────────────────────────────────────────────
# FILE: main_chat.py (refactor visual + robustez)
# ──────────────────────────────────────────────────────────────────────────────
import os
import re
import json
import hashlib
from pathlib import Path
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

from core.history import load_history, save_history
from core.graph_agent import app
from utils.voz_a_prompt import escuchar_y_convertir
from core.vectorizer import cargar_documentos, aplicar_chunking, crear_vectorstore

load_dotenv()

# ─────────── Config general UI ─────────── #
st.set_page_config(page_title="TaxMiner • Chat", layout="wide")

st.markdown(
    """
    <style>
    .stChatMessage {max-width: 1100px; margin-left: auto; margin-right: auto;}
    .stChatInputContainer {max-width: 1100px; margin-left: auto; margin-right: auto;}
    .badge {display:inline-block; padding:2px 8px; border-radius:999px; background:#eef2ff; color:#3730a3; font-size:12px; font-weight:600;}
    .badge-law {background:#ecfeff; color:#155e75;}
    .small-note {color: #6b7280; font-size: 0.85rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────── Helpers compartidos ─────────── #
_WS_ROOT = Path("storage/workspaces")

def _ws_key(workspace: str) -> str:
    return f"messages:{workspace}"


def _get_messages(workspace: str) -> list[BaseMessage]:
    key = _ws_key(workspace)
    if key not in st.session_state:
        historial = load_history(workspace)
        msgs: list[BaseMessage] = []
        for q, a in historial:
            msgs.append(HumanMessage(content=q))
            msgs.append(AIMessage(content=a))
        st.session_state[key] = msgs
    return st.session_state[key]


def _save_messages(workspace: str):
    key = _ws_key(workspace)
    mensajes = st.session_state.get(key, [])
    pares: list[tuple] = []
    for i in range(0, len(mensajes), 2):
        if (
            i + 1 < len(mensajes)
            and isinstance(mensajes[i], HumanMessage)
            and isinstance(mensajes[i + 1], AIMessage)
        ):
            pares.append((mensajes[i].content, mensajes[i + 1].content))
    save_history(workspace, pares)


def _fingerprint_workspace_docs(workspace: str) -> str:
    folder = _WS_ROOT / workspace / "documents"
    if not folder.exists():
        return ""
    h = hashlib.md5()
    for root, _, files in os.walk(folder):
        for f in sorted(files):
            if f.lower().endswith((".pdf", ".docx", ".xls", ".xlsx", ".xlsm")):
                p = os.path.join(root, f)
                try:
                    stat = os.stat(p)
                    h.update(f.encode())
                    h.update(str(stat.st_mtime_ns).encode())
                    h.update(str(stat.st_size).encode())
                except Exception:
                    pass
    return h.hexdigest()


def _extract_artifacts(text: str):
    artifacts = []
    for block in re.findall(r"```json\s*(\{[\s\S]*?\})\s*```", text):
        try:
            obj = json.loads(block)
            if isinstance(obj, dict) and "path" in obj:
                artifacts.append(
                    {
                        "path": obj.get("path"),
                        "name": obj.get("name") or os.path.basename(obj.get("path", "")) or "archivo",
                        "mime": obj.get("mime") or "application/octet-stream",
                    }
                )
        except Exception:
            pass
    m = re.search(r"La ruta es:\s*(.*)", text)
    if m:
        p = m.group(1).strip()
        artifacts.append({"path": p, "name": os.path.basename(p), "mime": "application/octet-stream"})
    out = [a for a in artifacts if a.get("path") and os.path.exists(a["path"])]
    return out


def _meta_path(name: str) -> Path:
    return _WS_ROOT / name / "meta.json"


def get_workspace_type(name: str) -> str:
    try:
        p = _meta_path(name)
        if not p.exists():
            return "No definido"
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("type")
    except Exception:
        return "No encontrado"


def _type_badge(ws_type: str) -> str:
    if ws_type.lower().startswith("analisis"):
        return '<span class="badge">🧾 Análisis de facturas</span>'
    else:
        return '<span class="badge badge-law">⚖️ Conocimiento de leyes</span>'


# ─────────── Vista principal ─────────── #

def chat(workspace: str):
    ws_type = get_workspace_type(workspace)
    st.markdown(f"### 💬 Chat — Tipo de Workspace: {ws_type}")
    st.markdown(_type_badge(ws_type), unsafe_allow_html=True)

    # Captura de acciones disparadas desde el sidebar
    if st.session_state.pop(f"action:clear:{workspace}", False):
        st.session_state.pop(_ws_key(workspace), None)
        save_history(workspace, [])
        st.toast("Historial borrado")
        st.rerun()

    if st.session_state.pop(f"action:voice:{workspace}", False):
        try:
            text = escuchar_y_convertir()
            if text:
                st.session_state["chat_input_voz"] = text
                st.rerun()
        except Exception as e:
            st.toast(f"Error de voz: {e}")

    do_process = st.session_state.pop(f"action:update:{workspace}", False)

    # Procesamiento de documentos: manual (desde sidebar) + cambio detectado
    if "docs_fingerprint" not in st.session_state:
        st.session_state.docs_fingerprint = {}
    fp_before = st.session_state.docs_fingerprint.get(workspace)
    fp_now = _fingerprint_workspace_docs(workspace)

    if do_process or (fp_before != fp_now and fp_now):
        with st.status("Procesando documentos…", expanded=True) as status:
            status.write("Cargando documentos…")
            documentos = cargar_documentos(workspace)
            if documentos:
                status.write("Chunking…")
                chunks = aplicar_chunking(documentos)
                status.write("Creando vectorstore…")
                crear_vectorstore(workspace, chunks)
                st.session_state.docs_fingerprint[workspace] = fp_now
                status.update(label="✅ Base de conocimiento actualizada", state="complete")
            else:
                status.update(label="No se encontraron documentos válidos", state="error")

    st.markdown(
        "<div class='small-note'>Consejo: usá el panel lateral para acciones (limpiar, actualizar base, voz). </div>",
        unsafe_allow_html=True,
    )

    # Mostrar historial
    messages = _get_messages(workspace)
    for msg in messages:
        role = "user" if isinstance(msg, HumanMessage) else "assistant"
        avatar = "🧑" if role == "user" else "🤖"
        with st.chat_message(role, avatar=avatar):
            st.markdown(msg.content)

    # Placeholder adaptado por tipo
    placeholder = (
        "Preguntá por CUIT, CAE, totales, duplicadas… (ej.: 'Listá facturas apócrifas de 2024')."
        if ws_type.lower().startswith("analisis")
        else "Consultá artículos y jurisprudencia. (ej.: '¿Qué dice la Ley 11.683 art. 35?')."
    )

    # Entrada del usuario (texto o voz)
    prompt = st.chat_input(placeholder)
    if "chat_input_voz" in st.session_state:
        prompt = st.session_state.pop("chat_input_voz")

    # Llamada al agente
    if prompt:
        messages.append(HumanMessage(content=prompt))
        with st.chat_message("user", avatar="🧑"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Pensando…"):
                graph_state = {"messages": list(messages), "workspace": workspace, "ws_type": ws_type}
                final_response = None
                try:
                    for event in app.stream(graph_state, {"recursion_limit": 15}):
                        agent_state = event.get("agent") if isinstance(event, dict) else None
                        if agent_state and agent_state.get("messages"):
                            final_response = agent_state["messages"][-1]
                except Exception as e:
                    st.error(f"Fallo del grafo: {e}")

                if final_response and getattr(final_response, "content", None):
                    st.markdown(final_response.content)
                    messages.append(AIMessage(content=final_response.content))
                    _save_messages(workspace)

                    artifacts = _extract_artifacts(final_response.content)
                    if artifacts:
                        st.markdown("---")
                        st.caption("Descargas generadas:")
                        for art in artifacts:
                            try:
                                with open(art["path"], "rb") as fh:
                                    st.download_button(
                                        label=f"⬇️ {art['name']}",
                                        data=fh,
                                        file_name=art["name"],
                                        mime=art["mime"],
                                    )
                            except Exception:
                                pass
                else:
                    st.error("El agente no devolvió una respuesta utilizable.")

# Nota: ahora el toolbar de acciones está en el sidebar. También se pasa `ws_type` al grafo
# por si querés cambiar herramientas/prompting en `core.graph_agent` según el tipo.
