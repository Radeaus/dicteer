@echo off
cd /d "%~dp0"
if not exist venv\Scripts\pythonw.exe (
    echo Voer eerst install.bat uit.
    echo Druk op een toets om af te sluiten.
    pause >nul
    exit /b 1
)
start "" venv\Scripts\pythonw.exe dicteer.py
