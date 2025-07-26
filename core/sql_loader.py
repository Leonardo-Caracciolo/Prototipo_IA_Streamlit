import pandas as pd
from sqlalchemy import create_engine
import os

def cargar_excel_a_postgres(path_excel: str, workspace_slug: str, db_url: str):
    try:
        df = pd.read_excel(path_excel)

        # Normalizar nombre tabla
        nombre_tabla = f"facturas_{workspace_slug.lower()}".replace(" ", "_")

        engine = create_engine(db_url)

        with engine.begin() as conn:
            df.to_sql(nombre_tabla, conn, if_exists="replace", index=False)

        return f"✅ Tabla '{nombre_tabla}' cargada con éxito."
    
    except Exception as e:
        return f"❌ Error al cargar tabla: {e}"
