@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
call "%~dp0ensure_runtime.cmd"
if errorlevel 1 exit /b 3
"%USERPROFILE%\KilicPython\teklif-python.exe" "%~dp0runtime_launcher.py" %*
exit /b %ERRORLEVEL%
