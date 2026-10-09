@echo off
cd /d "%~dp0"
if not exist ".venv-studio-qt\Scripts\python.exe" (
  echo Run Setup Qt Preview.bat first.
  pause
  exit /b 1
)
".venv-studio-qt\Scripts\python.exe" -m pip install -r requirements-studio-live.txt
if errorlevel 1 (
  echo Live dependencies could not be installed.
  pause
  exit /b 1
)
echo LIVE dependencies installed. Launch Qt Preview.bat still defaults to DEMO.
pause
