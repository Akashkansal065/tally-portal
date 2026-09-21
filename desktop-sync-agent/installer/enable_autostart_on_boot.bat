@echo off
REM ===========================================================================
REM  SnehDistribuors Windows Sync Agent - Enable Auto-Start on System Boot
REM ===========================================================================

echo ===========================================================================
echo  Setting up SnehDistribuors Sync Agent to start automatically on Windows boot...
echo ===========================================================================
echo.

set "EXE_PATH=%~dp0..\dist\SnehDistribuorsSync.exe"

if exist "%EXE_PATH%" (
    reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "SnehDistribuorsSyncAgent" /t REG_SZ /d "\"%EXE_PATH%\" --tray" /f
    echo.
    echo ===========================================================================
    echo  🎉 SUCCESS! SnehDistribuorsSync.exe will now start automatically whenever Windows boots!
    echo ===========================================================================
) else (
    echo [INFO] dist\SnehDistribuorsSync.exe not found. Setting up Python GUI script startup...
    cd /d "%~dp0\.."
    python -c "from config import install_startup; install_startup()"
)

echo.
pause
