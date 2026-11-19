@echo off
set SESSION_IDENTIFIER="test"

set /P SESSION_IDENTIFIER=Enter Session Identifier: 

set BATCH_PATH=%~dp0
Echo %BATCH_PATH%

echo Starting ECG Controller with Session Identifier %SESSION_IDENTIFIER% 
@REM start cmd.exe /C python "%BATCH_PATH%\plotECG_v3.py" "%BATCH_PATH%temp_ECG.csv"
@REM python "%BATCH_PATH%\ECG_Device_Controller.py" %SESSION_IDENTIFIER% "%BATCH_PATH%temp_ECG.csv"
python "%BATCH_PATH%\ECG_Device_Controller_v2.py" %SESSION_IDENTIFIER%
pause