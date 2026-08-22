@echo off
REM ============================================================
REM KillSpooler.bat
REM Purpose:
REM   Stop Windows Print Spooler, clear stuck print jobs,
REM   and restart the spooler.
REM
REM IMPORTANT:
REM   Run as Administrator.
REM ============================================================

echo Stopping Print Spooler...
net stop spooler

echo Clearing stuck print jobs...
del /Q /F "%SystemRoot%\System32\spool\PRINTERS\*.*"

echo Starting Print Spooler...
net start spooler

echo.
echo Print spooler reset complete.
pause