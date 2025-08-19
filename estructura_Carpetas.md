# Estructura de carpetas y archivos del proyecto

Ruta base:  
`c:\Users\seba\Desktop\IA_DELOITTE\Prototipo_IA_Streamlit`

---

## core/
**Núcleo de la lógica de negocio y agentes.**

- **file_handler.py**  
  Manejo de archivos, rutas y operaciones de lectura/escritura.
- **graph_agent.py**  
  (Probablemente) Agente para consultas o análisis de grafos.
- **history.py**  
  Gestión del historial de conversaciones por workspace.
- **mcp_runner.py**  
  Ejecución de procesos MCP auxiliares.
- **rag_pipeline.py**  
  Pipeline RAG: vectorización y recuperación de información.
- **sql_agent.py**  
  Agente SQL (LangChain + OpenAI) con validaciones y guard-rails para consultas Postgres.
- **sql_loader.py**  
  Carga/ingesta de datos hacia SQL.
- **tools.py**  
  Herramientas utilitarias para agentes o pipelines.
- **vectorizer.py**  
  Vectorización de documentos/textos para búsquedas semánticas.
- **watchdog_manager.py**  
  Observa cambios en archivos/carpeta para recarga o actualización.
- **workspace_manager.py**  
  Orquestación de workspaces y recursos asociados.
- **__pycache__/**  
  Archivos compilados de Python.

---

## utils/
**Utilidades y helpers reutilizables.**

- **__init__.py**  
  Inicialización del módulo utils.
- **chunking.py**  
  Funciones para segmentar textos/documentos en partes manejables.
- **embeddings.py**  
  Funciones para generar embeddings vectoriales.
- **excel_analyzer.py**  
  Utilidades para analizar y leer archivos Excel.
- **helpers.py**  
  Funciones auxiliares generales.
- **tabla_parser.py**  
  Parseo de tablas desde texto o HTML.
- **voz_a_prompt.py**  
  Conversión de entrada de voz a prompts de texto.
- **__pycache__/**  
  Archivos compilados de Python.

---

## ui/
**Componentes de interfaz de usuario (Streamlit).**

- **file_uploader.py**  
  Componente para carga de documentos.
- **main_chat.py**  
  Vista principal de chat con el agente.
- **sidebar.py**  
  Barra lateral para configuración y selección de workspace.
- **__pycache__/**  
  Archivos compilados de Python.

---

## storage/
**Almacenamiento persistente por workspace.**

- **workspaces/**  
  Carpeta raíz para workspaces.
  - **base_conocimiento/**  
    - **history.json**: Historial de chat.
    - **meta.json**: Metadatos del workspace.
    - **documents/**: Archivos subidos (ej: PDFs).
    - **vectorstore/**: Índices FAISS (`index.faiss`, `index.pkl`).
  - **facturas/**  
    - **Anterior_history.json**: Historial anterior.
    - **history.json**: Historial actual.
    - **meta.json**: Metadatos.
    - **documents/**: Archivos Excel de facturas.
    - **vectorstore/**: Índices FAISS.
  - **facturas-2024/**  
    - **history.json**, **meta.json**
    - **documents/**, **knowledge/**, **threads/**: Carpetas para documentos, conocimiento y hilos de conversación.

---

## mcps/
**Módulos para generación de salidas y artefactos.**

- **__init__.py**  
  Inicialización del módulo.
- **crear_tabla_excel.py**  
  Creación de tablas y exportación a Excel.
- **generar_excel.py**  
  Generación de reportes o archivos Excel.
- **generar_word.py**  
  Generación de reportes Word.
- **resaltar_facturas.py**  
  Marcado/resaltado de facturas relevantes.
- **resumen_conversacion.py**  
  Síntesis de conversaciones.
- **resumen_factura.py**  
  Resúmenes automáticos de facturas.
- **workspace_manager.py**  
  Utilidades específicas para workspaces.
- **__pycache__/**  
  Archivos compilados de Python.

---

## Otros archivos relevantes

- **estructura_Carpetas.md**  
  Este archivo: resumen y documentación de la estructura del proyecto.
- **app.py**  
  Punto de entrada principal de la app Streamlit. Orquesta la UI y la selección de workspace.

---

## Notas generales

- **__pycache__/**:  
  Carpetas generadas automáticamente por Python para almacenar bytecode compilado.
- **Variables de entorno**:  
  - `DB_URL`: Conexión a base de datos.
  - `OPENAI_API_KEY`: API Key de OpenAI.
  - `MODEL_NAME`: Modelo de LLM a usar (por defecto "gpt-4o").
- **Dependencias clave**:  
  - `python-dotenv`, `langchain`, `langchain_openai`, `langchain_community`, `streamlit`.

---

**Esta estructura permite separar claramente la lógica de negocio, utilidades, interfaz, almacenamiento y generación de reportes, facilitando el mantenimiento y evolución del sistema.**