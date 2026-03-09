@echo off
title Sales Pitch Analyzer - Setup
color 0E

echo ============================================
echo   Sales Pitch Analyzer - Initial Setup
echo ============================================
echo.

cd /d "%~dp0backend"

:: Create data directories
echo [1/4] Creating data directories...
if not exist "data" mkdir data
if not exist "data\uploads" mkdir data\uploads
if not exist "data\frames" mkdir data\frames
if not exist "data\audio" mkdir data\audio
echo      Data directories created.

:: Create virtual environment
echo [2/4] Setting up Python virtual environment...
if not exist "venv" (
    python -m venv venv
    echo      Virtual environment created.
) else (
    echo      Virtual environment already exists.
)

:: Activate venv and install dependencies
echo [3/4] Installing Python dependencies...
call venv\Scripts\activate.bat
pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
echo      Dependencies installed.

:: Pull Redis image
echo [4/4] Pulling Docker images...
docker pull redis:alpine >nul 2>&1
echo      Redis image ready.

echo.
echo ============================================
echo   Setup Complete!
echo ============================================
echo.
echo   Next steps:
echo   1. Make sure Ollama is installed with llama3:8b model
echo      Run: ollama pull llama3:8b
echo.
echo   2. Run start_services.bat to start all services
echo.
pause
