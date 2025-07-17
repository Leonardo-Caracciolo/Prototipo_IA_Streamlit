import streamlit as st
import os
from openai import OpenAI
from dotenv import load_dotenv
from core.vectorizer import cargar_documentos, aplicar_chunking, crear_vectorstore
from core.history import load_history, save_history
from core.mcp_runner import ejecutar_mcp
from utils.voz_a_prompt import escuchar_y_convertir
from core.agent_backend import despachar_consulta

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def chat(workspace):
    st.subheader(f"✬ Chat para Workspace: {workspace}")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = load_history(workspace)

    if st.button("🎤 Escuchar voz y preguntar"):
        texto = escuchar_y_convertir()
        st.session_state.chat_input_voz = texto

    if st.button("🔄 Procesar y vectorizar documentos"):
        documentos = cargar_documentos(workspace)
        if documentos:
            chunks = aplicar_chunking(documentos)
            crear_vectorstore(workspace, chunks)
            st.success("✅ Documentos vectorizados correctamente.")
        else:
            st.warning("⚠️ No se encontraron documentos válidos (PDF, Word, Excel).")

    prompt = st.chat_input("Escribí tu pregunta...", key="chat_input_manual")

    if not prompt and "chat_input_voz" in st.session_state:
        prompt = st.session_state.pop("chat_input_voz")

    if prompt:
        with st.spinner("Consultando al agente inteligente..."):
            respuesta = despachar_consulta(prompt, workspace)

        st.session_state.chat_history.append((prompt, respuesta))
        save_history(workspace, st.session_state.chat_history)

        # MCP
        if "generá un word" in prompt.lower():
            historial_completo = "\n\n".join(f"🧑 Usuario: {q}\n🤖 GPT: {a}" for q, a in st.session_state.chat_history)
            archivo = ejecutar_mcp("generar_word", nombre_archivo="conversacion_completa", contenido=historial_completo, workspace=workspace)
            st.success("📄 Word generado.")
            with open(archivo, "rb") as f:
                st.download_button("⬇️ Descargar Word", f, file_name=os.path.basename(archivo))

        elif "generá un excel" in prompt.lower() and "[" in respuesta:
            try:
                tabla = eval(respuesta.strip())
                archivo = ejecutar_mcp("generar_excel", nombre_archivo="reporte_tabla", tabla=tabla, workspace=workspace)
                st.success("📋 Excel generado.")
                with open(archivo, "rb") as f:
                    st.download_button("⬇️ Descargar Excel", f, file_name=os.path.basename(archivo))
            except Exception as e:
                st.error(f"Error al generar Excel: {e}")

    # Mostrar historial
    for pregunta, respuesta in st.session_state.chat_history:
        st.markdown(f"**🧑 Usuario:** {pregunta}")
        st.markdown(f"**🤖 GPT-4o:** {respuesta}")
        st.markdown("---")
