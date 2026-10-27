@echo off
setlocal EnableExtensions

set "BASE=%~dp0"
set "INNER=%BASE%tools\benchmarks\run-windows-ml-checkpoint.cmd"
if not exist "%INNER%" set "INNER=%BASE%run-windows-ml-checkpoint.cmd"

if not exist "%INNER%" (
  echo [ERROR] Inner checkpoint launcher not found.
  echo Checked:
  echo   %BASE%tools\benchmarks\run-windows-ml-checkpoint.cmd
  echo   %BASE%run-windows-ml-checkpoint.cmd
  exit /b 2
)

set "LOGDIR=%BASE%_research_output\windows-ml-runtime"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "LOG=%LOGDIR%\checkpoint-console.log"

echo ========================================
echo   Windows ML Checkpoint
echo ========================================
echo.
echo Console output is also saved to:
echo   %LOG%
echo.

call "%INNER%" %* > "%LOG%" 2>&1
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
