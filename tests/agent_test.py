from core.agent_backend import despachar_consulta

if __name__ == "__main__":
    resp = despachar_consulta(
        "¿Cuántas filas tiene la tabla sheet1?",
        "test"
    )
    print("Respuesta:", resp)
