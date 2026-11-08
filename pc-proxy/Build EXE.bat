@echo off
rem Optional: builds dist\LocaProxy.exe, a single file you can run without Python.
cd /d "%~dp0"
py -m pip install --upgrade pyinstaller || python -m pip install --upgrade pyinstaller
py -m PyInstaller --onefile --windowed --name LocaProxy locaproxy.py || python -m PyInstaller --onefile --windowed --name LocaProxy locaproxy.py
echo.
echo Done. Your app is in the "dist" folder: dist\LocaProxy.exe
pause
