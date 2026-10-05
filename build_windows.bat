@echo off
cd /d "%~dp0"
py -m pip install -r requirements.txt
if errorlevel 1 goto failed
py -m pip install --upgrade pyinstaller
if errorlevel 1 goto failed
py -m PyInstaller --noconfirm --clean --windowed --onefile --name "Olive RGB" --icon "olive_rgb.ico" --collect-all lotus_lamp --collect-all bleak --collect-all bleak_winrt --collect-all soundcard --collect-all mss --collect-all winrt --collect-all PIL --hidden-import=PIL._tkinter_finder --hidden-import=bleak.backends.winrt --hidden-import=bleak.backends.winrt.client --hidden-import=bleak.backends.winrt.scanner olive_rgb.py
if errorlevel 1 goto failed
echo Build complete: dist\Olive RGB.exe
pause
exit /b 0
:failed
echo Build failed. Please review the error above.
pause
exit /b 1
