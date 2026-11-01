@echo off
cd /d "%~dp0"
python -m venv .venv
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :failed
echo Dependencies installed. Run start.bat or build.bat.
pause
exit /b 0
:failed
echo Setup failed. Read the error above.
pause
exit /b 1
