@echo off
title AI KnowledgeHub - Iniciando Plataforma
echo -------------------------------------------
echo   Iniciando Streamlit App y Monitor Watchdog
echo -------------------------------------------
start cmd /k "streamlit run app.py"
start cmd /k "python monitor.py"
