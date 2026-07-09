@echo off
REM build.bat - Script para compilar la aplicación con PyInstaller

echo ===========================================
echo Compilando Procesador Topográfico a .exe
echo ===========================================

REM Obtener la ruta de customtkinter para incluir sus assets war
for /f "delims=" %%i in ('python -c "import customtkinter; print(customtkinter.__path__[0])"') do set CTKDIR=%%i

echo CustomTkinter encontrado en: %CTKDIR%

pyinstaller --name "ProcesadorTopografico" ^
    --onefile ^
    --windowed ^
    --add-data "%CTKDIR%;customtkinter" ^
    --hidden-import customtkinter ^
    --hidden-import PIL ^
    --hidden-import PIL._imagingtk ^
    --hidden-import PIL._tkinter_finder ^
    src/main.py

echo.
echo Compilación finalizada. Ejecutable en: dist\ProcesadorTopografico.exe
pause
