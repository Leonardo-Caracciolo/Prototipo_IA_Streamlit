# 🧩 MCPs en AI KnowledgeHub

**MCP (Modular Command Plugin)** es un plugin Python que puede ejecutarse desde un prompt escrito por el usuario, permitiendo extender el sistema con nuevas funcionalidades como:

- Generar archivos Excel o Word automáticamente
- Consultar bases de datos
- Ejecutar resúmenes
- Realizar cálculos avanzados

---

## 📁 ¿Dónde van los MCPs?

Todos los MCPs deben colocarse en la carpeta:

```
AI_KnowledgeHub/mcps/
```

Ejemplo:
```
mcps/
├── generar_excel.py
├── generar_word.py
├── resaltar_facturas.py
├── resumen_conversacion.py
```

---

## 🧠 ¿Cómo se llama un MCP?

Desde código, todos los MCPs se ejecutan con:

```python
from core.mcp_runner import ejecutar_mcp

resultado = ejecutar_mcp("nombre_del_mcp", **kwargs)
```

Donde `nombre_del_mcp` es el nombre del archivo sin `.py`.

---

## ✍️ ¿Cómo se activa un MCP desde un prompt?

El sistema analiza los mensajes y activa automáticamente MCPs si detecta ciertos patrones.

### ✅ Ejemplo 1: `generar_excel.py`

Prompt:
```
Generá un Excel con los resultados
```

El código detecta que la respuesta es una tabla y ejecuta:

```python
ejecutar_mcp("generar_excel", nombre_archivo="reporte_tabla", tabla=tabla, workspace=workspace)
```

---

### ✅ Ejemplo 2: `resumen_conversacion.py`

Prompt:
```
Generá un resumen general en Word
```

Detecta "generá un word" y "resumen", y ejecuta:

```python
ejecutar_mcp("resumen_conversacion", workspace=workspace, historial=st.session_state.chat_history)
```

---

### ✅ Ejemplo 3: `resaltar_facturas.py`

Prompt:
```
Resaltá las facturas duplicadas
Resaltá en Excel las apócrifas
```

Activa:

```python
ejecutar_mcp("resaltar_facturas", workspace=workspace)
```

---

## 🛠 Cómo crear un nuevo MCP

1. Creá un archivo `.py` dentro de `/mcps`
2. Debe contener una función pública `run(...)`
3. Todos los argumentos deben pasarse por `**kwargs`

### Ejemplo:

```python
# mcps/crear_csv.py
def run(workspace, datos):
    # generar un CSV con pandas, guardar en /output/, y retornar la ruta
    return "/ruta/final.csv"
```

Y luego se puede llamar así:

```python
ejecutar_mcp("crear_csv", workspace="acme", datos=mi_lista)
```

---

## 📦 ¿Dónde se guardan los archivos generados?

Todos los MCPs deben guardar sus resultados en:

```
storage/workspaces/<nombre>/output/
```

Para mantener orden modular por workspace.

---

## ✅ Consejos para que los MCPs se activen desde prompts

- Usá palabras clave como `generá`, `resaltá`, `resumen`, `word`, `excel`
- Si es un prompt complejo, dividilo en partes con lógica clara
- Asegurate de que `main_chat.py` tenga las condiciones para detectar tus comandos

---

¿Querés agregar un nuevo tipo de MCP (por ejemplo, envío de mail, generación de gráficos, análisis financiero)? Solo tenés que crear el `.py` con la función `run()` y usar `ejecutar_mcp`.

