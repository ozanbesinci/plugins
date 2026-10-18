@echo off
setlocal
set "KILIC_CALC_BOOTSTRAP=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
if not exist "%KILIC_CALC_BOOTSTRAP%" (
  echo Once ayni klasordeki Kur.cmd ile Python ortamini hazirlayin.
  exit /b 3
)
"%KILIC_CALC_BOOTSTRAP%" -X utf8 -I -B "%~dp0calculation_install.py"
exit /b %ERRORLEVEL%
