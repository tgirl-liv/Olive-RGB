@echo off
cd /d "%~dp0"
if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
  "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" studio_preview.py
) else (
  py -3 studio_preview.py
)
if errorlevel 1 pause
