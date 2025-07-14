import importlib.util
import os

def ejecutar_mcp(nombre, **kwargs):
    mcp_path = f"mcps/{nombre}.py"
    if not os.path.exists(mcp_path):
        return f"⚠️ El MCP '{nombre}' no existe."

    spec = importlib.util.spec_from_file_location("modulo", mcp_path)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)

    if hasattr(modulo, "run"):
        return modulo.run(**kwargs)
    return "⚠️ El MCP no tiene una función 'run'."
