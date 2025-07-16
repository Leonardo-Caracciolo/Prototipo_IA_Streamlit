# import streamlit as st
# import os
# from openai import OpenAI
# from dotenv import load_dotenv
# from core.vectorizer import cargar_documentos, aplicar_chunking, crear_vectorstore
# from utils.excel_analyzer import cargar_excel
# from core.history import load_history, save_history

# load_dotenv()
# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# def chat(workspace):
#     st.subheader(f"💬 Chat para Workspace: {workspace}")

#     if "chat_history" not in st.session_state:
#         st.session_state.chat_history = load_history(workspace)

#     if st.button("🔄 Procesar archivos y crear base vectorial"):
#         docs = cargar_documentos(workspace)
#         chunks = aplicar_chunking(docs)
#         crear_vectorstore(workspace, chunks)
#         st.success("Documentos vectorizados correctamente.")

#     prompt = st.chat_input("Escribí tu pregunta sobre el archivo Excel...")

#     if prompt:
#         folder = f"storage/workspaces/{workspace}/documents"
#         archivos_excel = [
#             f for f in os.listdir(folder)
#             if f.endswith((".xls", ".xlsx", ".xlsm"))
#         ]

#         if not archivos_excel:
#             st.warning("No hay archivos Excel para analizar.")
#         else:
#             path_excel = os.path.join(folder, archivos_excel[0])
#             contexto, _ = cargar_excel(path_excel)

#             with st.spinner("Analizando el archivo con GPT-4o..."):
#                 response = client.chat.completions.create(
#                     model=os.getenv("MODEL_NAME", "gpt-4o"),
#                     messages=[
#                         {
#                             "role": "system",
#                             "content": "Actuá como un contador experto y respondé preguntas sobre este archivo Excel."
#                         },
#                         {
#                             "role": "user",
#                             "content": f"{contexto}\n\n{prompt}"
#                         }
#                     ]
#                 )
#                 respuesta = response.choices[0].message.content
#                 st.session_state.chat_history.append((prompt, respuesta))
#                 save_history(workspace, st.session_state.chat_history)

#     # Mostrar historial
#     for pregunta, respuesta in st.session_state.chat_history:
#         st.markdown(f"**🧑 Usuario:** {pregunta}")
#         st.markdown(f"**🤖 GPT-4o:** {respuesta}")
#         st.markdown("---")


#Funcional 13/7
# import streamlit as st
# import os
# from openai import OpenAI
# from dotenv import load_dotenv
# from core.vectorizer import cargar_documentos, aplicar_chunking, crear_vectorstore, cargar_vectorstore
# from utils.excel_analyzer import cargar_excel
# from core.history import load_history, save_history
# from core.mcp_runner import ejecutar_mcp
# from utils.voz_a_prompt import escuchar_y_convertir

# from langchain.chains.question_answering import load_qa_chain
# from langchain_community.llms import OpenAI as LangOpenAI

# load_dotenv()
# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# def chat(workspace):
#     st.subheader(f"💬 Chat para Workspace: {workspace}")

#     if "chat_history" not in st.session_state:
#         st.session_state.chat_history = load_history(workspace)

#     if st.button("🎙️ Escuchar voz y preguntar"):
#         texto = escuchar_y_convertir()
#         st.session_state.chat_input_voz = texto

#     if st.button("🔄 Procesar y vectorizar documentos"):
#         documentos = cargar_documentos(workspace)
#         if documentos:
#             chunks = aplicar_chunking(documentos)
#             crear_vectorstore(workspace, chunks)
#             st.success("✅ Documentos vectorizados correctamente.")
#         else:
#             st.warning("⚠️ No se encontraron documentos válidos (PDF, Word, Excel).")

#     prompt = st.chat_input("Escribí tu pregunta...", key="chat_input_manual")

#     if not prompt and "chat_input_voz" in st.session_state:
#         prompt = st.session_state.pop("chat_input_voz")

