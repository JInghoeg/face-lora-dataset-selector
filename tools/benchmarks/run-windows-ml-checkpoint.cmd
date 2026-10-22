@echo off
setlocal

rem Work around PowerShell 7.6.x startup crash in localized update
rem notifications (for example zh-Hans totalWidth -17). This environment
rem variable is scoped to this launcher and its child process only.
set "POWERSHELL_UPDATECHECK=Off"

set "SCRIPT=%~dp0run-windows-ml-checkpoint.ps1"

if not exist "%SCRIPT%" (
  echo [ERROR] Checkpoint script not found: "%SCRIPT%"
  exit /b 2
)

if /I "%~1"=="--wrapper-self-test" (
  where pwsh.exe >nul 2>nul
  if not errorlevel 1 (
    pwsh.exe -NoLogo -NoProfile -Command "if ($env:POWERSHELL_UPDATECHECK -ne 'Off') { exit 3 }; exit 0"
    exit /b %ERRORLEVEL%
  )

  where powershell.exe >nul 2>nul
  if errorlevel 1 (
    echo [ERROR] Neither pwsh.exe nor powershell.exe is available.
    exit /b 4
  )
  powershell.exe -NoLogo -NoProfile -Command "if ($env:POWERSHELL_UPDATECHECK -ne 'Off') { exit 3 }; exit 0"
  exit /b %ERRORLEVEL%
)

where pwsh.exe >nul 2>nul
if not errorlevel 1 (
  pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %*
  exit /b %ERRORLEVEL%
)

where powershell.exe >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Neither pwsh.exe nor powershell.exe is available.
  exit /b 4
)

echo [INFO] pwsh.exe not found; falling back to Windows PowerShell.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %*
exit /b %ERRORLEVEL%
