@echo off
title AI KnowledgeHub - Iniciando Plataforma
echo -------------------------------------------
echo   Activando entorno virtual y lanzando la app
echo -------------------------------------------

REM Ruta del proyecto
cd /d "C:\Users\JArdita\Desktop\BT - Prototipo IA\Prototipo_IA_Streamlit>"

REM Activar entorno virtual
call .venv\Scripts\activate.bat

REM Abrir Streamlit en una terminal
start cmd /k "call .venv\Scripts\activate.bat && streamlit run app.py"

REM Abrir Watchdog en otra terminal
start cmd /k "call .venv\Scripts\activate.bat && python monitor.py"

cmdow.exe @ /min
