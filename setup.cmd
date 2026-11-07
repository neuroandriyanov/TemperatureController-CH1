@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  python setup.py %*
) else (
  py -3 setup.py %*
)
if errorlevel 1 (
  echo Setup failed. Read the error above.
  pause
  exit /b 1
)
pause
