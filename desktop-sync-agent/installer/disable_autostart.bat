@echo off
REM ===========================================================================
REM  SnehDistribuors Windows Sync Agent - Disable Auto-Start on System Boot
REM ===========================================================================

echo Removing SnehDistribuors Sync Agent from Windows Startup...
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "SnehDistribuorsSyncAgent" /f >nul 2>&1
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "MyTallySyncAgent" /f >nul 2>&1

echo.
echo ===========================================================================
echo  ℹ️ Auto-start has been disabled.
echo ===========================================================================
echo.
pause
