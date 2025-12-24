# Troubleshooting Guide

> Руководство по решению типичных проблем Free AI Selector.

---

## Диагностика

### Быстрая проверка

```bash
# 1. Статус контейнеров
docker compose ps

# 2. Health endpoints
make health

# 3. Логи ошибок
docker compose logs --tail=50 | grep -i error
```

---

## Проблемы запуска

### Сервис не запускается

**Симптомы:** Контейнер в статусе `Restarting` или `Exited`

**Диагностика:**

```bash
docker compose logs free-ai-selector-business-api --tail=100
```

**Решения:**

| Ошибка в логах | Причина | Решение |
|----------------|---------|---------|
| `Connection refused` | Data API не готов | Подождать, проверить Data API |
| `Database not ready` | PostgreSQL не готов | `docker compose restart postgres` |
| `ModuleNotFoundError` | Зависимости не установлены | `make build` |

### PostgreSQL не запускается

**Диагностика:**

```bash
docker compose logs postgres
```

**Решения:**

```bash
# Проверить порт
lsof -i :5432

# Если порт занят, остановить локальный PostgreSQL
sudo systemctl stop postgresql

# Или изменить порт в docker-compose.yml
```

### Порты заняты

**Диагностика:**

```bash
# Проверить порты
lsof -i :8000
lsof -i :8001
lsof -i :5432
```

**Решение:**

```bash
# Остановить конфликтующие сервисы
sudo kill -9 $(lsof -t -i :8000)
```

---

## Проблемы с AI провайдерами

### Ошибка 503: All AI providers failed

**Причины:**
1. Все API ключи некорректны
2. Все провайдеры временно недоступны
3. Rate limit превышен у всех провайдеров

**Диагностика:**

```bash
# Тест провайдеров
curl -X POST http://localhost:8000/api/v1/providers/test

# Проверить логи
make logs-business | grep -i "provider\|error\|failed"
```

**Решения:**

```bash
# 1. Проверить API ключи
docker compose exec free-ai-selector-business-api env | grep API_KEY

# 2. Проверить .env файл
cat .env | grep -v "^#" | grep API

# 3. Перезапустить сервисы
make down && make up
```

### Rate Limit Exceeded

**Симптомы:** Ошибка 429 или сообщение "Rate limit exceeded"

**Решение:**

Система автоматически переключается на другой провайдер. Если все провайдеры заблокированы:

1. Подождите 1-5 минут
2. Проверьте лимиты провайдеров:

| Провайдер | RPM | RPD |
|-----------|-----|-----|
| Google Gemini | 10 | 250 |
| Groq | 20 | 14,400 |
| Cerebras | 30 | unlimited |
| SambaNova | 20 | unlimited |

### Invalid API Key

**Диагностика:**

```bash
curl -X POST http://localhost:8000/api/v1/providers/test | jq '.results[] | select(.success == false)'
```

**Решение:**

1. Проверить ключ в `.env`
2. Убедиться что нет пробелов: `API_KEY=key` (не `API_KEY = key`)
3. Проверить валидность ключа на сайте провайдера
4. Создать новый ключ если необходимо

### HuggingFace: Model is loading

**Симптомы:** Статус 503 с сообщением "Model is currently loading"

**Это нормально!** HuggingFace загружает модель по требованию.

**Решение:**
- Подождать 20-60 секунд
- Повторить запрос
- Система автоматически использует fallback на другой провайдер

---

## Проблемы с базой данных

### Ошибка подключения к БД

**Диагностика:**

```bash
# Проверить PostgreSQL
docker compose exec postgres psql -U free_ai_selector_user -d free_ai_selector_db -c "SELECT 1"

# Проверить Data API
curl http://localhost:8002/health
```

**Решения:**

```bash
# Перезапустить PostgreSQL
docker compose restart postgres

# Проверить connection string
docker compose exec free-ai-selector-data-postgres-api env | grep DATABASE
```

### Миграции не применяются

**Диагностика:**

```bash
docker compose exec free-ai-selector-data-postgres-api alembic current
```

**Решение:**

```bash
# Принудительно применить миграции
docker compose exec free-ai-selector-data-postgres-api alembic upgrade head

# Если ошибка - проверить логи
docker compose logs free-ai-selector-data-postgres-api | grep -i alembic
```

### Нет AI-моделей в БД

**Диагностика:**

```bash
curl http://localhost:8002/api/v1/models
# Ожидается: {"models": [...], "total": 6}
```

**Решение:**

```bash
make seed
```

---

## Проблемы с Telegram Bot

### Bot не отвечает

**Диагностика:**

```bash
docker compose logs free-ai-selector-telegram-bot --tail=50
```

**Решения:**

| Ошибка | Причина | Решение |
|--------|---------|---------|
| `Unauthorized` | Неверный токен | Проверить TELEGRAM_BOT_TOKEN |
| `Conflict: terminated by other getUpdates` | Bot запущен дважды | Остановить другие инстансы |
| `Connection refused` | Business API недоступен | Проверить Business API |

### Bot не получает сообщения

**Проверки:**

1. Отправьте `/start` боту
2. Проверьте что токен правильный
3. Проверьте что webhook не настроен (для polling mode)

```bash
# Проверить webhook
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo
```

---

## Проблемы с Docker

### Нехватка места

**Диагностика:**

```bash
docker system df
```

**Решение:**

```bash
# Очистка неиспользуемых ресурсов
docker system prune -a

# Очистка volumes
docker volume prune
```

### Контейнеры не видят друг друга

**Диагностика:**

```bash
docker compose exec free-ai-selector-business-api ping free-ai-selector-data-postgres-api
```

**Решение:**

```bash
# Пересоздать сеть
docker compose down
docker network prune
docker compose up -d
```

---

## Логи и отладка

### Включить debug логи

```bash
# В .env
LOG_LEVEL=DEBUG

# Перезапустить
make down && make up
```

### Просмотр логов конкретного сервиса

```bash
# Business API
docker compose logs -f free-ai-selector-business-api

# Data API
docker compose logs -f free-ai-selector-data-postgres-api

# Health Worker
docker compose logs -f free-ai-selector-health-worker
```

### Shell в контейнере

```bash
# Business API
make shell-business

# Data API
docker compose exec free-ai-selector-data-postgres-api /bin/bash

# PostgreSQL
make db-shell
```

---

## Чеклист диагностики

При любой проблеме проверьте по порядку:

- [ ] `docker compose ps` - все контейнеры Up и healthy
- [ ] `make health` - все endpoints отвечают
- [ ] `curl http://localhost:8002/api/v1/models` - есть модели в БД
- [ ] `curl -X POST .../providers/test` - провайдеры работают
- [ ] `.env` файл существует и содержит ключи
- [ ] `docker compose logs` - нет критических ошибок

---

## Получение помощи

Если проблема не решена:

1. Соберите логи: `docker compose logs > logs.txt`
2. Опишите проблему и шаги воспроизведения
3. Создайте Issue на GitHub

---

## Related Documentation

- [Deployment](deployment.md) - Развёртывание
- [API Keys](api-keys.md) - Настройка ключей
- [../api/errors.md](../api/errors.md) - Коды ошибок API
