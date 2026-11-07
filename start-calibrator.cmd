@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  python run.py calibrator %*
) else (
  py -3 run.py calibrator %*
)
if errorlevel 1 (
  echo Start failed. Run setup.cmd if the environment is missing.
  pause
  exit /b 1
)
