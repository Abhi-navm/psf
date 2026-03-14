Write-Host "=== Sales Pitch Analyzer - RunPod Mode ===" -ForegroundColor Cyan
Write-Host "  Analysis runs on RunPod GPU cloud - no Redis/Celery needed" -ForegroundColor Gray
Write-Host ""

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# 1. Start Backend API
Write-Host "[1/2] Starting Backend API ..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$scriptDir\backend'; & '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --reload --port 8000"
Write-Host "  Backend started on port 8000" -ForegroundColor Green

# 2. Start Frontend
Write-Host "[2/2] Starting Frontend ..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:Path += ';C:\Program Files\nodejs'; Set-Location '$scriptDir\frontend'; npm run dev"
Write-Host "  Frontend started on port 3000" -ForegroundColor Green

Write-Host ""
Write-Host "=== Ready! ===" -ForegroundColor Cyan
Write-Host "  Frontend:  http://localhost:3000" -ForegroundColor White
Write-Host "  Backend:   http://localhost:8000" -ForegroundColor White
Write-Host ""
Write-Host "Upload a video in the frontend - analysis will run on RunPod." -ForegroundColor Gray
