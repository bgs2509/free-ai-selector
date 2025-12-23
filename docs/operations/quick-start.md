# Quick Start Guide

> Быстрый запуск Free AI Selector за 5 минут.

## Требования

| Компонент | Версия | Проверка |
|-----------|--------|----------|
| Docker | 24.0+ | `docker --version` |
| Docker Compose | 2.0+ | `docker compose version` |
| Git | 2.0+ | `git --version` |

---

## Шаг 1: Клонирование репозитория

```bash
git clone https://github.com/yourusername/free-ai-selector.git
cd free-ai-selector
```

---

## Шаг 2: Настройка окружения

### Создание .env файла

```bash
cp .env.example .env
```

### Минимальная конфигурация

Отредактируйте `.env` и добавьте хотя бы 2-3 API ключа:

```bash
# Обязательно: минимум 2-3 провайдера для fallback
GOOGLE_AI_STUDIO_API_KEY=AIzaSy...
GROQ_API_KEY=gsk_...
CEREBRAS_API_KEY=...

# Опционально: Telegram бот
TELEGRAM_BOT_TOKEN=...
```

> **Подробная инструкция:** [api-keys.md](api-keys.md)

---

## Шаг 3: Запуск сервисов

```bash
# Собрать Docker образы
make build

# Запустить все сервисы
make up
```

Подождите ~30 секунд для инициализации.

---

## Шаг 4: Проверка здоровья

```bash
make health
```

Ожидаемый вывод:

```
✅ PostgreSQL: Ready
✅ Data API (http://localhost:8001/health): Healthy
✅ Business API (http://localhost:8000/health): Healthy
```

---

## Шаг 5: Инициализация БД

```bash
# Применить миграции
make migrate

# Загрузить AI-модели
make seed
```

---

## Шаг 6: Тестирование

### REST API

```bash
# Обработать промпт
curl -X POST http://localhost:8000/api/v1/prompts/process \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Привет! Напиши короткое стихотворение об AI"}'
```

### Пример ответа

```json
{
  "prompt_text": "Привет! Напиши короткое стихотворение об AI",
  "response_text": "В мире битов и цифр живёт разум стальной...",
  "selected_model_name": "Gemini 2.5 Flash",
  "selected_model_provider": "GoogleGemini",
  "response_time_seconds": 1.234,
  "success": true,
  "error_message": null
}
```

### Статистика моделей

```bash
curl http://localhost:8000/api/v1/models/stats
```

---

## Telegram Bot (опционально)

1. Получить токен у [@BotFather](https://t.me/BotFather)
2. Добавить в `.env`: `TELEGRAM_BOT_TOKEN=...`
3. Перезапустить: `make down && make up`
4. Найти бота в Telegram и отправить `/start`

---

## Что дальше?

| Задача | Документ |
|--------|----------|
| Настроить все API ключи | [api-keys.md](api-keys.md) |
| Деплой в production | [deployment.md](deployment.md) |
| Решение проблем | [troubleshooting.md](troubleshooting.md) |
| API Reference | [../api/business-api.md](../api/business-api.md) |

---

## Полезные команды

```bash
make logs           # Все логи
make logs-business  # Логи Business API
make down           # Остановить сервисы
make test           # Запустить тесты
make lint           # Проверка кода
```

---

## Related Documentation

- [Deployment](deployment.md) - Полный деплой
- [API Keys](api-keys.md) - Настройка ключей
- [../api/business-api.md](../api/business-api.md) - API Reference
