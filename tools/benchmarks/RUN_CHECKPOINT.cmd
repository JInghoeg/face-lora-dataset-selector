@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "LOGDIR=%~dp0_research_output\windows-ml-runtime"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "LOG=%LOGDIR%\checkpoint-console.log"

echo ========================================
echo   Windows ML Checkpoint
echo ========================================
echo.
echo Console output is also saved to:
echo   %LOG%
echo.

call tools\benchmarks\run-windows-ml-checkpoint.cmd %* > "%LOG%" 2>&1
set "RC=%ERRORLEVEL%"

type "%LOG%"

echo.
echo ========================================
echo   Checkpoint launcher exit code: %RC%
echo ========================================
echo.

if /I "%FACE_LORA_CHECKPOINT_NO_HOLD%"=="1" exit /b %RC%

echo The window will remain open.
echo Use Ctrl+A / Ctrl+C normally, or type EXIT when finished.
echo.
cmd /k
