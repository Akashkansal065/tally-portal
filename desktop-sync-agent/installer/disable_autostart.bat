@echo off
REM ===========================================================================
REM  MyTally Windows Sync Agent - Disable Auto-Start on System Boot
REM ===========================================================================

echo Removing MyTally Sync Agent from Windows Startup...
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "MyTallySyncAgent" /f >nul 2>&1

echo.
echo ===========================================================================
echo  ℹ️ Auto-start has been disabled.
echo ===========================================================================
echo.
pause
