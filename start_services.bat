@echo off
title Sales Pitch Analyzer - Service Launcher
color 0A

echo ============================================
echo   Sales Pitch Analyzer - Starting Services
echo ============================================
echo.

:: Check if Docker is running
echo [1/4] Checking Docker...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker is not running! Please start Docker Desktop first.
    pause
    exit /b 1
)
echo      Docker is running.

:: Start Redis container
echo [2/4] Starting Redis...
docker start redis >nul 2>&1
if %errorlevel% neq 0 (
    echo      Redis container not found, creating new one...
    docker run -d --name redis -p 6379:6379 redis:alpine >nul 2>&1
)
echo      Redis started on port 6379.

:: Start Ollama (if not already running)
echo [3/4] Starting Ollama...
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe">NUL
if %errorlevel% neq 0 (
    start "" "ollama" serve
    timeout /t 2 >nul
)
echo      Ollama is running.

:: Change to backend directory
cd /d "%~dp0backend"

:: Start FastAPI server in new window
echo [4/4] Starting FastAPI and Celery...
start "FastAPI Server" cmd /k "title FastAPI Server && color 0B && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

:: Wait a moment for FastAPI to initialize
timeout /t 3 >nul

:: Start Celery worker in new window
start "Celery Worker" cmd /k "title Celery Worker && color 0D && python -m celery -A app.tasks.celery_app worker --loglevel=info --pool=solo"

echo.
echo ============================================
echo   All Services Started Successfully!
echo ============================================
echo.
echo   - Redis:    localhost:6379
echo   - FastAPI:  http://127.0.0.1:8000
echo   - API Docs: http://127.0.0.1:8000/docs
echo   - Ollama:   localhost:11434
echo.
echo   Press any key to open API docs in browser...
pause >nul

:: Open browser to API docs
start http://127.0.0.1:8000/docs

echo.
echo   Services are running in separate windows.
echo   Close this window when done, or press any key to exit.
pause >nul
