# Script PowerShell para gerenciar ambiente de testes do AutomaSEI v2.0

param(
    [Parameter(Position=0)]
    [string]$Command,

    [Parameter(Position=1, ValueFromRemainingArguments=$true)]
    [string[]]$Args
)

$COMPOSE_FILE = "docker-compose.test.yml"

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

function Start-TestEnvironment {
    Write-Host "🚀 Iniciando ambiente de testes..." -ForegroundColor Cyan
    docker-compose -f $COMPOSE_FILE up -d

    Write-Host "⏳ Aguardando serviços ficarem prontos..."
    Start-Sleep -Seconds 5

    # Verificar status
    $status = docker-compose -f $COMPOSE_FILE ps
    if ($status -match "healthy") {
        Write-Success "PostgreSQL iniciado (porta 5433)"
    } else {
        Write-Warning "PostgreSQL pode não estar pronto ainda"
    }

    if ($status -match "firebase-emulator.*Up") {
        Write-Success "Firebase Emulator iniciado (portas 9199, 4000)"
    } else {
        Write-Warning "Firebase Emulator pode não estar pronto ainda"
    }

    Write-Host ""
    Write-Host "📊 Status dos serviços:" -ForegroundColor Cyan
    docker-compose -f $COMPOSE_FILE ps

    Write-Host ""
    Write-Success "Ambiente de testes pronto!"
    Write-Host "   Database: postgresql://automasei_test:***@localhost:5433/automasei_test"
    Write-Host "   Firebase Storage: http://localhost:9199"
    Write-Host "   Firebase UI: http://localhost:4000"
}

function Stop-TestEnvironment {
    Write-Host "🛑 Parando ambiente de testes..." -ForegroundColor Cyan
    docker-compose -f $COMPOSE_FILE stop
    Write-Success "Ambiente parado"
}

function Clean-TestEnvironment {
    Write-Host "🧹 Limpando ambiente de testes..." -ForegroundColor Cyan
    docker-compose -f $COMPOSE_FILE down -v
    Write-Success "Ambiente limpo (volumes removidos)"
}

function Show-Logs {
    param([string]$Service)

    if ([string]::IsNullOrEmpty($Service)) {
        docker-compose -f $COMPOSE_FILE logs -f
    } else {
        docker-compose -f $COMPOSE_FILE logs -f $Service
    }
}

function Run-Tests {
    param([string[]]$TestArgs)

    Write-Host "🧪 Executando testes..." -ForegroundColor Cyan

    # Verificar se ambiente está rodando
    $status = docker-compose -f $COMPOSE_FILE ps
    if ($status -notmatch "Up") {
        Write-Warning "Ambiente não está rodando. Iniciando..."
        Start-TestEnvironment
    }

    # Executar pytest
    if ($TestArgs.Count -eq 0) {
        pytest -v
    } else {
        pytest -v @TestArgs
    }
}

function Run-Coverage {
    Write-Host "📊 Executando testes com cobertura..." -ForegroundColor Cyan

    # Verificar se ambiente está rodando
    $status = docker-compose -f $COMPOSE_FILE ps
    if ($status -notmatch "Up") {
        Write-Warning "Ambiente não está rodando. Iniciando..."
        Start-TestEnvironment
    }

    pytest --cov=api --cov=core --cov=database --cov=utils `
           --cov-report=html --cov-report=term-missing `
           -v

    Write-Host ""
    Write-Success "Relatório de cobertura gerado em: htmlcov\index.html"

    # Abrir relatório no navegador
    $htmlReport = Join-Path $PSScriptRoot "..\htmlcov\index.html"
    if (Test-Path $htmlReport) {
        Start-Process $htmlReport
    }
}

function Connect-PostgreSQL {
    Write-Host "🐘 Conectando ao PostgreSQL de teste..." -ForegroundColor Cyan
    docker exec -it automasei_postgres_test psql -U automasei_test -d automasei_test
}

function Reset-Database {
    Write-Host "🔄 Resetando banco de dados de teste..." -ForegroundColor Cyan
    docker exec -it automasei_postgres_test psql -U automasei_test -d automasei_test -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
    Write-Success "Banco de dados resetado"

    # Executar migrations
    Write-Host "📝 Executando migrations..."
    alembic upgrade head
    Write-Success "Migrations aplicadas"
}

function Show-Status {
    Write-Host "📊 Status do ambiente de testes:" -ForegroundColor Cyan
    docker-compose -f $COMPOSE_FILE ps
}

function Show-Help {
    @"
Gerenciador de Ambiente de Testes - AutomaSEI v2.0

Uso: .\scripts\test-env.ps1 <comando> [argumentos]

Comandos:
    start           Inicia o ambiente de testes (PostgreSQL + Firebase Emulator)
    stop            Para o ambiente de testes
    clean           Para e remove volumes (limpa todos os dados)
    restart         Reinicia o ambiente

    test [args]     Executa testes com pytest (passa argumentos opcionais)
    coverage        Executa testes com relatório de cobertura

    logs [service]  Mostra logs (todos ou de um serviço específico)
    status          Mostra status dos serviços

    psql            Conecta ao PostgreSQL de teste via psql
    reset_db        Reseta o banco de dados e reaplica migrations

    help            Mostra esta ajuda

Exemplos:
    .\scripts\test-env.ps1 start
    .\scripts\test-env.ps1 test
    .\scripts\test-env.ps1 test tests/test_api/test_institutions.py
    .\scripts\test-env.ps1 test -k "institution"
    .\scripts\test-env.ps1 coverage
    .\scripts\test-env.ps1 logs postgres-test
    .\scripts\test-env.ps1 clean

"@
}

# Main
switch ($Command) {
    "start" {
        Start-TestEnvironment
    }
    "stop" {
        Stop-TestEnvironment
    }
    "clean" {
        Clean-TestEnvironment
    }
    "restart" {
        Stop-TestEnvironment
        Start-TestEnvironment
    }
    "test" {
        Run-Tests -TestArgs $Args
    }
    "coverage" {
        Run-Coverage
    }
    "logs" {
        Show-Logs -Service $Args[0]
    }
    "status" {
        Show-Status
    }
    "psql" {
        Connect-PostgreSQL
    }
    "reset_db" {
        Reset-Database
    }
    "help" {
        Show-Help
    }
    default {
        Write-Error "Comando inválido: $Command"
        Write-Host ""
        Show-Help
        exit 1
    }
}
