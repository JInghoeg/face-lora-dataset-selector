@echo off
setlocal
cd /d "%~dp0\.."
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "BASEPY=G:\miniconda3\python.exe"
set "VENV=%~dp0.venv-imgutils"
set "PY=%VENV%\Scripts\python.exe"

if not exist "%BASEPY%" (
    echo Missing: %BASEPY%
    pause
    exit /b 1
)

if not exist "%PY%" (
    echo Creating isolated mature-baseline environment on G: ...
    "%BASEPY%" -m venv "%VENV%"
    if errorlevel 1 goto :failed

    echo Installing only the mature upstream stack. Pip cache is disabled.
    "%PY%" -m pip install --disable-pip-version-check --no-cache-dir "onnxruntime>=1.19,<2" "dghs-imgutils==0.19.0"
    if errorlevel 1 goto :failed
)

echo.
echo Running DeepGHS person detector on prior Auto Crop failure cases...
"%PY%" -u "research\mature_person_benchmark.py"
if errorlevel 1 goto :failed

echo.
echo Finished.
pause
exit /b 0

:failed
echo.
echo Mature baseline failed. Copy the terminal output when reporting it.
pause
exit /b 1
