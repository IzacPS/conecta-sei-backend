#!/bin/bash
# Script para gerenciar ambiente de testes do AutomaSEI v2.0

set -e

COMPOSE_FILE="docker-compose.test.yml"

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo_success() {
    echo -e "${GREEN}✓${NC} $1"
}

echo_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

echo_error() {
    echo -e "${RED}✗${NC} $1"
}

# Função: Iniciar ambiente de testes
start() {
    echo "🚀 Iniciando ambiente de testes..."
    docker-compose -f $COMPOSE_FILE up -d

    echo "⏳ Aguardando serviços ficarem prontos..."
    sleep 5

    # Verificar health dos serviços
    if docker-compose -f $COMPOSE_FILE ps | grep -q "healthy"; then
        echo_success "PostgreSQL iniciado (porta 5433)"
    else
        echo_warning "PostgreSQL pode não estar pronto ainda"
    fi

    if docker-compose -f $COMPOSE_FILE ps firebase-emulator | grep -q "Up"; then
        echo_success "Firebase Emulator iniciado (portas 9199, 4000)"
    else
        echo_warning "Firebase Emulator pode não estar pronto ainda"
    fi

    echo ""
    echo "📊 Status dos serviços:"
    docker-compose -f $COMPOSE_FILE ps

    echo ""
    echo_success "Ambiente de testes pronto!"
    echo "   Database: postgresql://automasei_test:***@localhost:5433/automasei_test"
    echo "   Firebase Storage: http://localhost:9199"
    echo "   Firebase UI: http://localhost:4000"
}

# Função: Parar ambiente de testes
stop() {
    echo "🛑 Parando ambiente de testes..."
    docker-compose -f $COMPOSE_FILE stop
    echo_success "Ambiente parado"
}

# Função: Parar e remover volumes (limpar dados)
clean() {
    echo "🧹 Limpando ambiente de testes..."
    docker-compose -f $COMPOSE_FILE down -v
    echo_success "Ambiente limpo (volumes removidos)"
}

# Função: Ver logs
logs() {
    SERVICE=$1
    if [ -z "$SERVICE" ]; then
        docker-compose -f $COMPOSE_FILE logs -f
    else
        docker-compose -f $COMPOSE_FILE logs -f $SERVICE
    fi
}

# Função: Executar testes
test() {
    echo "🧪 Executando testes..."

    # Verificar se ambiente está rodando
    if ! docker-compose -f $COMPOSE_FILE ps | grep -q "Up"; then
        echo_warning "Ambiente não está rodando. Iniciando..."
        start
    fi

    # Executar pytest
    if [ -z "$1" ]; then
        pytest -v
    else
        pytest -v "$@"
    fi
}

# Função: Executar testes com cobertura
coverage() {
    echo "📊 Executando testes com cobertura..."

    # Verificar se ambiente está rodando
    if ! docker-compose -f $COMPOSE_FILE ps | grep -q "Up"; then
        echo_warning "Ambiente não está rodando. Iniciando..."
        start
    fi

    pytest --cov=api --cov=core --cov=database --cov=utils \
           --cov-report=html --cov-report=term-missing \
           -v

    echo ""
    echo_success "Relatório de cobertura gerado em: htmlcov/index.html"
}

# Função: Conectar ao PostgreSQL
psql() {
    echo "🐘 Conectando ao PostgreSQL de teste..."
    docker exec -it automasei_postgres_test psql -U automasei_test -d automasei_test
}

# Função: Resetar banco de dados
reset_db() {
    echo "🔄 Resetando banco de dados de teste..."
    docker exec -it automasei_postgres_test psql -U automasei_test -d automasei_test -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
    echo_success "Banco de dados resetado"

    # Executar migrations
    echo "📝 Executando migrations..."
    alembic upgrade head
    echo_success "Migrations aplicadas"
}

# Função: Mostrar status
status() {
    echo "📊 Status do ambiente de testes:"
    docker-compose -f $COMPOSE_FILE ps
}

# Função: Ajuda
help() {
    cat << EOF
Gerenciador de Ambiente de Testes - AutomaSEI v2.0

Uso: ./scripts/test-env.sh <comando> [argumentos]

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
    ./scripts/test-env.sh start
    ./scripts/test-env.sh test
    ./scripts/test-env.sh test tests/test_api/test_institutions.py
    ./scripts/test-env.sh test -k "institution"
    ./scripts/test-env.sh coverage
    ./scripts/test-env.sh logs postgres-test
    ./scripts/test-env.sh clean

EOF
}

# Main
case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    clean)
        clean
        ;;
    restart)
        stop
        start
        ;;
    test)
        shift
        test "$@"
        ;;
    coverage)
        coverage
        ;;
    logs)
        logs "$2"
        ;;
    status)
        status
        ;;
    psql)
        psql
        ;;
    reset_db)
        reset_db
        ;;
    help|--help|-h)
        help
        ;;
    *)
        echo_error "Comando inválido: $1"
        echo ""
        help
        exit 1
        ;;
esac
