@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
set "KILIC_BOOTSTRAP_VERSION=3.14.8"
set "KILIC_BOOTSTRAP_URL=https://www.python.org/ftp/python/3.14.8/python-3.14.8-amd64.exe"
set "KILIC_BOOTSTRAP_SHA256=759be887b96e736a3ca886daf8d575f18fcae1a09efab6902f42d59e8999f8ef"
set "KILIC_INSTALL_ROOT=%USERPROFILE%\KilicPython"
if not defined USERPROFILE goto failed
if defined KILIC_BASE_PYTHON goto explicit
set "KILIC_BASE_PYTHON=%KILIC_INSTALL_ROOT%\python-%KILIC_BOOTSTRAP_VERSION%\python.exe"
call :probe
if not errorlevel 1 goto ready
set "KILIC_BASE_PYTHON=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
call :probe
if not errorlevel 1 goto ready
set "KILIC_BASE_PYTHON="
for /f "tokens=2,*" %%A in ('reg.exe query "HKCU\SOFTWARE\Python\PythonCore\3.14\InstallPath" /v ExecutablePath 2^>nul') do if "%%A"=="REG_SZ" set "KILIC_BASE_PYTHON=%%B"
call :probe
if not errorlevel 1 goto ready
echo Python kullanici hesabina kuruluyor...
if not exist "%KILIC_INSTALL_ROOT%" mkdir "%KILIC_INSTALL_ROOT%"
if not exist "%KILIC_INSTALL_ROOT%" goto failed
set "KILIC_DOWNLOAD=%KILIC_INSTALL_ROOT%\python-%KILIC_BOOTSTRAP_VERSION%-amd64.exe"
"%SystemRoot%\System32\curl.exe" --fail --location --proto =https --tlsv1.2 --retry 2 --output "%KILIC_DOWNLOAD%" "%KILIC_BOOTSTRAP_URL%"
if errorlevel 1 goto failed
"%SystemRoot%\System32\certutil.exe" -hashfile "%KILIC_DOWNLOAD%" SHA256 | "%SystemRoot%\System32\findstr.exe" /i /x /c:"%KILIC_BOOTSTRAP_SHA256%" >nul
if errorlevel 1 goto hashfailed
start "" /b /wait "%KILIC_DOWNLOAD%" /quiet InstallAllUsers=0 Include_launcher=0 InstallLauncherAllUsers=0 PrependPath=0 AppendPath=0 Include_test=0 Include_doc=0 Include_dev=0 Include_tcltk=0 Include_pip=1 Shortcuts=0 TargetDir="%KILIC_INSTALL_ROOT%\python-%KILIC_BOOTSTRAP_VERSION%"
if errorlevel 1 goto failed
set "KILIC_BASE_PYTHON=%KILIC_INSTALL_ROOT%\python-%KILIC_BOOTSTRAP_VERSION%\python.exe"
:explicit
call :probe
if errorlevel 1 goto incompatible
:ready
"%KILIC_BASE_PYTHON%" -X utf8 -I -B "%~dp0install_runtime.py"
if errorlevel 1 goto failed
echo Kurulum tamamlandi. Bu pencereyi kapatabilirsiniz.
pause
exit /b 0
:probe
if not defined KILIC_BASE_PYTHON exit /b 1
if not exist "%KILIC_BASE_PYTHON%" exit /b 1
"%KILIC_BASE_PYTHON%" -I -B "%~dp0probe_python.py" >nul 2>&1
exit /b %ERRORLEVEL%
:hashfailed
echo Python kurucusunun SHA256 dogrulamasi basarisiz.
goto failed
:incompatible
echo Secilen Python, Windows 3.14 / 64 bit profiline uygun degil.
:failed
echo Kurulum tamamlanamadi. Yukaridaki hata bilgisini saklayin.
pause
exit /b 3

