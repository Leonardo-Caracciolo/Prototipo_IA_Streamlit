# 🧠 AI KnowledgeHub

**AI KnowledgeHub** es una plataforma inteligente para contadores y analistas que permite subir archivos Excel o PDF y hacer preguntas directamente sobre su contenido utilizando el modelo GPT-4o de OpenAI. El sistema es escalable, modular y puede extenderse fácilmente a otros formatos o flujos de trabajo empresariales.

---

## ✨ Características principales

- 📁 Múltiples workspaces independientes
- 📤 Subida de archivos Excel y PDF
- 🧠 Análisis automático con GPT-4o (sin necesidad de funciones personalizadas)
- 💬 Chat tipo ChatGPT con historial persistente
- 📦 Vectorización automática (FAISS)
- 🧩 Estructura lista para migrar a pgvector y PostgreSQL

---

## 📂 Estructura del proyecto

```
AI_KnowledgeHub/
├── app.py                  # Punto de entrada principal (Streamlit)
├── .env                    # Claves API (OPENAI_API_KEY, MODEL_NAME)
├── requirements.txt        # Librerías necesarias
├── excel_analyzer.py       # Analizador de Excel para GPT-4o
│
├── core/
│   ├── workspace_manager.py    # Crear/eliminar workspaces
│   ├── file_handler.py         # Guardar archivos por workspace
│   ├── vectorizer.py           # Chunking, embedding, vectorstore
│   ├── rag_pipeline.py         # Consulta a base vectorial con LangChain
│   ├── mcp_runner.py           # Ejecución de scripts dinámicos (opcional)
│   ├── history.py              # Carga y guardado del historial por workspace
│
├── ui/
│   ├── sidebar.py              # Barra lateral con botón y lista de workspaces
│   ├── file_uploader.py        # Interfaz para subir archivos
│   ├── main_chat.py            # Chat principal con análisis y GPT-4o
│
├── mcps/                   # Plugins de Python ejecutables desde prompts
│   ├── resumen_factura.py
│   ├── crear_tabla_excel.py
│
└── storage/
    └── workspaces/         # Estructura de carpetas por workspace
        └── <nombre>/
            ├── documents/
            ├── knowledge/
            ├── threads/
            ├── history.json
            └── vectorstore/
```

---

## 🔮 Tecnologías utilizadas

- `Python`, `Streamlit`, `LangChain`, `OpenAI`, `pandas`, `FAISS`, `dotenv`
- Pensado para extender a: `pgvector`, `PostgreSQL`, `FastAPI`, `Django`, `RAG`, etc.

---

## 📌 Autor

Desarrollado por **Leonardo** con enfoque profesional y escalable para entornos contables y empresariales.