@echo off
title TFT Advisor - Unregister Startup
setlocal

schtasks /delete /tn "TFTAdvisorWatcher" /f

if %errorlevel% == 0 (
    echo [OK] Startup task removed.
) else (
    echo [ERROR] Startup task was not found or could not be removed.
)
pause
