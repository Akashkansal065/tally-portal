@echo off
setlocal enabledelayedexpansion
REM ===========================================================================
REM  SnehDistribuors Windows Desktop Sync Agent - Standalone Executable Builder
REM ===========================================================================

echo ===========================================================================
echo  [1/3] Detecting Python on your Windows system...
echo ===========================================================================

set "PYTHON_EXE="
set "PYTHON_UNUSABLE="

REM A Python is only used if it can build an .exe that opens on an ordinary PC:
REM  - it has tkinter (the "tcl/tk and IDLE" part of the Python installer), which the window needs;
REM  - it is the 64-bit Intel/AMD build. An ARM64 Python builds an .exe that only runs on ARM PCs,
REM    and the cryptography package has no ready-made build for it.
set "PYTHON_CHECK=import sys, tkinter; sys.exit(0 if 'AMD64' in sys.version else 1)"

REM 1. Check if 'python' is in PATH and actually works (not Microsoft store alias)
python -c "%PYTHON_CHECK%" >nul 2>&1 && set "PYTHON_EXE=python" && goto :PYTHON_FOUND
python -c "import sys" >nul 2>&1 && set "PYTHON_UNUSABLE=python"

REM 2. Check if 'py' launcher is available
py -c "%PYTHON_CHECK%" >nul 2>&1 && set "PYTHON_EXE=py" && goto :PYTHON_FOUND
py -c "import sys" >nul 2>&1 && set "PYTHON_UNUSABLE=py"

REM 3. Search common Windows installation folders
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python*" "C:\Python*" "%ProgramFiles%\Python*") do (
    if exist "%%D\python.exe" (
        "%%D\python.exe" -c "%PYTHON_CHECK%" >nul 2>&1 && set "PYTHON_EXE=%%D\python.exe" && goto :PYTHON_FOUND
        set "PYTHON_UNUSABLE=%%D\python.exe"
    )
)

if defined PYTHON_UNUSABLE (
    echo.
    echo  Python was found ^(!PYTHON_UNUSABLE!^) but it cannot build the agent: it is either an ARM64
    echo  Python or was installed without tkinter.
    echo  Fix: from python.org download the "Windows installer (64-bit)" - not the ARM64 one -
    echo  choose Customize installation, keep "tcl/tk and IDLE" and "pip" ticked, install,
    echo  then run this script again. Other Pythons can stay installed.
    pause
    exit /b 1
)

REM If Python was not found, automatically download and install it silently
echo.
echo ===========================================================================
echo  ⚡ Python was not detected. Automatically downloading and installing...
echo ===========================================================================
echo.
echo  [Step 1/2] Downloading official Python 3.11 from python.org...
set "INSTALLER_PATH=%TEMP%\python_installer_311.exe"
powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe', '%INSTALLER_PATH%')"

if not exist "%INSTALLER_PATH%" (
    echo ❌ Automatic download failed. Please check your internet connection.
    pause
    exit /b 1
)

echo  [Step 2/2] Installing Python silently in background (takes ~15-20 seconds)...
start /wait "" "%INSTALLER_PATH%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_tcltk=1 SimpleInstall=1

del "%INSTALLER_PATH%" >nul 2>&1

REM Refresh and search newly installed location
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
    if exist "%%D\python.exe" (
        set "PYTHON_EXE=%%D\python.exe"
        goto :PYTHON_FOUND
    )
)

echo.
echo ⚠️ Installation finished. Please close and re-run this script once to initialize.
pause
exit /b 0

:PYTHON_FOUND
echo  ✅ Found Python: !PYTHON_EXE!
"%PYTHON_EXE%" --version
echo.

echo ===========================================================================
echo  [2/3] Installing / Updating Dependencies (CustomTkinter, PyInstaller, Pillow)...
echo ===========================================================================
REM A Python installed with the "pip" box unticked has none; add it for this Windows user
"%PYTHON_EXE%" -m pip --version >nul 2>&1 || "%PYTHON_EXE%" -m ensurepip --upgrade --user
"%PYTHON_EXE%" -m pip install --upgrade pip pyinstaller customtkinter pystray pillow cryptography keyring
if errorlevel 1 (
    echo.
    echo  BUILD FAILED: the packages above could not be installed.
    pause
    exit /b 1
)

echo.
echo ===========================================================================
echo  [3/3] Bundling SnehDistribuorsSync.exe...
echo ===========================================================================
cd /d "%~dp0\.."

"%PYTHON_EXE%" -m PyInstaller --onefile --windowed --name "SnehDistribuorsSync" ^
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
    echo  BUILD FAILED. See the messages above.
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
echo  🎉 BUILD SUCCESSFUL!
echo  Your standalone GUI executable is ready in:
echo  📂 desktop-sync-agent\dist\SnehDistribuorsSync.exe
echo  (agent_config.json is created on first launch; credentials go to Windows Credential Manager)
echo ===========================================================================
pause
