# agent.py
import os
from langchain.agents import initialize_agent, Tool
from langchain.agents.agent_types import AgentType
from langchain_community.llms import OpenAI as LangOpenAI
from langchain.tools import tool
from core.rag_pipeline import consultar_vectorstore
from core.sql_pipeline import ejecutar_query_natural
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.prebuilt.tool_node import tool_node

load_dotenv()

# LLM base
llm = LangOpenAI(temperature=0.6, model_name=os.getenv("MODEL_NAME", "gpt-4o"))

# Herramienta 1: consulta vectorial
@tool
def buscar_en_documentos(pregunta: str, workspace: str) -> str:
    """Busca una respuesta en la base vectorial del workspace"""
    return consultar_vectorstore(workspace, pregunta)

# Herramienta 2: consulta SQL
@tool
def buscar_en_sql(pregunta: str, workspace: str) -> str:
    """Realiza una consulta natural sobre la base de datos SQL del workspace"""
    return ejecutar_query_natural(workspace, pregunta)

# Diccionario de herramientas por tipo de workspace
AGENTES = {
    "excel": [buscar_en_sql, buscar_en_documentos],  # SQL + vectores
    "texto": [buscar_en_documentos],                 # solo vectores
}

def obtener_agente(workspace: str, tipo: str):
    tools = AGENTES.get(tipo, [buscar_en_documentos])
    return initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
        handle_parsing_errors=True
    )


def crear_agente(tools, instrucciones: str, temperatura: float = 0.7):
    llm = ChatOpenAI(
        temperature=temperatura,
        model="gpt-4o",
        api_key=os.getenv("OPENAI_API_KEY")
    )
    return create_tool_calling_agent(
        llm=llm,
        tools=tools,
        system_message=instrucciones
    )