@echo off
chcp 65001 > nul
title TFT Advisor - スタートアップ解除

schtasks /delete /tn "TFTAdvisorWatcher" /f

if %errorlevel% == 0 (
    echo [OK] 自動起動を解除しました。
) else (
    echo [NG] タスクが見つかりません（すでに解除済みかもしれません）。
)
pause
