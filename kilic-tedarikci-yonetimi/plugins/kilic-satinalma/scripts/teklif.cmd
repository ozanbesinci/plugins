@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
if not exist "%USERPROFILE%\KilicPython\teklif-python.exe" (
    echo {"status":"BLOCKED","reason":"Kayitli teklif ortami bulunamadi; ayri Kur.cmd kurucusunu calistirin."}
    exit /b 3
)
"%USERPROFILE%\KilicPython\teklif-python.exe" "%~dp0runtime_launcher.py" %*
