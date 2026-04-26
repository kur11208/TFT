@echo off
title Restart Backend
setlocal EnableDelayedExpansion

set "BASE_DIR=%~dp0"
set "BACKEND_DIR=%BASE_DIR%backend"
set "VENV_PY=%BACKEND_DIR%\.venv\Scripts\python.exe"
set "FOUND=0"

if not exist "%VENV_PY%" (
    echo [ERROR] Backend virtual environment not found.
    echo Run setup.bat first.
    echo.
    pause
    exit /b 1
)

echo Stopping existing TFT backend...
for /f %%P in ('powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -like '*uvicorn app.main:app*' -and $_.CommandLine -like '*--port 8000*' } | Select-Object -ExpandProperty ProcessId"') do (
    set "FOUND=1"
    echo - stopping PID %%P
    taskkill /PID %%P /T /F >nul 2>&1
)

if "!FOUND!"=="0" (
    echo - no matching backend process found
)

timeout /t 2 /nobreak >nul

echo Starting fresh backend...
start "TFT Backend" cmd /k "cd /d ""%BACKEND_DIR%"" && ""%VENV_PY%"" -m uvicorn app.main:app --reload --port 8000"

echo Done. Wait 5 seconds then check the browser.
timeout /t 5 /nobreak >nul
