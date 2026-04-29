@echo off
title TFT Overlay
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "ROOT_DIR=%%~fI"
set "OVERLAY_DIR=%ROOT_DIR%\overlay_app"

echo Installing overlay dependencies...
cd /d "%OVERLAY_DIR%"
call npm install --silent

echo Starting overlay...
start "TFT Overlay" npx electron .
