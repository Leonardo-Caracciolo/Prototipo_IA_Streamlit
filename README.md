# 🧠 AI KnowledgeHub

**AI KnowledgeHub** es una plataforma inteligente para contadores, analistas y profesionales que permite subir archivos (Excel, PDF, Word) y realizar consultas complejas directamente sobre su contenido utilizando el modelo **GPT-4o** de OpenAI. Es modular, escalable y lista para integrarse con agentes inteligentes, RAG y plugins personalizados.

---

## ✨ Características principales

- 📁 Múltiples **Workspaces** independientes
- 🧾 Soporte para **Excel (.xls, .xlsx, .xlsm), PDF y Word (.docx)**
- 💬 Interfaz tipo ChatGPT (con historial persistente por workspace)
- 🔊 Entrada por voz con reconocimiento automático
- 📤 Subida de archivos manual desde la interfaz o directamente en carpetas
- 🧠 Vectorización automática con LangChain y FAISS
- 🤖 Comandos MCP (generación automática de Word o Excel desde el prompt)
- 🔌 Preparado para migrar fácilmente a `pgvector` y `PostgreSQL`
- 📦 Arquitectura fácilmente integrable a `FastAPI` o `Django`

---

## 📂 Estructura del proyecto

```
AI_KnowledgeHub/
├── app.py                         # Punto de entrada principal (Streamlit)
├── .env                           # Claves API y configuración
├── requirements.txt               # Dependencias necesarias

├── core/                          # Núcleo del sistema
│   ├── workspace_manager.py           # Crear/eliminar workspaces
│   ├── file_handler.py                # Guardado de archivos y monitoreo
│   ├── vectorizer.py                  # Procesamiento y vectorización (FAISS/pgvector)
│   ├── rag_pipeline.py                # Función buscar_en_documentos() para RAG
│   ├── sql_pipeline.py                # Función buscar_en_sql() + carga Excel a SQL
│   ├── history.py                     # Historial por workspace
│   ├── mcp_runner.py                  # Ejecuta MCP desde prompts
│   ├── agente_backend.py              # Orquestador principal de agentes  ✅ NUEVO
│   ├── saludo_agente.py               # Agente intermedio para saludo y filtro       ✅ NUEVO
│   └── agente.py                      # Factories o abstracciones de agentes         ✅ NUEVO

├── ui/                           # Interfaz de usuario (Streamlit)
│   ├── sidebar.py                   # Lateral izquierdo con selección de workspaces
│   ├── file_uploader.py             # Subida de archivos con monitoreo
│   └── main_chat.py                 # Lógica del chat principal

├── utils/                        # Funciones auxiliares
│   ├── excel_analyzer.py            # Resumen y contexto inicial de Excel
│   ├── voz_a_prompt.py              # Conversión de voz a texto
│   └── sql_connector.py             # Conexión SQL por workspace (SQLite o Postgre)

├── agents/                      # Agentes específicos
│   ├── agente_sql_excel.py          # Agente SQL para archivos Excel
│   ├── agente_postgre_pgvector.py   # Agente RAG para pgvector / PostgreSQL
│   └── saludo_agente.py             # Repetido para compatibilidad directa

├── langgraph_flows/             # Flujos LangGraph
│   ├── base_sql.graph.py            # Flujo para SQL
│   └── base_rag.graph.py            # Flujo para documentos largos RAG

├── mcps/                         # Plugins dinámicos (desde prompt)
│   ├── generar_word.py              # Crear Word desde texto
│   ├── generar_excel.py             # Crear Excel desde tabla
│   └── resumen_excel.py             # Genera resumen automático del Excel

└── storage/                     # Datos persistentes
    └── workspaces/
        └── <workspace_name>/
            ├── documents/              # Archivos subidos
            ├── vectorstore/            # FAISS o pgvector
            ├── sql/                    # Base SQLite del workspace
            ├── output/                 # Archivos Word/Excel generados
            ├── history.json            # Historial del chat
            └── threads/                # Conversaciones separadas por hilo (opcional)

```

---

## 🧠 Funcionalidades de IA

- **Chat contextual** con vista previa automática si hay archivos Excel
- **Respuestas sobre Word y PDF** mediante embeddings vectorizados
- **Entrada por voz** y envío automático al detectar silencio
- **Generación automática de archivos Word o Excel** desde un prompt

---

## 🚀 Preparado para crecer

El sistema puede escalar fácilmente a:

- `PostgreSQL + pgvector` para mayor rendimiento
- `Django`, `FastAPI` o `Flask` para backend robusto
- Agentes LLM con `LangGraph`, `LangChain Agents`, o `AnythingLLM`
- RAG avanzado, chunking dinámico, embedding personalizado

---