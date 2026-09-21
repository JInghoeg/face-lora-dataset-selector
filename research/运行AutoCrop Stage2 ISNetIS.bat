@echo off
setlocal
cd /d "%~dp0\.."

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "HF_HUB_DISABLE_SYMLINKS_WARNING=1"

set "BASEPY=G:\miniconda3\python.exe"
set "RESEARCH_ROOT=%CD%\_research_output\auto_crop_stage2"
set "FACE_LORA_RESEARCH_ROOT=%RESEARCH_ROOT%"
set "VENV=%RESEARCH_ROOT%\.venv-imgutils"
set "PY=%VENV%\Scripts\python.exe"

set "HF_HOME=%RESEARCH_ROOT%\hf_home"
set "HF_HUB_CACHE=%HF_HOME%\hub"
set "HUGGINGFACE_HUB_CACHE=%HF_HUB_CACHE%"
set "XDG_CACHE_HOME=%RESEARCH_ROOT%\xdg_cache"
set "PIP_CACHE_DIR=%RESEARCH_ROOT%\pip_cache"
set "PIP_DEFAULT_TIMEOUT=180"
set "PIP_RETRIES=12"
set "TEMP=%RESEARCH_ROOT%\temp"
set "TMP=%RESEARCH_ROOT%\temp"

if not exist "%BASEPY%" (
    echo Missing base Python: %BASEPY%
    pause
    exit /b 1
)

if not exist "%RESEARCH_ROOT%" mkdir "%RESEARCH_ROOT%"
if not exist "%HF_HOME%" mkdir "%HF_HOME%"
if not exist "%TEMP%" mkdir "%TEMP%"
if not exist "%PIP_CACHE_DIR%" mkdir "%PIP_CACHE_DIR%"

echo ============================================================
echo Auto Crop Stage 2 - ISNetIS raw mask validation
echo ============================================================
echo Research root:
echo   %RESEARCH_ROOT%
echo.
echo New venv / model cache / temp / benchmark output all stay here.
echo Existing LOCALAPPDATA review files are read-only input only.
echo.

if not exist "%PY%" (
    echo Creating isolated environment...
    "%BASEPY%" -m venv "%VENV%"
    if errorlevel 1 goto :failed
)

echo Installing / repairing mature upstream stack...
echo Pip cache:
echo   %PIP_CACHE_DIR%
echo Network policy:
echo   timeout=%PIP_DEFAULT_TIMEOUT%s, retries=%PIP_RETRIES%
echo.
call :install_stack
if errorlevel 1 goto :failed

echo Verifying upstream imports...
"%PY%" -c "from imgutils.detect import detect_person; from imgutils.segment import get_isnetis_mask; print('dghs-imgutils Stage 2 imports OK')"
if errorlevel 1 goto :failed

echo.
echo Running the frozen 20-image challenge set...
echo First run may download the ISNetIS model into:
echo   %HF_HOME%
echo.
"%PY%" -u "research\auto_crop_stage2_isnetis.py"
if errorlevel 1 goto :failed

echo.
echo Stage 2 run finished.
echo Open:
echo   %RESEARCH_ROOT%\latest_run.txt
echo and inspect contact_01.jpg ... contact_05.jpg in that run folder.
pause
exit /b 0

:failed
echo.
echo Stage 2 failed. The terminal output above is the diagnostic source.
pause
exit /b 1

:install_stack
for /L %%A in (1,1,3) do (
    echo Pip install attempt %%A/3...
    "%PY%" -m pip install ^
        --disable-pip-version-check ^
        --prefer-binary ^
        --timeout %PIP_DEFAULT_TIMEOUT% ^
        --retries %PIP_RETRIES% ^
        "onnxruntime>=1.19,<2" ^
        "dghs-imgutils==0.19.0"
    if not errorlevel 1 exit /b 0
    echo.
    echo Pip attempt %%A failed. Waiting 5 seconds before retry...
    timeout /t 5 /nobreak >nul
)
exit /b 1
