#sidebar.py

import streamlit as st
from core.workspace_manager import get_all_workspaces, create_workspace

def sidebar():
    st.sidebar.title("🧠 TaxMiner")

    if st.sidebar.button("➕ New Workspace"):
        st.session_state['show_input'] = True

    if st.session_state.get('show_input', False):
        new_name = st.sidebar.text_input("Enter workspace name", key="new_workspace_name_input")
        if new_name:
            create_workspace(new_name)
            st.session_state['show_input'] = False
            st.rerun()

    st.sidebar.markdown("## Workspaces")
    for ws in get_all_workspaces():
        st.sidebar.markdown(f"- [{ws}](?workspace={ws})")
#sidebar.py - fin