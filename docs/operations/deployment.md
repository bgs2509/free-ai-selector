# Deployment Guide

> Руководство по развёртыванию Free AI Selector.

## Обзор архитектуры развёртывания

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Nginx :8000    │────▶│ Business API    │────▶│   Data API      │
│  (external)     │     │    :8000        │     │    :8001        │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
┌─────────────────┐                              ┌───────▼────────┐
│ Telegram Bot    │────────────────────────────▶│   PostgreSQL   │
│                 │                              │    :5432       │
└─────────────────┘                              └────────────────┘
        ▲
        │
┌───────┴────────┐
│ Health Worker  │
│ (APScheduler)  │
└────────────────┘
```

---

## Development Deployment

### Полный запуск

```bash
# 1. Сборка образов
make build

# 2. Запуск сервисов
make up

# 3. Проверка здоровья
make health

# 4. Инициализация БД
make migrate
make seed
```

### Перезапуск после изменений

```bash
# Перезапуск конкретного сервиса
docker compose restart free-ai-selector-business-api

# Полная пересборка
make down
make build
make up
```

---

## Docker Compose Services

### Порядок запуска

```yaml
# docker-compose.yml определяет зависимости:
services:
  postgres:           # 1. Сначала БД

  free-ai-selector-data-postgres-api:
    depends_on:
      postgres:       # 2. Data API после БД
        condition: service_healthy

  free-ai-selector-business-api:
    depends_on:
      free-ai-selector-data-postgres-api:  # 3. Business API после Data API
        condition: service_healthy

  free-ai-selector-telegram-bot:
    depends_on:
      free-ai-selector-business-api:       # 4. Bot после Business API
        condition: service_healthy
```

### Health Checks

Каждый сервис имеет встроенную проверку здоровья:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

---

## Проверка развёртывания

### 1. Статус контейнеров

```bash
docker compose ps
```

Ожидаемый вывод:

```
NAME                              STATUS          PORTS
free-ai-selector-business-api            Up (healthy)    8000/tcp
free-ai-selector-data-postgres-api       Up (healthy)    8001/tcp
free-ai-selector-health-worker           Up
free-ai-selector-nginx                   Up              0.0.0.0:8000->80/tcp
free-ai-selector-telegram-bot            Up
postgres                          Up (healthy)    5432/tcp
```

### 2. Health Endpoints

```bash
# Business API
curl http://localhost:8000/health

# Data API
curl http://localhost:8002/health
```

### 3. Проверка провайдеров

```bash
curl -X POST http://localhost:8000/api/v1/providers/test
```

---

## Переменные окружения

### Обязательные

| Переменная | Сервис | Описание |
|------------|--------|----------|
| `DATABASE_URL` | Data API | PostgreSQL connection string |
| `DATA_API_URL` | Business API | URL Data API |
| `GROQ_API_KEY` | Business API | Groq ключ |
| `DEEPSEEK_API_KEY` | Business API | DeepSeek ключ |
| `CEREBRAS_API_KEY` | Business API | Cerebras ключ |

### Опциональные

| Переменная | Сервис | По умолчанию |
|------------|--------|--------------|
| `LOG_LEVEL` | Все | INFO |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot | - |
| `BOT_ADMIN_IDS` | Telegram Bot | - |

---

## База данных

### Миграции

```bash
# Применить все миграции
make migrate

# Или напрямую через Alembic
docker compose exec free-ai-selector-data-postgres-api alembic upgrade head
```

### Seed данные

```bash
# Загрузить AI-модели
make seed
```

### Backup

```bash
# Создать backup
docker compose exec postgres pg_dump -U free_ai_selector_user free_ai_selector_db > backup.sql

# Восстановить
docker compose exec -T postgres psql -U free_ai_selector_user -d free_ai_selector_db < backup.sql
```

---

## Логирование

### Просмотр логов

```bash
# Все сервисы
make logs

# Конкретный сервис
make logs-business
make logs-data

# Следить за логами
docker compose logs -f free-ai-selector-business-api
```

### Формат логов (JSON)

```json
{
  "timestamp": "2025-01-20T12:00:00.000Z",
  "level": "INFO",
  "service": "business-api",
  "message": "Prompt processed successfully",
  "model": "DeepSeek Chat",
  "response_time": 1.234
}
```

---

## Мониторинг

### Health Worker

Health Worker выполняет каждый час:
1. Отправляет тестовые промпты всем провайдерам
2. Обновляет статистику в БД
3. Помечает недоступных провайдеров

### Проверка статуса

```bash
# Логи Health Worker
docker compose logs free-ai-selector-health-worker

# Статистика моделей
curl http://localhost:8000/api/v1/models/stats
```

---

## Troubleshooting

### Сервис не запускается

```bash
# Проверить логи
docker compose logs free-ai-selector-business-api

# Проверить зависимости
docker compose ps
```

### Ошибки подключения к БД

```bash
# Проверить PostgreSQL
docker compose exec postgres psql -U free_ai_selector_user -c "SELECT 1"

# Проверить connection string
echo $DATABASE_URL
```

### Провайдеры недоступны

```bash
# Тест провайдеров
curl -X POST http://localhost:8000/api/v1/providers/test

# Проверить API ключи
docker compose exec free-ai-selector-business-api env | grep API_KEY
```

---

## Полезные команды

```bash
# Остановить всё
make down

# Полная очистка (включая volumes)
docker compose down -v

# Shell в контейнере
make shell-business

# PostgreSQL shell
make db-shell

# Пересоздать контейнер
docker compose up -d --force-recreate free-ai-selector-business-api
```

---

## Related Documentation

- [Quick Start](quick-start.md) - Быстрый запуск
- [Troubleshooting](troubleshooting.md) - Решение проблем
- [../project/database-schema.md](../project/database-schema.md) - Схема БД
