@echo off
chcp 936 >nul
title SmartKefu 一键启动
cd /d "%~dp0"

echo ================================================
echo    SmartKefu 一键启动
echo    MySQL(检查) -^> 后端(8000) -^> 前端(5173)
echo ================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-dev.ps1"

echo.
echo 启动流程结束。后端与前端在各自弹出的窗口中运行。
echo 关闭本窗口不影响服务；需要停止时请双击 stop.bat。
echo.
pause
