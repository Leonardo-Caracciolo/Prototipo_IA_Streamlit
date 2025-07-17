import os
from core.agent_backend import create_agent, tool_buscar_en_sql, tool_buscar_en_documentos
from core.workspace_manager import detectar_tipo_workspace

def get_agente_para_workspace(workspace: str):
    tipo = detectar_tipo_workspace(workspace)

    if tipo == "sql":
        tools = [tool_buscar_en_sql]
    elif tipo == "vectorial":
        tools = [tool_buscar_en_documentos]
    elif tipo == "mixto":
        tools = [tool_buscar_en_sql, tool_buscar_en_documentos]
    else:
        raise ValueError(f"El workspace '{workspace}' no contiene datos útiles (ni SQL ni vectores)")

    return create_agent(tools)
