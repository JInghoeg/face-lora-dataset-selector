@echo off
setlocal
cd /d "%~dp0\.."

set "PY=G:\miniconda3\python.exe"
if not exist "%PY%" (
    echo G:\miniconda3\python.exe not found.
    pause
    exit /b 1
)

set "DATA=G:\ComfyUI-aki\数据集\渥尔比"

"%PY%" -u "research\auto_crop_harness.py" "%DATA%"
set "RC=%ERRORLEVEL%"

echo.
echo ExitCode=%RC%
if not "%RC%"=="0" pause
exit /b %RC%
