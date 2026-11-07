@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  python run.py thermal %*
) else (
  py -3 run.py thermal %*
)
if errorlevel 1 (
  echo Start failed. Run setup.cmd if the environment is missing.
  pause
  exit /b 1
)
