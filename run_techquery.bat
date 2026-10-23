@echo off
setlocal enabledelayedexpansion
title TechQuery -- AI Technical Knowledge Assistant Launcher
cd /d "%~dp0"

cls
echo ====================================================================
echo        TechQuery -- AI Technical Knowledge Assistant
echo ====================================================================
echo.

:: 1. Check Python Virtual Environment
echo [*] Checking Python environment...
if exist "backend\.venv\Scripts\python.exe" (
    echo     [OK] Python Virtual Environment found: backend\.venv
) else (
    echo     [ERROR] Python virtual environment not found in backend\.venv
    echo     Please run: cd backend ^& python -m venv .venv ^& pip install -r requirements.txt
    pause
    exit /b 1
)

:: 2. Check Node & npm
echo [*] Checking Node.js and npm...
where node >nul 2>&1
if !errorlevel! == 0 (
    echo     [OK] Node.js is installed
) else (
    echo     [ERROR] Node.js not found in PATH
    pause
    exit /b 1
)

:: 3. Check Gemini API Key Status in backend\.env
echo [*] Checking Google Gemini API Key...
set API_KEY_STATUS=NOT CONFIGURED
findstr /R "^GEMINI_API_KEY=..*" backend\.env >nul 2>&1
if !errorlevel! == 0 (
    set API_KEY_STATUS=KEY ENTRY FOUND - see backend/.env
    echo     [OK] Gemini API Key: CONFIGURED
) else (
    echo     [WARN] Gemini API Key: NOT CONFIGURED
    echo            TechQuery will start using local keyword retrieval.
    echo            Add your free key to backend\.env to enable Gemini AI answers.
)

:: 4. Check Local SQLite Database
echo [*] Checking Local Database...
if exist "data\techquery.db" (
    echo     [OK] SQLite Database found: data\techquery.db
) else (
    echo     [INFO] Database will be initialized on first startup.
)
echo.

:: 5. Launch Backend Server
echo [*] Starting FastAPI Backend Server on port 8000...
start "TechQuery - Backend Server" cmd /c "cd /d "%~dp0backend" && title TechQuery Backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

:: 6. Launch Frontend Server
echo [*] Starting Vite Frontend Server on port 5173...
start "TechQuery - Frontend Server" cmd /c "cd /d "%~dp0frontend" && title TechQuery Frontend && npm.cmd run dev"

echo.
echo [*] Initializing application servers, please wait...
ping -n 4 127.0.0.1 >nul

:: 7. Query live health check
set BACKEND_STATUS=Starting...
set DOC_COUNT=0
set CHUNK_COUNT=0
set GEMINI_LIVE=false

backend\.venv\Scripts\python.exe -c "import urllib.request, json; res = urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health'); d = json.loads(res.read()); print(f'OK|{d[\"database\"][\"total_documents\"]}|{d[\"database\"][\"total_indexed_chunks\"]}|{d[\"gemini\"][\"configured\"]}')" > "%TEMP%\techquery_health.tmp" 2>nul
if !errorlevel! == 0 (
    set /p HEALTH_DATA=<"%TEMP%\techquery_health.tmp"
    for /f "tokens=1,2,3,4 delims=|" %%a in ("!HEALTH_DATA!") do (
        set BACKEND_STATUS=ONLINE
        set DOC_COUNT=%%b
        set CHUNK_COUNT=%%c
        set GEMINI_LIVE=%%d
    )
    del "%TEMP%\techquery_health.tmp" >nul 2>&1
) else (
    set BACKEND_STATUS=STARTING [Port 8000]
)

:: 8. Display Status Dashboard
cls
echo ====================================================================
echo        TechQuery -- AI Technical Knowledge Assistant
echo ====================================================================
echo.
echo   ======================= STATUS DASHBOARD =======================
echo.
echo     Frontend App URL  : http://localhost:5173
echo     Backend API URL   : http://127.0.0.1:8000
echo     Swagger Docs URL  : http://127.0.0.1:8000/docs
echo.
echo     Backend Status    : !BACKEND_STATUS!
echo     Database Type     : SQLite [data\techquery.db]
echo     Indexed Textbooks : !DOC_COUNT! Books [!CHUNK_COUNT! Chunks Indexed]
echo     Google Gemini AI  : !API_KEY_STATUS!
if "!GEMINI_LIVE!"=="True" (
echo     AI Model Status   : Configured Gemini model - see backend/.env [Embedding: gemini-embedding-001]
)
echo.
echo   ================================================================
echo.
echo [*] Opening TechQuery in your default browser...
start http://localhost:5173

echo.
echo --------------------------------------------------------------------
echo   TechQuery is running! Keep this or the server windows open.
echo   To stop all servers, close the windows or run: stop_techquery.bat
echo --------------------------------------------------------------------
echo.
pause
