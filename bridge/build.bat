@echo off
rem One-click build: produces dist\ViberEventBridge.exe
cd /d "%~dp0\.."
if not exist venv ( python -m venv venv )
call venv\Scripts\activate
pip install -q -r requirements.txt pyinstaller uiautomation pillow winrt-runtime winrt-Windows.Media.Ocr winrt-Windows.Graphics.Imaging winrt-Windows.Storage.Streams winrt-Windows.Globalization winrt-Windows.Foundation winrt-Windows.Foundation.Collections
pyinstaller --noconfirm --onefile --windowed --name ViberEventBridge --paths bridge --hidden-import screenreader --collect-submodules winrt --collect-submodules uiautomation bridge\bridge.py
echo.
echo Done: dist\ViberEventBridge.exe
pause
