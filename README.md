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
├── app.py                  # Punto de entrada principal (Streamlit)
├── .env                    # Claves API (OPENAI_API_KEY, MODEL_NAME)
├── requirements.txt        # Librerías necesarias

├── core/
│   ├── workspace_manager.py    # Crear/eliminar workspaces
│   ├── file_handler.py         # Guardado de archivos por workspace
│   ├── vectorizer.py           # Procesamiento y embeddings
│   ├── rag_pipeline.py         # Consulta a vectores (QA)
│   ├── history.py              # Manejo de historial JSON
│   ├── mcp_runner.py           # Ejecución de MCPs desde prompts

├── ui/
│   ├── sidebar.py              # Navegación lateral y creación de workspaces
│   ├── file_uploader.py        # Módulo de subida de archivos
│   ├── main_chat.py            # Lógica de chat, GPT-4o, procesamiento
│
├── utils/
│   ├── excel_analyzer.py       # Carga, resumen y contexto para archivos Excel
│   ├── voz_a_prompt.py         # Reconocimiento de voz a texto

├── mcps/                   # Plugins dinámicos ejecutables desde el prompt
│   ├── generar_word.py         # Genera Word desde texto
│   ├── generar_excel.py        # Genera Excel desde tabla (formato lista)

└── storage/
    └── workspaces/
        └── <nombre_workspace>/
            ├── documents/          # Archivos cargados (PDF, Word, Excel)
            ├── vectorstore/        # Embeddings persistentes
            ├── history.json        # Historial de chat por workspace
            ├── threads/            # (Opcional) Subconversaciones
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

## 📌 Autor

Desarrollado por **Leonardo** con enfoque profesional, extensible y robusto para automatización contable, análisis documental e inteligencia aumentada.