#     if prompt:
#         folder = f"storage/workspaces/{workspace}/documents"
#         archivos_excel = [f for f in os.listdir(folder)] if os.path.exists(folder) else []
#         archivos_excel = [f for f in archivos_excel if f.endswith((".xls", ".xlsx", ".xlsm"))]

#         if archivos_excel:
#             path_excel = os.path.join(folder, archivos_excel[0])
#             contexto, _ = cargar_excel(path_excel)

#             with st.spinner("Analizando Excel con GPT-4o..."):
#                 response = client.chat.completions.create(
#                     model=os.getenv("MODEL_NAME", "gpt-4o"),
#                     messages=[
#                         {
#                             "role": "system",
#                             "content": "Actuá como un contador experto. Vas a recibir una vista previa de un archivo Excel. Podés calcular, resumir o generar documentos si se solicita."
#                         },
#                         {
#                             "role": "user",
#                             "content": f"{contexto}\n\n{prompt}"
#                         }
#                     ]
#                 )
#                 respuesta = response.choices[0].message.content

#         else:
#             # Fallback a búsqueda vectorial
#             st.warning("No hay archivos Excel. Buscando en documentos vectorizados...")

#             vectordb = cargar_vectorstore(workspace)
#             if vectordb is None:
#                 st.error("❌ No hay base vectorial disponible.")
#                 return

#             chain = load_qa_chain(LangOpenAI(temperature=0), chain_type="stuff")
#             docs = vectordb.similarity_search(prompt, k=5)
#             respuesta = chain.run(input_documents=docs, question=prompt)

#         st.session_state.chat_history.append((prompt, respuesta))
#         save_history(workspace, st.session_state.chat_history)

#         # Comandos especiales desde prompt
#         if "generá un word" in prompt.lower():
#             archivo = ejecutar_mcp("generar_word", nombre_archivo="reporte", contenido=respuesta, workspace=workspace)
#             st.success("📄 Archivo Word generado.")
#             with open(archivo, "rb") as f:
#                 st.download_button("⬇️ Descargar Word", f, file_name=os.path.basename(archivo))

#         elif "generá un excel" in prompt.lower() and "[" in respuesta:
#             try:
#                 tabla = eval(respuesta.strip())  # asumir que es una lista de listas o dicts
#                 archivo = ejecutar_mcp("generar_excel", nombre_archivo="reporte_tabla", tabla=tabla, workspace=workspace)
#                 st.success("📊 Archivo Excel generado.")
#                 with open(archivo, "rb") as f:
#                     st.download_button("⬇️ Descargar Excel", f, file_name=os.path.basename(archivo))
#             except Exception as e:
#                 st.error(f"Error al generar Excel: {e}")

#     # Mostrar historial
#     for pregunta, respuesta in st.session_state.chat_history:
#         st.markdown(f"**🧑 Usuario:** {pregunta}")
#         st.markdown(f"**🤖 GPT-4o:** {respuesta}")
#         st.markdown("---")



#Funcional con descarga de archivo word -> falta correccion de link descarga 13/7
# import streamlit as st
# import os
# from openai import OpenAI
# from dotenv import load_dotenv
# from core.vectorizer import cargar_documentos, aplicar_chunking, crear_vectorstore, cargar_vectorstore
# from utils.excel_analyzer import cargar_excel
# from core.history import load_history, save_history
# from core.mcp_runner import ejecutar_mcp
# from utils.voz_a_prompt import escuchar_y_convertir

# load_dotenv()
# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# def chat(workspace):
#     st.subheader(f"💬 Chat para Workspace: {workspace}")

#     if "chat_history" not in st.session_state:
#         st.session_state.chat_history = load_history(workspace)

#     if st.button("🎙️ Escuchar voz y preguntar"):
#         texto = escuchar_y_convertir()
#         st.session_state.chat_input_voz = texto

#     if st.button("🔄 Procesar y vectorizar documentos"):
#         documentos = cargar_documentos(workspace)
#         if documentos:
#             chunks = aplicar_chunking(documentos)
#             crear_vectorstore(workspace, chunks)
#             st.success("✅ Documentos vectorizados correctamente.")
#         else:
#             st.warning("⚠️ No se encontraron documentos válidos (PDF, Word, Excel).")

