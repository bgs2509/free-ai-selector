# Research: F026 — Унификация логов в единый JSON-формат

**Дата**: 2026-02-26
**FID**: F026
**PRD**: `_analysis/2026-02-26_F026_unified-json-logging.md`

---

## 1. Текущая конфигурация structlog

Файл `app/utils/logger.py` **идентичен** во всех 4 сервисах (68 строк):

- `LOG_LEVEL` = `os.getenv("LOG_LEVEL", "INFO")`
- `LOG_FORMAT` = `os.getenv("LOG_FORMAT", "json")`
- Процессоры: `merge_contextvars` → `sanitize_sensitive_data` → `add_log_level` → `TimeStamper(iso)` → `JSONRenderer`
- Фабрика: `PrintLoggerFactory()` (пишет в stdout через `print()`)
- **Нет интеграции со stdlib logging** — `structlog.stdlib.ProcessorFormatter` не используется

---

## 2. Инвентаризация проблемных файлов

### 2.1 Файлы с `logging.getLogger()` (stdlib) — 7 файлов

| # | Сервис | Файл | Строка | f-string вызовов |
|---|--------|------|--------|------------------|
| 1 | Business API | `app/infrastructure/ai_providers/base.py` | 20 | 4 |
| 2 | Business API | `app/infrastructure/ai_providers/cloudflare.py` | 18 | 3 + kwargs баг |
| 3 | Business API | `app/api/v1/models.py` | 13 | 1 |
| 4 | Business API | `app/api/v1/providers.py` | 15 | 2 |
| 5 | Business API | `app/infrastructure/http_clients/data_api_client.py` | 19 | 6 |
| 6 | Data API | `app/infrastructure/database/seed.py` | 24 | 7 |
| 7 | Data API | `app/infrastructure/database/migrate_to_new_providers.py` | 23 | 5 |

**Health Worker и Telegram Bot** — чистые, используют только `get_logger()`.

### 2.2 Файлы с `get_logger()` (structlog) — корректные

| Сервис | Файлы |
|--------|-------|
| Business API | `main.py`, `prompts.py`, `process_prompt.py`, `test_all_providers.py`, `retry_service.py`, `circuit_breaker.py` |
| Data API | `main.py` |
| Health Worker | `main.py` |
| Telegram Bot | `main.py` |

### 2.3 f-string вызовы в structlog-файлах — 12 мест

| Файл | Примеры |
|------|---------|
| `test_all_providers.py` | `logger.info(f"Testing provider: {model.provider}")`, `logger.info(f"✅ {model.provider} responded...")`, `logger.error(f"❌ {model.provider} failed...")` — **~10 мест** |
| `prompts.py` | `logger.error(f"Failed to process prompt: ...")` — 1 место |
| `process_prompt.py` | нет f-string (все structured) |

### 2.4 Дополнительные проблемы

**`logging.basicConfig()` в Data API** — 2 файла:
- `seed.py:23` — `logging.basicConfig(level=logging.INFO)`
- `migrate_to_new_providers.py:22` — `logging.basicConfig(level=logging.INFO)`

Эти вызовы конфигурируют stdlib root logger и могут конфликтовать при перехвате.

**`cloudflare.py` kwargs баг** (строки 102-106):
```python
logger.warning(
    "response_format_not_supported",
    provider=self.get_provider_name(),  # stdlib игнорирует kwargs
    requested_format=response_format,
)
```

---

## 3. Uvicorn access log

### Сервисы с uvicorn

| Сервис | Dockerfile CMD | Порт |
|--------|---------------|------|
| Business API | `uvicorn app.main:app --host 0.0.0.0 --port 8000` | 8000 |
| Data API | `uvicorn app.main:app --host 0.0.0.0 --port 8001` | 8001 |

Оба **без** `--no-access-log`, `--log-config`, `--log-level`.

### Сервисы без uvicorn

| Сервис | CMD | Формат |
|--------|-----|--------|
| Health Worker | `python -m app.main` (APScheduler) | Чистый structlog |
| Telegram Bot | `python -m app.main` (aiogram polling) | Чистый structlog |

---

## 4. ENV-переменные для логирования

