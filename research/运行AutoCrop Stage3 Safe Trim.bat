@echo off
setlocal
cd /d "%~dp0\.."

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "STAGE2_VENV=%CD%\_research_output\auto_crop_stage2\.venv-imgutils"
set "PY=%STAGE2_VENV%\Scripts\python.exe"

if not exist "%PY%" (
    echo Missing reusable Stage 2 environment:
    echo   %PY%
    echo.
    echo Stage 3 intentionally does not download or create a new environment.
    echo Run Stage 2 once in this same research checkout first.
    pause
    exit /b 1
)

if not exist "%CD%\_research_output\auto_crop_stage2\latest_run.txt" (
    echo Missing Stage 2 latest_run.txt.
    echo Stage 3 reuses the existing Stage 2 masks and will not rerun ISNetIS.
    pause
    exit /b 1
)

echo ============================================================
echo Auto Crop Stage 3 - mask to conservative trim benchmark
echo ============================================================
echo.
echo Reusing:
echo   Stage 2 venv
echo   Stage 2 masks
echo.
echo No pip install.
echo No model download.
echo No ISNetIS inference.
echo.

"%PY%" -u "research\auto_crop_stage3_safe_trim.py" --self-test
if errorlevel 1 goto :failed

"%PY%" -u "research\auto_crop_stage3_safe_trim.py"
if errorlevel 1 goto :failed

set "LATEST=%CD%\_research_output\auto_crop_stage3\latest_run.txt"
for /f "usebackq delims=" %%R in ("%LATEST%") do set "RUN=%%R"

echo.
echo Stage 3 finished:
echo   %RUN%
explorer.exe "%RUN%"
pause
exit /b 0

:failed
echo.
echo Stage 3 failed. No source image was modified.
pause
exit /b 1
