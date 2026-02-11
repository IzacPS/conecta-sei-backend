# AutomaSEI v2 - Prepare local environment (minimal)
# Run from project root: .\scripts\run-local.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
if (-not (Test-Path (Join-Path $root "app\api\main.py"))) {
    Write-Host "Run this script from project root or from scripts/ (e.g. .\scripts\run-local.ps1)" -ForegroundColor Red
    exit 1
}
Set-Location $root

Write-Host "Project root: $root" -ForegroundColor Cyan

# 1. Ensure .env exists with minimal dev vars
$envPath = Join-Path $root ".env"
if (-not (Test-Path $envPath)) {
    @"
DATABASE_URL=postgresql://automasei:automasei_dev_password@localhost:5432/automasei
AUTH_DEV_MODE=true
"@ | Set-Content $envPath -Encoding UTF8
    Write-Host "Created .env with DATABASE_URL and AUTH_DEV_MODE=true" -ForegroundColor Green
} else {
    $content = Get-Content $envPath -Raw
    if ($content -notmatch "AUTH_DEV_MODE") {
        Add-Content $envPath "`nAUTH_DEV_MODE=true"
        Write-Host "Added AUTH_DEV_MODE=true to .env" -ForegroundColor Yellow
    }
    Write-Host ".env already present" -ForegroundColor Gray
}

# 2. Docker: start Postgres
Write-Host "`nStarting PostgreSQL (ParadeDB)..." -ForegroundColor Cyan
docker-compose up -d 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker not running or docker-compose failed. Start Docker Desktop and run: docker-compose up -d" -ForegroundColor Red
    exit 1
}

# Wait for Postgres to be ready
$max = 30
for ($i = 0; $i -lt $max; $i++) {
    $r = docker exec automasei_postgres pg_isready -U automasei -d automasei 2>$null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 1
}
if ($i -eq $max) {
    Write-Host "PostgreSQL did not become ready in time." -ForegroundColor Red
    exit 1
}
Write-Host "PostgreSQL is ready." -ForegroundColor Green

# 3. Migrations
Write-Host "`nRunning Alembic migrations..." -ForegroundColor Cyan
& alembic upgrade head 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Migrations failed. Ensure you have: pip install -r requirements-new.txt" -ForegroundColor Red
    exit 1
}
Write-Host "Migrations OK." -ForegroundColor Green

Write-Host "`n--- Next steps ---" -ForegroundColor Cyan
Write-Host "Seed (dados de teste): python scripts/seed-test-data.py" -ForegroundColor White
Write-Host "Terminal 1 (backend):  uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000" -ForegroundColor White
Write-Host "Terminal 2 (frontend): cd frontend && npm install && npm run dev" -ForegroundColor White
Write-Host "`nThen open: http://localhost:3000  (API: http://localhost:8000/docs). See TESTING.md for full flow." -ForegroundColor Gray
