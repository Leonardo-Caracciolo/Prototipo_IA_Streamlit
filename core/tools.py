# NUEVA VERSIÓN DE: core/tools.py

from langchain_core.tools import tool
from langchain_core.tools import tool
from core.sql_agent import crear_agente_sql
from core.vectorizer import cargar_vectorstore
from utils.excel_analyzer import cargar_excel
from core.mcp_runner import ejecutar_mcp
import os
import psycopg2 # O la librería de DB que uses
import os
import json

# --- Función Auxiliar para la Base de Datos ---
def _ejecutar_consulta_segura(query: str, params: tuple = None) -> str:
    """Función interna para conectar y ejecutar una consulta SQL de forma segura."""
    try:
        # Es una buena práctica obtener la URL de la DB aquí
        # db_url = os.getenv("DB_URL")
        print(f"query: {query}\nparams: {params}")
        # db_url = 'postgresql+psycopg2://postgres:132576@localhost:5432/conocimiento_ia'
        db_name = "conocimiento_ia"
        db_user = "postgres"
        db_pass = "132576"
        db_host = "localhost"
        db_port = "5432"

        # 2. ✅ CONSTRUIR LA CADENA DSN CORRECTA PARA PSYCOPG2
        dsn = f"dbname='{db_name}' user='{db_user}' password='{db_pass}' host='{db_host}' port='{db_port}'"
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        cur.execute(query, params or ())
        resultado = cur.fetchall()
        cur.close()
        conn.close()
        # Formateamos el resultado para que el LLM lo entienda bien
        return json.dumps(resultado) if resultado else "No se encontraron resultados."
    except Exception as e:
        return f"Error al ejecutar la consulta: {e}"

# --- Herramientas Específicas ---

@tool
def obtener_total_facturas_apocrifas(workspace: str) -> str:
    """
    Útil para obtener la cantidad total de facturas marcadas como apócrifas.
    No recibe parámetros. Devuelve un número.
    Úsalo cuando pregunten 'cuántas facturas apócrifas hay' o similar.
    """
    # El nombre de la tabla puede depender del workspace
    tabla_nombre = f'facturas_{workspace.lower()}'
    sql_query = f'SELECT COUNT(*) FROM public."{tabla_nombre}" WHERE "Apocrifas" = \'Si\';'
    return _ejecutar_consulta_segura(sql_query)

@tool
def listar_facturas_por_cuit_emisor(cuit_emisor: str, workspace: str) -> str:
    """
    Busca y devuelve las últimas 5 facturas emitidas por un CUIT específico.
    Necesita el CUIT del emisor como parámetro.
    Úsalo cuando pregunten 'dame las facturas de tal CUIT' o 'buscá facturas del CUIT X'.
    """
    tabla_nombre = f'facturas_{workspace.lower()}'
    sql_query = f"""
        SELECT "Fecha", "Nro. de Factura", "Total" 
        FROM public."{tabla_nombre}" 
        WHERE "Cuit del Emisor" = %s 
        ORDER BY "Fecha" DESC 
        LIMIT 5;
    """
    return _ejecutar_consulta_segura(sql_query, (cuit_emisor,))

@tool
def listar_facturas_por_email_emisor(email: str, workspace: str) -> str:
    """
    Busca y devuelve las facturas emitidas por un email específico.
    Necesita el email del emisor como parámetro.
    Úsalo cuando pregunten 'dame las facturas de tal email' o 'buscá facturas del email X'.
    """
    tabla_nombre = f'facturas_{workspace.lower()}'
    sql_query = f"""
        SELECT *
        FROM public."{tabla_nombre}" 
        WHERE "Emisor_mail" = %s 
        ORDER BY "Fecha" DESC;
    """
    print("Se ejecuto ✅listar_facturas_por_email_emisor✅")
    return _ejecutar_consulta_segura(sql_query, (email,))

# Herramienta 2: Búsqueda en documentos (RAG)
@tool
def buscar_en_documentos_de_conocimiento(consulta: str, workspace: str) -> str:
    """
    Útil para responder preguntas generales basadas en los documentos PDF y DOCX
    cargados (leyes, normativas, teoría contable). Úsalo cuando la pregunta no
    sea sobre datos específicos de facturas en la base de datos.
    """
    vectordb = cargar_vectorstore(workspace)
    if not vectordb:
        return "La base de conocimiento vectorial no está disponible."
    
    docs = vectordb.similarity_search(consulta, k=4)
    if not docs:
        return "No se encontraron documentos relevantes."
        
    contexto = "\n\n".join([doc.page_content for doc in docs])
    return f"Contexto encontrado:\n{contexto}"

# Herramienta 3: Generar un documento Word
@tool
def generar_documento_word(nombre_archivo: str, contenido: str, workspace: str) -> str:
    """
    Genera un archivo .docx con el contenido proporcionado. Úsalo cuando el usuario
    pida explícitamente 'generá un word' o un reporte escrito.
    """
    try:
        ruta_archivo = ejecutar_mcp("generar_word", nombre_archivo=nombre_archivo, contenido=contenido, workspace=workspace)
        return f"Documento Word '{nombre_archivo}.docx' generado exitosamente. La ruta es: {ruta_archivo}"
    except Exception as e:
        return f"Error al generar el documento Word: {e}"

# Herramienta 4: Generar un reporte en Excel a partir de datos
@tool
def generar_reporte_excel(nombre_archivo: str, tabla_json: str, workspace: str) -> str:
    """
    Genera un archivo .xlsx a partir de una tabla de datos. La entrada 'tabla_json'
    debe ser un string JSON que represente una lista de listas o una lista de diccionarios.
    Úsalo cuando el usuario pida 'generá un excel' y los datos ya se hayan calculado.
    """
    import json
    try:
        # El LLM es mejor generando JSON que listas de Python como strings
        tabla = json.loads(tabla_json)
        ruta_archivo = ejecutar_mcp("generar_excel", nombre_archivo=nombre_archivo, tabla=tabla, workspace=workspace)
        return f"Reporte Excel '{nombre_archivo}.xlsx' generado. La ruta es: {ruta_archivo}"
    except Exception as e:
        return f"Error al generar el reporte Excel: {e}. Asegúrate de que la entrada sea un JSON válido."

# Agrupamos todas las herramientas en una lista
lista_de_herramientas = [
    obtener_total_facturas_apocrifas,
    listar_facturas_por_email_emisor,
    buscar_en_documentos_de_conocimiento,
    generar_documento_word,
    generar_reporte_excel,
]