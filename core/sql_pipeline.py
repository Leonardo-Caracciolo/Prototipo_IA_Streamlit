import os
import sqlite3
import pandas as pd
import json
from langchain_openai import OpenAI
from langchain_community.utilities import SQLDatabase
from langchain_experimental.sql import SQLDatabaseChain
from dotenv import load_dotenv

load_dotenv()
DB_FILENAME = "base.db"

def cargar_a_sql(path_excel: str, workspace: str):
    db_path = f"storage/workspaces/{workspace}/sql/{DB_FILENAME}"
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    hojas = pd.ExcelFile(path_excel).sheet_names
    tablas, resumen = [], []
    for hoja in hojas:
        df = pd.read_excel(path_excel, sheet_name=hoja)
        nombre = hoja.replace(" ", "_").lower()
        df.to_sql(nombre, conn, index=False, if_exists="replace")
        resumen.append(f"Hoja '{hoja}' → tabla '{nombre}' ({len(df)} filas)")
        tablas.append(nombre)
    with open(f"storage/workspaces/{workspace}/workspace_metadata.json", "w", encoding="utf-8") as f:
        json.dump({"tablas_sql": tablas}, f, indent=2)
    return conn, "\n".join(resumen)

def buscar_en_sql(prompt: str, workspace: str) -> str:
    db_path = f"storage/workspaces/{workspace}/sql/{DB_FILENAME}"
    if not os.path.exists(db_path):
        return "❌ No hay base de datos SQL disponible para este workspace."

    db_uri = f"sqlite:///{db_path}"
    db = SQLDatabase.from_uri(db_uri)
    llm = OpenAI(temperature=0, verbose=False)
    chain = SQLDatabaseChain.from_llm(llm, db, verbose=False)

    try:
        respuesta = chain.run(prompt)
        return respuesta
    except Exception as e:
        return f"⚠️ Error al consultar SQL: {e}"
