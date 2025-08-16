# main_chat.py

import streamlit as st
import os
import re
from dotenv import load_dotenv

# LangChain y LangGraph imports
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

# Imports de tu proyecto
from core.history import load_history, save_history
from core.graph_agent import app  # ¡Importamos el agente compilado!
from utils.voz_a_prompt import escuchar_y_convertir
from core.vectorizer import cargar_documentos, aplicar_chunking, crear_vectorstore

load_dotenv()

def convertir_historial_a_mensajes(historial_tuplas: list[tuple]) -> list[BaseMessage]:
    """Convierte el historial de (pregunta, respuesta) al formato de mensajes de LangChain."""
    mensajes = []
    for pregunta, respuesta in historial_tuplas:
        mensajes.append(HumanMessage(content=pregunta))
        mensajes.append(AIMessage(content=respuesta))
    return mensajes

def guardar_mensajes_a_historial(mensajes: list[BaseMessage]) -> list[tuple]:
    """Convierte los mensajes de LangChain de vuelta a tuplas para guardarlos."""
    historial_tuplas = []
    # Iteramos de a pares (Humano, AI)
    for i in range(0, len(mensajes), 2):
        if i + 1 < len(mensajes) and isinstance(mensajes[i], HumanMessage) and isinstance(mensajes[i+1], AIMessage):
            pregunta = mensajes[i].content
            respuesta = mensajes[i+1].content
            historial_tuplas.append((pregunta, respuesta))
    return historial_tuplas


def chat(workspace):
    st.subheader(f"💬 Chat para Workspace: {workspace}")

    # --- INICIALIZACIÓN DEL HISTORIAL (ADAPTADO) ---
    if "messages" not in st.session_state:
        # Cargamos el historial antiguo y lo convertimos al nuevo formato de objetos
        historial_antiguo = load_history(workspace)
        st.session_state.messages = convertir_historial_a_mensajes(historial_antiguo)

    # --- LÓGICA DE PREPARACIÓN DEL WORKSPACE (SIN CAMBIOS) ---
    # Esta parte sigue siendo útil para asegurar que los documentos estén procesados.
    folder = f"storage/workspaces/{workspace}/documents"
    if os.path.exists(folder):
        nuevos_documentos = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith((".pdf", ".docx", ".xls", ".xlsx", ".xlsm"))]
        if nuevos_documentos:
            with st.spinner("Actualizando base de conocimiento..."):
                documentos = cargar_documentos(workspace)
                if documentos:
                    chunks = aplicar_chunking(documentos)
                    crear_vectorstore(workspace, chunks)
            st.success("✅ Base de conocimiento actualizada.")
            
    # --- INTERFAZ DE USUARIO ---
    if st.button("🎙️ Escuchar voz y preguntar"):
        texto = escuchar_y_convertir()
        if texto:
            st.session_state.chat_input_voz = texto
            st.rerun()

    # --- MOSTRAR HISTORIAL DE CHAT (ADAPTADO) ---
    for message in st.session_state.messages:
        role = "🧑 Usuario" if isinstance(message, HumanMessage) else "🤖 TaxMiner"
        with st.chat_message(role):
            st.markdown(message.content)

    # --- GESTIÓN DE LA ENTRADA DEL USUARIO ---
    prompt = st.chat_input("Escribí tu pregunta...")
    if "chat_input_voz" in st.session_state:
        prompt = st.session_state.pop("chat_input_voz")

    # --- LLAMADA AL AGENTE LANGGRAPH (LÓGICA PRINCIPAL REFACTORIZADA) ---
    if prompt:
        st.session_state.messages.append(HumanMessage(content=prompt))
        with st.chat_message("🧑 Usuario"):
            st.markdown(prompt)

        with st.chat_message("🤖 TaxMiner"):
            with st.spinner("Pensando..."):
                # Preparamos el estado para el grafo
                graph_state = {
                    "messages": list(st.session_state.messages),
                    "workspace": workspace,
                }
                
                final_response = None
                # Usamos stream para poder ver los pasos intermedios si quisiéramos
                # Por ahora, solo nos interesa la respuesta final
                for event in app.stream(graph_state, {"recursion_limit": 15}):
                    if "agent" in event:
                        # La respuesta final es el último mensaje del nodo 'agent'
                        if event["agent"]["messages"][-1].content:
                             final_response = event["agent"]["messages"][-1]

                if final_response:
                    st.markdown(final_response.content)
                    st.session_state.messages.append(final_response)
                    
                    # Guardamos el historial en el formato antiguo para retrocompatibilidad
                    historial_para_guardar = guardar_mensajes_a_historial(st.session_state.messages)
                    save_history(workspace, historial_para_guardar)
                else:
                    st.error("El agente no pudo generar una respuesta.")

        # --- GESTIÓN DE DESCARGAS (ADAPTADO) ---
        # Ahora, en lugar de revisar `if "generá un excel" in prompt...`,
        # revisamos si la respuesta del agente contiene una ruta de archivo.
        # Esto es mucho más robusto.
        if final_response and "La ruta es:" in final_response.content:
            st.rerun() # Hacemos un rerun para que el botón de descarga aparezca abajo

    # --- MOSTRAR BOTONES DE DESCARGA ---
    # Esta lógica se activa después del rerun, cuando la ruta ya está en el último mensaje
    if st.session_state.messages:
        last_message = st.session_state.messages[-1]
        if isinstance(last_message, AIMessage) and "La ruta es:" in last_message.content:
            # Extraemos la ruta del archivo del texto del mensaje
            match = re.search(r"La ruta es: (.*)", last_message.content)
            if match:
                file_path = match.group(1).strip()
                if os.path.exists(file_path):
                    file_name = os.path.basename(file_path)
                    file_extension = file_name.split('.')[-1].upper()
                    with open(file_path, "rb") as f:
                        st.download_button(
                            f"⬇️ Descargar {file_extension}",
                            f,
                            file_name=file_name
                        )
# main_chat.py - fin