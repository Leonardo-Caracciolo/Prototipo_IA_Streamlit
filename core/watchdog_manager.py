from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from core.vectorizer import cargar_documentos, aplicar_chunking, crear_vectorstore
from core.sql_loader import cargar_excel_a_postgres
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Configuración: qué acción aplicar a cada workspace
WORKSPACES_ACTIVOS = {
    "base_conocimiento": "vector",
    "facturas": "sql"
}

class WorkspaceHandler(FileSystemEventHandler):
    def __init__(self, workspace, tipo):
        self.workspace = workspace
        self.tipo = tipo

    def log(self, msg):
        now = datetime.now().strftime("%H:%M:%S")
        print(f"[{now}] [{self.workspace.upper()}] {msg}")

    def on_created(self, event):
        if not event.is_directory:
            self.procesar_archivo(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self.procesar_archivo(event.src_path)

    def procesar_archivo(self, path):
        ext = os.path.splitext(path)[1].lower()

        if self.tipo == "vector" and ext in [".pdf", ".docx"]:
            self.log(f"📄 Archivo detectado: {os.path.basename(path)} (vectorizando...)")
            documentos = cargar_documentos(self.workspace)
            chunks = aplicar_chunking(documentos)
            crear_vectorstore(self.workspace, chunks)
            self.log("✅ Vectorstore actualizado.")

        # elif self.tipo == "sql" and ext in [".xls", ".xlsx", ".xlsm"]:
        #     self.log(f"📊 Excel detectado: {os.path.basename(path)} (cargando a PostgreSQL...)")
        #     try:
        #         resultado = cargar_excel_a_postgres(path, self.workspace, os.getenv("DB_URL"))
        #         self.log(resultado)
        #     except Exception as e:
        #         self.log(f"❌ Error SQL: {e}")

def activar_watchdog_para_workspace(workspace):
    tipo = WORKSPACES_ACTIVOS.get(workspace)
    if not tipo:
        print(f"⚠️ Workspace '{workspace}' no está habilitado para automatización.")
        return None

    path = os.path.join("storage", "workspaces", workspace, "documents")
    os.makedirs(path, exist_ok=True)

    observer = Observer()
    observer.schedule(WorkspaceHandler(workspace, tipo), path=path, recursive=False)
    observer.start()
    print(f"👀 Iniciando monitoreo en: {path} (modo: {tipo})")
    return observer
