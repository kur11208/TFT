@echo off
title TFT Advisor
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "ROOT_DIR=%%~fI"
set "BACKEND_DIR=%ROOT_DIR%\backend"
set "FRONTEND_DIR=%ROOT_DIR%\frontend"
set "OVERLAY_DIR=%ROOT_DIR%\overlay_app"
set "VENV_PY=%BACKEND_DIR%\.venv\Scripts\python.exe"

echo === TFT Advisor ===

if not exist "%VENV_PY%" (
    echo [ERROR] Backend virtual environment not found.
    echo Run setup.bat first.
    echo.
    pause
    exit /b 1
)

if not exist "%FRONTEND_DIR%\node_modules" (
    echo [INFO] Frontend dependencies not found. Installing...
    cd /d "%FRONTEND_DIR%"
    call npm install
    if errorlevel 1 (
        echo [ERROR] frontend npm install failed.
        pause
        exit /b 1
    )
)

if not exist "%OVERLAY_DIR%\node_modules" (
    echo [INFO] Overlay dependencies not found. Installing...
    cd /d "%OVERLAY_DIR%"
    call npm install --silent
    if errorlevel 1 (
        echo [ERROR] overlay_app npm install failed.
        pause
        exit /b 1
    )
)

echo [1/3] Starting backend...
call "%SCRIPT_DIR%restart_backend.bat"

timeout /t 4 /nobreak > nul

echo [2/3] Starting frontend...
start "TFT Frontend" cmd /k "cd /d ""%FRONTEND_DIR%"" && npm run dev"

echo Waiting for frontend...
powershell -NoProfile -Command "$deadline=(Get-Date).AddSeconds(20); while((Get-Date) -lt $deadline){ foreach($u in 'http://127.0.0.1:5173','http://localhost:5173'){ try { $r = Invoke-WebRequest -UseBasicParsing $u -TimeoutSec 2; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { exit 0 } } catch {} }; Start-Sleep -Milliseconds 500 }; exit 1"
if errorlevel 1 (
    echo [WARN] Frontend did not become ready in time. Overlay may use fallback UI.
)

echo [3/3] Starting overlay...
cd /d "%OVERLAY_DIR%"
start "TFT Overlay" npx electron .

echo.
echo === Running ===
echo - Main app : http://localhost:5173
echo - Overlay  : floating window (top-right of screen)
echo.
pause
