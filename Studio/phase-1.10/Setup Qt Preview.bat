@echo off
cd /d "%~dp0"
py -3.14 -m venv .venv-studio-qt
if errorlevel 1 goto failed
".venv-studio-qt\Scripts\python.exe" -m pip install -r requirements-studio-qt.txt
if errorlevel 1 goto failed
echo Setup complete. Run Launch Qt Preview.bat.
pause
exit /b 0
:failed
echo Setup failed. Review the error above.
pause
exit /b 1
