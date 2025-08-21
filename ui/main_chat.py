import os
import re
import json
import hashlib
from pathlib import Path
from datetime import datetime
import pandas as pd
from io import StringIO
import streamlit as st
from dotenv import load_dotenv

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

from core.history import load_history, save_history
from core.graph_agent import app
from utils.voz_a_prompt import escuchar_y_convertir
from core.vectorizer import cargar_documentos, aplicar_chunking, crear_vectorstore

import os
import shutil
import subprocess
import sys

load_dotenv()

# ─────────── Config general UI ─────────── #
st.set_page_config(page_title="TaxMiner • Chat", layout="wide")

# ---- Pegar en main_chat.py (helpers de detección/parseo) --------------------

MD_ROW_SEP_PAT = r"^\s*\|.*\|\s*$"  # línea con pipes al inicio y fin
MD_HEADER_SEP_PAT = r"^\s*\|?\s*:?-{3,}\s*(\|\s*:?-{3,}\s*)+\|?\s*$"

def _is_markdown_table(text: str) -> bool:
    lines = [l.rstrip() for l in text.strip().splitlines() if l.strip()]
    if len(lines) < 2: 
        return False
    has_row = sum(1 for l in lines if re.match(MD_ROW_SEP_PAT, l)) >= 2
    has_header_sep = any(re.match(MD_HEADER_SEP_PAT, l) for l in lines[:4])
    return has_row and has_header_sep

def _is_html_table(text: str) -> bool:
    t = text.lower()
    return "<table" in t and "</table>" in t

