# PRD: Унификация логов в единый JSON-формат

**Версия**: 1.0
**Дата**: 2026-02-26
**FID**: F026
**Автор**: AI Agent (Аналитик)
**Статус**: Draft

---

## 1. Обзор

### 1.1 Проблема

В контейнерах сервисов (business-api, data-api) логи пишутся одновременно в **три разных формата**, что делает автоматический парсинг и мониторинг невозможным:

| Формат | Источник | Пример |
|--------|----------|--------|
| **JSON** (structlog) | middleware, use cases | `{"event": "request_started", "method": "POST", ...}` |
| **Plain text** (stdlib) | AI providers, HTTP clients, API routes | `ERROR:app.infrastructure.ai_providers.base:Groq API error...` |
| **Uvicorn access** | uvicorn internal | `INFO: 127.0.0.1 - "GET /health" 200 OK` |

**Последствия**:
- Невозможно парсить логи одним JSON-парсером (часть строк — не JSON)
- Дублирование: uvicorn access log повторяет middleware `request_started`/`request_completed`
- Потеря structured data: stdlib `logging.getLogger()` не передаёт context (request_id, correlation_id, run_id)
- Невозможно корректно агрегировать логи в системах мониторинга (ELK, Loki)
- Баг: `cloudflare.py` передаёт kwargs в stdlib logger, которые игнорируются

### 1.2 Решение

Унифицировать все источники логов во всех сервисах в единый JSON-формат через:
1. Замену `logging.getLogger()` на `get_logger()` (structlog) во всех файлах
2. Перехват stdlib logging через structlog (для сторонних библиотек: httpx, asyncio и др.)
3. Отключение дублирующего uvicorn access log
4. Стандартизацию стиля вызовов (structured events вместо f-string)

### 1.3 Целевая аудитория

- Разработчики: единый формат для отладки и диагностики
- Ops/DevOps: парсинг логов в мониторинге (docker logs, Loki, ELK)
- AI-агенты: автоматический анализ логов (как в текущей сессии)

---

## 2. Функциональные требования

| ID | Название | Описание | Приоритет | Критерий приёмки |
|----|----------|----------|-----------|------------------|
| FR-001 | Замена stdlib на structlog в business-api | Заменить `logging.getLogger(__name__)` на `get_logger(__name__)` в 5 файлах: `base.py`, `cloudflare.py`, `data_api_client.py`, `models.py`, `providers.py` | Must | Все логи этих модулей выходят в JSON |
| FR-002 | Отключение uvicorn access log | Добавить `--no-access-log` в CMD Dockerfile для business-api и data-api | Must | Нет дублирующих строк `INFO: 127.0.0.1 - "GET..."` |
| FR-003 | Перехват stdlib logging через structlog | В `setup_logging()` добавить интеграцию structlog ↔ stdlib для перехвата логов от httpx, asyncio, uvicorn.error | Must | Все логи сторонних библиотек рендерятся в JSON |
| FR-004 | Стандартизация вызовов в structlog | Заменить f-string вызовы (`logger.info(f"Testing provider: {name}")`) на structured events (`logger.info("testing_provider", provider=name)`) | Should | Все events — snake_case строки, данные — в kwargs |
| FR-005 | Унификация логов в data-api | Применить FR-001..FR-003 к сервису `free-ai-selector-data-postgres-api` | Must | Все логи data-api в JSON |
| FR-006 | Унификация логов в health-worker | Проверить и применить FR-001..FR-003 к `free-ai-selector-health-worker` | Should | Все логи health-worker в JSON |
| FR-007 | Унификация логов в telegram-bot | Проверить и применить FR-001..FR-003 к `free-ai-selector-telegram-bot` | Should | Все логи telegram-bot в JSON |
| FR-008 | Консистентные context-поля | Все JSON-записи содержат: `service`, `module`, `timestamp`, `level`, `event`, `request_id` (где применимо), `correlation_id`, `run_id` | Must | 100% записей содержат обязательные поля |

---

## 3. User Stories

