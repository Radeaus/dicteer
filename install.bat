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
        echo.
        echo Druk op een toets om af te sluiten.
        pause >nul
        exit /b 1
    )
    set "PYCMD=py -3"
) else (
    set "PYCMD=python"
)

echo [1/4] Virtuele omgeving vers aanmaken...
if exist venv rmdir /s /q venv
%PYCMD% -m venv venv
if errorlevel 1 (
    echo FOUT bij aanmaken venv.
    echo Druk op een toets om af te sluiten.
    pause >nul
    exit /b 1
)

echo [2/4] Pakketten installeren (dit kan enkele minuten duren)...
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo FOUT bij installeren pakketten.
    echo Druk op een toets om af te sluiten.
    pause >nul
    exit /b 1
)

rem GPU-versnelling is alleen mogelijk met NVIDIA (CUDA). Op AMD/Intel
rem draait Dicteer automatisch op de processor; de grote NVIDIA-
rem bibliotheken (~600 MB) worden dan overgeslagen.
powershell -NoProfile -Command "(Get-CimInstance Win32_VideoController).Name" 2>nul | findstr /i "NVIDIA" >nul
if not errorlevel 1 (
    echo NVIDIA-videokaart gevonden: GPU-ondersteuning installeren...
    venv\Scripts\python.exe -m pip install -r requirements-nvidia.txt
) else (
    echo Geen NVIDIA-videokaart gevonden: Dicteer gebruikt de processor.
    echo Dat werkt prima; kies eventueel het model 'medium' of 'small' voor extra snelheid.
)

echo [3/4] Snelkoppeling op het bureaublad maken...
venv\Scripts\python.exe make_shortcut.py

echo [4/4] Klaar! Dicteer wordt nu gestart...
echo (De eerste keer wordt het spraakmodel gedownload, ~1,6 GB.)
start "" "%~dp0start.bat"
exit /b 0
