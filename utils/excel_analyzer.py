import pandas as pd

def cargar_excel(path, max_filas=100):
    df = pd.read_excel(path)
    total_filas = len(df)
    columnas = df.columns.tolist()

    # Tomamos solo las primeras filas si es muy largo
    preview = df.head(max_filas).to_markdown(index=False)

    contexto = f"""
Este archivo contiene {total_filas} filas y las siguientes columnas:
{', '.join(columnas)}

Primeras {min(max_filas, total_filas)} filas:

{preview}
"""

    return contexto, df