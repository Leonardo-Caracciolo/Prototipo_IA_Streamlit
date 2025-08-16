

import os, re, json
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_community.utilities.sql_database import SQLDatabase

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import Tool
from langchain.prompts import ChatPromptTemplate

load_dotenv()

# ───────────────────────── Dominio / Whitelist ─────────────────────────
ALLOWED_COLUMNS = [
    "Emisor_mail","Fecha_Recepcion","Archivo_Original","Tipo de documento","Letra de comprobante",
    "Nro. de Factura","Fecha","Cuit del Emisor","Categoría en IVA Emisor","Categoría en IIBB Emisor",
    "Domicilio Emisor","Cuit del receptor","Categoría en IVA Receptor","Categoría en IIBB Receptor",
    "Domicilio Receptor","Código del servicio","Detalle","Importe neto de Impuestos","Importe neto gravado",
    "IVA","iva 27","iva 21","iva 10.5","iva 5","iva 2.5","Percepciones de IVA","Percepciones de IIGG",
    "Percepciones de Ingresos Brutos","Impuestos Internos","Otros Impuestos","CAE","Fecha del Vto. del CAE",
    "Periodo Facturado","Total","Total control","Duplicado","Apocrifas","Mis comprobantes",
    "Cuit Receptor Correcto","autorizacion_cae"
]

WORKSPACE_SQL_DESCRIPTION = {
    "facturas": """
Consultá sobre la base de datos. Tené en cuenta los siguientes mapeos semánticos:

📌 Mapeo semántico (consultas comunes):
- Si preguntás por **facturas apócrifas**, usá la columna "Apocrifas" = 'Si'.
- Si preguntás por **facturas duplicadas**, usá "Duplicado" = 'Si'.
- Si preguntás por **autorización del CAE**, usá autorizacion_cae = 'Autorizado'.
- Si preguntás por **CAE incorrecto** por inexistente, usá autorizacion_cae = 'CAE no encontrado'.
- Si preguntás por **CAE incorrecto** por fecha, usá autorizacion_cae = 'Fecha no coincide'.
- Si preguntás por **total de facturas**, usá COUNT(*) sobre la tabla.
- Si preguntás por **importe total**, usá "Total".
- Si preguntás por **fecha de emisión**, usá "Fecha".
- Si preguntás por **CUIT del emisor**, usá "Cuit del Emisor".
- Si preguntás por **CUIT del receptor**, usá "Cuit del receptor".
- Si preguntás por **detalle del servicio**, usá "Detalle".
- Si preguntás por **IVA**, usá "IVA".
- Si preguntás por **Percepciones de IVA**, usá "Percepciones de IVA".
- Si preguntás por **CAE**, usá "CAE".
- Si preguntás por **categoría del emisor**, usá "Categoría en IVA Emisor" y "Categoría en IIBB Emisor".
- Si preguntás por **domicilio del emisor**, usá "Domicilio Emisor".
- Si preguntás por **domicilio del receptor**, usá "Domicilio Receptor".

⚠️ SIEMPRE comillas dobles en nombres de columnas (por ejemplo: "Apocrifas", "Duplicado", "Total").
⚠️ Usá SIEMPRE la tabla FQN con alias: FROM public."facturas_facturas" AS f
❌ No uses backticks ni markdown en las consultas.
"""
}

# ───────────────────────── Helpers de validación ─────────────────────────
FORBIDDEN = re.compile(
    r"(;)|\b(insert|update|delete|drop|alter|create|grant|revoke|truncate|commit|rollback|union)\b",
    re.IGNORECASE
)


def ensure_limit(sql: str) -> str:
    # Evitar LIMIT para agregados; añadir LIMIT 100 en resto de casos
    # Buscar funciones de agregación: COUNT/SUM/AVG/MIN/MAX seguidas de '('
    if re.search(r'\b(count|sum|avg|min|max)\s*\(', sql, re.IGNORECASE):
        return sql.strip().rstrip(';')
    return (sql.strip().rstrip(';')) + " LIMIT 100"

def only_one_table(sql: str) -> bool:
    # Fuerza FROM public."facturas_facturas" AS f
    return bool(re.search(r'from\s+public\."facturas_facturas"\s+as\s+f\b', sql, re.IGNORECASE))

