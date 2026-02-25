---
feature_id: "F025"
feature_name: "adaptive-concurrency"
title: "Адаптивный Concurrency для массового прогона"
created: "2026-02-25"
author: "AI (Researcher)"
type: "research"
status: "RESEARCH_DONE"
version: 1
mode: "FEATURE"
---

# Research Report: F025 — Adaptive Concurrency

**Feature ID**: F025
**Дата**: 2026-02-25
**Режим**: FEATURE
**Исследователь**: AI (Researcher)

---

## 1. Краткое резюме

F025 предполагает создание компонента `AdaptiveConcurrency` для динамического управления параллелизмом в скрипте массового прогона LLM-запросов. Компонент реагирует на скользящий error rate: снижает concurrency при высоком error rate (> 50%), повышает при низком (< 20%), добавляет cooldown-паузу между запросами.

**Ключевой вывод**: Business API и Data API **не затрагиваются**. AdaptiveConcurrency — standalone-компонент уровня `app/application/services/`, аналогичный `circuit_breaker.py`. Скрипт массового прогона **не существует** в репозитории — нужно создать.

---

## 2. Анализ существующего кода

### 2.1 Структура обработки запросов

```
POST /api/v1/prompts/process
  → ProcessPromptUseCase.execute()
    → get_all_models() [Data API HTTP]
    → _filter_configured_models()
    → sort by effective_reliability_score
    → fallback loop:
        → CircuitBreakerManager.is_available() [F024]
        → retry_with_exponential_backoff() [F023]
          → provider.generate() [httpx.AsyncClient per-call]
        → classify_error() [F022]
        → record_success/failure + history
```

### 2.2 Существующие сервисы устойчивости

| Сервис | Файл | Назначение | Паттерн |
|--------|------|------------|---------|
| Error Classifier | `error_classifier.py` | Классификация HTTP-ошибок → доменные типы | Stateless функция |
| Retry Service | `retry_service.py` | Exponential backoff для retryable ошибок | Stateless async функция |
| Circuit Breaker | `circuit_breaker.py` | In-memory CB: CLOSED→OPEN→HALF-OPEN | ClassVar singleton |

**AdaptiveConcurrency — другой уровень абстракции**: существующие сервисы работают на уровне единичного запроса (внутри Business API), а AC работает на уровне пакетной обработки (внешний клиент Business API).

### 2.3 Скрипт массового прогона

**Статус: НЕ существует в репозитории.**

| Место поиска | Результат |
|-------------|-----------|
| `scripts/` | Директория не существует |
| `tools/` | Директория не существует |
| `docs/api-tests/` | 3 markdown-файла (аналитические отчёты, нет кода) |
| Grep: batch, reclassif, Semaphore, gather | Нет результатов в Python-файлах |

В `docs/api-tests/fix_plan_llm_errors.md` содержится **предложенный** класс `AdaptiveConcurrency` (строки 673-726) — это план, не реализация.

### 2.4 Компоненты с параллельной обработкой

В кодовой базе **полностью отсутствуют** паттерны параллельной обработки:
- Health Worker — последовательный `for model in models:`
- TestAllProviders — последовательный `for model in models:`
- ProcessPromptUseCase — последовательный fallback loop
- Нет `asyncio.Semaphore`, `asyncio.gather`, `aiohttp`

### 2.5 Технические ограничения

| # | Ограничение | Влияние на F025 |
|---|------------|----------------|
| 1 | Скрипт прогона НЕ существует | Нужно создать с нуля или создать только компонент AC |
| 2 | Business API rate limiter: 100 req/60s (slowapi) | При max_concurrency > ~1.6 req/s скрипт может упереться в rate limiter |
| 3 | Каждый `generate()` создаёт новый httpx.AsyncClient | При высоком concurrency возможно исчерпание сокетов |
| 4 | CB и retry работают ВНУТРИ Business API | AC видит только финальный HTTP-ответ (200/5xx), не промежуточные retry |
| 5 | Пересоздание Semaphore при смене concurrency | Кратковременный всплеск параллелизма (старые in-flight запросы) |

