@echo off
title Restart Backend
setlocal EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "ROOT_DIR=%%~fI"
set "BACKEND_DIR=%ROOT_DIR%\backend"
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
for /f %%P in ('powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -and $_.CommandLine -like '*uvicorn app.main:app*' -and $_.CommandLine -like '*--port 8010*' } | Select-Object -ExpandProperty ProcessId"') do (
    set "FOUND=1"
    echo - stopping PID %%P
    taskkill /PID %%P /T /F >nul 2>&1
)

for /f %%P in ('powershell -NoProfile -Command "Get-NetTCPConnection -State Listen -LocalPort 8010 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique"') do (
    set "FOUND=1"
    echo - stopping port 8010 owner PID %%P
    taskkill /PID %%P /T /F >nul 2>&1
)

if "!FOUND!"=="0" (
    echo - no matching backend process found
)

timeout /t 2 /nobreak >nul

echo Starting fresh backend...
powershell -NoProfile -Command "$logDir=Join-Path '%BACKEND_DIR%' 'logs'; New-Item -ItemType Directory -Force -Path $logDir | Out-Null; $out=Join-Path $logDir 'uvicorn_stdout.log'; $err=Join-Path $logDir 'uvicorn_stderr.log'; Start-Process -FilePath '%VENV_PY%' -WorkingDirectory '%BACKEND_DIR%' -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8010' -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err"

echo Done. Wait 5 seconds then check the browser.
timeout /t 5 /nobreak >nul
