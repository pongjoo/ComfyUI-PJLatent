@echo off
chcp 65001 >nul
title PJ 桌面离线翻译器启动中...

set SCRIPT_DIR=%~dp0
set PORTABLE_ROOT=%SCRIPT_DIR%..\..\

if exist "%PORTABLE_ROOT%python_embeded\python.exe" (
    set PYTHON_EXE="%PORTABLE_ROOT%python_embeded\python.exe"
) else (
    set PYTHON_EXE=python
)

echo 正在启动 PJ 桌面离线翻译器...
%PYTHON_EXE% "%SCRIPT_DIR%pj_standalone_translator.py"

if errorlevel 1 (
    echo.
    echo 启动发生错误，请按任意键退出...
    pause >nul
)
