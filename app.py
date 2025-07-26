import streamlit as st
from ui.sidebar import sidebar
from ui.file_uploader import uploader
from ui.main_chat import chat
from dotenv import load_dotenv
import os

st.set_page_config(layout='wide')
sidebar()

st.title("TaxMiner")

query_params = st.query_params

workspace = query_params.get("workspace", [None])

if workspace:
    st.markdown(f"### Workspace seleccionado: `{workspace}``")
    uploader(workspace)
    chat(workspace)
else:
    st.info("Seleccioná o creá un workspace desde la barra lateral.")