#     prompt = st.chat_input("Escribí tu pregunta...", key="chat_input_manual")

#     if not prompt and "chat_input_voz" in st.session_state:
#         prompt = st.session_state.pop("chat_input_voz")

#     if prompt:
#         folder = f"storage/workspaces/{workspace}/documents"
#         archivos_excel = [f for f in os.listdir(folder)] if os.path.exists(folder) else []
#         archivos_excel = [f for f in archivos_excel if f.endswith((".xls", ".xlsx", ".xlsm"))]

#         if archivos_excel:
#             path_excel = os.path.join(folder, archivos_excel[0])
#             contexto, _ = cargar_excel(path_excel)

#             with st.spinner("Analizando Excel con GPT-4o..."):
#                 response = client.chat.completions.create(
#                     model=os.getenv("MODEL_NAME", "gpt-4o"),
#                     messages=[
#                         {
#                             "role": "system",
#                             "content": "Actuá como un contador experto. Vas a recibir una vista previa de un archivo Excel. Podés calcular, resumir o generar documentos si se solicita."
#                         },
#                         {
#                             "role": "user",
#                             "content": f"{contexto}\n\n{prompt}"
#                         }
#                     ]
#                 )
#                 respuesta = response.choices[0].message.content

#         else:
#             st.warning("No hay archivos Excel. Buscando en documentos vectorizados...")

#             vectordb = cargar_vectorstore(workspace)
#             if vectordb is None:
#                 st.error("❌ No hay base vectorial disponible.")
#                 return

#             docs = vectordb.similarity_search(prompt, k=5)
#             contexto = "\n\n".join([doc.page_content for doc in docs])

#             with st.spinner("Buscando en la base de conocimiento..."):
#                 response = client.chat.completions.create(
#                     model=os.getenv("MODEL_NAME", "gpt-4o"),
#                     messages=[
#                         {
#                             "role": "system",
#                             "content": "Actuá como un contador experto. Vas a recibir documentos procesados previamente. "
#                                        "Podés responder consultas complejas, generar Word o Excel si se solicita, y brindar análisis."
#                         },
#                         {
#                             "role": "user",
#                             "content": f"{contexto}\n\n{prompt}"
#                         }
#                     ]
#                 )
#                 respuesta = response.choices[0].message.content

#         st.session_state.chat_history.append((prompt, respuesta))
#         save_history(workspace, st.session_state.chat_history)

#         # Comandos especiales desde prompt
#         if "generá un word" in prompt.lower():
#             historial_completo = "\n\n".join(
#                 f"🧑 Usuario: {q}\n🤖 GPT: {a}" for q, a in st.session_state.chat_history
#             )
#             archivo = ejecutar_mcp("generar_word", nombre_archivo="conversacion_completa", contenido=historial_completo, workspace=workspace)
#         elif "generá un excel" in prompt.lower() and "[" in respuesta:
#             try:
#                 tabla = eval(respuesta.strip())  # asumir que es una lista de listas o dicts
#                 archivo = ejecutar_mcp("generar_excel", nombre_archivo="reporte_tabla", tabla=tabla, workspace=workspace)
#                 st.success("📊 Archivo Excel generado.")
#                 with open(archivo, "rb") as f:
#                     st.download_button("⬇️ Descargar Excel", f, file_name=os.path.basename(archivo))
#             except Exception as e:
#                 st.error(f"Error al generar Excel: {e}")

#     # Mostrar historial
#     for pregunta, respuesta in st.session_state.chat_history:
#         st.markdown(f"**🧑 Usuario:** {pregunta}")
#         st.markdown(f"**🤖 GPT-4o:** {respuesta}")
#         st.markdown("---")



# import streamlit as st
# import os
# from openai import OpenAI
# from dotenv import load_dotenv
# from core.vectorizer import cargar_documentos, aplicar_chunking, crear_vectorstore, cargar_vectorstore
# from utils.excel_analyzer import cargar_excel
# from core.history import load_history, save_history
# from core.mcp_runner import ejecutar_mcp
# from utils.voz_a_prompt import escuchar_y_convertir