---

## 3. Рекомендации по интеграции

### 3.1 Размещение файлов

| Файл | Описание |
|------|----------|
| `app/application/services/adaptive_concurrency.py` | Класс AdaptiveConcurrency |
| `tests/unit/test_adaptive_concurrency.py` | Unit-тесты |

### 3.2 Конфигурация через env (паттерн проекта)

| Переменная | Default | Описание |
|-----------|---------|----------|
| `AC_WINDOW_SIZE` | 50 | Размер скользящего окна |
| `AC_HIGH_THRESHOLD` | 0.5 | Порог снижения concurrency |
| `AC_LOW_THRESHOLD` | 0.2 | Порог повышения concurrency |
| `AC_COOLDOWN_SECONDS` | 5.0 | Пауза при высоком error rate |
| `AC_INITIAL_CONCURRENCY` | 8 | Начальный concurrency |
| `AC_MIN_CONCURRENCY` | 1 | Минимальный concurrency |
| `AC_MAX_CONCURRENCY` | 16 | Максимальный concurrency |

### 3.3 Интерфейс (рекомендуемый)

```python
class AdaptiveConcurrency:
    """F025: Adaptive concurrency для массового прогона."""

    def __init__(self, initial_concurrency, min_concurrency, max_concurrency,
                 window_size, high_threshold, low_threshold, cooldown_seconds): ...

    async def acquire(self) -> None:
        """Ожидание семафора + cooldown при высоком error_rate."""

    def record(self, success: bool) -> None:
        """Запись результата в скользящее окно + _adjust()."""

    def release(self) -> None:
        """Освобождение семафора."""

    @property
    def error_rate(self) -> float: ...

    @property
    def current_concurrency(self) -> int: ...

    def get_report(self) -> dict:
        """Post-run отчёт (FR-011)."""
```

### 3.4 Паттерны тестирования

| Паттерн из проекта | Применение в F025 |
|-------------------|-------------------|
| `setup_method()` + reset | Сброс состояния AC между тестами |
| `@patch("...asyncio.sleep", new_callable=AsyncMock)` | Мокание cooldown-паузы (FR-004) |
| `@patch("...time.time")` | Контроль времени (если AC использует time) |
| `pytest.approx()` | Проверка float error_rate |
| Реальный `asyncio.Semaphore` | Не мокать — детерминированный в single-threaded event loop |
| `asyncio_mode = auto` | Не нужен `@pytest.mark.asyncio` внутри `@pytest.mark.unit` классов |

---

## 4. Код для переиспользования

| Модуль | Что использовать |
|--------|-----------------|
| `app/utils/logger.py` | `get_logger(__name__)` для structlog-логирования |
| Паттерн `os.getenv("NAME", "default")` | Конфигурация AC через env |
| `collections.deque(maxlen=N)` | Скользящее окно (stdlib) |
| `asyncio.Semaphore` | Ограничение параллелизма (stdlib) |
| Формат docstring `"""F025: ..."""` | Конвенция проекта |

**Дополнительные зависимости НЕ нужны** — всё из стандартной библиотеки Python.

---

## 5. Анализ сложности PRD

