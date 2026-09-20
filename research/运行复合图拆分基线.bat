@echo off
setlocal
cd /d "%~dp0\.."
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "PY=%~dp0.venv-imgutils\Scripts\python.exe"

if not exist "%PY%" (
    echo Mature baseline environment not found.
    echo Run research\运行成熟人物检测基线.bat first.
    pause
    exit /b 1
)

echo Running Composite Split research with the existing DeepGHS person detector...
echo No source image will be modified.
echo.
"%PY%" -u "research\mature_composite_split_benchmark.py"
if errorlevel 1 goto :failed

echo.
echo Finished.
pause
exit /b 0

:failed
echo.
echo Composite Split research failed. Copy the terminal output when reporting it.
pause
exit /b 1
