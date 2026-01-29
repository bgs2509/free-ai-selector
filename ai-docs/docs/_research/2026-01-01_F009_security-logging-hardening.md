# Исследование: F009 Security Hardening & Reverse Proxy Alignment

**Дата**: 2026-01-01
**Исследователь**: AI Agent (Researcher)
**Feature ID**: F009
**Статус**: RESEARCH_DONE

---

## 1. Резюме

| Аспект | Текущее состояние | Best Practice (.aidd) |
|--------|-------------------|----------------------|
| Фильтрация секретов | Ручной вызов `sanitize_error_message()` | SensitiveDataFilter в structlog chain |
| Количество вызовов | 133 вызова в 36 файлах | 0 вызовов (автоматически) |
| ROOT_PATH (Business API) | ✅ Реализован | ✅ Соответствует |
| ROOT_PATH (Data API) | ❌ Отсутствует | Требуется добавить |
| StaticFiles mount | Двойной hardcode | Один mount `/static` |

---

## 2. Анализ: SensitiveDataFilter

### 2.1 Текущая реализация (`security.py`)

**Файл**: `services/*/app/utils/security.py`

```python
def sanitize_error_message(error: Union[Exception, str]) -> str:
    """Sanitize error messages to remove sensitive information before logging."""
    # 12 паттернов: Google keys, OpenAI, HuggingFace, Groq, Bearer tokens, etc.
    ...
```

**Проблема**: Функция вызывается **вручную** в 133 местах:

| Сервис | Файлов | Вызовов |
|--------|--------|---------|
| Business API | 19 | ~70 |
| Data API | 5 | ~15 |
| Health Worker | 2 | ~9 |
| Telegram Bot | 2 | ~5 |
| utils/__init__.py | 4 | 4 (re-export) |
| security.py | 4 | 4 (определение) |
| **ИТОГО** | 36 | 133 |

**Примеры ручных вызовов**:

```python
# services/free-ai-selector-business-api/app/main.py:111
logger.error("data_api_connection_failed", error=sanitize_error_message(e))

# services/free-ai-selector-health-worker/app/main.py
logger.error("health_check_failed", error=sanitize_error_message(e))
```

**Риск**: Разработчик может забыть вызвать `sanitize_error_message()` → утечка секрета в логи.

### 2.2 Best Practice: SensitiveDataFilter

**Файл**: `.aidd/templates/shared/utils/logger.py`

```python
# structlog processor - автоматическая фильтрация
def sanitize_sensitive_data(logger, method_name, event_dict):
    return _sanitize_dict(event_dict)

# В setup_logging():
shared_processors = [
    structlog.contextvars.merge_contextvars,
    add_tracing_context,
    sanitize_sensitive_data,  # ← АВТОМАТИЧЕСКИ для ВСЕХ логов
    structlog.processors.add_log_level,
    ...
]
```

**Преимущества**:
- Defensive-in-depth: невозможно забыть
- Централизованная логика фильтрации
- Рекурсивная обработка nested dict/list

### 2.3 Gap Analysis: SENSITIVE_FIELD_NAMES

| Поле в .aidd шаблоне | Поле в проекте (.env.example) | Статус |
|---------------------|-------------------------------|--------|
| `api_key` | ✅ | Покрыт |
| `token` | ✅ | Покрыт |
| `password` | ✅ | Покрыт |
| `database_url` | `DATABASE_URL` | Покрыт |
| `telegram_bot_token` | `TELEGRAM_BOT_TOKEN` | Покрыт |
| — | `GOOGLE_AI_STUDIO_API_KEY` | ❌ Нужно добавить |
| — | `GROQ_API_KEY` | ❌ Нужно добавить |
| — | `CEREBRAS_API_KEY` | ❌ Нужно добавить |
| — | `SAMBANOVA_API_KEY` | ❌ Нужно добавить |
| — | `HUGGINGFACE_API_KEY` | ❌ Нужно добавить |
| — | `CLOUDFLARE_API_TOKEN` | ❌ Нужно добавить |
| — | `DEEPSEEK_API_KEY` | ❌ Нужно добавить |
| — | `COHERE_API_KEY` | ❌ Нужно добавить |
| — | `OPENROUTER_API_KEY` | ❌ Нужно добавить |
| — | `GITHUB_TOKEN` | ❌ Нужно добавить |
| — | `FIREWORKS_API_KEY` | ❌ Нужно добавить |
| — | `HYPERBOLIC_API_KEY` | ❌ Нужно добавить |
| — | `NOVITA_API_KEY` | ❌ Нужно добавить |
| — | `SCALEWAY_API_KEY` | ❌ Нужно добавить |
| — | `KLUSTER_API_KEY` | ❌ Нужно добавить |
| — | `NEBIUS_API_KEY` | ❌ Нужно добавить |