| Компонент | Сложность | Необходимость | Рекомендация |
|-----------|-----------|---------------|-------------|
| FR-001: Скользящее окно | Низкая (deque) | Must Have | Включить |
| FR-002: Снижение concurrency | Низкая (// 2) | Must Have | Включить |
| FR-003: Повышение concurrency | Низкая (+ 1) | Must Have | Включить |
| FR-004: Cooldown пауза | Низкая (sleep) | Must Have | Включить |
| FR-005: Semaphore | Низкая (stdlib) | Must Have | Включить |
| FR-010: Логирование | Низкая (structlog) | Should Have | Включить |
| FR-011: Post-run отчёт | Низкая (dict) | Should Have | Включить |
| FR-020: Early stop | Низкая (~5 строк) | Could Have | Включить (тривиально) |

---

## 6. Фильтрация scope

| Компонент | В scope? | Обоснование |
|-----------|----------|-------------|
| AdaptiveConcurrency class | Да | Core функциональность |
| FR-001..FR-005 (Must Have) | Да | Минимальная рабочая версия |
| FR-010, FR-011 (Should Have) | Да | Необходимы для диагностики |
| FR-020 (Early stop) | Да | Тривиальная реализация, высокая ценность |
| Скрипт batch_run.py | Отложить | F025 создаёт только компонент AC, не скрипт |
| Предиктивная адаптация | Нет | PRD сам исключает |
| Dashboard/UI мониторинг | Нет | Не в scope PRD |

---

## 7. Архитектура существующего кода

```
app/
├── api/v1/              # HTTP endpoints (prompts.py, routers)
│   └── POST /process    # Точка входа для промптов
├── application/
│   ├── use_cases/       # Бизнес-логика
│   │   ├── process_prompt.py    # Выбор модели + fallback loop
│   │   └── test_all_providers.py
│   └── services/        # Cross-cutting concerns  ← СЮДА adaptive_concurrency.py
│       ├── error_classifier.py  # HTTP → доменные ошибки
│       ├── retry_service.py     # Exponential backoff
│       └── circuit_breaker.py   # CLOSED→OPEN→HALF-OPEN
├── domain/
│   ├── models.py        # AIModelInfo, PromptRequest/Response
│   └── exceptions.py    # ProviderError hierarchy
├── infrastructure/
│   ├── ai_providers/    # 14 провайдеров + base.py + registry.py
│   └── http_clients/    # DataAPIClient
└── utils/
    ├── logger.py        # structlog get_logger()
    ├── log_helpers.py   # log_decision()
    └── security.py      # sanitize_error_message()
```

### Ответственности модулей

| Модуль | Ответственность | Граница |
|--------|----------------|---------|
| `process_prompt.py` | Выбор модели, fallback, retry, CB check | Единичный запрос |
| `error_classifier.py` | HTTP status → доменное исключение | Stateless, per-error |
| `retry_service.py` | Retry с backoff для retryable ошибок | Stateless, per-attempt |
| `circuit_breaker.py` | Исключение мёртвых провайдеров | Stateful, per-provider |
| **adaptive_concurrency.py** | **Управление параллелизмом пакета** | **Stateful, per-run** |

---

## 8. Источники данных (SSoT)

| Тип данных | Файл-источник |
|-----------|--------------|
| Retry config | `retry_service.py`: MAX_RETRIES, RETRY_BASE_DELAY, RETRY_MAX_DELAY |
| CB config | `circuit_breaker.py`: CB_FAILURE_THRESHOLD, CB_RECOVERY_TIMEOUT |
| AC config (новый) | `adaptive_concurrency.py`: AC_WINDOW_SIZE, AC_HIGH/LOW_THRESHOLD |
| Доменные модели | `domain/models.py` |
| Исключения | `domain/exceptions.py` |
| Provider registry | `infrastructure/ai_providers/registry.py` |
| Rate limiter | `main.py`: 100 req/60s (slowapi) |

---

## 9. Конвенции проекта

| Конвенция | Пример из кода |
|-----------|----------------|
| Env constants на уровне модуля | `CB_FAILURE_THRESHOLD = int(os.getenv("CB_FAILURE_THRESHOLD", "5"))` |
| ClassVar dict для singleton state | `_circuits: ClassVar[dict[str, ProviderCircuit]] = {}` |
| `reset()` classmethod для тестов | `CircuitBreakerManager.reset()` |
| Autouse fixture для cleanup | `conftest.py: reset_circuit_breaker` |
| Docstring с Feature ID | `"""F024: In-memory circuit breaker..."""` |
| Тесты с Feature ID в class name | `class TestF024CircuitBreaker` |
| Логирование structlog | `logger.info("event_name", key=value)` |
| asyncio_mode = auto | Нет `@pytest.mark.asyncio` в `@pytest.mark.unit` классах |
| Маркер `@pytest.mark.unit` на всех test-классах | Обязателен (strict markers) |

---

## 10. Security-контекст

- AdaptiveConcurrency **не обрабатывает** пользовательские данные — только счётчики success/failure
- Нет sensitive данных в логах — только concurrency, error_rate, window_stats
- `sanitize_error_message()` — существующая утилита для фильтрации секретов
- `sensitive_filter.py` — structlog-фильтр для автоочистки логов

**Security-рисков для F025 нет** — компонент работает только с числовыми метриками.

---

## 11. Риски

| # | Риск | Вероятность | Влияние | Митигация |
|---|------|-------------|---------|-----------|
| 1 | Business API rate limiter (100/60s) блокирует скрипт при высоком concurrency | Med | Med | Настроить AC_MAX_CONCURRENCY с учётом rate limit или увеличить лимит для batch |
| 2 | Скрипт batch_run.py не тестируем в CI (нет живых провайдеров) | High | Low | Unit-тесты для AC покрывают логику; integration — ручной |
| 3 | Пересоздание Semaphore при изменении concurrency — race condition | Low | Low | Старые in-flight запросы завершатся штатно со старым semaphore |
| 4 | AC не учитывает какой именно провайдер упал | Med | Low | AC работает с агрегированным error_rate; дифференциация — отдельная фича |
| 5 | Зависимость от F022/F023/F024 — без них базовый error rate высокий | Low | High | Все 3 фичи уже реализованы |

---

## Quality Cascade Checklist (7/7)

### DRY ✅
- [x] Поиск похожих модулей: retry_service, circuit_breaker — другой уровень абстракции, не дублируют AC
- [x] Утилиты для переиспользования: get_logger(), os.getenv() паттерн
- [x] Дополнительные зависимости не нужны — stdlib only
→ Рекомендация: Использовать существующие утилиты, НЕ создавать новые

### KISS ✅
- [x] Все FR-001..FR-005 — минимально сложные (5-15 строк каждый)
- [x] Один класс, один файл, stdlib only
- [x] FR-020 (early stop) тривиален — включить
→ Рекомендация: Один файл adaptive_concurrency.py с классом AdaptiveConcurrency

### YAGNI ✅
- [x] Предиктивная адаптация — за scope
- [x] Dashboard/UI — за scope
- [x] Скрипт batch_run.py — отложить, создать только компонент AC
→ Рекомендация: Scope ограничен FR-001..FR-011 + FR-020

### SoC ✅
- [x] AC — application service (cross-cutting concern)
- [x] Не касается domain, infrastructure, api
- [x] Чёткая граница: AC работает с bool (success/failure) и int (concurrency)
→ Рекомендация: Разместить в app/application/services/

### SSoT ✅
- [x] Конфигурация: env-переменные AC_* (один источник)
- [x] State: единственный экземпляр AC per-run
→ Рекомендация: Следовать паттерну circuit_breaker.py

### CoC ✅
- [x] Именование: adaptive_concurrency.py (snake_case)
- [x] Тесты: test_adaptive_concurrency.py, @pytest.mark.unit
- [x] Логирование: structlog через get_logger()
- [x] Docstring: "F025: ..." prefix
→ Рекомендация: Полное соответствие конвенциям проекта

### Security ✅
- [x] Нет обработки пользовательских данных
- [x] Нет sensitive данных в логах
- [x] Нет security-рисков
→ Рекомендация: Security-контекст минимальный

---

## Качественные ворота RESEARCH_DONE

- [x] Существующий код проанализирован
- [x] Архитектурные паттерны выявлены (DDD/Hexagonal, singleton services, env config)
- [x] Технические ограничения определены (5 ограничений)
- [x] Зависимости определены (stdlib only, нет новых pip-зависимостей)
- [x] Рекомендации сформулированы (размещение, интерфейс, конвенции)
- [x] Риски идентифицированы (5 рисков с митигацией)
- [x] Quality Cascade Checklist (7/7) включён и пройден
