import streamlit as st
from core.file_handler import guardar_archivo
from core.sql_pipeline import cargar_a_sql

def uploader(workspace):
    st.subheader("📂 Subir archivos")
    uploaded_files = st.file_uploader(
        "Seleccioná archivos PDF o Excel", 
        type=["pdf", "xls", "xlsx", "xlsm", "docx"], 
        accept_multiple_files=True
    )

    if uploaded_files:
        for file in uploaded_files:
            path = guardar_archivo(file, workspace)
            st.success(f"Archivo guardado: {path}")

            if path.endswith((".xls", ".xlsx", ".xlsm")):
                _, resumen = cargar_a_sql(path, workspace)
                st.info(f"✅ Excel procesado como SQL:\n{resumen}")
