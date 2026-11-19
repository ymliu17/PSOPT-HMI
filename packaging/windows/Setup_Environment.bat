@echo off
setlocal
cd /d "%~dp0"
echo Optional setup: create a local Python 3.10 x64 environment.
echo If your existing ECG environment already works, you can keep using it.
if exist ".venv\Scripts\python.exe" goto validate
py -3.10-64 -c "import struct,sys; sys.exit(0 if sys.version_info[:2] == (3,10) and struct.calcsize('P') == 8 else 1)" >nul 2>&1
if errorlevel 1 goto try_path
py -3.10-64 -m venv .venv
if errorlevel 1 goto failed
goto validate
:try_path
python -c "import struct,sys; sys.exit(0 if sys.version_info[:2] == (3,10) and struct.calcsize('P') == 8 else 1)" >nul 2>&1
if errorlevel 1 goto missing_python
python -m venv .venv
if errorlevel 1 goto failed
:validate
".venv\Scripts\python.exe" -c "import struct,sys; sys.exit(0 if sys.version_info[:2] == (3,10) and struct.calcsize('P') == 8 else 1)"
if errorlevel 1 goto wrong_environment
".venv\Scripts\python.exe" -m pip install -r requirements-windows-py310.lock.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" check_windows_environment.py
if errorlevel 1 goto failed
echo Setup complete. Run Start_ECG_Monitor_v2.bat.
pause
exit /b 0
:missing_python
echo Python 3.10 x64 was not found. See README_WINDOWS.txt.
echo You can also use your existing working ECG environment without this setup.
pause
exit /b 1
:wrong_environment
echo The existing .venv is not Python 3.10 x64. It has not been replaced.
echo Use a fresh extracted folder, or use your existing environment directly.
pause
exit /b 1
:failed
echo Setup did not finish. Read the error above; see README_WINDOWS.txt.
pause
exit /b 1
