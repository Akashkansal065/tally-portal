@echo off
setlocal enabledelayedexpansion
REM ===========================================================================
REM  SnehDistribuors Windows Desktop Sync Agent - Standalone Executable Builder
REM
REM  Every problem this script can run into is explained on screen with its fix,
REM  and the ones it can fix itself (no suitable Python, no pip) it fixes.
REM  Keep this file plain ASCII: other characters show as garbage in cmd.exe.
REM ===========================================================================

set "CHECK=%~dp0check_build_python.py"
set "SEEN=%TEMP%\mytally_build_pythons.txt"
set "PY_VERSION=3.13.10"
set "PY_INSTALLER_URL=https://www.python.org/ftp/python/%PY_VERSION%/python-%PY_VERSION%-amd64.exe"
set "PYTHON_EXE="
set "SAW_UNUSABLE="
del "%SEEN%" >nul 2>&1

echo ===========================================================================
echo  [1/3] Looking for a Python that can build the agent...
echo ===========================================================================
echo  It must be the 64-bit Intel/AMD build and include tkinter.
echo.

call :FIND_PYTHON
if defined PYTHON_EXE goto :PYTHON_FOUND

echo.
if defined SAW_UNUSABLE (
    echo  None of the Pythons on this PC can build the agent. The reasons are listed above.
) else (
    echo  No Python was found on this PC.
)
echo.
echo  This script can install the right one for you: Python %PY_VERSION% 64-bit from python.org,
echo  with tkinter and pip, for your Windows user only. Pythons already installed are left alone.
echo.
choice /c YN /m "  Download and install it now"
if errorlevel 2 goto :MANUAL_PYTHON

echo.
echo  Downloading Python %PY_VERSION% from python.org...
set "INSTALLER_PATH=%TEMP%\python-%PY_VERSION%-amd64.exe"
del "%INSTALLER_PATH%" >nul 2>&1
powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('%PY_INSTALLER_URL%', '%INSTALLER_PATH%')"
if not exist "%INSTALLER_PATH%" (
    echo.
    echo  The download failed. Check the internet connection, or install it by hand:
    goto :MANUAL_PYTHON
)

echo  Installing. A small progress window opens; wait for it to close...
start /wait "" "%INSTALLER_PATH%" /passive InstallAllUsers=0 PrependPath=0 Include_test=0 Include_tcltk=1 Include_pip=1 Include_launcher=0
del "%INSTALLER_PATH%" >nul 2>&1

call :FIND_PYTHON
if defined PYTHON_EXE goto :PYTHON_FOUND

echo.
echo  Python was installed but still cannot be used. This happens when the same version was
echo  already installed without tkinter. Install it by hand:

:MANUAL_PYTHON
echo.
echo   1. Open https://www.python.org/downloads/windows/
echo   2. Download "Windows installer (64-bit)". The file name ends in -amd64.exe.
echo      Do NOT take the ARM64 one, even on an ARM PC.
echo   3. Run it and choose "Customize installation".
echo   4. Keep "tcl/tk and IDLE" and "pip" ticked, then Next, then Install.
echo      If it shows Modify / Repair / Uninstall instead, choose Modify and tick both.
echo      If it then asks you to browse for a file, cancel, choose Uninstall, and install again.
echo   5. Run this script again.
echo.
pause
exit /b 1

:PYTHON_FOUND
echo  Using Python: !PYTHON_EXE!
"%PYTHON_EXE%" --version
echo.

echo ===========================================================================
echo  [2/3] Installing the packages the agent needs...
echo ===========================================================================
REM A Python installed with the "pip" box unticked has none; add it for this Windows user
"%PYTHON_EXE%" -m pip --version >nul 2>&1
if errorlevel 1 (
    echo  This Python has no pip. Adding it...
    "%PYTHON_EXE%" -m ensurepip --upgrade --user
)
"%PYTHON_EXE%" -m pip --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  BUILD FAILED: pip could not be added to this Python.
    echo  Fix: run the python.org installer again, choose Modify, tick "pip", then Next and Install.
    echo  Then run this script again.
    pause
    exit /b 1
)