# from langchain.chains.question_answering import load_qa_chain
# from langchain_community.llms import OpenAI as LangOpenAI

# load_dotenv()
# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# def chat(workspace):
#     st.subheader(f"💬 Chat para Workspace: {workspace}")

#     if "chat_history" not in st.session_state:
#         st.session_state.chat_history = load_history(workspace)

#     if st.button("🎙️ Escuchar voz y preguntar"):
#         texto = escuchar_y_convertir()
#         st.session_state.chat_input_voz = texto

#     if st.button("🔄 Procesar y vectorizar documentos"):
#         documentos = cargar_documentos(workspace)
#         if documentos:
#             chunks = aplicar_chunking(documentos)
#             crear_vectorstore(workspace, chunks)
#             st.success("✅ Documentos vectorizados correctamente.")
#         else:
#             st.warning("⚠️ No se encontraron documentos válidos (PDF, Word, Excel).")

#     prompt = st.chat_input("Escribí tu pregunta...", key="chat_input_manual")

#     if not prompt and "chat_input_voz" in st.session_state:
#         prompt = st.session_state.pop("chat_input_voz")

#     if prompt:
#         folder = f"storage/workspaces/{workspace}/documents"
#         archivos_excel = [f for f in os.listdir(folder)] if os.path.exists(folder) else []
#         archivos_excel = [f for f in archivos_excel if f.endswith((".xls", ".xlsx", ".xlsm"))]

#         if archivos_excel:
#             path_excel = os.path.join(folder, archivos_excel[0])
#             contexto, _ = cargar_excel(path_excel)

#             with st.spinner("Analizando Excel con GPT-4o..."):
#                 response = client.chat.completions.create(
#                     model=os.getenv("MODEL_NAME", "gpt-4o"),
#                     messages=[
#                         {
#                             "role": "system",
#                             "content": "Actuá como un contador experto. Vas a recibir una vista previa de un archivo Excel. Podés calcular, resumir o generar documentos si se solicita."
#                         },
#                         {
#                             "role": "user",
#                             "content": f"{contexto}\n\n{prompt}"
#                         }
#                     ]
#                 )
#                 respuesta = response.choices[0].message.content

#         else:
#             # Fallback a búsqueda vectorial
#             st.warning("No hay archivos Excel. Buscando en documentos vectorizados...")

#             vectordb = cargar_vectorstore(workspace)
#             if vectordb is None:
#                 st.error("❌ No hay base vectorial disponible.")
#                 return

#             chain = load_qa_chain(LangOpenAI(temperature=0), chain_type="stuff")
#             docs = vectordb.similarity_search(prompt, k=5)
#             respuesta = chain.run(input_documents=docs, question=prompt)

#         # Comandos especiales desde prompt
#         if "generá un word" in prompt.lower():
#             ruta_archivo = ejecutar_mcp("generar_word", nombre_archivo="reporte", contenido=respuesta, workspace=workspace)
#             if ruta_archivo:
#                 nombre = os.path.basename(ruta_archivo)
#                 link = f"[Descargar Documento Word](/static/generated/{nombre})"
#                 respuesta += f"\n\n{link}"

#         elif "generá un excel" in prompt.lower() and "[" in respuesta:
#             try:
#                 tabla = eval(respuesta.strip())  # Asumimos que es una lista de listas o dicts
#                 ruta_archivo = ejecutar_mcp("generar_excel", nombre_archivo="reporte_tabla", tabla=tabla, workspace=workspace)
#                 if ruta_archivo:
#                     nombre = os.path.basename(ruta_archivo)
#                     link = f"[Descargar Documento Excel](/static/generated/{nombre})"
#                     respuesta += f"\n\n{link}"
#             except Exception as e:
#                 st.error(f"Error al generar Excel: {e}")

#         st.session_state.chat_history.append((prompt, respuesta))
#         save_history(workspace, st.session_state.chat_history)

