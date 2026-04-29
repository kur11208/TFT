@echo off
setlocal

set "BASE_DIR=%~dp0"
set "VENV_PY=%BASE_DIR%\.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
    echo [ERROR] Virtual environment not found.
    echo Run ..\setup.bat first.
    exit /b 1
)

cd /d "%BASE_DIR%"
"%VENV_PY%" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
