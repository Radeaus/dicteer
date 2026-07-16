@echo off
setlocal
cd /d "%~dp0"
echo ============================================
echo  Dicteer - installatie
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    where py >nul 2>nul
    if errorlevel 1 (
        echo FOUT: Python is niet gevonden.
        echo Installeer Python 3.10 t/m 3.12 via https://www.python.org/downloads/
        echo en vink tijdens installatie "Add python.exe to PATH" aan.
        pause
        exit /b 1
    )
    set "PYCMD=py -3"
) else (
    set "PYCMD=python"
)

echo [1/4] Virtuele omgeving vers aanmaken...
if exist venv rmdir /s /q venv
%PYCMD% -m venv venv
if errorlevel 1 ( echo FOUT bij aanmaken venv. & pause & exit /b 1 )

echo [2/4] Pakketten installeren (dit kan enkele minuten duren)...
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 ( echo FOUT bij installeren pakketten. & pause & exit /b 1 )

echo [3/4] Snelkoppeling op het bureaublad maken...
venv\Scripts\python.exe make_shortcut.py

echo [4/4] Klaar!
echo.
echo Start het programma voortaan met start.bat
echo (De eerste keer wordt het spraakmodel gedownload, ~1,6 GB.)
echo.
pause