#     # Mostrar historial
#     for pregunta, respuesta in st.session_state.chat_history:
#         st.markdown(f"**🧑 Usuario:** {pregunta}")
#         st.markdown(f"**🤖 GPT-4o:** {respuesta}", unsafe_allow_html=True)
#         st.markdown("---")


import streamlit as st
import os
from openai import OpenAI
from dotenv import load_dotenv
from core.vectorizer import cargar_documentos, aplicar_chunking, crear_vectorstore, cargar_vectorstore
from utils.excel_analyzer import cargar_excel
from core.history import load_history, save_history
from core.mcp_runner import ejecutar_mcp
from utils.voz_a_prompt import escuchar_y_convertir

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def chat(workspace):
    st.subheader(f"💬 Chat para Workspace: {workspace}")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = load_history(workspace)

    if st.button("🎙️ Escuchar voz y preguntar"):
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
        folder = f"storage/workspaces/{workspace}/documents"
        archivos_excel = [f for f in os.listdir(folder)] if os.path.exists(folder) else []
        archivos_excel = [f for f in archivos_excel if f.endswith((".xls", ".xlsx", ".xlsm"))]

        if archivos_excel:
            path_excel = os.path.join(folder, archivos_excel[0])
            contexto, _ = cargar_excel(path_excel)

            with st.spinner("Analizando Excel con GPT-4o..."):
                response = client.chat.completions.create(
                    model=os.getenv("MODEL_NAME", "gpt-4o"),
                    messages=[
                        {
                            "role": "system",
                            "content": "Actuá como un contador experto. Vas a recibir una vista previa de un archivo Excel. Podés calcular, resumir o generar documentos si se solicita."
                        },
                        {
                            "role": "user",
                            "content": f"{contexto}\n\n{prompt}"
                        }
                    ]
                )
                respuesta = response.choices[0].message.content

        else:
            st.warning("No hay archivos Excel. Buscando en documentos vectorizados...")

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
                        {
                            "role": "system",
                            "content": "Actuá como un contador experto. Vas a recibir documentos procesados previamente. "
                                       "Podés responder consultas complejas, generar Word o Excel si se solicita, y brindar análisis."
                        },
                        {
                            "role": "user",
                            "content": f"{contexto}\n\n{prompt}"
                        }
                    ]
                )
                respuesta = response.choices[0].message.content

        st.session_state.chat_history.append((prompt, respuesta))
        save_history(workspace, st.session_state.chat_history)

        # Comandos especiales desde prompt
        if "generá un word" in prompt.lower():
            historial_completo = "\n\n".join(
                f"🧑 Usuario: {q}\n🤖 GPT: {a}" for q, a in st.session_state.chat_history
            )
            archivo = ejecutar_mcp(
                "generar_word",
                nombre_archivo="conversacion_completa",
                contenido=historial_completo,
                workspace=workspace
            )
            st.session_state["archivo_word_generado"] = archivo
            st.success("📄 Documento Word generado.")

        elif "generá un excel" in prompt.lower() and "[" in respuesta:
            try:#Ver de pasar el input a string o cambiar el input (postgreSQL)
                tabla = eval(respuesta.strip())  # asumir que es una lista de listas o dicts
                archivo = ejecutar_mcp("generar_excel", nombre_archivo="reporte_tabla", tabla=tabla, workspace=workspace)
                st.success("📊 Archivo Excel generado.")
                with open(archivo, "rb") as f:
                    st.download_button("⬇️ Descargar Excel", f, file_name=os.path.basename(archivo))
            except Exception as e:
                st.error(f"Error al generar Excel: {e}")

    # Mostrar historial
    for pregunta, respuesta in st.session_state.chat_history:
        st.markdown(f"**🧑 Usuario:** {pregunta}")
        st.markdown(f"**🤖 GPT-4o:** {respuesta}")
        st.markdown("---")

    # Mostrar botón si hay un Word generado en esta sesión
    if "archivo_word_generado" in st.session_state:
        with open(st.session_state["archivo_word_generado"], "rb") as f:
            st.download_button(
                "⬇️ Descargar Documento Word",
                f,
                file_name=os.path.basename(st.session_state["archivo_word_generado"])
            )