@echo off
title TechQuery -- Stop Application Servers
cd /d "%~dp0"

echo ====================================================================
echo        Stopping TechQuery Application Servers...
echo ====================================================================
echo.

set STOPPED_ANY=0

:: Stop Backend on port 8000
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    echo [*] Terminating Backend process on port 8000 (PID: %%a)...
    taskkill /f /pid %%a >nul 2>&1
    set STOPPED_ANY=1
)

:: Stop Frontend on port 5173
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5173" ^| findstr "LISTENING"') do (
    echo [*] Terminating Frontend process on port 5173 (PID: %%a)...
    taskkill /f /pid %%a >nul 2>&1
    set STOPPED_ANY=1
)

if %STOPPED_ANY% == 1 (
    echo.
    echo [OK] All TechQuery servers have been successfully stopped.
) else (
    echo.
    echo [INFO] No running TechQuery servers were found on port 8000 or 5173.
)

echo.
timeout /t 3