"%PYTHON_EXE%" -m pip install --upgrade pip pyinstaller customtkinter pystray pillow cryptography keyring
if errorlevel 1 (
    echo.
    echo  BUILD FAILED: the packages above could not be installed. Find your case:
    echo.
    echo   - "Could not find a version" or a connection / proxy / SSL error:
    echo     the PC cannot reach pypi.org. Check the internet connection, then run this again.
    echo   - "Failed building wheel", "link.exe not found" or anything about Rust or Visual Studio:
    echo     this Python is too new for the ready-made packages. Install Python %PY_VERSION% 64-bit
    echo     from python.org, uninstall this one, and run this again.
    echo   - "Access is denied" or "Permission denied":
    echo     close the running Sync Agent and any other Python window, then run this again.
    pause
    exit /b 1
)

echo.
echo ===========================================================================
echo  [3/3] Bundling SnehDistribuorsSync.exe...
echo ===========================================================================
cd /d "%~dp0\.."

"%PYTHON_EXE%" -m PyInstaller --noconfirm --onefile --windowed --name "SnehDistribuorsSync" ^
    --icon "assets\icon.ico" ^
    --collect-all customtkinter ^
    --copy-metadata customtkinter ^
    --collect-submodules keyring ^
    --copy-metadata keyring ^
    --add-data "assets;assets" ^
    --add-data "security.py;." ^
    --add-data "config.py;." ^
    --add-data "agent.py;." ^
    --add-data "tally_client.py;." ^
    --add-data "cloud_client.py;." ^
    gui_app.py
if errorlevel 1 (
    echo.
    echo  BUILD FAILED while bundling. Find your case in the messages above:
    echo.
    echo   - "PermissionError" or "Access is denied" on SnehDistribuorsSync.exe:
    echo     the agent is running. Right-click its tray icon, choose Quit, then run this again.
    echo   - The .exe disappears or the build stops with no clear error:
    echo     the antivirus removed it. Allow the desktop-sync-agent\dist folder, then run this again.
    echo   - "No module named ...":
    echo     a package did not install. Run this script again and read step [2/3].
    pause
    exit /b 1
)

REM Never ship the build machine's agent_config.json: it identifies the developer's account and
REM backend. The .exe creates a fresh config on first launch and stores credentials in the
REM Windows Credential Manager.
if exist "%~dp0\..\dist\agent_config.json" del /q "%~dp0\..\dist\agent_config.json"

if exist "%~dp0\..\assets" (
    xcopy /e /i /y "%~dp0\..\assets" "%~dp0\..\dist\assets" >nul 2>&1
)

echo.
echo ===========================================================================
echo  BUILD SUCCESSFUL
echo  The program is ready in:
echo    desktop-sync-agent\dist\SnehDistribuorsSync.exe
echo  It runs on any 64-bit Windows PC, including ARM ones. No Python is needed there.
echo  agent_config.json is created on first launch; credentials go to Windows Credential Manager.
echo ===========================================================================
pause
exit /b 0

REM ---------------------------------------------------------------------------
REM  Sets PYTHON_EXE to the first Python that can build the agent. Each one that
REM  cannot is explained on screen, and SAW_UNUSABLE is set.
REM ---------------------------------------------------------------------------
:FIND_PYTHON
call :TRY_PYTHON python
if defined PYTHON_EXE exit /b 0
call :TRY_PYTHON py
if defined PYTHON_EXE exit /b 0
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python*" "%ProgramFiles%\Python*" "C:\Python*" "%LOCALAPPDATA%\Python\pythoncore-*") do (
    if not defined PYTHON_EXE if exist "%%D\python.exe" call :TRY_PYTHON "%%D\python.exe"
)
exit /b 0

:TRY_PYTHON
REM Not there, or the Microsoft Store placeholder that only opens the Store: skip quietly
"%~1" -c "import sys" >nul 2>&1
if errorlevel 1 exit /b 0
"%~1" "%CHECK%" "%SEEN%"
if errorlevel 1 (
    set "SAW_UNUSABLE=1"
) else (
    set "PYTHON_EXE=%~1"
)
exit /b 0
