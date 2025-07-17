import os
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.pgvector import PGVector
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
from utils.sql_connector import conectar_sqlite

EMBEDDING_MODEL = OpenAIEmbeddings()

# === FUNCIONES PARA VECTORIAL ===
def cargar_vectorstore_faiss(workspace):
    path = f"storage/workspaces/{workspace}/vectorstore"
    if not os.path.exists(path):
        return None
    return FAISS.load_local(path, EMBEDDING_MODEL)

def cargar_vectorstore_pgvector():
    return PGVector(embedding_function=EMBEDDING_MODEL, collection_name="vectores_normativa")

def buscar_en_documentos(prompt: str, workspace: str) -> str:
    vectordb = cargar_vectorstore_faiss(workspace)
    if not vectordb:
        return "No hay base vectorial disponible para este workspace."

    resultados = vectordb.similarity_search(prompt, k=3)
    contexto = "\n---\n".join([doc.page_content for doc in resultados])

    return f"Respuesta basada en documentos:{contexto}"


# === FUNCIONES PARA SQL ===
def buscar_en_sql(prompt: str, workspace: str) -> str:
    conn, cursor = conectar_sqlite(workspace)
    if not cursor:
        return "No se pudo conectar a la base SQL del workspace."

    # Traducción de pregunta a SQL (podés extender esto con LangChain Agents o funciones)
    if "total de facturas" in prompt.lower():
        cursor.execute("SELECT COUNT(*) FROM datos")
        total = cursor.fetchone()[0]
        return f"El total de facturas es: {total}"

    if "total neto" in prompt.lower():
        cursor.execute("SELECT SUM([Importe neto de Impuestos]) FROM datos")
        total = cursor.fetchone()[0]
        return f"El total neto es: ${total:,.2f}"

    return "No pude interpretar esa consulta SQL. Probá reformularla."
