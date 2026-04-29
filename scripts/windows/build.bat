@echo off
title TFT Advisor - Build
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "ROOT_DIR=%%~fI"
set "FRONTEND_DIR=%ROOT_DIR%\frontend"

echo Building frontend...
cd /d "%FRONTEND_DIR%"
call npm install
call npm run build

if %errorlevel% == 0 (
    echo [OK] Build complete. Output: frontend/dist/
) else (
    echo [ERROR] Build failed.
)
pause
