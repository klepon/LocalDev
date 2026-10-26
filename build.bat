@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -m pip install -q pyinstaller
".venv\Scripts\pyinstaller.exe" --noconfirm --clean --windowed --name LocalDev ^
  --icon assets\icon.ico --add-data "assets\icon.ico;assets" main.py
echo.
echo Built: dist\LocalDev\LocalDev.exe
