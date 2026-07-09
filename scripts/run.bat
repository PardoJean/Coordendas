@echo off
REM run.bat - Script para ejecutar la aplicacion localmente en Windows
REM Requiere Python 3.11+ y dependencias de requirements.txt

echo ===========================================
echo   Procesador Topografico - Ejecucion Local
echo ===========================================

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python no se encuentra en el PATH.
    echo Por favor, instala Python 3.11+ desde https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Verificando dependencias...
pip install -r requirements.txt

echo Iniciando aplicacion...
python src/main.py

pause