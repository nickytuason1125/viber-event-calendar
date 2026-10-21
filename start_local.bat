@echo off
cd /d "%~dp0"
if not exist venv ( python -m venv venv & venv\Scripts\pip install -q -r requirements.txt )
start "" dist\ViberEventBridge.exe
venv\Scripts\python local.py
pause
