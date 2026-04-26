@echo off
title TFT Advisor Setup
setlocal

set "BASE_DIR=%~dp0"
set "BACKEND_DIR=%BASE_DIR%backend"
set "FRONTEND_DIR=%BASE_DIR%frontend"
set "OVERLAY_DIR=%BASE_DIR%overlay_app"
set "VENV_PY=%BACKEND_DIR%\.venv\Scripts\python.exe"

echo === TFT Advisor Setup ===
echo.

:: Python check
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install from https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python found.

:: Node check
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found. Install from https://nodejs.org/
    pause
    exit /b 1
)
echo [OK] Node.js found.

:: Backend setup
echo.
echo --- Backend setup ---
cd /d "%BACKEND_DIR%"

if not exist ".venv" (
    echo Creating venv...
    python -m venv .venv
)

if not exist "%VENV_PY%" (
    echo [ERROR] Virtual environment python not found.
    pause
    exit /b 1
)

echo Installing Python packages...
"%VENV_PY%" -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] pip install failed.
    pause
    exit /b 1
)
echo [OK] Backend ready.

:: Frontend setup
echo.
echo --- Frontend setup ---
cd /d "%FRONTEND_DIR%"
echo Installing npm packages...
call npm install
if %errorlevel% neq 0 (
    echo [ERROR] frontend npm install failed.
    pause
    exit /b 1
)
echo [OK] Frontend ready.

:: Overlay setup
echo.
echo --- Overlay setup ---
cd /d "%OVERLAY_DIR%"
echo Installing npm packages...
call npm install
if %errorlevel% neq 0 (
    echo [ERROR] overlay_app npm install failed.
    pause
    exit /b 1
)
echo [OK] Overlay ready.

echo.
echo === Setup complete! ===
echo Run start.bat to launch the app.
echo.
pause
