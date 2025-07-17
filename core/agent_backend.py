# import os
# from dotenv import load_dotenv
# from langgraph.prebuilt.tool_node import tool_node
# from langchain.agents import AgentExecutor
# from langchain_openai import ChatOpenAI

# from core.rag_pipeline import buscar_en_documentos
# from core.sql_pipeline import buscar_en_sql

# load_dotenv()

# llm = ChatOpenAI(model=os.getenv("MODEL_NAME", "gpt-4o"), temperature=0.6)

# # Herramientas registradas para el agente
# herramientas = [
#     buscar_en_documentos,
#     buscar_en_sql
# ]

# # Agente con instrucciones y tools disponibles
# system_prompt = """
# Actuá como un analista inteligente. Nunca inventes información. Solo respondé en base a:
# 1. Archivos vectorizados (PDF/Word/Texto) mediante búsqueda semántica.
# 2. Datos tabulados provenientes de archivos Excel cargados en SQL.
# 3. NO uses conocimiento externo. Saludá primero si el mensaje es 'Hola'.
# """

# agent_executor = AgentExecutor(
#     agent=create_tool_calling_agent(llm=llm, tools=herramientas, system_message=system_prompt),
#     tools=herramientas,
#     verbose=True
# )

# # Interfaz para ejecutar una consulta desde el chat
# async def responder_con_agente(prompt: str, workspace: str) -> str:
#     resultado = await agent_executor.ainvoke({
#         "input": prompt,
#         "workspace": workspace  # útil si los tools lo necesitan
#     })
#     return resultado["output"]

# from saludo_Agente import agente_saludo


import os
import json
from typing import List
from dotenv import load_dotenv

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.utils.function_calling import convert_to_openai_function
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.messages import HumanMessage, AIMessage

from core.rag_pipeline import buscar_en_documentos
from core.sql_pipeline import buscar_en_sql

load_dotenv()

# --------------------------------------
# ✨ 1. Definición de herramientas (tool-binder)
@tool(description="Cuenta filas desde SQL en el workspace.")
def tool_buscar_en_sql(input: dict) -> str:
    return buscar_en_sql(prompt=input["input"], workspace=input["workspace"])

@tool(description="Busca información en los documentos del workspace.")
def tool_buscar_en_documentos(input: dict) -> str:
    return buscar_en_documentos(prompt=input["input"], workspace=input["workspace"])

tools: List = [tool_buscar_en_sql, tool_buscar_en_documentos]

# --------------------------------------
# 🔧 2. Modelo con tool-calling
llm = ChatOpenAI(
    temperature=0.0,
    model=os.getenv("MODEL_NAME", "gpt-4o"),
    api_key=os.getenv("OPENAI_API_KEY")
)

functions = [convert_to_openai_function(t) for t in tools]
llm_with_tools = llm.bind_tools(functions)

# --------------------------------------
# 🧠 3. Prompt estructurado para el agente
prompt_template = ChatPromptTemplate.from_messages([
    ("system", "Eres un asistente contable. Solo usás herramientas si es necesario."),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

# --------------------------------------
# ✅ 4. Creación del agente y executor
agent = create_tool_calling_agent(llm_with_tools, tools, prompt_template)
executor = AgentExecutor(agent=agent, tools=tools, verbose=False)

# --------------------------------------
# 🌐 5. Función pública

def despachar_consulta(prompt: str, workspace: str) -> str:
    clave_sql = any(k in prompt.lower() for k in ["fila", "filas", "tabla", "hoja", "excel"])
    if clave_sql:
        return buscar_en_sql(prompt, workspace)
    return buscar_en_documentos(prompt, workspace)