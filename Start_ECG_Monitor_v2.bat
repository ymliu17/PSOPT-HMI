@echo off
setlocal
cd /d "%~dp0"
set "SESSION_IDENTIFIER=test"
set /P "SESSION_IDENTIFIER=Enter Session Identifier: "
python "%~dp0ECG_Device_Controller_v2.py" "%SESSION_IDENTIFIER%" monitor
pause