**Вывод**: Нужно расширить `SENSITIVE_FIELD_NAMES` на 16 специфичных API key полей проекта.

---

## 3. Анализ: Текущий logger.py

**Файл**: `services/free-ai-selector-business-api/app/utils/logger.py`

```python
def setup_logging(service_name: str) -> None:
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,        # ← НЕТ sanitize_sensitive_data!
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    ...
```

**Отсутствует**: `sanitize_sensitive_data` processor.

**Все 4 сервиса имеют идентичный logger.py**:
- `services/free-ai-selector-business-api/app/utils/logger.py`
- `services/free-ai-selector-data-postgres-api/app/utils/logger.py`
- `services/free-ai-selector-telegram-bot/app/utils/logger.py`
- `services/free-ai-selector-health-worker/app/utils/logger.py`

---

## 4. Анализ: ROOT_PATH

### 4.1 Business API (✅ Реализован)

**Файл**: `services/free-ai-selector-business-api/app/main.py:56-137`

```python
ROOT_PATH = os.getenv("ROOT_PATH", "")

app = FastAPI(
    ...
    openapi_url=f"{ROOT_PATH}/openapi.json" if ROOT_PATH else "/openapi.json",
    root_path=ROOT_PATH,
    ...
)
```

**Статус**: ✅ Реализован корректно

### 4.2 Data API (❌ Отсутствует)

**Файл**: `services/free-ai-selector-data-postgres-api/app/main.py:96-100`

```python
app = FastAPI(
    title="AI Manager Platform - Data API",
    ...
    docs_url="/docs",
    # ← НЕТ root_path!
)
```

**Статус**: ❌ Нужно добавить ROOT_PATH

### 4.3 docker-compose.yml

**Проверка**: ROOT_PATH передаётся только в Business API.

```yaml
# Business API
environment:
  - ROOT_PATH=${ROOT_PATH:-}

# Data API
# ← ROOT_PATH не передаётся
```

---

## 5. Анализ: StaticFiles Mount

**Файл**: `services/free-ai-selector-business-api/app/main.py:149-155`

```python
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    # Для nginx-proxy который передаёт полный путь /free-ai-selector/static/
    app.mount("/free-ai-selector/static", StaticFiles(directory=static_dir), name="static-proxy")
```

**Проблема**:
1. Hardcoded path `/free-ai-selector/static`
2. Нарушает DRY — путь дублируется
3. Не следует best practice: root_path должен обрабатывать префикс автоматически

**Best Practice** (из `.aidd/contributors/2025-12-31-aidd-enhancement-reverse-proxy-root-path.md`):

```python
# nginx: proxy_pass http://backend:8000; (БЕЗ rewrite)
# FastAPI: root_path=os.getenv("ROOT_PATH", "")
# → Starlette автоматически обрабатывает префикс
app.mount("/static", StaticFiles(directory=static_dir), name="static")
# Один mount достаточно!
```

---

## 6. Существующие паттерны кода

### 6.1 Структура utils/ во всех сервисах

