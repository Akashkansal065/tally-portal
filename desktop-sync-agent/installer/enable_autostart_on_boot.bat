@echo off
REM ===========================================================================
REM  MyTally Windows Sync Agent - Enable Auto-Start on System Boot
REM ===========================================================================

echo ===========================================================================
echo  Setting up MyTally Sync Agent to start automatically on Windows boot...
echo ===========================================================================
echo.

set "EXE_PATH=%~dp0..\dist\MyTallySyncAgent.exe"

if exist "%EXE_PATH%" (
    reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "MyTallySyncAgent" /t REG_SZ /d "\"%EXE_PATH%\"" /f
    echo.
    echo ===========================================================================
    echo  🎉 SUCCESS! MyTallySyncAgent.exe will now start automatically whenever Windows boots!
    echo ===========================================================================
) else (
    echo [INFO] dist\MyTallySyncAgent.exe not found. Setting up Python script startup...
    cd /d "%~dp0\.."
    python agent.py --install-startup
)

echo.
pause
