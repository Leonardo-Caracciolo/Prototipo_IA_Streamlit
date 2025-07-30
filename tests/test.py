import streamlit as st

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

prompt = st.chat_input("Tu mensaje...")

if prompt:
    st.session_state.chat_history.append((prompt, f"Respuesta a: {prompt}"))

# Mostrar historial después del input
for p, r in st.session_state.chat_history:
    st.markdown(f"**🧑:** {p}")
    st.markdown(f"**🤖:** {r}")


