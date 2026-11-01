@echo off
powershell.exe -NoProfile -File "%~dp0scripts\build.ps1" %*
exit /b %ERRORLEVEL%
