import os
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_community.utilities.sql_database import SQLDatabase

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import Tool
from langchain.prompts import ChatPromptTemplate

load_dotenv()

WORKSPACE_SQL_DESCRIPTION = {
    "facturas": """
Consultá sobre la base de datos. Tené en cuenta los siguientes mapeos semánticos:

📌 Mapeo semántico (consultas comunes):
- Si preguntás por **facturas apócrifas**, usá la columna "Apocrifa" con valor 'Si'.
- Si preguntás por **facturas duplicadas**, usá la columna "Duplicado" con valor 'Si'.
- Si preguntás por **autorización del CAE**, usá la columna "autorizacion_cae" con valor 'Autorizado'.
- Si preguntás por **CAE incorrecto** por inexistente, usá "autorizacion_cae" = 'CAE no encontrado'.
- Si preguntás por **CAE incorrecto** por fecha, usá "autorizacion_cae" = 'Fecha no coincide'.
- Si preguntás por **total de facturas**, contá las filas, por ejemplo COUNT(*) sobre la tabla.
- Si preguntás por **importe total**, usá la columna "Total".
- Si preguntás por **fecha de emisión**, usá la columna "Fecha".
- Si preguntás por **CUIT del emisor**, usá "Cuit del Emisor".
- Si preguntás por **CUIT del receptor**, usá "Cuit del receptor".
- Si preguntás por **detalle del servicio**, usá "Detalle".
- Si preguntás por **IVA**, usá "Iva".
- Si preguntás por **Percepciones de IVA**, usá "Percepciones de IVA".
- Si preguntás por **CAE**, usá "CAE".
- Si preguntás por **categoría del emisor**, usá:
    - "Categoría en IVA Emisor"
    - "Categoría en IIBB Emisor"
- Si preguntás por **domicilio del emisor**, usá "Domicilio Emisor".
- Si preguntás por **domicilio del receptor**, usá "Domicilio Receptor".

⚠️ Siempre usá comillas dobles en nombres de columnas (por ejemplo: "Apocrifa", "Duplicado", "Total", etc.).
❌ No uses backticks ni markdown en las consultas.
"""
}

def crear_agente_sql(workspace_slug: str) -> AgentExecutor:
    workspace_slug = workspace_slug.lower()
    nombre_tabla = f"facturas_{workspace_slug}".replace(" ", "_")

    db_url = os.getenv("DB_URL")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    model_name = os.getenv("MODEL_NAME", "gpt-4o")

    if not db_url or not openai_api_key:
        raise EnvironmentError("Faltan DB_URL u OPENAI_API_KEY")

    # LLM con tool-calling nativo
    llm = ChatOpenAI(
        temperature=0,
        model=model_name,
        openai_api_key=openai_api_key
    )

    # Limita el acceso a la/s tabla/s relevante/s
    db = SQLDatabase.from_uri(db_url, include_tables=[nombre_tabla])

    # Descripción semántica / reglas
    workspace_description = WORKSPACE_SQL_DESCRIPTION.get("facturas", "")

    tool_description = f"""
Consultá sobre la tabla "{nombre_tabla}" del workspace '{workspace_slug}'.

{workspace_description}

⚠️ Usá SIEMPRE comillas dobles en nombres de columnas. Ejemplo válido:
SELECT COUNT(*) FROM {nombre_tabla} WHERE "Duplicado" = 'Si';
"""

    # Envoltorio para recibir un string y devolver resultado crudo claro
    def run_sql(query: str) -> str:
        return db.run(query)

    herramienta = Tool(
        name="PostgreSQL",
        func=run_sql,
        description=tool_description,
    )

    # Prompt sin ReAct; el agente decide cuándo llamar a la herramienta
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "Sos un analista SQL. Cuando necesites datos, usá la herramienta PostgreSQL. "
         "Escribí consultas válidas para PostgreSQL citando columnas con comillas dobles. "
         "Devolvé respuestas claras y, si corresponde, un breve resumen. "
         "Nunca imprimas pensamientos internos."),
        ("human", "{input}")
    ])

    agent = create_tool_calling_agent(llm, [herramienta], prompt)

    executor = AgentExecutor(
        agent=agent,
        tools=[herramienta],
        verbose=False,               # evita ANSI en logs
        handle_parsing_errors=False, # ya no dependemos de formateo ReAct
        max_iterations=6
    )

    return executor