### US-001: Автоматический парсинг логов

> Как DevOps-инженер, я хочу чтобы `docker logs <container> | jq .` работал без ошибок для каждой строки, чтобы я мог фильтровать и агрегировать логи.

**Критерий приёмки**: Каждая строка вывода `docker logs` — валидный JSON.

### US-002: Диагностика ошибок провайдеров

> Как разработчик, я хочу чтобы ошибки AI-провайдеров содержали `provider`, `model`, `error_type`, `http_status` как structured fields, чтобы я мог быстро фильтровать: `jq 'select(.provider == "Groq")'`.

### US-003: Отсутствие дублирования

> Как разработчик, я не хочу видеть один и тот же HTTP-запрос дважды (uvicorn + middleware), потому что это засоряет вывод и удваивает объём логов.

---

## 4. Пайплайны

### 4.1 Бизнес-пайплайн

Не затрагивается — логирование является инфраструктурным слоем, не влияющим на бизнес-логику.

### 4.2 Data Pipeline

**Поток данных при логировании (текущий)**:
```
Use case logger.info() ──→ structlog ──→ JSONRenderer ──→ PrintLoggerFactory ──→ stdout (JSON)
Provider logging.error() ──→ stdlib StreamHandler ──→ stdout (plain text)
Uvicorn access ──→ uvicorn.logging.DefaultFormatter ──→ stdout (custom text)
```

**Поток данных при логировании (целевой)**:
```
Все модули get_logger() ──→ structlog ──→ JSONRenderer ──→ PrintLoggerFactory ──→ stdout (JSON)
Сторонние библиотеки ──→ stdlib logging ──→ structlog ProcessorFormatter ──→ stdout (JSON)
Uvicorn access ──→ ОТКЛЮЧЁН (дублирует middleware)
```

### 4.3 Интеграционный пайплайн

| Компонент | Влияние |
|-----------|---------|
| Docker logs | Все строки становятся валидным JSON |
| Health check monitoring | Без изменений (HTTP уровень) |
| Audit JSONL | Без изменений (отдельная система) |
| Будущий ELK/Loki | JSON-парсинг без кастомных grok-паттернов |

### 4.4 Влияние на существующие пайплайны

- **Формат вывода меняется**: Скрипты/инструменты, парсящие plain text логи, перестанут работать. На данный момент таких нет (парсинг всегда был ad-hoc через grep).
- **Объём логов уменьшится**: Удаление дублирующего uvicorn access log сократит ~30% строк.
- **Load testing**: Скрипты анализа аудит-логов (`docs/api-tests/`) не затрагиваются — они парсят JSONL файлы, а не docker logs.

---

## 5. UI/UX требования

Нет UI-изменений. Логирование — внутренний инфраструктурный компонент.

---

## 6. Нефункциональные требования

| ID | Название | Описание | Метрика |
|----|----------|----------|---------|
| NF-001 | Единый формат | 100% строк docker logs — валидный JSON | `docker logs <ctr> \| jq . \| wc -l` == `docker logs <ctr> \| wc -l` |
| NF-002 | Нет дублирования | Каждый HTTP-запрос логируется ровно один раз (middleware) | Отсутствие строк `INFO: <ip> - "..."` |
| NF-003 | Производительность | Изменение не увеличивает latency > 1ms на запрос | Сравнительный бенчмарк до/после |
| NF-004 | Обратная совместимость | `LOG_FORMAT=console` переключает на human-readable формат для локальной разработки | Переменная окружения работает |

### 6.5 Требования к тестированию

| ID | Название | Тип | Приоритет |
|----|----------|-----|-----------|
| TRQ-001 | Smoke: business-api запускается и логирует JSON | Smoke | Must |
| TRQ-002 | Smoke: data-api запускается и логирует JSON | Smoke | Must |
| TRQ-003 | Smoke: health-worker запускается и логирует JSON | Smoke | Must |
| TRQ-004 | Smoke: telegram-bot запускается и логирует JSON | Smoke | Must |
| TRQ-005 | Валидация: каждая строка docker logs — валидный JSON | Integration | Must |
| TRQ-006 | Валидация: нет uvicorn access log строк | Integration | Must |
| TRQ-007 | Context-поля: request_id, service, module присутствуют | Integration | Should |

