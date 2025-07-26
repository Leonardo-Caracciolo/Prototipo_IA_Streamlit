import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_community.utilities.sql_database import SQLDatabase
from langchain.agents import AgentExecutor, Tool, initialize_agent
from langchain.agents.agent_types import AgentType

load_dotenv()

# Diccionario de descripciones por workspace (podés ampliarlo)
WORKSPACE_SQL_DESCRIPTION = {
    "facturas": """
Consultá sobre la base de datos. Tené en cuenta los siguientes mapeos semánticos:

📌 Mapeo semántico (consultas comunes):
- Si preguntás por **facturas apócrifas**, usá la columna "Apocrifa" con valor 'Sí'.
- Si preguntás por **facturas duplicadas**, usá la columna "Duplicado" con valor 'Sí'.
- Si preguntás por **autorización del CAE**, usá la columna "autorizacion_cae" con valor 'Autorizado'.
- Si preguntás por **total de facturas**, contá las filas usando la columna "Nro. de Factura".
- Si preguntás por **importe total**, usá la columna "Total".
- Si preguntás por **fecha de emisión**, usá la columna "Fecha".
- Si preguntás por **CUIT del emisor**, usá la columna "Cuit del Emisor".
- Si preguntás por **CUIT del receptor**, usá la columna "Cuit del receptor".
- Si preguntás por **detalle del servicio**, usá la columna "Detalle".
- Si preguntás por **IVA**, usá la columna "Iva".
- Si preguntás por **Percepciones de IVA**, usá la columna "Percepciones de IVA".
- Si preguntás por **CAE**, usá la columna "CAE".
- Si preguntás por **categoría del emisor**, usá las columnas:
    - "Categoría en IVA Emisor"
    - "Categoría en IIBB Emisor"
- Si preguntás por **domicilio del emisor**, usá la columna "Domicilio Emisor".
- Si preguntás por **domicilio del receptor**, usá la columna "Domicilio Receptor".

⚠️ Siempre usá comillas dobles en nombres de columnas (por ejemplo: "Apocrifa", "Duplicado", "Total", etc.).
❌ No uses backticks (`` ` ``) ni markdown tipo ```sql en las consultas.
"""
}

def crear_agente_sql(workspace_slug: str):
    workspace_slug = workspace_slug.lower()
    nombre_tabla = f"facturas_{workspace_slug}".replace(" ", "_")

    db_url = os.getenv("DB_URL")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if not db_url or not openai_api_key:
        raise EnvironmentError("Faltan DB_URL u OPENAI_API_KEY")

    llm = ChatOpenAI(
        temperature=0,
        model=os.getenv("MODEL_NAME", "gpt-4o"),
        openai_api_key=openai_api_key
    )

    db = SQLDatabase.from_uri(db_url)

    description = f"""
Consultá sobre la tabla "{nombre_tabla}" correspondiente al workspace '{workspace_slug}'.

⚠️ Usá comillas dobles en nombres de columnas. Por ejemplo: "Duplicado", "Total", etc.
Ejemplo válido:
SELECT COUNT(*) FROM {nombre_tabla} WHERE "Duplicado" = 'Sí';
"""

    herramienta = Tool(
        name="PostgreSQL",
        func=db.run,
        description=description
    )

    agente = initialize_agent(
        tools=[herramienta],
        llm=llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
        handle_parsing_errors=True
    )

    return agente

