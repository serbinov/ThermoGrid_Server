@echo off
setlocal

REM Build minimal one-file EXE into WIN_64 using PyInstaller and headless entrypoint
set PROJECT_ROOT=%~dp0
cd /d "%PROJECT_ROOT%"

if not exist WIN_64 mkdir WIN_64

set PY=%VIRTUAL_ENV%\Scripts\python.exe
if not exist "%PY%" set PY=python

REM Ensure PyInstaller
"%PY%" -m PyInstaller --version >nul 2>&1 || (
  "%PY%" -m pip install --upgrade pip && "%PY%" -m pip install pyinstaller
)

set ICON=icons\app_icon.ico

REM Data to bundle (use ; separator on Windows)
set DATA1=index.html;.
set DATA2=static;static
set DATA3=icons;icons

"%PY%" -m PyInstaller ^
  --name ThermoGridServer ^
  --onefile --noconsole --clean ^
  --icon "%ICON%" ^
  --add-data "%DATA1%" ^
  --add-data "%DATA2%" ^
  --add-data "%DATA3%" ^
  --exclude-module PySide6 ^
  --exclude-module PyQt5 ^
  --exclude-module tkinter ^
  --exclude-module matplotlib ^
  --exclude-module PIL ^
  --exclude-module numpy ^
  --exclude-module scipy ^
  --exclude-module pydoc ^
  --exclude-module asyncpg ^
  --hidden-import anyio ^
  --hidden-import idna ^
  --hidden-import sniffio ^
  server_headless.py

if exist dist\ThermoGridServer.exe move /y dist\ThermoGridServer.exe WIN_64\ThermoGridServer.exe >nul

echo Built WIN_64\ThermoGridServer.exe
endlocal
