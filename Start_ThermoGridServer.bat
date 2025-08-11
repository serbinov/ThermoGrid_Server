@echo off
setlocal
rem Start ThermoGrid Server using the local .venv Python
cd /d %~dp0
set "VENV=%CD%\.venv"

if not exist "%VENV%\Scripts\python.exe" (
	echo [ThermoGrid] Creating .venv...
	py -3 -m venv .venv || goto :error
	"%VENV%\Scripts\python.exe" -m pip install --upgrade pip
	if exist requirements.txt (
		"%VENV%\Scripts\python.exe" -m pip install -r requirements.txt
	)
)

echo [ThermoGrid] Starting with .venv Python...
"%VENV%\Scripts\python.exe" main.py
goto :eof

:error
echo [ThermoGrid] Failed to create/use .venv
exit /b 1
