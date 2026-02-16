# Deployment Guide

> Руководство по развёртыванию Free AI Selector в двух режимах: `local` (локальная разработка) и `vps` (VPS/proxy).

## Режимы запуска

| Режим | Compose файлы | Назначение | Доступ к API |
|-------|---------------|------------|--------------|
| `local` | `docker-compose.yml` + `docker-compose.override.yml` (авто) | Локальная разработка | Прямо через `localhost:8000/8001` |
| `vps` | `docker-compose.yml` + `docker-compose.vps.yml` | VPS/production за внешним reverse proxy | Через внешний nginx + `ROOT_PATH` |

Паттерн Docker Compose:
- базовый `docker-compose.yml` содержит все сервисы без портов;
- `docker-compose.override.yml` автоматически подгружается и добавляет порты для local;
- `docker-compose.vps.yml` явно указывается для VPS и добавляет `proxy-network`.

---

## Развёртывание (VPS/proxy режим)

```bash
# 1. Сборка
make build MODE=vps

# 2. Запуск
make vps

# 3. Проверка состояния
make status MODE=vps
make health MODE=vps

# 4. Инициализация БД
make migrate MODE=vps
make seed MODE=vps
```

Важно:
- в `vps` режиме порты API на host не публикуются;
- внешний nginx должен проксировать запросы в контейнер `free-ai-selector-business-api`;
- значение `ROOT_PATH` (например `/free-ai-selector`) должно совпадать с конфигурацией reverse proxy.

---

## Развёртывание (локальный режим)

```bash
# 1. Сборка
make build

# 2. Запуск
make local

# 3. Проверка состояния
make status
make health

# 4. Инициализация БД
make migrate
make seed
```

Локальные endpoint'ы:
- `http://localhost:8000/health`
- `http://localhost:8000/docs`
- `http://localhost:8001/health`
- `http://localhost:8001/docs`

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
make status MODE=vps
# или
make status
```

### Проверка health

```bash
# Внутриконтейнерная проверка (подходит для обоих режимов)
make health MODE=vps

# Для local дополнительно доступны host-проверки
curl http://localhost:8000/health
curl http://localhost:8001/health
```

### Проверка провайдеров

```bash
# local mode
curl -X POST http://localhost:8000/api/v1/providers/test

# vps mode
# Используйте URL reverse proxy с вашим ROOT_PATH
# Пример: https://example.com/free-ai-selector/api/v1/providers/test
```

---

## База данных

### Миграции

```bash
make migrate MODE=vps
# или
make migrate
```

### Seed данные

```bash
make seed MODE=vps
# или
make seed
```

### Backup

```bash
docker compose -f docker-compose.yml -f docker-compose.vps.yml exec postgres \
  pg_dump -U free_ai_selector_user free_ai_selector_db > backup.sql

docker compose -f docker-compose.yml -f docker-compose.vps.yml exec -T postgres \
  psql -U free_ai_selector_user -d free_ai_selector_db < backup.sql
```

---

## Логи и обслуживание

```bash
# Логи всех сервисов
make logs MODE=vps

# Логи конкретного сервиса
make logs-business MODE=vps
make logs-data MODE=vps

# Остановка
make down MODE=vps

# Полная очистка (включая volume)
docker compose -f docker-compose.yml -f docker-compose.vps.yml down -v
```

Для локального режима замените `MODE=vps` на `MODE=local` (или опустите — local по умолчанию).

---

## Troubleshooting

### Сервисы не поднимаются

```bash
make status MODE=vps
docker compose -f docker-compose.yml -f docker-compose.vps.yml logs free-ai-selector-business-api
```

### Ошибки подключения к БД

```bash
docker compose -f docker-compose.yml -f docker-compose.vps.yml exec postgres \
  psql -U free_ai_selector_user -c "SELECT 1"
```

### Провайдеры недоступны

```bash
docker compose -f docker-compose.yml -f docker-compose.vps.yml exec free-ai-selector-business-api env | grep API_KEY
```

---

## Related Documentation

- [Quick Start](quick-start.md) - Быстрый запуск
- [Troubleshooting](troubleshooting.md) - Решение проблем
- [../project/database-schema.md](../project/database-schema.md) - Схема БД
