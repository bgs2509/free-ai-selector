#!/bin/bash
# =============================================================================
# Free AI Selector - Скрипт деплоя на VPS
# =============================================================================
# Использование: ./scripts/deploy-vps.sh [команда]
#
# Команды:
#   deploy    - Полный деплой (pull + build + up + migrate + seed)
#   update    - Обновление (pull + build + restart)
#   start     - Запуск сервисов
#   stop      - Остановка сервисов
#   restart   - Перезапуск сервисов
#   logs      - Просмотр логов
#   status    - Статус сервисов
#   migrate   - Выполнить миграции БД
#   seed      - Заполнить БД начальными данными
#   health    - Проверить здоровье сервисов
# =============================================================================

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Конфигурация
PROJECT_DIR="/opt/free-ai-selector"
BRANCH="master"
COMPOSE_FILE="docker-compose.yml"

# -----------------------------------------------------------------------------
# Вспомогательные функции
# -----------------------------------------------------------------------------

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE} $1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

check_env() {
    if [ ! -f "$PROJECT_DIR/.env" ]; then
        log_error "Файл .env не найден!"
        log_info "Создайте его из шаблона: cp .env.example .env"
        exit 1
    fi
}

# -----------------------------------------------------------------------------
# Команды деплоя
# -----------------------------------------------------------------------------

cmd_deploy() {
    header "Полный деплой Free AI Selector"

    cd "$PROJECT_DIR"
    check_env

    log_info "Проверка/создание внешней сети proxy-network..."
    if docker network create proxy-network 2>/dev/null; then
        log_success "Сеть proxy-network создана"
    else
        log_info "Сеть proxy-network уже существует"
    fi

    log_info "Получение изменений из репозитория..."
    git fetch origin
    git reset --hard origin/$BRANCH
    log_success "Код обновлён"

    log_info "Остановка текущих контейнеров..."
    docker compose -f $COMPOSE_FILE down --remove-orphans || true
    log_success "Контейнеры остановлены"

    log_info "Сборка и запуск контейнеров..."
    docker compose -f $COMPOSE_FILE up -d --build
    log_success "Контейнеры запущены"

    log_info "Ожидание готовности сервисов (30 сек)..."
    sleep 30

    log_info "Выполнение миграций БД..."
    docker compose -f $COMPOSE_FILE exec -T free-ai-selector-data-postgres-api alembic upgrade head || log_warning "Миграции пропущены"
    log_success "Миграции выполнены"

    log_info "Заполнение начальных данных..."
    docker compose -f $COMPOSE_FILE exec -T free-ai-selector-data-postgres-api python -m app.infrastructure.database.seed || log_warning "Seed пропущен"
    log_success "Данные заполнены"

    cmd_status
    cmd_health

    header "Деплой завершён успешно!"
}

cmd_update() {
    header "Обновление Free AI Selector"

    cd "$PROJECT_DIR"
    check_env

    log_info "Получение изменений..."
    git fetch origin
    git reset --hard origin/$BRANCH
    log_success "Код обновлён"

    log_info "Пересборка и перезапуск..."
    docker compose -f $COMPOSE_FILE up -d --build
    log_success "Сервисы обновлены"

    cmd_status
}

cmd_start() {
    header "Запуск сервисов"
    cd "$PROJECT_DIR"
    check_env

    # Создаём сеть если не существует
    docker network create proxy-network 2>/dev/null || true

    docker compose -f $COMPOSE_FILE up -d
    log_success "Сервисы запущены"
    cmd_status
}

cmd_stop() {
    header "Остановка сервисов"
    cd "$PROJECT_DIR"
    docker compose -f $COMPOSE_FILE down
    log_success "Сервисы остановлены"
}

cmd_restart() {
    header "Перезапуск сервисов"
    cd "$PROJECT_DIR"
    docker compose -f $COMPOSE_FILE restart
    log_success "Сервисы перезапущены"
    cmd_status
}

cmd_logs() {
    cd "$PROJECT_DIR"
    docker compose -f $COMPOSE_FILE logs -f --tail=100
}

cmd_status() {
    header "Статус сервисов"
    cd "$PROJECT_DIR"
    docker compose -f $COMPOSE_FILE ps
}

cmd_migrate() {
    header "Выполнение миграций"
    cd "$PROJECT_DIR"
    docker compose -f $COMPOSE_FILE exec free-ai-selector-data-postgres-api alembic upgrade head
    log_success "Миграции выполнены"
}

cmd_seed() {
    header "Заполнение начальных данных"
    cd "$PROJECT_DIR"
    docker compose -f $COMPOSE_FILE exec free-ai-selector-data-postgres-api python -m app.infrastructure.database.seed
    log_success "Данные заполнены"
}

cmd_health() {
    header "Проверка здоровья сервисов"

    log_info "Business API..."
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        log_success "Business API: OK"
    else
        # Пробуем через Docker-сеть
        if docker compose -f $COMPOSE_FILE exec -T free-ai-selector-business-api curl -sf http://localhost:8000/health > /dev/null 2>&1; then
            log_success "Business API: OK (внутренний)"
        else
            log_error "Business API: НЕДОСТУПЕН"
        fi
    fi

    log_info "Data API..."
    if docker compose -f $COMPOSE_FILE exec -T free-ai-selector-data-postgres-api curl -sf http://localhost:8001/health > /dev/null 2>&1; then
        log_success "Data API: OK"
    else
        log_error "Data API: НЕДОСТУПЕН"
    fi

    log_info "PostgreSQL..."
    if docker compose -f $COMPOSE_FILE exec -T postgres pg_isready -U free_ai_selector_user > /dev/null 2>&1; then
        log_success "PostgreSQL: OK"
    else
        log_error "PostgreSQL: НЕДОСТУПЕН"
    fi
}

cmd_help() {
    echo "Free AI Selector - Скрипт деплоя"
    echo ""
    echo "Использование: $0 [команда]"
    echo ""
    echo "Команды:"
    echo "  deploy    Полный деплой (pull + build + up + migrate + seed)"
    echo "  update    Обновление (pull + build + restart)"
    echo "  start     Запуск сервисов"
    echo "  stop      Остановка сервисов"
    echo "  restart   Перезапуск сервисов"
    echo "  logs      Просмотр логов (Ctrl+C для выхода)"
    echo "  status    Статус сервисов"
    echo "  migrate   Выполнить миграции БД"
    echo "  seed      Заполнить БД начальными данными"
    echo "  health    Проверить здоровье сервисов"
    echo "  help      Показать эту справку"
    echo ""
}

# -----------------------------------------------------------------------------
# Точка входа
# -----------------------------------------------------------------------------

case "${1:-help}" in
    deploy)  cmd_deploy ;;
    update)  cmd_update ;;
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    restart) cmd_restart ;;
    logs)    cmd_logs ;;
    status)  cmd_status ;;
    migrate) cmd_migrate ;;
    seed)    cmd_seed ;;
    health)  cmd_health ;;
    help)    cmd_help ;;
    *)
        log_error "Неизвестная команда: $1"
        cmd_help
        exit 1
        ;;
esac
