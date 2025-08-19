# vectorizer.py - Inicio

import os
from langchain_community.document_loaders import PyPDFLoader, UnstructuredWordDocumentLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from dotenv import load_dotenv

load_dotenv()
EMBEDDING_MODEL = OpenAIEmbeddings()


from langchain.docstore.document import Document
import pandas as pd

def cargar_documentos(workspace):
    carpeta = f"storage/workspaces/{workspace}/documents"
    documentos = []

    if not os.path.exists(carpeta):
        print(f"❌ Carpeta no encontrada: {carpeta}")
        return []

    for archivo in os.listdir(carpeta):
        path = os.path.join(carpeta, archivo)

        if archivo.endswith(".pdf"):
            try:
                loader = PyPDFLoader(path)
                documentos.extend(loader.load())
            except Exception as e:
                print(f"❌ Error cargando PDF {archivo}: {e}")
                continue

        elif archivo.endswith(".docx"):
            try:
                loader = UnstructuredWordDocumentLoader(path)
                documentos.extend(loader.load())
            except Exception as e:
                print(f"❌ Error cargando Word {archivo}: {e}")
                continue

        elif archivo.endswith((".xls", ".xlsx", ".xlsm")):
            try:
                xls = pd.ExcelFile(path)
                for sheet_name in xls.sheet_names:
                    df = xls.parse(sheet_name)
                    text = df.astype(str).to_string(index=False)
                    documentos.append(Document(page_content=text, metadata={"source": archivo, "sheet": sheet_name}))
            except Exception as e:
                print(f"❌ Error cargando Excel {archivo}: {e}")
                continue

    return documentos

def aplicar_chunking(documentos):
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    return splitter.split_documents(documentos)

def crear_vectorstore(workspace, chunks):
    path = f"storage/workspaces/{workspace}/vectorstore"
    os.makedirs(path, exist_ok=True)
    vectorstore = FAISS.from_documents(chunks, EMBEDDING_MODEL)
    vectorstore.save_local(path)

def cargar_vectorstore(workspace):
    path = f"storage/workspaces/{workspace}/vectorstore"
    if not os.path.exists(path):
        return None
    return FAISS.load_local(path, EMBEDDING_MODEL, allow_dangerous_deserialization=True)
# vectorizer.py - Fin