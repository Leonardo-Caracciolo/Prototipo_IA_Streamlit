import re

def extraer_tabla_desde_respuesta(texto):
    """
    Detecta y convierte una tabla Markdown, tabulada o separada por múltiples espacios.
    """
    lineas = texto.splitlines()
    tabla = []

    for linea in lineas:
        if "\t" in linea:
            fila = linea.split("\t")
        elif "  " in linea:
            fila = [col.strip() for col in re.split(r"\s{2,}", linea)]
        else:
            continue

        if len(fila) >= 2:
            tabla.append(fila)

    return tabla if len(tabla) >= 2 else None
