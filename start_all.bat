@echo off
title The Logic Inside Your Agent - Auto-Pilot Launcher
echo =====================================================================
echo    THE LOGIC INSIDE YOUR AGENT - 100%% AUTONOMOUS AUTO-PILOT SYSTEM
echo =====================================================================
echo.
echo [1/2] Launching 24/7 Background Auto-Agent Daemon (5-minute test interval)...
start /B .venv\Scripts\python.exe auto_agent.py --test-5min
echo [2/2] Launching Streamlit Interactive Dashboard on http://localhost:8501 ...
.venv\Scripts\streamlit.exe run app.py --server.port 8501
