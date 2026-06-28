@echo off
title PJ 桌面离线翻译器
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0启动桌面翻译器.ps1"
if errorlevel 1 pause
