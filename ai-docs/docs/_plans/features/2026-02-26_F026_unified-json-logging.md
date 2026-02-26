# План фичи: F026 — Унификация логов в единый JSON-формат

**Дата**: 2026-02-26
**FID**: F026
**PRD**: `_analysis/2026-02-26_F026_unified-json-logging.md`
**Research**: `_research/2026-02-26_F026_unified-json-logging.md`

---

## 1. Контекст

Логи в контейнерах business-api и data-api пишутся в 3 форматах (JSON, plain text, uvicorn), что ломает автоматический парсинг. Из 4 сервисов: health-worker и telegram-bot уже чистые (только structlog). Проблема сконцентрирована в business-api (5 файлов со stdlib) и data-api (2 файла со stdlib). Дополнительно — uvicorn дублирует middleware логи, а LOG_LEVEL env vars не маппятся.

---

## 2. Содержание

1. Обновить `logger.py` — добавить перехват stdlib logging
2. Заменить `logging.getLogger` → `get_logger` в Business API (5 файлов)
3. Заменить `logging.getLogger` → `get_logger` в Data API (2 файла)
4. Отключить uvicorn access log (2 Dockerfile)
5. Стандартизировать f-string → structured events
6. Исправить LOG_LEVEL env var disconnect

---

## 3. Краткая версия плана

### Этап 1: Обновить `logger.py` — добавить перехват stdlib logging

1. **Проблема** — Сторонние библиотеки (httpx, asyncio, uvicorn.error) пишут через stdlib logging мимо structlog, выводя plain text вместо JSON.
2. **Действие** — Добавить в `setup_logging()` перехват stdlib root logger через `structlog.stdlib.ProcessorFormatter`, чтобы все stdlib-логи проходили через structlog pipeline.
3. **Результат** — Любой вызов `logging.getLogger().info()` из любой библиотеки будет рендериться в JSON.
4. **Зависимости** — Нет, первый этап.
5. **Риски** — Сторонние библиотеки могут генерировать много debug-логов; нужно установить root logger уровень на WARNING.
6. **Без этого** — Логи httpx, asyncio, uvicorn.error останутся в plain text.

### Этап 2: Заменить stdlib → structlog в Business API (5 файлов)

1. **Проблема** — 5 файлов Business API используют `logging.getLogger()`: base.py, cloudflare.py, data_api_client.py, models.py, providers.py. Их логи не содержат request_id, run_id и не проходят через sensitive_filter.
2. **Действие** — Заменить `import logging` / `logging.getLogger(__name__)` на `from app.utils.logger import get_logger` / `get_logger(__name__)`. Адаптировать f-string вызовы на structlog стиль.
3. **Результат** — Все логи AI-провайдеров, HTTP-клиента, API routes выходят в JSON с полным контекстом.
4. **Зависимости** — После Этапа 1 (чтобы не было двойного перехвата).
5. **Риски** — Баг в cloudflare.py с kwargs: при переходе на structlog kwargs станут работать правильно. В base.py `extra={}` нужно заменить на kwargs.
6. **Без этого** — 16 точек логирования в business-api остаются в plain text без request_id.

### Этап 3: Заменить stdlib → structlog в Data API (2 файла)

1. **Проблема** — seed.py и migrate_to_new_providers.py используют stdlib с `logging.basicConfig()`. Эти файлы запускаются и как standalone скрипты (через entrypoint.sh), и в контексте FastAPI.
2. **Действие** — Заменить на `get_logger()`. Удалить `logging.basicConfig()`. Добавить `setup_logging()` в начало standalone-функций (seed_database, run_migration).
3. **Результат** — Логи seed/migration выходят в JSON.
4. **Зависимости** — После Этапа 1.
5. **Риски** — Standalone-запуск (через entrypoint.sh) может не вызывать setup_logging(); нужно добавить вызов.
6. **Без этого** — Логи миграций и seed в plain text.

### Этап 4: Отключить uvicorn access log (2 Dockerfile)

1. **Проблема** — Uvicorn пишет `INFO: 127.0.0.1 - "GET /health" 200 OK` для каждого запроса — дублирует middleware request_started/request_completed.
2. **Действие** — Добавить `--no-access-log` к CMD в Dockerfile business-api и data-api.
3. **Результат** — ~30% меньше строк, нет дублирования, нет plain text.
4. **Зависимости** — Независим (можно параллельно).
5. **Риски** — Нет. Middleware полностью покрывает функциональность access log с доп. полями.
6. **Без этого** — Дублирование каждого HTTP-запроса в логах.

### Этап 5: Стандартизировать f-string → structured events

