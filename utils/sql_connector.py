# utils/sql_connector.py

import os
import sqlite3

def conectar_sqlite(workspace: str):
    """
    Conecta a la base SQLite del workspace dado. Devuelve conexión y cursor.
    """
    db_path = f"storage/workspaces/{workspace}/sql/base.db"
    if not os.path.exists(db_path):
        return None, None

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        return conn, cursor
    except Exception as e:
        print(f"[SQL CONNECTOR] Error al conectar con {db_path}: {e}")
        return None, None
