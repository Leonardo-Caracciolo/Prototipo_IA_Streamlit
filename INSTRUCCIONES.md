# 🚀 Instrucciones para correr el proyecto AI KnowledgeHub

---

## ✅ Requisitos

- Python 3.10+
- Cuenta de OpenAI con clave de API
- pip + entorno virtual recomendado (`.venv`)

---

## 📦 1. Clonar el proyecto

```bash
git clone <repo-url>
cd AI_KnowledgeHub
```

---

## 🧪 2. Crear y activar entorno virtual

```bash
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate         # Windows
```

---

## 📥 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

---

## 🔐 4. Crear archivo `.env`

```env
OPENAI_API_KEY=tu_api_key_de_openai
MODEL_NAME=gpt-4o
```

---

## 🧠 5. Ejecutar la aplicación

```bash
streamlit run app.py
```

---

## 📁 6. Usar el sistema

1. En la barra lateral, hacé clic en **"➕ New Workspace"**.
2. Asignale un nombre y seleccioná el workspace.
3. Subí archivos Excel (`.xls`, `.xlsx`, `.xlsm`).
4. Procesalos con el botón **"🔄 Procesar archivos y crear base vectorial"**.
5. Hacé preguntas como:
   - “¿Qué cliente tiene más facturas?”
   - “¿Cuál es el total de IVA discriminado?”
   - “¿Cuántos comprobantes tienen alícuota del 10.5%?”

El historial se guarda automáticamente por workspace en `history.json`.

---

## ✅ ¡Listo para usar!

Tu entorno contable inteligente está listo para responder cualquier consulta con GPT-4o y el archivo que subas.