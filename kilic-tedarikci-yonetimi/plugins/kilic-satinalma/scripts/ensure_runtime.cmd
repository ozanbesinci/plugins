@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
rem This entry needs no Python. Download authority is this pinned release/hash.
if not defined USERPROFILE goto failed
set "KILIC_ACTIVE_PACKAGE=%~dp0.."
set "KILIC_NATIVE_ENTRY=%USERPROFILE%\KilicPython\teklif-python.exe"
if not exist "%KILIC_NATIVE_ENTRY%" goto install
"%KILIC_NATIVE_ENTRY%" "%~dp0runtime_launcher.py" runtime_probe >nul 2>&1
if "%ERRORLEVEL%"=="0" exit /b 0
:install
if not exist "%USERPROFILE%\KilicPython" mkdir "%USERPROFILE%\KilicPython"
set "KILIC_SETUP_LOCK=%USERPROFILE%\KilicPython\teklif-setup.lock"
mkdir "%KILIC_SETUP_LOCK%" 2>nul
if not "%ERRORLEVEL%"=="0" goto busy
set "KILIC_LOCK_OWNED=1"
set "KILIC_SETUP_STAGE=%USERPROFILE%\KilicPython\setup-%RANDOM%-%RANDOM%"
if exist "%KILIC_SETUP_STAGE%" goto failed
mkdir "%KILIC_SETUP_STAGE%"
if not "%ERRORLEVEL%"=="0" goto failed
set "KILIC_SETUP_ARCHIVE=%KILIC_SETUP_STAGE%\installer.zip"
set "KILIC_SETUP_URL=https://github.com/ozanbesinci/plugins/releases/download/kilic-tedarikci-yonetimi-v1.4.0/kilic-teklif-1.4.0-kurulum.zip"
set "KILIC_SETUP_SHA256=928ff61174f8d01c8441090f4c45376cae98c312147c946aa22d54d50a8c29c4"
echo {"status":"INSTALLING_ENVIRONMENT","automatic_installation":true}
"%SystemRoot%\System32\curl.exe" --fail --location --proto =https --proto-redir =https --tlsv1.2 --retry 2 --connect-timeout 30 --max-time 180 --output "%KILIC_SETUP_ARCHIVE%" "%KILIC_SETUP_URL%"
if not "%ERRORLEVEL%"=="0" goto downloadfailed
"%SystemRoot%\System32\certutil.exe" -hashfile "%KILIC_SETUP_ARCHIVE%" SHA256 | "%SystemRoot%\System32\findstr.exe" /i /x /c:"%KILIC_SETUP_SHA256%" >nul
if not "%ERRORLEVEL%"=="0" goto hashfailed
rem Normal inline command; no execution-policy or system security changes.
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -Command "$ErrorActionPreference='Stop'; Expand-Archive -LiteralPath $env:KILIC_SETUP_ARCHIVE -DestinationPath (Join-Path $env:KILIC_SETUP_STAGE 'payload')"
if not "%ERRORLEVEL%"=="0" goto extractfailed
if not exist "%KILIC_SETUP_STAGE%\payload\kurulum\Kur.cmd" goto extractfailed
rem Use a relative command after PUSHD so spaces/metacharacters never enter /c.
pushd "%KILIC_SETUP_STAGE%\payload\kurulum"
if not "%ERRORLEVEL%"=="0" goto extractfailed
rem NUL satisfies the published installer's final PAUSE without user input.
"%ComSpec%" /d /c Kur.cmd <nul
set "KILIC_INSTALL_EXIT=%ERRORLEVEL%"
popd
if not "%KILIC_INSTALL_EXIT%"=="0" goto installfailed
if not exist "%KILIC_NATIVE_ENTRY%" goto verifyfailed
"%KILIC_NATIVE_ENTRY%" "%~dp0runtime_launcher.py" runtime_probe
if not "%ERRORLEVEL%"=="0" goto verifyfailed
rmdir "%KILIC_SETUP_LOCK%"
exit /b 0
:downloadfailed
echo {"status":"BLOCKED_INSTALLATION","reason":"INSTALLER_DOWNLOAD_FAILED","automatic_installation":true}
goto cleanupfailed
:hashfailed
echo {"status":"BLOCKED_INSTALLATION","reason":"INSTALLER_HASH_MISMATCH","automatic_installation":true}
goto cleanupfailed
:extractfailed
echo {"status":"BLOCKED_INSTALLATION","reason":"INSTALLER_EXTRACTION_FAILED","automatic_installation":true}
goto cleanupfailed
:installfailed
echo {"status":"BLOCKED_INSTALLATION","reason":"INSTALLER_FAILED","automatic_installation":true}
goto cleanupfailed
:verifyfailed
echo {"status":"BLOCKED_INSTALLATION","reason":"RUNTIME_VERIFICATION_FAILED","automatic_installation":true}
goto cleanupfailed
:busy
echo {"status":"BLOCKED_INSTALLATION","reason":"SETUP_ALREADY_RUNNING_OR_LOCKED","automatic_installation":true}
exit /b 3
:failed
echo {"status":"BLOCKED_INSTALLATION","reason":"SETUP_DIRECTORY_UNAVAILABLE","automatic_installation":true}
:cleanupfailed
if defined KILIC_LOCK_OWNED rmdir "%KILIC_SETUP_LOCK%"
exit /b 3
