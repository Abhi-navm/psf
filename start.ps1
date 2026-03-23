Write-Host "=== AI Sales Pitch Analyzer ===" -ForegroundColor Cyan
Write-Host ""

# 1. Check Docker is running
Write-Host "[1/5] Starting Docker services (Redis + PostgreSQL)..." -ForegroundColor Yellow
$dockerRunning = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Docker Desktop is not running!" -ForegroundColor Red
    Write-Host "  Please start Docker Desktop first, then re-run this script." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Start Redis
$redis = docker ps --filter "name=redis" --filter "status=running" -q 2>$null
if ($redis) {
    Write-Host "  Redis already running" -ForegroundColor Green
} else {
    docker start redis 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Creating new Redis container..." -ForegroundColor Gray
        docker run -d -p 6379:6379 --name redis redis:alpine
    }
    Start-Sleep -Seconds 2
    Write-Host "  Redis started" -ForegroundColor Green
}

# Start PostgreSQL
$postgres = docker ps --filter "name=pitch-postgres" --filter "status=running" -q 2>$null
if ($postgres) {
    Write-Host "  PostgreSQL already running" -ForegroundColor Green
} else {
    docker start pitch-postgres 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Creating new PostgreSQL container..." -ForegroundColor Gray
        docker run -d -p 5432:5432 --name pitch-postgres `
            -e POSTGRES_DB=sales_analyzer `
            -e POSTGRES_USER=app `
            -e POSTGRES_PASSWORD=pitch-analyzer-secret `
            -v pitch_postgres_data:/var/lib/postgresql/data `
            postgres:16-alpine
    }
    Start-Sleep -Seconds 3
    Write-Host "  PostgreSQL started" -ForegroundColor Green
}

# 2. Start Backend API
Write-Host "[2/5] Starting Backend API (port 8000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$PSScriptRoot\backend'; & '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --reload --port 8000"
Write-Host "  Backend started" -ForegroundColor Green

# 3. Start Celery Worker (concurrency=20 for RunPod polling, threads pool)
Write-Host "[3/5] Starting Celery Worker (concurrency=20)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$PSScriptRoot\backend'; & '.\.venv\Scripts\python.exe' -m celery -A app.tasks.celery_app worker --loglevel=info --pool=threads --concurrency=20 -Q default,video,analysis,runpod"
Write-Host "  Celery started" -ForegroundColor Green

# 4. Start Frontend
Write-Host "[4/5] Starting Frontend (port 3000)..." -ForegroundColor Yellow
$env:Path += ";C:\Program Files\nodejs"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:Path += ';C:\Program Files\nodejs'; Set-Location '$PSScriptRoot\frontend'; npm run dev"
Write-Host "  Frontend started" -ForegroundColor Green

# 5. Summary
Write-Host ""
Write-Host "=== All services started! ===" -ForegroundColor Cyan
Write-Host "  Frontend:   http://localhost:3000" -ForegroundColor White
Write-Host "  Backend:    http://localhost:8000" -ForegroundColor White
Write-Host "  API Docs:   http://localhost:8000/docs" -ForegroundColor White
Write-Host "  PostgreSQL: localhost:5432" -ForegroundColor White
Write-Host "  Flower:     http://localhost:5555 (if started separately)" -ForegroundColor White
Write-Host ""
Write-Host "Capacity: 50+ parallel video analyses via Celery + RunPod" -ForegroundColor Gray
Write-Host "Close all opened PowerShell windows to stop." -ForegroundColor Gray