```
services/*/app/utils/
├── __init__.py         # Re-exports: sanitize_error_message
├── logger.py           # setup_logging, get_logger
├── request_id.py       # Context vars для tracing
└── security.py         # sanitize_error_message (идентичен во всех 4)
```

### 6.2 Паттерн импорта security

```python
# Все сервисы используют:
from app.utils.security import sanitize_error_message
```

### 6.3 Паттерн логирования ошибок

```python
# Типичный паттерн:
try:
    result = await some_operation()
except Exception as e:
    logger.error("operation_failed", error=sanitize_error_message(e))  # ← Ручной вызов
```

---

## 7. Рекомендации для реализации

### 7.1 SensitiveDataFilter

1. **Создать** `sensitive_filter.py` в каждом `services/*/app/utils/`
2. **Адаптировать** шаблон из `.aidd/templates/shared/utils/logger.py`
3. **Расширить** `SENSITIVE_FIELD_NAMES` специфичными полями проекта:
   ```python
   SENSITIVE_FIELD_NAMES.update({
       "google_ai_studio_api_key", "groq_api_key", "cerebras_api_key",
       "sambanova_api_key", "huggingface_api_key", "cloudflare_api_token",
       "cloudflare_account_id", "deepseek_api_key", "cohere_api_key",
       "openrouter_api_key", "github_token", "fireworks_api_key",
       "hyperbolic_api_key", "novita_api_key", "scaleway_api_key",
       "kluster_api_key", "nebius_api_key", "postgres_password",
   })
   ```
4. **Обновить** `logger.py` — добавить processor в chain
5. **НЕ удалять** `sanitize_error_message()` — оставить для обратной совместимости

### 7.2 ROOT_PATH для Data API

1. **Добавить** в `data-postgres-api/app/main.py`:
   ```python
   ROOT_PATH = os.getenv("ROOT_PATH", "")

   app = FastAPI(
       ...
       root_path=ROOT_PATH,
   )
   ```
2. **Добавить** в `docker-compose.yml`:
   ```yaml
   free-ai-selector-data-postgres-api:
     environment:
       - ROOT_PATH=${DATA_API_ROOT_PATH:-}
   ```

### 7.3 Удаление hardcoded mount

1. **Удалить** строку в `business-api/app/main.py`:
   ```python
   # УДАЛИТЬ:
   app.mount("/free-ai-selector/static", StaticFiles(directory=static_dir), name="static-proxy")
   ```
2. **Проверить** nginx config на VPS — убедиться что используется подход без rewrite

---

## 8. Технические ограничения

| ID | Ограничение | Обоснование |
|----|-------------|-------------|
| TC-001 | Все 4 сервиса уже используют structlog | F006 DEPLOYED |
| TC-002 | logger.py идентичен во всех сервисах | Можно создать один sensitive_filter.py и скопировать |
| TC-003 | sanitize_error_message() используется в 133 местах | Не удалять, постепенная миграция |
| TC-004 | nginx config внешний (VPS) | Документация вместо изменений |

---

## 9. Оценка объёма работ

| Задача | Файлов | Строк кода |
|--------|--------|------------|
| sensitive_filter.py × 4 | 4 | ~80 каждый |
| logger.py × 4 | 4 | +2 строки |
| data-postgres-api/main.py | 1 | +5 строк |
| business-api/main.py | 1 | -1 строка |
| docker-compose.yml | 1 | +1 строка |
| Unit тесты | 1 | ~50 строк |
| **ИТОГО** | 12 | ~400 |

---

## 10. Качественные ворота

### RESEARCH_DONE Checklist

- [x] Существующий код изучен
- [x] Архитектурные паттерны выявлены (logger.py, security.py в 4 сервисах)
- [x] Технические ограничения определены
- [x] Gap analysis завершён (SensitiveDataFilter, ROOT_PATH, hardcoded mount)
- [x] Рекомендации сформулированы
- [x] Объём работ оценён

**Результат**: ✅ RESEARCH_DONE

---

## Следующий шаг

```bash
/aidd-feature-plan
```
