@echo off
title TFT Overlay

echo Installing overlay dependencies...
cd /d %~dp0overlay_app
call npm install --silent

echo Starting overlay...
start "TFT Overlay" npx electron .
