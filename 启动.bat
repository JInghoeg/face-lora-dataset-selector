@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" app.py
    goto :done
)

for %%V in (3.12 3.11 3.10 3.9) do (
    py -%%V -c "import sys" >nul 2>nul
    if not errorlevel 1 (
        py -%%V app.py
        goto :done
    )
)

python -c "import sys; raise SystemExit(0 if (3,9) <= sys.version_info[:2] <= (3,12) else 1)" >nul 2>nul
if not errorlevel 1 (
    python app.py
    goto :done
)

echo No supported Python found.
echo Please install Python 3.12 x64, then double-click 安装.bat
pause
exit /b 1

:done
if errorlevel 1 pause
