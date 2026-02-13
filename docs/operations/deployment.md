# Deployment Guide

> Руководство по развёртыванию Free AI Selector в двух режимах: `nginx` (VPS/proxy) и `loc` (локальная разработка).

## Режимы запуска

| Режим | Compose файл | Назначение | Доступ к API |
|-------|--------------|------------|--------------|
| `nginx` | `docker-compose.nginx.yml` | VPS/production за внешним reverse proxy | Через внешний nginx + `ROOT_PATH` |
| `loc` | `docker-compose.loc.yml` | Локальная разработка без nginx | Прямо через `localhost:8000/8001` |

Почему сделано именно так:
- два независимых compose-файла проще читать и сопровождать;
- нет скрытого merge-поведения override-конфигов;
- меньше риск случайно открыть production-порты на VPS.

---

## Развёртывание (VPS/proxy режим)

```bash
# 1. Сборка
make build MODE=nginx

# 2. Запуск
make nginx

# 3. Проверка состояния
make status MODE=nginx
make health MODE=nginx

# 4. Инициализация БД
make migrate MODE=nginx
make seed MODE=nginx
```

Важно:
- в `nginx` режиме порты API на host не публикуются;
- внешний nginx должен проксировать запросы в контейнер `free-ai-selector-business-api`;
- значение `ROOT_PATH` (например `/free-ai-selector`) должно совпадать с конфигурацией reverse proxy.

---

## Развёртывание (локальный режим)

```bash
# 1. Сборка
make build MODE=loc

# 2. Запуск
make loc

# 3. Проверка состояния
make status MODE=loc
make health MODE=loc

# 4. Инициализация БД
make migrate MODE=loc
make seed MODE=loc
```

Локальные endpoint'ы:
- `http://localhost:8000/health`
- `http://localhost:8000/docs`
- `http://localhost:8001/health`
- `http://localhost:8001/docs`

---

## Порядок запуска сервисов

Оба compose-файла используют одинаковую последовательность зависимостей:
1. `postgres`
2. `free-ai-selector-data-postgres-api`
3. `free-ai-selector-business-api`
4. `free-ai-selector-telegram-bot`

`free-ai-selector-health-worker` зависит от Data API и стартует после него.

---

## Проверка развёртывания

### Статус контейнеров

```bash
make status MODE=nginx
# или
make status MODE=loc
```

### Проверка health

```bash
# Внутриконтейнерная проверка (подходит для обоих режимов)
make health MODE=nginx

# Для loc дополнительно доступны host-проверки
curl http://localhost:8000/health
curl http://localhost:8001/health
```

### Проверка провайдеров

```bash
# loc mode
curl -X POST http://localhost:8000/api/v1/providers/test

# nginx mode
# Используйте URL reverse proxy с вашим ROOT_PATH
# Пример: https://example.com/free-ai-selector/api/v1/providers/test
```

---

## База данных

### Миграции

```bash
make migrate MODE=nginx
# или
make migrate MODE=loc
```

### Seed данные

```bash
make seed MODE=nginx
# или
make seed MODE=loc
```

### Backup

```bash
docker compose -f docker-compose.nginx.yml exec postgres \
  pg_dump -U free_ai_selector_user free_ai_selector_db > backup.sql

docker compose -f docker-compose.nginx.yml exec -T postgres \
  psql -U free_ai_selector_user -d free_ai_selector_db < backup.sql
```

---

## Логи и обслуживание

```bash
# Логи всех сервисов
make logs MODE=nginx

# Логи конкретного сервиса
make logs-business MODE=nginx
make logs-data MODE=nginx

# Остановка
make down MODE=nginx

# Полная очистка (включая volume)
docker compose -f docker-compose.nginx.yml down -v
```

Для локального режима замените `MODE=nginx` на `MODE=loc`.

---

## Troubleshooting

### Сервисы не поднимаются

```bash
make status MODE=nginx
docker compose -f docker-compose.nginx.yml logs free-ai-selector-business-api
```

### Ошибки подключения к БД

```bash
docker compose -f docker-compose.nginx.yml exec postgres \
  psql -U free_ai_selector_user -c "SELECT 1"
```

### Провайдеры недоступны

```bash
docker compose -f docker-compose.nginx.yml exec free-ai-selector-business-api env | grep API_KEY
```

---

## Related Documentation

- [Quick Start](quick-start.md) - Быстрый запуск
- [Troubleshooting](troubleshooting.md) - Решение проблем
- [../project/database-schema.md](../project/database-schema.md) - Схема БД
