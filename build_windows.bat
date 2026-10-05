@echo off
setlocal
cd /d "%~dp0"
.venv\Scripts\python.exe -m pip install --no-cache-dir pyinstaller
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name VirtualComputerControl app.py
pause
