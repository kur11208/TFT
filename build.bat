@echo off
title TFT Advisor - Build

echo Building frontend...
cd /d %~dp0frontend
call npm install
call npm run build

if %errorlevel% == 0 (
    echo [OK] Build complete. Output: frontend/dist/
) else (
    echo [ERROR] Build failed.
)
pause
