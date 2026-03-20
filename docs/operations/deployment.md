# Deployment Guide

> Руководство по развёртыванию Free AI Selector. Единый `docker-compose.yml` для всех окружений.

## Конфигурация

Проект использует единый `docker-compose.yml` для всех окружений. Различия между локальной разработкой и VPS задаются через значения в `.env`.

---

## Развёртывание

```bash
# 1. Сборка
make build

# 2. Запуск
make up

# 3. Проверка состояния
make status
make health

# 4. Инициализация БД
make migrate
make seed
```

Endpoint'ы:
- `http://localhost:8020/health`
- `http://localhost:8020/docs`
- `http://localhost:8021/health`
- `http://localhost:8021/docs`

Для VPS с внешним reverse proxy:
- внешний nginx должен проксировать запросы в `localhost:8020`;
- значение `ROOT_PATH` (например `/free-ai-selector`) должно совпадать с конфигурацией reverse proxy.

---

## Порядок запуска сервисов

Базовый `docker-compose.yml` определяет единую последовательность зависимостей:
1. `postgres`
2. `free-ai-selector-data-postgres-api`
3. `free-ai-selector-business-api`
4. `free-ai-selector-telegram-bot`

`free-ai-selector-health-worker` зависит от Data API и стартует после него.

---

## Проверка развёртывания

### Статус контейнеров

```bash
make status
```

### Проверка health

```bash
make health

# Host-проверки
curl http://localhost:8020/health
curl http://localhost:8021/health
```

### Проверка провайдеров

```bash
curl -X POST http://localhost:8020/api/v1/providers/test

# Через reverse proxy (VPS)
# Пример: https://example.com/free-ai-selector/api/v1/providers/test
```

---

## База данных

### Миграции

```bash
make migrate
```

### Seed данные

```bash
make seed
```

### Backup

```bash
docker compose exec postgres \
  pg_dump -U free_ai_selector_user free_ai_selector_db > backup.sql

docker compose exec -T postgres \
  psql -U free_ai_selector_user -d free_ai_selector_db < backup.sql
```

---

## Логи и обслуживание

```bash
# Логи всех сервисов
make logs

# Логи конкретного сервиса
make logs-business
make logs-data

# Остановка
make down

# Полная очистка (включая volume)
docker compose down -v
```

---

## Troubleshooting

### Сервисы не поднимаются

```bash
make status
docker compose logs free-ai-selector-business-api
```

### Ошибки подключения к БД

```bash
docker compose exec postgres \
  psql -U free_ai_selector_user -c "SELECT 1"
```

### Провайдеры недоступны

```bash
docker compose exec free-ai-selector-business-api env | grep API_KEY
```

---

## Related Documentation

- [Quick Start](quick-start.md) - Быстрый запуск
- [Troubleshooting](troubleshooting.md) - Решение проблем
- [../project/database-schema.md](../project/database-schema.md) - Схема БД
