@echo off
setlocal enabledelayedexpansion

REM Base directory of this script (project root)
set "BASEDIR=%~dp0"

REM Timestamp for archive name
for /f %%i in ('powershell -NoProfile -Command "(Get-Date).ToString('yyyy-MM-dd_HH-mm-ss')"') do set "TS=%%i"

REM Output folder for backups
set "OUTDIR=%BASEDIR%backups"
if not exist "%OUTDIR%" mkdir "%OUTDIR%"

REM Archive path
set "ZIP=%OUTDIR%\ThermoGridServer_!TS!.zip"

echo Creating archive: %ZIP%

REM Try using built-in tar (Windows 10+)
set "TAROK=1"
tar.exe --version >nul 2>&1 || set "TAROK=0"
if "%TAROK%"=="1" (
  tar.exe -a -c -f "%ZIP%" -C "%BASEDIR%" index.html main.py static 2>nul
)

REM Fallback to PowerShell Compress-Archive if tar failed
if not exist "%ZIP%" (
  powershell -NoProfile -Command "Compress-Archive -Force -CompressionLevel Optimal -Path '%BASEDIR%index.html','%BASEDIR%main.py','%BASEDIR%static' -DestinationPath '%ZIP%'"
)

if exist "%ZIP%" (
  echo Done: %ZIP%
) else (
  echo Failed to create archive.
)

pause