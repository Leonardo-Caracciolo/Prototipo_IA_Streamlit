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
- 📊 Carga automática de Excel a PostgreSQL (por workspace)
- 🤖 Comandos MCP (generación automática de Word o Excel desde el prompt)
- 👀 Monitoreo con `watchdog` para workspaces específicos
- 🔌 Preparado para migrar fácilmente a `pgvector` y `PostgreSQL`
- 📦 Arquitectura integrable a `FastAPI`, `Django`, `LangGraph`, etc.

---

## 📂 Estructura del proyecto

\`\`\`
AI_KnowledgeHub/
├── app.py                       # Punto de entrada principal (Streamlit)
├── monitor.py                   # Monitor que observa cambios en carpetas
├── .env                         # Claves API y DB (OPENAI_API_KEY, DB_URL, MODEL_NAME)
├── requirements.txt             # Librerías necesarias

├── core/
│   ├── workspace_manager.py     # Crear/eliminar workspaces
│   ├── file_handler.py          # Guardado de archivos por workspace
│   ├── vectorizer.py            # Procesamiento y embeddings FAISS
│   ├── rag_pipeline.py          # Consulta a vectores (QA con LangChain)
│   ├── sql_loader.py            # Carga de Excel → PostgreSQL automáticamente
│   ├── sql_agent.py             # Agente LLM para interactuar con SQL
│   ├── watchdog_manager.py      # Monitor de cambios por workspace
│   ├── history.py               # Manejo de historial JSON
│   ├── mcp_runner.py            # Ejecución de MCPs desde prompts

├── ui/
│   ├── sidebar.py               # Navegación lateral y creación de workspaces
│   ├── file_uploader.py         # Módulo de subida de archivos
│   ├── main_chat.py             # Lógica principal del chat

├── utils/
│   ├── excel_analyzer.py        # Carga, resumen y contexto para archivos Excel
│   ├── voz_a_prompt.py          # Reconocimiento de voz a texto

├── mcps/                        # Plugins dinámicos ejecutables desde el prompt
│   ├── generar_word.py
│   ├── generar_excel.py

└── storage/
    └── workspaces/
        └── <nombre_workspace>/
            ├── documents/          # Archivos cargados (PDF, Word, Excel)
            ├── vectorstore/        # Embeddings persistentes
            ├── history.json        # Historial de chat por workspace
            ├── threads/            # (Opcional) Subconversaciones
\`\`\`

---

## 🧠 Funcionalidades de IA

- **Chat contextual** sobre Excel, Word y PDF
- **Respuestas inteligentes** basadas en contenido vectorizado o SQL
- **Reconocimiento de voz** y conversión automática a consulta
- **Agente SQL** exclusivo por workspace (ej: `facturas`)
- **Generación de Word/Excel** directamente desde los prompts

---

## 🚀 Automatización inteligente

### 🛰 Monitoreo automático de carpetas (`monitor.py`)

AI KnowledgeHub incluye un **monitor de archivos** (`watchdog`) que detecta cambios en carpetas y ejecuta acciones automáticas:

| Workspace           | Acción automática                            |
|---------------------|-----------------------------------------------|
| `base_conocimiento` | Vectoriza nuevos PDFs                        |
| `facturas`          | Carga automáticamente Excels a PostgreSQL    |

> El monitoreo es modular. Podés agregar más workspaces fácilmente.

---

## ▶️ Cómo ejecutar la plataforma

### 1. Instalar dependencias

\`\`\`bash
pip install -r requirements.txt
\`\`\`

> Asegurate también de tener `psycopg2-binary` si usás PostgreSQL.

---

### 2. Configurar `.env`

\`\`\`
OPENAI_API_KEY=tu_clave_openai
MODEL_NAME=gpt-4o
DB_URL=postgresql+psycopg2://usuario:clave@localhost:5432/nombre_db
\`\`\`

---

### 3. Ejecutar la app principal

\`\`\`bash
streamlit run app.py
\`\`\`

---

### 4. En otra terminal, ejecutar el monitor

\`\`\`bash
python monitor.py
\`\`\`

> 🔁 Este script observará las carpetas de los workspaces activos. Cuando detecte un archivo nuevo, actualizará automáticamente el vectorstore o cargará el Excel a SQL.

---

## 🔧 Escalable a futuro

AI KnowledgeHub está diseñado para integrarse fácilmente con:

- Agentes LLM (`LangChain Agents`, `AnythingLLM`, `LangGraph`)
- RAG avanzado con pgvector + PostgreSQL
- Backend robusto (`FastAPI`, `Django`, `Flask`)
- API REST, interfaces móviles, frontend React, dashboards, etc.

---

## 📌 Autor

Desarrollado por **Leonardo** con enfoque profesional, extensible y robusto para automatización contable, análisis documental e inteligencia aumentada.
