@echo off
rem Double-click this file to open LocaProxy.
cd /d "%~dp0"
where pyw >nul 2>nul && (start "" pyw "%~dp0locaproxy.py" & exit /b)
where pythonw >nul 2>nul && (start "" pythonw "%~dp0locaproxy.py" & exit /b)
echo.
echo  Python is not installed.
echo  1. Go to https://www.python.org/downloads/ and install Python 3
echo     (tick "Add python.exe to PATH" during setup).
echo  2. Double-click "Start LocaProxy.bat" again.
echo.
start "" https://www.python.org/downloads/
pause