### docker-compose.yml прокидывает

| Сервис | ENV var | Значение |
|--------|---------|----------|
| Data API | `DATA_API_LOG_LEVEL` | `${DATA_API_LOG_LEVEL}` |
| Business API | `BUSINESS_API_LOG_LEVEL` | `${BUSINESS_API_LOG_LEVEL}` |
| Telegram Bot | `TELEGRAM_BOT_LOG_LEVEL` | `${TELEGRAM_BOT_LOG_LEVEL}` |
| Health Worker | `WORKER_LOG_LEVEL` | `${WORKER_LOG_LEVEL}` |

### logger.py читает

```python
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")  # ← Не совпадает с docker-compose!
```

**Disconnect**: Docker-compose прокидывает `BUSINESS_API_LOG_LEVEL`, а logger.py читает `LOG_LEVEL`. Переменные с префиксом **нигде не маппятся** на `LOG_LEVEL`.

### LOG_FORMAT — не прокидывается

Ни один сервис не имеет `LOG_FORMAT` в docker-compose. Всегда default `"json"`.

---

## 5. Вспомогательные модули (сравнение между сервисами)

| Модуль | Business API | Data API | Health Worker | Telegram Bot |
|--------|-------------|----------|---------------|--------------|
| `logger.py` | ✅ (68 строк) | ✅ идентичен | ✅ идентичен | ✅ идентичен |
| `sensitive_filter.py` | ✅ | ✅ | ✅ | ✅ |
| `request_id.py` | ✅ (полная: run_*) | ✅ идентичен | ❌ нет | ⚠️ урезанная (без run_*) |
| `log_helpers.py` | ✅ | ❌ нет (inline) | ❌ нет | ❌ нет |
| `audit.py` | ✅ | ✅ | ✅ | ❌ нет |

---

## 6. Middleware request logging

| Сервис | Реализация | Уровень по status_code |
|--------|-----------|------------------------|
| Business API | `log_helpers.py` | ✅ error для 5xx, warning для 4xx, info для 2xx |
| Data API | Inline в main.py | ❌ всегда info |
| Health Worker | Нет HTTP (APScheduler) | N/A |
| Telegram Bot | Нет HTTP (aiogram) | N/A |

---

## 7. Объём изменений (оценка)

| Категория | Файлов | Изменений |
|-----------|--------|-----------|
| Замена `logging.getLogger` → `get_logger` | 7 | ~40 вызовов адаптировать |
| Добавить stdlib перехват в `logger.py` | 1 (shared × 4) | ~15 строк |
| `--no-access-log` в Dockerfile | 2 | 1 строка каждый |
| f-string → structured events | 3 файла | ~12 вызовов |
| Удалить `logging.basicConfig()` | 2 | 1 строка каждый |
| Fix LOG_LEVEL env disconnect | 4 сервиса | docker-compose.yml или logger.py |

**Итого**: ~15 файлов, ~80 точечных изменений.

---

## 8. Риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| `seed.py` и `migrate_to_new_providers.py` запускаются как standalone скрипты (не через FastAPI) — structlog может быть не инициализирован | Средняя | Средний | Добавить `setup_logging()` в начало скриптов или оставить stdlib с перехватом |
| Сторонние библиотеки (httpx, aiogram, apscheduler) генерируют много debug-логов через stdlib | Средняя | Низкий | Установить уровень root logger на INFO/WARNING |
| Изменение формата логов ломает внешние инструменты | Низкая | Низкий | Нет внешних инструментов парсящих plain text |

---

## 9. Рекомендации

1. **Приоритет 1**: Изменить `logger.py` (1 раз, скопировать в 4 сервиса) — добавить перехват stdlib
2. **Приоритет 2**: Заменить 7 файлов `logging.getLogger` → `get_logger`
3. **Приоритет 3**: `--no-access-log` в 2 Dockerfile
4. **Приоритет 4**: f-string → structured events (12 мест)
5. **Приоритет 5**: Маппинг `{SERVICE}_LOG_LEVEL` → `LOG_LEVEL` в docker-compose или logger.py
6. **Вне скоупа F026**: DRY shared library (отдельная фича), синхронизация request_id.py