1. **Проблема** — ~12 мест в test_all_providers.py и prompts.py используют `logger.info(f"Testing provider: {name}")` вместо `logger.info("testing_provider", provider=name)`.
2. **Действие** — Заменить f-string events на snake_case event names + kwargs. Убрать эмодзи из event messages.
3. **Результат** — Все events фильтруемы по `event == "testing_provider"`. Данные доступны как отдельные JSON-поля.
4. **Зависимости** — После Этапа 2 (файлы уже будут правиться).
5. **Риски** — Нет. Чисто стилистическое изменение.
6. **Без этого** — События нефильтруемы по имени, данные вшиты в строку.

### Этап 6: Исправить LOG_LEVEL env var disconnect

1. **Проблема** — docker-compose прокидывает `BUSINESS_API_LOG_LEVEL`, `DATA_API_LOG_LEVEL` и т.д., но logger.py читает `LOG_LEVEL`. Переменные с префиксом не работают.
2. **Действие** — В logger.py добавить fallback: сначала читать `LOG_LEVEL`, затем проверить типовые варианты через `SERVICE_NAME`. Или проще: добавить `LOG_LEVEL: ${BUSINESS_API_LOG_LEVEL:-INFO}` в docker-compose для каждого сервиса.
3. **Результат** — Уровень логирования настраивается через docker-compose.
4. **Зависимости** — Независим.
5. **Риски** — Минимальный. Маппинг env vars — безрисковое изменение.
6. **Без этого** — LOG_LEVEL всегда INFO, нельзя переключить на DEBUG/WARNING через docker-compose.

---

## 4. Полная версия плана

## Этап 1: Обновить `logger.py` — добавить перехват stdlib logging

**Файл**: `app/utils/logger.py` (идентичен в 4 сервисах, меняем 1 раз → копируем)

**Изменение**: В функцию `setup_logging()` после `structlog.configure()` добавить:

```python
import sys

def setup_logging(service_name: str) -> None:
    # ... существующий код structlog.configure() ...

    # Перехват stdlib logging → structlog JSON
    # Все логи от сторонних библиотек (httpx, asyncio, uvicorn.error)
    # проходят через structlog processors и рендерятся в JSON.
    stdlib_handler = logging.StreamHandler(sys.stdout)
    stdlib_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                sanitize_sensitive_data,
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer() if json_logs
                else structlog.dev.ConsoleRenderer(colors=True),
            ],
        )
    )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(stdlib_handler)
    root_logger.setLevel(logging.getLevelName(LOG_LEVEL))

    # Подавить шумные логи сторонних библиотек
    for noisy in ("httpx", "httpcore", "asyncio", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    structlog.contextvars.bind_contextvars(service=service_name)
```

**Копирование**: После изменения скопировать в 4 сервиса:
- `services/free-ai-selector-business-api/app/utils/logger.py`
- `services/free-ai-selector-data-postgres-api/app/utils/logger.py`
- `services/free-ai-selector-health-worker/app/utils/logger.py`
- `services/free-ai-selector-telegram-bot/app/utils/logger.py`

---

## Этап 2: Заменить stdlib → structlog в Business API (5 файлов)

### 2.1 `app/infrastructure/ai_providers/base.py`

**Строка 20**: Заменить:
```python
# Было:
import logging
logger = logging.getLogger(__name__)

# Стало:
from app.utils.logger import get_logger
logger = get_logger(__name__)
```

**Вызовы** (4 места):
```python
# Было (f-string):
logger.error(f"Unexpected {self.PROVIDER_NAME} response: {err_msg}")

# Стало (structured):
logger.error("unexpected_response", provider=self.PROVIDER_NAME, error=err_msg)
```

```python
# Было (extra={}):
logger.warning("response_format_not_supported", extra={"provider": self.PROVIDER_NAME, ...})

# Стало (kwargs):
logger.warning("response_format_not_supported", provider=self.PROVIDER_NAME, requested_format=response_format)
```

### 2.2 `app/infrastructure/ai_providers/cloudflare.py`

**Строка 18**: Аналогичная замена import.

**Вызовы** (3 + kwargs баг):
```python
# Было (kwargs баг — stdlib игнорирует):
logger.warning("response_format_not_supported", provider=self.get_provider_name(), requested_format=response_format)

# Стало (structlog принимает kwargs):
logger.warning("response_format_not_supported", provider=self.get_provider_name(), requested_format=response_format)
# ↑ Код тот же, но теперь работает корректно через structlog
```

### 2.3 `app/infrastructure/http_clients/data_api_client.py`

**Строка 19**: Замена import.

**Вызовы** (6 мест) — все f-string:
```python
# Было:
logger.error(f"Failed to fetch models from Data API: {sanitize_error_message(e)}")

# Стало:
logger.error("data_api_fetch_models_failed", error=sanitize_error_message(e))
```

### 2.4 `app/api/v1/models.py`

**Строка 13**: Замена import.

**Вызовы** (1 место):
```python
# Было:
logger.error(f"Failed to fetch models statistics: {sanitize_error_message(e)}")

# Стало:
logger.error("fetch_models_statistics_failed", error=sanitize_error_message(e))
```

