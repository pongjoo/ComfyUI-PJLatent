@echo off
title PJ ×ÀÃæÀëÏß·­ÒëÆ÷
chcp 936 >nul

set "PYTHON_EXE=D:\ComfyUI_windows_portable_nvidia_cu128\ComfyUI_windows_portable\python_embeded\python.exe"
set "SCRIPT_PATH=%~dp0pj_standalone_translator.py"

if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" "%SCRIPT_PATH%"
