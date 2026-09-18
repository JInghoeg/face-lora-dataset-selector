@echo off
setlocal
cd /d "%~dp0"

set "PY="

for %%V in (3.12 3.11 3.10 3.9) do (
    py -%%V -c "import sys" >nul 2>nul
    if not errorlevel 1 (
        set "PY=py -%%V"
        goto :found_python
    )
)

python -c "import sys; raise SystemExit(0 if (3,9) <= sys.version_info[:2] <= (3,12) else 1)" >nul 2>nul
if not errorlevel 1 (
    set "PY=python"
    goto :found_python
)

echo.
echo No supported Python was found.
echo Please install Python 3.12 x64 and run this file again.
echo.
pause
exit /b 1

:found_python
echo.
echo Using: %PY%
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Creating local virtual environment...
    %PY% -m venv .venv
    if errorlevel 1 goto :failed
)

echo Installing dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed

echo.
echo Installation complete.
echo You can now double-click 启动.bat
echo.
pause
exit /b 0

:failed
echo.
echo Installation failed. Please copy the error message above when reporting the problem.
echo.
pause
exit /b 1
