@echo off
title TFT Advisor - Register Startup
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "ROOT_DIR=%%~fI"
set "PYTHONW=%ROOT_DIR%\backend\.venv\Scripts\pythonw.exe"
set "SCRIPT=%ROOT_DIR%\backend\watch_bg.pyw"
set "TASK=TFTAdvisorWatcher"

echo Registering startup task...
schtasks /delete /tn "%TASK%" /f >nul 2>&1
schtasks /create /tn "%TASK%" /tr "\"%PYTHONW%\" \"%SCRIPT%\"" /sc ONLOGON /rl HIGHEST /f

if %errorlevel% == 0 (
    echo [OK] Registered. App will auto-launch when TFT starts.
) else (
    echo [ERROR] Run this file as Administrator.
)
pause
