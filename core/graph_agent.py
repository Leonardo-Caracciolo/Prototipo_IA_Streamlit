# core/graph_agent.py (SOLUCIÓN DEFINITIVA)

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, ToolMessage
from typing import TypedDict, Annotated, Sequence, List
import operator

from langgraph.graph import StateGraph, END
from core.tools import lista_de_herramientas

# --- Definición del Estado (sin cambios) ---
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    workspace: str

# --- Componentes del Grafo ---
model = ChatOpenAI(temperature=0, model="gpt-4o", streaming=True)
# A diferencia del intento anterior, ahora sí vinculamos las herramientas originales
# porque el modelo necesita conocer sus firmas sin el 'workspace' inyectado.
model_with_tools = model.bind_tools(lista_de_herramientas)

# --- Nodos del Grafo ---
def call_model(state: AgentState):
    """
    Este nodo invoca al LLM. Ya no necesita modificar las herramientas,
    solo llama al modelo que ya las tiene vinculadas.
    """
    messages = state['messages']
    response = model_with_tools.invoke(messages)
    return {"messages": [response]}

# ✅ NUEVO NODO EJECUTOR DE HERRAMIENTAS PERSONALIZADO
def execute_tools_node(state: AgentState) -> dict:
    """
    Toma la última respuesta del LLM, extrae las llamadas a herramientas,
    les inyecta el 'workspace' y las ejecuta.
    """
    last_message = state['messages'][-1]
    tool_calls = last_message.tool_calls
    
    # Creamos un mapa para buscar herramientas por su nombre fácilmente
    tool_map = {tool.name: tool for tool in lista_de_herramientas}
    
    # Obtenemos el workspace del estado
    workspace = state["workspace"]
    
    tool_messages: List[ToolMessage] = []
    for call in tool_calls:
        tool_name = call['name']
        if tool_name in tool_map:
            tool_to_call = tool_map[tool_name]
            # Preparamos los argumentos que vienen del LLM
            tool_args = call['args']
            
            # --- ¡AQUÍ ESTÁ LA MAGIA! ---
            # Inyectamos el workspace en los argumentos antes de llamar a la herramienta.
            tool_args['workspace'] = workspace
            
            try:
                # Invocamos la herramienta con los argumentos aumentados
                output = tool_to_call.invoke(tool_args)
                
                # Guardamos el resultado
                tool_messages.append(
                    ToolMessage(content=str(output), tool_call_id=call['id'])
                )
            except Exception as e:
                # Si la herramienta falla, guardamos el error
                tool_messages.append(
                    ToolMessage(content=f"Error al ejecutar la herramienta {tool_name}: {e}", tool_call_id=call['id'])
                )
    
    return {"messages": tool_messages}


def should_continue(state: AgentState):
    """Decide si continuar llamando herramientas o finalizar."""
    last_message = state['messages'][-1]
    if last_message.tool_calls:
        return "continue"
    else:
        return "end"

# --- Ensamblado del Grafo ---
def crear_grafo_agente():
    workflow = StateGraph(AgentState)

    workflow.add_node("agent", call_model)
    # Reemplazamos el ToolNode por nuestra función personalizada
    workflow.add_node("action", execute_tools_node)

    workflow.set_entry_point("agent")

    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "continue": "action",
            "end": END
        }
    )
    workflow.add_edge('action', 'agent')

    return workflow.compile()

# --- Instancia del Agente ---
app = crear_grafo_agente()