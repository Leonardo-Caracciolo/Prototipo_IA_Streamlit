import streamlit as st
import os
from openai import OpenAI
from dotenv import load_dotenv
from core.vectorizer import cargar_documentos, aplicar_chunking, crear_vectorstore, cargar_vectorstore
from utils.excel_analyzer import cargar_excel
from core.history import load_history, save_history
from core.mcp_runner import ejecutar_mcp
from utils.voz_a_prompt import escuchar_y_convertir
from core.sql_loader import cargar_excel_a_postgres
from core.sql_agent import crear_agente_sql

load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=API_KEY)


def chat(workspace):
    st.subheader(f"💬 Chat para Workspace: {workspace}")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = load_history(workspace)

    if st.button("🎙️ Escuchar voz y preguntar"):
        texto = escuchar_y_convertir()
        st.session_state.chat_input_voz = texto
        st.rerun()

    # ✅ Proceso automático: vectorización y carga a SQL
    folder = f"storage/workspaces/{workspace}/documents"
    archivos = [f for f in os.listdir(folder)] if os.path.exists(folder) else []
    nuevos_documentos = []

    for archivo in archivos:
        ext = archivo.lower().split(".")[-1]
        if ext in ["pdf", "docx", "xls", "xlsx", "xlsm"]:
            nuevos_documentos.append(os.path.join(folder, archivo))

    if nuevos_documentos:
        documentos = cargar_documentos(workspace)
        if documentos:
            chunks = aplicar_chunking(documentos)
            crear_vectorstore(workspace, chunks)
            st.success("🔁 Documentos vectorizados nuevamente.")
        for archivo in nuevos_documentos:
            if archivo.endswith((".xls", ".xlsx", ".xlsm")):
                resultado = cargar_excel_a_postgres(archivo, workspace, os.getenv("DB_URL"))
                st.info(resultado)

    # Mostrar historial en orden cronológico ascendente
    for pregunta, respuesta in st.session_state.chat_history:
        st.markdown(f"**🧑 Usuario:** {pregunta}")
        st.markdown(f"**🤖 GPT-4o:** {respuesta}")
        st.markdown("---")

    prompt = st.chat_input("Escribí tu pregunta...", key="chat_input_manual")

    if not prompt and "chat_input_voz" in st.session_state:
        prompt = st.session_state.pop("chat_input_voz")

    if prompt:
        try:
            
            agente_sql = crear_agente_sql(workspace)
            with st.spinner("Consultando base de datos..."):
                respuesta = agente_sql.run(prompt)
        except Exception as e:
            # st.warning(f"⚠️ No se pudo usar SQL ({e}). Usando vectorstore...")
            st.warning(f"⚠️ Utilizando otro método de búsqueda...")

            archivos_excel = [f for f in archivos if f.endswith((".xls", ".xlsx", ".xlsm"))]
            if archivos_excel:
                path_excel = os.path.join(folder, archivos_excel[0])
                contexto, _ = cargar_excel(path_excel)
                with st.spinner("Analizando Excel con GPT-4o..."):
                    response = client.chat.completions.create(
                        model=os.getenv("MODEL_NAME", "gpt-4o"),
                        messages=[
                            {"role": "system", "content": "Actuá como un contador experto."},
                            {"role": "user", "content": f"{contexto}\n\n{prompt}"}
                        ]
                    )
                    respuesta = response.choices[0].message.content
            else:
                vectordb = cargar_vectorstore(workspace)
                if vectordb is None:
                    st.error("❌ No hay base vectorial disponible.")
                    return
                docs = vectordb.similarity_search(prompt, k=5)
                contexto = "\n\n".join([doc.page_content for doc in docs])
                with st.spinner("Buscando en la base de conocimiento..."):
                    response = client.chat.completions.create(
                        model=os.getenv("MODEL_NAME", "gpt-4o"),
                        messages=[
                            {"role": "system", "content": "Actuá como un contador experto."},
                            {"role": "user", "content": f"{contexto}\n\n{prompt}"}
                        ]
                    )
                    respuesta = response.choices[0].message.content

        st.session_state.chat_history.append((prompt, respuesta))
        save_history(workspace, st.session_state.chat_history)

        # Ejecutar comandos MCP si aplica
        if "generá un word" in prompt.lower():
            historial_completo = "\n\n".join(f"🧑 Usuario: {q}\n🤖 GPT: {a}" for q, a in st.session_state.chat_history)
            archivo = ejecutar_mcp("generar_word", nombre_archivo="conversacion_completa", contenido=historial_completo, workspace=workspace)
            st.session_state["archivo_word_generado"] = archivo

        elif "generá un excel" in prompt.lower() and "[" in respuesta:
            try:
                tabla = eval(respuesta.strip())
                archivo = ejecutar_mcp("generar_excel", nombre_archivo="reporte_tabla", tabla=tabla, workspace=workspace)
                st.session_state["archivo_excel_generado"] = archivo
            except Exception as e:
                st.error(f"Error al generar Excel: {e}")
        elif "resaltá" in prompt.lower() and "facturas" in prompt.lower():
            archivo = ejecutar_mcp("resaltar_facturas", workspace=workspace, prompt=prompt)
            st.success("📊 Excel generado con resaltado.")
            with open(archivo, "rb") as f:
                st.download_button("⬇️ Descargar Excel", f, file_name=os.path.basename(archivo))

        st.rerun()

    # Mostrar botones de descarga si existen
    if "archivo_word_generado" in st.session_state:
        with open(st.session_state["archivo_word_generado"], "rb") as f:
            st.download_button("⬇️ Descargar Word", f, file_name=os.path.basename(st.session_state["archivo_word_generado"]))
    if "archivo_excel_generado" in st.session_state:
        with open(st.session_state["archivo_excel_generado"], "rb") as f:
            st.download_button("⬇️ Descargar Excel", f, file_name=os.path.basename(st.session_state["archivo_excel_generado"]))

# Elemento marcador invisible al final
st.markdown('<div id="scroll-anchor"></div>', unsafe_allow_html=True)

# Script para hacer scroll hacia el marcador
st.markdown("""
    <script>
        const anchor = document.getElementById("scroll-anchor");
        if(anchor){
            anchor.scrollIntoView({ behavior: "smooth", block: "end" });
        }
    </script>
""", unsafe_allow_html=True)