---

## 7. Технические ограничения

| Ограничение | Описание |
|-------------|----------|
| Sторонние библиотеки | httpx, asyncio, aiohttp могут писать через stdlib — нужен перехват |
| Uvicorn startup | Сообщения `Started server process [1]` всё равно пойдут через stdlib — перехватываются через structlog интеграцию |
| `LOG_FORMAT` не в docker-compose | Переменная не прокидывается — нужно добавить или оставить default=json |
| `BUSINESS_API_LOG_LEVEL` vs `LOG_LEVEL` | В docker-compose прокидывается `BUSINESS_API_LOG_LEVEL`, а `logger.py` читает `LOG_LEVEL` — нужно согласовать |

---

## 8. Допущения и риски

| Тип | Описание | Митигация |
|-----|----------|-----------|
| Допущение | Все сервисы используют одинаковый `logger.py` | Подтверждено исследованием |
| Допущение | Uvicorn access log полностью дублирует middleware | Подтверждено — middleware уже логирует method, path, status_code, duration_ms |
| Риск | Сторонние библиотеки могут генерировать неожиданные логи | Перехват stdlib logging через structlog покрывает этот случай |
| Риск | Breaking change для скриптов, парсящих логи | Низкий — таких скриптов нет в кодовой базе |

---

## 9. Открытые вопросы

Нет блокирующих вопросов.

---

## 10. Глоссарий

| Термин | Определение |
|--------|-------------|
| **structlog** | Библиотека структурированного логирования для Python |
| **stdlib logging** | Стандартный модуль `logging` Python |
| **PrintLoggerFactory** | Фабрика structlog, пишущая через `print()` в stdout |
| **JSONRenderer** | Процессор structlog, рендерящий записи в JSON |
| **Uvicorn access log** | Встроенный в uvicorn логгер HTTP-запросов |

---

## 11. Затрагиваемые файлы

### Business API (`services/free-ai-selector-business-api/`)

| Файл | Изменение |
|------|-----------|
| `app/utils/logger.py` | Добавить перехват stdlib logging |
| `app/infrastructure/ai_providers/base.py` | `logging.getLogger()` → `get_logger()` |
| `app/infrastructure/ai_providers/cloudflare.py` | `logging.getLogger()` → `get_logger()` + исправить kwargs |
| `app/infrastructure/http_clients/data_api_client.py` | `logging.getLogger()` → `get_logger()` |
| `app/api/v1/models.py` | `logging.getLogger()` → `get_logger()` |
| `app/api/v1/providers.py` | `logging.getLogger()` → `get_logger()` |
| `app/application/use_cases/test_all_providers.py` | f-string → structured events |
| `Dockerfile` | `--no-access-log` |

### Data API (`services/free-ai-selector-data-postgres-api/`)

| Файл | Изменение |
|------|-----------|
| `app/utils/logger.py` | Добавить перехват stdlib logging |
| `Dockerfile` | `--no-access-log` |
| Файлы с `logging.getLogger()` | → `get_logger()` (если есть) |

### Health Worker (`services/free-ai-selector-health-worker/`)

| Файл | Изменение |
|------|-----------|
| `app/utils/logger.py` | Добавить перехват stdlib logging |
| Файлы с `logging.getLogger()` | → `get_logger()` (если есть) |

### Telegram Bot (`services/free-ai-selector-telegram-bot/`)

| Файл | Изменение |
|------|-----------|
| `app/utils/logger.py` | Добавить перехват stdlib logging |
| Файлы с `logging.getLogger()` | → `get_logger()` (если есть) |

---

## 12. История изменений

| Версия | Дата | Описание |
|--------|------|----------|
| 1.0 | 2026-02-26 | Начальная версия PRD |
