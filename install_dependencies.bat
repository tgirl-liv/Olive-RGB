@echo off
cd /d "%~dp0"
py -m pip install -r requirements.txt
if errorlevel 1 (
    echo Dependency installation failed. Please review the error above.
    pause
    exit /b 1
)
echo Dependencies installed. Start Olive RGB with: py olive_rgb.py
pause