def only_allowed_columns(sql: str) -> bool:
    # Busca referencias f."Columna" y f.autorizacion_cae
    quoted = set(re.findall(r'f\."([^"]+)"', sql))
    dotted = set(re.findall(r'f\.([a-z_][a-z0-9_]*)', sql))
    used = quoted | dotted
    # Permitir que no haya columnas (ej. COUNT(*))
    if not used:
        return True
    return all(u in ALLOWED_COLUMNS for u in used)

def validate_sql(sql: str) -> tuple[bool, str]:
    if FORBIDDEN.search(sql):
        return False, "Solo SELECT (sin DML/DDL/UNION ni múltiples statements)."
    if not re.match(r'^\s*select\b', sql.strip(), re.IGNORECASE):
        return False, "La consulta debe comenzar con SELECT."
    if not only_one_table(sql):
        return False, 'Debés consultar exclusivamente FROM public."facturas_facturas" AS f'
    if not only_allowed_columns(sql):
        return False, "Usá únicamente columnas whitelisted y el prefijo f."
    return True, "OK"

# ───────────────────────── Agente ─────────────────────────
def crear_agente_sql(workspace_slug: str) -> AgentExecutor:
    workspace_slug = workspace_slug.lower()
    nombre_tabla = f'public."facturas_{workspace_slug}"'  # p.ej. public."facturas_facturas"
    # A efectos de ejecución, instruimos al LLM a usar SIEMPRE public."facturas_facturas" AS f
    nombre_tabla_fqn_alias = 'public."facturas_facturas" AS f'

    db_url = os.getenv("DB_URL")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    model_name = os.getenv("MODEL_NAME", "gpt-4o")

    if not db_url or not openai_api_key:
        raise EnvironmentError("Faltan DB_URL u OPENAI_API_KEY")

    llm = ChatOpenAI(
        temperature=0,
        model=model_name,
        openai_api_key=openai_api_key
    )

    # Limita metadata visible, pero OJO: esto no evita que el LLM intente otra cosa.
    db = SQLDatabase.from_uri(db_url, include_tables=[f'facturas_{workspace_slug}'])

    workspace_description = WORKSPACE_SQL_DESCRIPTION.get("facturas", "")

    tool_description = f"""
Consultá sobre la tabla {nombre_tabla_fqn_alias}.

{workspace_description}

Reglas estrictas del SQL que debés generar:
- Usá SIEMPRE {nombre_tabla_fqn_alias}
- Prefijo de columnas: f."Columna" (o f.autorizacion_cae).
- Evitá SELECT *; pedí sólo lo necesario.
- Para conteos/sumas/promedios, usá agregaciones (COUNT/SUM/AVG).
- Para listados, devolvé <= 100 filas (habrá un LIMIT automático si omitís LIMIT).
Ejemplos válidos:
  SELECT COUNT(*) FROM {nombre_tabla_fqn_alias} WHERE f."Duplicado" = 'Si';
  SELECT f."Fecha", f."Total" FROM {nombre_tabla_fqn_alias} WHERE f."Apocrifas" = 'Si' ORDER BY f."Fecha" DESC LIMIT 100;
"""

    def run_sql(query: str) -> str:
        # Guard-rails y LIMIT
        sql = ensure_limit(query)
        ok, msg = validate_sql(sql)
        if not ok:
            # Devolvemos mensaje claro para que el propio agente se auto-corrija
            return f'[SQL inválido] {msg}\\nSQL recibido:\\n{sql}'
        try:
            return db.run(sql)
        except Exception as e:
            # Capturamos y devolvemos el error de forma controlada para que el agente se auto-corrija
            return f"[Error al ejecutar SQL] {e}\nSQL enviado:\n{sql}"

    herramienta = Tool(
        name="PostgreSQL",
        func=run_sql,
        description=tool_description,
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "Sos un analista SQL para Postgres. Cuando necesites datos, usá la herramienta PostgreSQL. "
         "Generá SIEMPRE consultas válidas para Postgres con FROM public.\"facturas_facturas\" AS f y columnas con prefijo f. "
         "Devolvé respuestas claras y, si corresponde, un breve resumen numérico. Nunca imprimas pensamientos internos."),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}")
    ])

    agent = create_tool_calling_agent(llm, [herramienta], prompt)

    executor = AgentExecutor(
        agent=agent,
        tools=[herramienta],
        verbose=False,
        handle_parsing_errors=False,
        max_iterations=6
    )

    return executor
