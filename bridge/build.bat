@echo off
rem One-click build: produces dist\ViberEventBridge.exe
cd /d "%~dp0\.."
if not exist venv ( python -m venv venv )
call venv\Scripts\activate
pip install -q -r requirements.txt pyinstaller
pyinstaller --noconfirm --onefile --windowed --name ViberEventBridge --paths bridge bridge\bridge.py
echo.
echo Done: dist\ViberEventBridge.exe
pause
