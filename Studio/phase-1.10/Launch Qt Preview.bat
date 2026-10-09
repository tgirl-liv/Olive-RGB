@echo off
cd /d "%~dp0"
if not exist ".venv-studio-qt\Scripts\python.exe" (
  echo Run Setup Qt Preview.bat first.
  pause
  exit /b 1
)
".venv-studio-qt\Scripts\python.exe" studio_qt_preview.py
if errorlevel 1 pause