### 2.5 `app/api/v1/providers.py`

**Строка 15**: Замена import.

**Вызовы** (2 места):
```python
# Было:
logger.info(f"Provider testing completed: {successful}/{len(results)} successful")

# Стало:
logger.info("provider_testing_completed", successful=successful, total=len(results))
```

---

## Этап 3: Заменить stdlib → structlog в Data API (2 файла)

### 3.1 `app/infrastructure/database/seed.py`

**Строки 23-24**: Удалить `logging.basicConfig(level=logging.INFO)`. Заменить import:
```python
# Было:
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Стало:
from app.utils.logger import setup_logging, get_logger
logger = get_logger(__name__)
```

**В функции `seed_database()` (или `async_seed_database()`)** добавить в начало:
```python
setup_logging("free-ai-selector-data-postgres-api")
```

**Вызовы** (7 мест): f-string → structured.

### 3.2 `app/infrastructure/database/migrate_to_new_providers.py`

Аналогично seed.py: удалить `logging.basicConfig`, заменить import, добавить `setup_logging()`.

---

## Этап 4: Отключить uvicorn access log (2 Dockerfile)

### 4.1 Business API Dockerfile (строка 39)

```dockerfile
# Было:
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Стало:
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
```

### 4.2 Data API Dockerfile (строка 46)

```dockerfile
# Было:
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]

# Стало:
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--no-access-log"]
```

---

## Этап 5: Стандартизировать f-string → structured events

### 5.1 `app/application/use_cases/test_all_providers.py` (~10 мест)

```python
# Было:
logger.info(f"Fetched {len(models)} active models from Data API")
logger.info(f"Testing provider: {model.provider}")
logger.info(f"✅ {model.provider} responded in {response_time:.2f}s (chars={len(response)})")
logger.warning(f"⚠️ {model.provider} returned empty response")
logger.error(f"❌ {model.provider} failed: {error_type}: {error_message}")

# Стало:
logger.info("fetched_models", count=len(models))
logger.info("testing_provider", provider=model.provider)
logger.info("provider_success", provider=model.provider, duration_s=round(response_time, 2), response_chars=len(response))
logger.warning("provider_empty_response", provider=model.provider)
logger.error("provider_failed", provider=model.provider, error_type=error_type, error=error_message)
```

### 5.2 `app/api/v1/prompts.py` (1 место)

```python
# Было:
logger.error(f"Failed to process prompt: {sanitize_error_message(e)}")

# Стало:
logger.error("process_prompt_failed", error=sanitize_error_message(e))
```

---

## Этап 6: Исправить LOG_LEVEL env var disconnect

**Файл**: `docker-compose.yml`

Для каждого сервиса добавить маппинг в секцию environment:

```yaml
free-ai-selector-data-postgres-api:
  environment:
    LOG_LEVEL: ${DATA_API_LOG_LEVEL:-INFO}

free-ai-selector-business-api:
  environment:
    LOG_LEVEL: ${BUSINESS_API_LOG_LEVEL:-INFO}

free-ai-selector-telegram-bot:
  environment:
    LOG_LEVEL: ${TELEGRAM_BOT_LOG_LEVEL:-INFO}

free-ai-selector-health-worker:
  environment:
    LOG_LEVEL: ${WORKER_LOG_LEVEL:-INFO}
```

---

## 5. Влияние на существующие тесты

- **Unit-тесты**: Не ломаются — логирование не является предметом тестов. Замена import не влияет на поведение.
- **Integration-тесты**: Не ломаются — формат логов не проверяется в тестах.
- **Smoke-тесты**: Нужно добавить проверку что все строки `docker logs` — JSON (TRQ-005).

---

## 6. План интеграции

| # | Шаг | Зависимости | Файлов |
|---|-----|-------------|--------|
| 1 | Обновить logger.py (4 копии) | — | 4 |
| 2 | Заменить stdlib в Business API | Этап 1 | 5 |
| 3 | Заменить stdlib в Data API | Этап 1 | 2 |
| 4 | --no-access-log в Dockerfile | — | 2 |
| 5 | f-string → structured events | Этапы 2-3 | 2 |
| 6 | LOG_LEVEL маппинг | — | 1 |

**Итого**: ~16 файлов, можно выполнить за 1 сессию.

---

## 7. Риски и митигация

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| seed.py не вызывает setup_logging() при standalone-запуске | Средняя | Добавить вызов setup_logging() в начало функций |
| Шумные debug-логи от httpx/asyncio | Средняя | Установить logging.getLogger("httpx").setLevel(WARNING) |
| Двойной вывод при перехвате (structlog + stdlib оба в stdout) | Низкая | root_logger.handlers.clear() перед добавлением нового handler |
| Rebuild Docker образов | Низкая | Штатная процедура `make build` |
