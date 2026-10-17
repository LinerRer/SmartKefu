@echo off
chcp 936 >nul
title SmartKefu 一键停止
cd /d "%~dp0"

echo ================================================
echo    正在停止 SmartKefu 前后端进程...
echo ================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-dev.ps1" -Stop

echo.
echo 完成。MySQL 服务保持运行。
echo.
pause
