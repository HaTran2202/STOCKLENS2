@echo off
setlocal
title StockLens
pushd "%~dp0"
echo ==========================================
echo          STOCKLENS - LOCAL RUN
echo ==========================================
echo.
set "PYTHON_EXE="
if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%~dp0..\.venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0..\.venv\Scripts\python.exe"
if not defined PYTHON_EXE (
    where python >nul 2>nul
    if not errorlevel 1 set "PYTHON_EXE=python"
)
if not defined PYTHON_EXE (
    echo [LOI] Khong tim thay Python.
    echo Hay cai Python 3.10 tro len hoac tao moi truong .venv trong thu muc du an.
    pause
    popd
    exit /b 1
)
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
echo [OK] Python:
"%PYTHON_EXE%" --version
"%PYTHON_EXE%" -c "import streamlit, svglib" >nul 2>nul
if errorlevel 1 (
    echo Dang cai thu vien con thieu...
    "%PYTHON_EXE%" -m pip install -r "%~dp0requirements.txt"
    if errorlevel 1 (
        echo [LOI] Cai thu vien that bai.
        pause
        popd
        exit /b 1
    )
)
echo Dang mo StockLens tai http://localhost:8501 ...
"%PYTHON_EXE%" -X utf8 -m streamlit run "%~dp0app.py" --server.port 8501
popd
endlocal