def _is_csv(text: str) -> bool:
    # Heurística simple: varias líneas, al menos una con 1+ comas y columnas ~consistentes
    lines = [l for l in text.strip().splitlines() if l.strip()]
    if len(lines) < 2: 
        return False
    counts = [l.count(",") for l in lines[:20]]
    return max(counts) >= 1 and len(set(counts)) <= max(3, len(lines)//2)

def _is_json_table(text: str) -> bool:
    try:
        obj = json.loads(text)
    except Exception:
        return False
    if isinstance(obj, list) and obj and all(isinstance(r, dict) for r in obj):
        # Chequeo liviano de “tabla”: llaves relativamente consistentes entre filas
        keys0 = set(obj[0].keys())
        same = sum(1 for r in obj[:50] if set(r.keys()) == keys0)
        return same >= max(1, min(5, len(obj)))
    return False

def _parse_json_table(text: str) -> pd.DataFrame | None:
    try:
        obj = json.loads(text)
        if isinstance(obj, list):
            return pd.DataFrame(obj)
    except Exception:
        pass
    return None

def _parse_csv(text: str) -> pd.DataFrame | None:
    # Intenta CSV estándar; si falla, intenta ; como separador
    try:
        return pd.read_csv(StringIO(text))
    except Exception:
        try:
            return pd.read_csv(StringIO(text), sep=";")
        except Exception:
            return None

def _extract_fenced_table(text: str):
    """
    Si el LLM devolvió bloques tipo:
    ```table:markdown ...```, ```table:csv ...``` o ```table:json ...```
    devolvemos (tipo, contenido). Si no, (None, None).
    """
    m = re.search(r"```table:(markdown|csv|json)\s+([\s\S]*?)```", text, flags=re.IGNORECASE)
    if not m:
        return None, None
    return m.group(1).lower(), m.group(2).strip()

# --- Extras robustos para tablas ------------------------------------------------
FENCE_ANY = re.compile(r"```(?:[a-zA-Z0-9_-]+)?\s*([\s\S]*?)```", re.IGNORECASE)

def _unwrap_if_md_table_in_code(text: str) -> str | None:
    """Si hay un bloque de código que adentro contiene una tabla Markdown, devuelve SOLO esa tabla sin fences."""
    for m in FENCE_ANY.finditer(text):
        candidate = m.group(1).strip()
        if _is_markdown_table(candidate):
            return candidate
    return None

MD_BLOCK_RE = re.compile(
    r"(?P<block>(?:^\s*\|.*\|\s*$\n)"      # header
    r"(?:^\s*\|?\s*[:\-]{3,}.*\|\s*$\n)"    # separator
    r"(?:^\s*\|.*\|\s*$\n?)+)",             # rows
    re.MULTILINE
)

def _extract_first_md_table_block(text: str):
    """
    Busca la primera tabla Markdown en el texto (aun si hay prosa antes/después).
    Devuelve (before, table_md, after) o (None, None, None) si no hay.
    """
    # 1) Probar dentro de code fences
    for m in FENCE_ANY.finditer(text):
        candidate = m.group(1)
        m2 = MD_BLOCK_RE.search(candidate)
        if m2:
            before = text[:m.start()].strip()
            table = m2.group("block").strip()
            after = text[m.end():].strip()
            return before, table, after

    # 2) Probar en texto plano
    m = MD_BLOCK_RE.search(text)
    if m:
        before = text[:m.start()].strip()
        table = m.group("block").strip()
        after = text[m.end():].strip()
        return before, table, after

    return None, None, None

def _render_table_or_text(st_container, raw_text: str):
    # 1) Fences explícitos tipo table:*
    # Detectar code fence ```json ... ``` con una lista de dicts
    m_json = re.search(r"```json\s+([\s\S]*?)```", raw_text, flags=re.IGNORECASE)
    if m_json:
        df = _parse_json_table(m_json.group(1).strip())
        if df is not None and not df.empty:
            st_container.dataframe(df, use_container_width=True)
            return

    ftype, fcontent = _extract_fenced_table(raw_text)
    if ftype == "json":
        df = _parse_json_table(fcontent)
        if df is not None and not df.empty:
            st_container.dataframe(df, use_container_width=True); return
    elif ftype == "csv":
        df = _parse_csv(fcontent)
        if df is not None and not df.empty:
            st_container.dataframe(df, use_container_width=True); return
    elif ftype == "markdown":
        st_container.markdown(fcontent); return

    # 2) Tabla Markdown dentro de code-fence genérico ```...```
    unwrapped = _unwrap_if_md_table_in_code(raw_text)
    if unwrapped:
        # Mostrar texto fuera del bloque como markdown normal si existiera
        before, _, after = _extract_first_md_table_block(raw_text)  # reutilizamos para capturar periferia
        if before: st_container.markdown(before)
        st_container.markdown(unwrapped)
        if after: st_container.markdown(after)
        return

    # 3) Texto mixto con tabla Markdown incrustada (sin fences)
    before, table_md, after = _extract_first_md_table_block(raw_text)
    if table_md:
        if before: st_container.markdown(before)
        st_container.markdown(table_md)
        if after: st_container.markdown(after)
        return

    # 4) Heurísticas restantes
    text = raw_text.strip()

    if _is_json_table(text):
        df = _parse_json_table(text)
        if df is not None and not df.empty:
            st_container.dataframe(df, use_container_width=True); return

    if _is_csv(text):
        df = _parse_csv(text)
        if df is not None and not df.empty:
            st_container.dataframe(df, use_container_width=True); return

    if _is_html_table(text):
        st_container.markdown(text, unsafe_allow_html=True); return

    # 5) Fallback: texto plano
    st_container.markdown(text)


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
    # Simulación para pruebas
    if "leyes" in name.lower():
        return "Conocimiento de leyes"
    if "facturas" in name.lower():
        return "Analisis de Facturas"
    
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

    # do_process = st.session_state.pop(f"action:update:{workspace}", False)
    if st.session_state.pop(f"action:update:{workspace}", False):
        # --- IMPORTANTE: CONFIGURA ESTAS 2 LÍNEAS ---
        # 1. Ruta del archivo Excel principal que quieres copiar.
        ruta_archivo_origen = r"C:\Users\seba\Desktop\IA_DELOITTE\Prototipo_IA_Streamlit\fac_acumuladas\Facturas_totales.xlsx"
        # 2. Ruta del historial del chat en formato JSON.
        ruta_json_historial = os.path.join(_WS_ROOT, workspace, "history.json")

        try:
            # --- Parte 1: Creación de la carpeta y copia del archivo principal ---
            ruta_descargas = os.path.join(os.path.expanduser("~"), "Downloads")
            ruta_carpeta_destino = os.path.join(ruta_descargas, "resumen_ia")
            os.makedirs(ruta_carpeta_destino, exist_ok=True)

            if os.path.exists(ruta_archivo_origen):
                shutil.copy(ruta_archivo_origen, ruta_carpeta_destino)
                st.toast("✅ Archivo principal copiado exitosamente!")
            else:
                st.warning("⚠️ No se encontró el archivo Excel principal para copiar. Saltando este paso.")

            # --- Parte 2: Lectura del JSON y creación del Excel a partir de la tabla ---
            with open(ruta_json_historial, 'r', encoding='utf-8') as f:
                historial_chat = json.load(f)

            if historial_chat:
                ultimo_par = historial_chat[-1]
                contenido_asistente = ultimo_par[1]

                if "table:json" in contenido_asistente:
                    st.toast("🔎 Tabla en formato JSON encontrada. Procesando...")
                    try:
                        # ---- INICIO DE LA CORRECCIÓN DEL ERROR "EXTRA DATA" ----
                        # 1. Dividimos el texto para obtener todo lo que está DESPUÉS de ```table:json
                        parte_posterior = contenido_asistente.split("```table:json", 1)[1]
                        
                        # 2. Sobre ese resultado, tomamos todo lo que está ANTES del siguiente ```
                        json_string = parte_posterior.split("```", 1)[0]
                        
                        # 3. Limpiamos espacios en blanco por seguridad
                        json_string = json_string.strip()
                        # ---- FIN DE LA CORRECCIÓN ----
                        
                        datos_tabla = json.loads(json_string)
                        df = pd.DataFrame(datos_tabla)
                        
                        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                        nombre_excel_tabla = f"tabla_generada_{timestamp}.xlsx"
                        ruta_excel_tabla = os.path.join(ruta_carpeta_destino, nombre_excel_tabla)

                        df.to_excel(ruta_excel_tabla, index=False)
                        st.success(f"📈 ¡Tabla guardada como '{nombre_excel_tabla}'!")

                    except (json.JSONDecodeError, IndexError) as e:
                        st.error(f"Error al procesar la tabla JSON: {e}")
                    except Exception as e:
                        st.error(f"Error al crear el Excel desde la tabla: {e}")

            # --- Parte 3: Abrir la carpeta de destino ---
            if sys.platform == "win32":
                subprocess.Popen(f'explorer "{os.path.realpath(ruta_carpeta_destino)}"')
            elif sys.platform == "darwin":
                subprocess.Popen(["open", ruta_carpeta_destino])
            else:
                subprocess.Popen(["xdg-open", ruta_carpeta_destino])
            
            st.toast(f"📂 Abriendo la carpeta: resumen_ia")

        except FileNotFoundError:
            st.error(f"❌ Error: No se encontró el archivo JSON en '{ruta_json_historial}'. Revisa la ruta.")
        except Exception as e:
            st.error(f"Ocurrió un error inesperado: {e}")


    # Procesamiento de documentos: manual (desde sidebar) + cambio detectado
    # if "docs_fingerprint" not in st.session_state:
    #     st.session_state.docs_fingerprint = {}
    # fp_before = st.session_state.docs_fingerprint.get(workspace)
    # fp_now = _fingerprint_workspace_docs(workspace)

    # if do_process or (fp_before != fp_now and fp_now):
    #     with st.status("Procesando documentos…", expanded=True) as status:
    #         status.write("Cargando documentos…")
    #         documentos = cargar_documentos(workspace)
    #         if documentos:
    #             status.write("Chunking…")
    #             chunks = aplicar_chunking(documentos)
    #             status.write("Creando vectorstore…")
    #             crear_vectorstore(workspace, chunks)
    #             st.session_state.docs_fingerprint[workspace] = fp_now
    #             status.update(label="✅ Base de conocimiento actualizada", state="complete")
    #         else:
    #             status.update(label="No se encontraron documentos válidos", state="error")

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
            if isinstance(msg, AIMessage):
                # --- MODIFICACIÓN 1: Renderizado condicional en el historial ---
                if ws_type.lower().startswith("analisis"):
                    _render_table_or_text(st, msg.content)
                else:
                    st.markdown(msg.content)
            else:
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
                    # --- MODIFICACIÓN 2: Renderizado condicional de la nueva respuesta ---
                    if ws_type.lower().startswith("analisis"):
                        _render_table_or_text(st, final_response.content)
                    else:
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

