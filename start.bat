@echo off
title TFT Advisor
setlocal

set "BASE_DIR=%~dp0"
set "BACKEND_DIR=%BASE_DIR%backend"
set "FRONTEND_DIR=%BASE_DIR%frontend"
set "OVERLAY_DIR=%BASE_DIR%overlay_app"
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

:: Backend
echo [1/3] Starting backend...
start "TFT Backend" cmd /k "cd /d ""%BACKEND_DIR%"" && ""%VENV_PY%"" -m uvicorn app.main:app --reload --port 8000"

timeout /t 4 /nobreak > nul

:: Frontend
echo [2/3] Starting frontend...
start "TFT Frontend" cmd /k "cd /d ""%FRONTEND_DIR%"" && npm run dev"

timeout /t 6 /nobreak > nul

:: Electron overlay
echo [3/3] Starting overlay...
cd /d "%OVERLAY_DIR%"
start "TFT Overlay" npx electron .

echo.
echo === Running ===
echo - Main app : http://localhost:5173
echo - Overlay  : floating window (top-right of screen)
echo.
pause
