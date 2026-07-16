@echo off
cd /d "%~dp0"
if not exist venv\Scripts\python.exe (
    echo Voer eerst install.bat uit.
    pause
    exit /b 1
)
echo Dicteer draait nu in debug-modus. Laat dit venster open;
echo als Dicteer crasht zie je hier de foutmelding.
echo.
venv\Scripts\python.exe dicteer.py
echo.
echo Dicteer is gestopt (exitcode %errorlevel%).
pause
