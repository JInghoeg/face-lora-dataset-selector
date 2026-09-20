@echo off
setlocal
cd /d "%~dp0\.."

set "PY=G:\miniconda3\envs\python312\python.exe"
if not exist "%PY%" set "PY=G:\miniconda3\python.exe"
set "DATA=G:\ComfyUI-aki\数据集\渥尔比"
set "LOG=%~dp0autocrop-startup.log"

if not exist "%PY%" (
    >"%LOG%" echo No supported Python found. Checked python312 env and base Miniconda.
    type "%LOG%"
    pause
    exit /b 1
)

echo ===== Auto Crop startup ===== > "%LOG%"
"%PY%" --version >> "%LOG%" 2>&1
echo. >> "%LOG%"
echo ===== Dependency preflight ===== >> "%LOG%"
"%PY%" -u -c "import cv2, mediapipe, PySide6, PIL, numpy; print('imports OK')" >> "%LOG%" 2>&1
if errorlevel 1 (
    type "%LOG%"
    echo.
    echo Startup failed. Log: %LOG%
    pause
    exit /b 1
)

echo. >> "%LOG%"
echo ===== Harness self-test ===== >> "%LOG%"
"%PY%" -u "research\auto_crop_harness.py" --self-test >> "%LOG%" 2>&1
if errorlevel 1 (
    type "%LOG%"
    echo.
    echo Harness self-test failed. Log: %LOG%
    pause
    exit /b 1
)

echo. >> "%LOG%"
echo ===== Valby benchmark ===== >> "%LOG%"
"%PY%" -u "research\auto_crop_harness.py" "%DATA%" >> "%LOG%" 2>&1
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
    type "%LOG%"
    echo.
    echo ExitCode=%RC%
    echo Log: %LOG%
    pause
    exit /b %RC%
)

echo.
echo Auto Crop benchmark exited normally.
echo Log: %LOG%
exit /b 0
