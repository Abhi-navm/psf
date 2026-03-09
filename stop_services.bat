@echo off
title Sales Pitch Analyzer - Stopping Services
color 0C

echo ============================================
echo   Sales Pitch Analyzer - Stopping Services
echo ============================================
echo.

:: Stop Celery workers (by window title and by process)
echo [1/3] Stopping Celery workers...
taskkill /F /FI "WINDOWTITLE eq Celery Worker*" >nul 2>&1
taskkill /F /IM celery.exe >nul 2>&1
echo      Celery stopped.

:: Stop FastAPI server (by window title and by killing uvicorn/python on port 8000)
echo [2/3] Stopping FastAPI server...
taskkill /F /FI "WINDOWTITLE eq FastAPI Server*" >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
echo      FastAPI stopped.

:: Stop Redis container
echo [3/3] Stopping Redis...
docker stop redis >nul 2>&1
echo      Redis stopped.

echo.
echo ============================================
echo   All Services Stopped
echo ============================================
echo.
pause
