@echo off
setlocal
cd /d "%~dp0"
set "PSOPT_PYTHON=python"
if exist "%~dp0.venv\Scripts\python.exe" set "PSOPT_PYTHON=%~dp0.venv\Scripts\python.exe"
"%PSOPT_PYTHON%" check_windows_environment.py
if errorlevel 1 goto failed
set "SESSION_IDENTIFIER="
set /P "SESSION_IDENTIFIER=Enter Session Identifier: "
if not defined SESSION_IDENTIFIER goto empty_session
"%PSOPT_PYTHON%" "%~dp0ECG_Device_Controller_v2.py" "%SESSION_IDENTIFIER%"
set "PSOPT_EXIT_CODE=%ERRORLEVEL%"
pause
exit /b %PSOPT_EXIT_CODE%
:empty_session
echo Session Identifier cannot be empty.
pause
exit /b 1
:failed
echo Environment check failed. Use the original ECG environment or run Setup_Environment.bat.
pause
exit /b 1
