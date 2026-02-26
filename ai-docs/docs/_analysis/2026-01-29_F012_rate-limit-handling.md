# PRD: Rate Limit Handling для AI Провайдеров

**Feature ID**: F012
**Дата создания**: 2026-01-29
**Автор**: AI (Claude)
**Статус**: DRAFT
**Приоритет**: MUST (Блокирующая проблема)

---

## 1. Executive Summary

### Проблема

Процесс дедупликации вопросов в проекте `python-sobes-questions-parsing` застопорился на 21/100 чанков (21% прогресса) из-за достижения rate limit на Cloudflare AI Workers API. Все запросы возвращают HTTP 429 "Too Many Requests" более 5 часов.

**Root Cause**: Система Free AI Selector не обрабатывает rate limit корректно:
- Нет надежной классификации 429 (в т.ч. когда приходит как HTTP 500 с текстом "429")
- Нет механизма временной недоступности (available_at) для остановки запросов к провайдеру
- 429 трактуется как failure → снижает `reliability_score`
- В fallback участвуют провайдеры без API ключей
- Fallback ограничен одной моделью

### Решение

Реализовать комплексную систему обработки rate limit:
1. **Error Classification** — распознавать 429 по статусу и по тексту ошибки
2. **Retry (fixed)** — 10 попыток с задержкой 10s только для 5xx/timeout
3. **Retry-After Parsing** — извлекать время ожидания или использовать дефолтный cooldown
4. **Availability Cooldown** — хранить `available_at` в Data API и исключать недоступные модели
5. **Graceful Degradation** — 429 не снижает reliability, сразу fallback
6. **Configured Providers Only** — исключать модели без ключей
7. **Full Fallback** — перебирать все доступные модели по убыванию score

### Бизнес-ценность

| Метрика | До | После |
|---------|-----|-------|
| Время простоя при rate limit | 5+ часов (ручное вмешательство) | 0 (автоматическое восстановление) |
| Процесс дедупликации | Застопорился на 21% | Завершится автоматически |
| Reliability score при rate limit | Падает → провайдер реже выбирается | Не падает (rate limit ≠ failure) |
| Доступность API | Зависит от одного провайдера | Автоматический fallback на 13 других |

---

## 2. Контекст

### 2.1. Текущая архитектура

**Компоненты:**
- **Базовый класс**: `AIProviderBase` с методами `generate()`, `health_check()`, `get_provider_name()`
- **Выбор модели**: `reliability_score = (success_rate × 0.6) + (speed_score × 0.4)`
- **Fallback механизм**: Primary model → Second best model при ошибке

**Файлы:**
```
services/free-ai-selector-business-api/
  app/infrastructure/ai_providers/
    base.py                  # AIProviderBase
    cloudflare.py            # Cloudflare провайдер
    groq.py, cerebras.py, ... # Другие провайдеры
  app/application/use_cases/
    process_prompt.py        # ProcessPromptUseCase.execute()
  app/domain/
    models.py                # AIModelInfo, PromptRequest
```

### 2.2. Проблема (исходные данные)

**Хронология инцидента:**
- 28.01, ~06:00 - Запущен процесс дедупликации (SEMAPHORE_LIMIT=5)
- 29.01, 05:56 - Обработан последний успешный чанк №21
- 29.01, ~06:00 - Все запросы начали падать с HTTP 429
- 29.01, 11:00 - Обнаружено зависание процесса (5+ часов простоя)

**Текущее поведение:**
```python
# process_prompt.py:124-131
except Exception as e:
    error_message = sanitize_error_message(e)
    logger.error("generation_failed", ...)
    # ❌ ВСЕ ошибки (429, 500, auth) обрабатываются ОДИНАКОВО
    fallback_model = self._select_fallback_model(models, best_model)
```

**Результат:** 429 → `increment_failure()` → `reliability_score` падает → провайдер остается active но выбирается реже

**Данные о rate limit:**
- Cloudflare достигнут после ~22 часов работы (21,000 батчей)
- Простые промпты (<1000 символов) → Groq → работают
- Большие промпты (>1000 символов, JSON format) → Cloudflare → 429
- Попытки снизить SEMAPHORE_LIMIT (5→2→1) не помогли
- Уменьшение размера батча (5→3→1 пара) не помогло

---

## 3. Цели и метрики успеха

### 3.1. Бизнес-цели

| # | Цель | Описание |
|---|------|----------|
| BG-1 | Автоматическое восстановление | При rate limit система продолжает работу без ручного вмешательства |
| BG-2 | Завершение процесса дедупликации | 79 оставшихся чанков обрабатываются автоматически |
| BG-3 | Предсказуемая работа | Rate limit не вызывает зависание процессов |
| BG-4 | Справедливая оценка провайдеров | Rate limit не снижает reliability_score |

### 3.2. Метрики успеха

| Метрика | Текущее | Целевое | Критерий приёмки |
|---------|---------|---------|------------------|
| Время простоя при rate limit | 5+ часов | 0 минут | Автоматический fallback |
| Процесс дедупликации | 21/100 (21%) | 100/100 (100%) | Завершается без зависания |
| Reliability score при 429 | Падает | Не падает | 429 не записывается как failure |
| Error rate | 100% при rate limit | <10% | Fallback на другие провайдеры |
| Retry attempts | 0 | 10 для 5xx/timeout; 0 для 429 | Fixed interval, configurable |

### 3.3. Non-Goals (Что НЕ входит в scope)

- ❌ Увеличение rate limits на стороне провайдеров (требует связи с поддержкой)
- ❌ Кэширование ответов AI (отдельная фича)
- ❌ Rate limit prediction (прогнозирование когда достигнется лимит)
- ❌ Изменение формулы `reliability_score` (уже оптимальная)
- ❌ Добавление новых провайдеров (есть 14, достаточно)

---

## 4. Functional Requirements

### FR-1: Error Classification

**Приоритет**: MUST
**Описание**: Система различает типы HTTP ошибок и обрабатывает их по-разному

**Детали:**
- FR-1.1: HTTP 429 (Rate Limit) → без retry, availability cooldown, затем fallback
- FR-1.2: HTTP 5xx (Server Error) → retry (fixed), затем fallback
- FR-1.3: HTTP 401/403 (Auth Error) → не retry, immediate fail
- FR-1.4: HTTP 400/422 (Validation Error) → не retry, immediate fail
- FR-1.5: Timeout → retry (fixed), затем fallback
- FR-1.6: Если status=500 и в тексте есть "429 Too Many Requests" → RateLimitError

**Критерии приёмки:**
```python
# Test: test_error_classification.py
assert classify_error(429) == RateLimitError
assert classify_error(500, detail="...429 Too Many Requests...") == RateLimitError
assert classify_error(500) == ServerError
assert classify_error(401) == AuthenticationError
assert classify_error(400) == ValidationError
```

**Файлы для модификации:**
- `app/domain/exceptions.py` (создать) - иерархия исключений
- `app/application/use_cases/process_prompt.py` - классификация ошибок

---

### FR-2: Retry Mechanism (fixed interval)

**Приоритет**: MUST
**Описание**: При временных ошибках (HTTP 5xx, timeout) система делает повторные попытки
с фиксированной задержкой. Для 429 retry не выполняется (см. FR-4).

**Детали:**
- FR-2.1: Retry только для HTTP 5xx и timeout
- FR-2.2: 10 попыток с фиксированной задержкой 10 секунд
- FR-2.3: Для 429 retry НЕ выполняется → сразу availability cooldown и fallback (FR-4)
- FR-2.4: Параметры настраиваются через env vars

**Параметры (environment variables):**
```yaml
MAX_RETRIES: 10              # Количество попыток
RETRY_DELAY_SECONDS: 10      # Задержка между попытками (секунды)
```

**Критерии приёмки:**
```python
# Test: test_retry_mechanism.py
async def test_retry_on_5xx():
    provider = MockProviderWith500()
    await provider.generate("test")
    assert provider.call_count == 10

async def test_retry_on_timeout():
    provider = MockProviderWithTimeout()
    await provider.generate("test")
    assert provider.call_count == 10
```

**Файлы для модификации:**
- `app/application/use_cases/process_prompt.py` - retry логика вокруг provider.generate()

### FR-3: Retry-After Parsing и дефолтный cooldown

**Приоритет**: MUST
**Описание**: При rate limit система извлекает время ожидания из заголовков
и, если это невозможно, использует дефолтный cooldown.

**Детали:**
- FR-3.1: Проверять заголовок `Retry-After` (секунды или HTTP-date)
- FR-3.2: Проверять заголовки `X-RateLimit-Reset` и `X-Rate-Limit-Reset` (Unix timestamp)
- FR-3.3: Если заголовков нет, но ошибка содержит "429" → использовать дефолтный cooldown
- FR-3.4: Если значение нераспознаваемо или <= 0 → использовать дефолтный cooldown

**Параметр:**
```yaml
RATE_LIMIT_DEFAULT_COOLDOWN: 3600  # секунды
```

**Пример заголовков:**
```http
# Cloudflare
HTTP/1.1 429 Too Many Requests
Retry-After: 60

# Groq
HTTP/1.1 429 Too Many Requests
X-RateLimit-Reset: 1738152000
```

**Критерии приёмки:**
```python
# Test: test_retry_after_parsing.py
async def test_parse_retry_after_seconds():
    response = Mock(headers={"Retry-After": "60"})
    wait_time = provider._parse_rate_limit_headers(response)
    assert wait_time == 60

async def test_parse_x_ratelimit_reset():
    now = int(time.time())
    response = Mock(headers={"X-RateLimit-Reset": str(now + 120)})
    wait_time = provider._parse_rate_limit_headers(response)
    assert 118 <= wait_time <= 122

async def test_default_cooldown_when_no_headers():
    error_detail = "...429 Too Many Requests..."
    wait_time = get_cooldown_from_error(detail=error_detail)
    assert wait_time == 3600
```

**Файлы для модификации:**
- `app/application/use_cases/process_prompt.py` - разбор заголовков/текста ошибки

### FR-4: Availability Cooldown через available_at (Data API)

**Приоритет**: MUST
**Описание**: При rate limit провайдер временно исключается из выбора через поле
`available_at` в Data API. Модели с `available_at` в будущем не выбираются.

**Детали:**
- FR-4.1: Добавить поле `ai_models.available_at: datetime | null` (timezone-aware)
- FR-4.2: При RateLimitError обновлять `available_at = now + retry_after_seconds`
- FR-4.3: Data API: параметр `available_only=true` исключает модели с `available_at > now`
- FR-4.4: Business API и health-worker используют `available_only=true`
- FR-4.5: Если retry_after не определён → использовать `RATE_LIMIT_DEFAULT_COOLDOWN`

**API изменение (Data API):**
- `PATCH /api/v1/models/{id}/availability?retry_after_seconds=60`

**Критерии приёмки:**
```python
# Test: test_availability_cooldown.py
async def test_available_at_updated_on_rate_limit():
    await data_api_client.set_availability(model_id=1, retry_after_seconds=60)
    model = await data_api_client.get_model_by_id(1)
    assert model.available_at is not None

async def test_available_only_filter():
    models = await data_api_client.get_all_models(available_only=True)
    assert all(m.available_at is None or m.available_at <= now for m in models)
```

**Файлы для модификации:**
- `services/free-ai-selector-data-postgres-api/app/infrastructure/database/models.py` - поле available_at
- `services/free-ai-selector-data-postgres-api/alembic/versions/*_add_available_at.py` - миграция
- `services/free-ai-selector-data-postgres-api/app/api/v1/models.py` - endpoint availability + фильтр
- `services/free-ai-selector-business-api/app/infrastructure/http_clients/data_api_client.py`
- `services/free-ai-selector-business-api/app/application/use_cases/process_prompt.py`
- `services/free-ai-selector-health-worker/app/main.py`

### FR-5: Graceful Degradation (Fallback без пенализации)

**Приоритет**: MUST
**Описание**: При rate limit система переключается на альтернативный провайдер БЕЗ
записи rate limit как failure (не снижает reliability_score).

**Детали:**
- FR-5.1: RateLimitError НЕ вызывает `increment_failure()`
- FR-5.2: Для RateLimitError обновляется `available_at` (FR-4)
- FR-5.3: ServerError и TimeoutError вызывают `increment_failure()`
- FR-5.4: Fallback модель выбирается из доступных (не rate-limited и с ключами)
- FR-5.5: Логирование rate limit отдельно от failures: `rate_limit_detected`

**До (текущее):**
```python
except Exception as e:
    # ❌ 429 записывается как failure
    await self.data_api_client.increment_failure(model_id=model.id)
```

**После:**
```python
except RateLimitError as e:
    # ✅ 429 НЕ записывается как failure
    logger.warning("rate_limit_detected", model=model.name, retry_after=e.retry_after_seconds)
    await self.data_api_client.set_availability(model_id=model.id, retry_after_seconds=e.retry_after_seconds)
    # Fallback без пенализации

except (ServerError, TimeoutError) as e:
    # ✅ Только реальные ошибки записываются как failure
    await self.data_api_client.increment_failure(model_id=model.id)
```

**Критерии приёмки:**
```python
# Test: test_graceful_degradation.py
async def test_rate_limit_not_recorded_as_failure():
    use_case = ProcessPromptUseCase(data_api_client)
    with patch.object(provider, 'generate', side_effect=RateLimitError(...)):
        await use_case.execute(PromptRequest(...))
    data_api_client.increment_failure.assert_not_called()
```

**Файлы для модификации:**
- `app/application/use_cases/process_prompt.py` - error handling в `execute()`

### FR-6: Конфигурируемые параметры через Environment Variables

**Приоритет**: SHOULD
**Описание**: Параметры retry и cooldown настраиваются через environment variables без изменения кода

**Детали:**
- FR-6.1: `MAX_RETRIES` (default: 10)
- FR-6.2: `RETRY_DELAY_SECONDS` (default: 10)
- FR-6.3: `RATE_LIMIT_DEFAULT_COOLDOWN` (default: 3600)

**Критерии приёмки:**
```bash
# docker-compose.yml
environment:
  - MAX_RETRIES=10
  - RETRY_DELAY_SECONDS=10
  - RATE_LIMIT_DEFAULT_COOLDOWN=3600
```

### FR-8: Исключение провайдеров без ключей

**Приоритет**: MUST
**Описание**: Модели без необходимых API ключей не участвуют в выборе и fallback.

**Детали:**
- FR-8.1: Если `env_var` пуст или `os.getenv(env_var)` пустой → модель исключается
- FR-8.2: Для провайдеров с несколькими ключами проверяются все необходимые env vars

**Критерии приёмки:**
```python
# Test: test_configured_providers_only.py
async def test_model_without_api_key_excluded():
    models = await use_case._get_available_models()
    assert all(m.provider != "SomeProviderWithoutKey" for m in models)
```

**Файлы для модификации:**
- `services/free-ai-selector-business-api/app/application/use_cases/process_prompt.py`

### FR-9: Полный fallback по списку доступных моделей

**Приоритет**: MUST
**Описание**: При ошибках система пробует все доступные модели по убыванию effective score
до успеха или исчерпания списка.

**Детали:**
- FR-9.1: Список кандидатов = active_only + available_only + configured_only
- FR-9.2: Попытки идут по убыванию `effective_reliability_score`
- FR-9.3: При RateLimitError у модели обновляется `available_at` и берется следующая

**Критерии приёмки:**
```python
# Test: test_full_fallback.py
async def test_fallback_iterates_all_models():
    use_case = ProcessPromptUseCase(data_api_client)
    await use_case.execute(PromptRequest(...))
    assert provider_calls >= 2
```

**Файлы для модификации:**
- `services/free-ai-selector-business-api/app/application/use_cases/process_prompt.py`

## 5. Non-Functional Requirements

### NFR-1: Performance

**Приоритет**: MUST
**Описание**: Retry механизм не должен значительно увеличивать latency для успешных запросов

**Детали:**
- NFR-1.1: Overhead на успешный запрос: <10ms (проверка retry не нужна)
- NFR-1.2: Retry delay для 5xx/timeout: 10 секунд (configurable)
- NFR-1.3: При 429 применяется availability cooldown (без retry)
- NFR-1.4: Fallback должен срабатывать быстро: <500ms

**Критерии приёмки:**
```python
# Test: test_performance.py
def test_no_overhead_for_successful_request():
    start = time.time()
    await provider.generate("test")
    elapsed = time.time() - start
    assert elapsed < 1.0  # <10ms overhead допустим в рамках 1 секунды
```

---

### NFR-2: Backward Compatibility

**Приоритет**: MUST
**Описание**: Изменения не ломают существующую функциональность

**Детали:**
- NFR-2.1: Все 14 провайдеров продолжают работать
- NFR-2.2: Существующие тесты проходят (70+ тестов Business API)
- NFR-2.3: Reliability score formula не меняется
- NFR-2.4: Fallback механизм работает как раньше (+ улучшения)

**Критерии приёмки:**
```bash
# Все существующие тесты проходят
make test-business
# Результат: ≥70 passed (как до изменений)
```

---

### NFR-3: Observability

**Приоритет**: SHOULD
**Описание**: Система логирует rate limit события отдельно от обычных ошибок для мониторинга

**Детали:**
- NFR-3.1: Логи rate limit: `rate_limit_detected`, `availability_updated`, `availability_skipped`
- NFR-3.2: Логи retry: `retry_attempt` с attempt number
- NFR-3.3: Логи fallback: `fallback_success` с причиной (rate_limit vs error)
- NFR-3.4: Включать `retry_after` в логи

**Пример логов:**
```json
{"event": "rate_limit_detected", "model": "Cloudflare", "retry_after": 60, "timestamp": "..."}
{"event": "availability_updated", "model": "Cloudflare", "available_at": "...", "timestamp": "..."}
{"event": "retry_attempt", "attempt": 2, "max_retries": 10, "wait_time": 10.0, "timestamp": "..."}
{"event": "fallback_success", "primary_model": "Cloudflare", "fallback_model": "Groq", "reason": "rate_limit", "timestamp": "..."}
```

**Файлы для модификации:**
- `app/application/use_cases/process_prompt.py` - добавить логи availability

---

### NFR-4: Testability

**Приоритет**: MUST
**Описание**: Код покрыт unit и integration тестами (≥75% coverage)

**Детали:**
- NFR-4.1: Unit тесты для retry механизма
- NFR-4.2: Unit тесты для availability cooldown
- NFR-4.3: Unit тесты для error classification
- NFR-4.4: Integration тесты для end-to-end flow
- NFR-4.5: Mock провайдеры для симуляции rate limit

**Критерии приёмки:**
```bash
# Coverage должен быть ≥75% для новых файлов
pytest --cov=app --cov-report=html tests/
# Результат: coverage ≥75%
```

---

## 6. User Stories

### US-1: Автоматическое восстановление при rate limit

**Как**: Пользователь процесса дедупликации
**Я хочу**: Чтобы процесс продолжал работу при достижении rate limit одного провайдера
**Чтобы**: Завершить обработку 99,347 батчей без ручного вмешательства

**Критерии приёмки:**
- Процесс не зависает при HTTP 429
- Автоматический fallback на другие провайдеры
- Прогресс продолжается: 22/100 → 23/100 → ... → 100/100
- Error rate остается ~4% (не увеличивается до 100%)

---

### US-2: Справедливая оценка провайдеров

**Как**: Администратор системы
**Я хочу**: Чтобы rate limit не снижал reliability_score провайдера
**Чтобы**: Cloudflare оставался доступным после истечения rate limit timeout

**Критерии приёмки:**
- Cloudflare `reliability_score` не падает из-за 429 ошибок
- После наступления `available_at` провайдер снова выбирается с нормальным приоритетом
- Логи показывают `rate_limit_detected` вместо `generation_failed`

---

### US-3: Предсказуемая работа при нагрузке

**Как**: Разработчик использующий API
**Я хочу**: Чтобы система автоматически retry при временных ошибках
**Чтобы**: Не писать retry логику на стороне клиента

**Критерии приёмки:**
- При HTTP 5xx/timeout система делает 10 retry с задержкой 10s
- Если retry исчерпаны → fallback на другую доступную модель
- Клиент получает либо успешный ответ, либо 429 с Retry-After

---

## 7. Out of Scope

Что НЕ реализуется в этой фиче:

1. **Увеличение rate limits** - требует связи с поддержкой провайдеров
2. **Кэширование ответов AI** - отдельная фича (F013)
3. **Rate limit prediction** - ML модель для прогнозирования (будущее)
4. **Изменение формулы reliability_score** - уже оптимальная (F010)
5. **Добавление новых провайдеров** - есть 14, достаточно (F003)

---

## 8. Риски и митигация

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Breaking changes для провайдеров | Низкая | Высокое | Retry/классификация в use case без изменений провайдеров |
| Performance degradation | Средняя | Среднее | Fixed retry: 10 попыток × 10s |
| available_at не сбрасывается | Низкая | Среднее | Проверка `available_at <= now` при выборке |
| Все провайдеры rate limited одновременно | Низкая | Высокое | 14 провайдеров - маловероятно |
| БД миграция ломает Data API | Очень низкая | Высокое | Миграция простая, можно откатить |

---

## 9. Dependencies

### Internal Dependencies

| Компонент | Зависимость | Причина |
|-----------|-------------|---------|
| F008 (Provider Registry SSOT) | DEPLOYED | Нужен для получения списка провайдеров |
| F010 (Rolling Window Reliability) | DEPLOYED | Нужен для `effective_reliability_score` |
| F011-B (System Prompts) | DEPLOYED | Совместимость с новыми параметрами |

### External Dependencies

Нет внешних зависимостей.

---

## 10. Implementation Phases (Pipelines)

Эта фича реализуется как один пайплайн (F012):

### Phase 1: Foundation (Этапы 1-3)

| Этап | Артефакт | Ворота |
|------|----------|--------|
| 1. Идея | PRD (этот документ) | PRD_READY |
| 2. Исследование | Research report | RESEARCH_DONE |
| 3. Планирование | Implementation plan | PLAN_APPROVED |

### Phase 2: Implementation (Этапы 4-5)

| Этап | Действия | Ворота |
|------|----------|--------|
| 4. Генерация | Создать exceptions, retry mechanism, availability cooldown | IMPLEMENT_OK |
| 5. Тестирование | Unit + integration тесты, coverage ≥75% | QA_PASSED |

### Phase 3: Validation (Этапы 6-8)

| Этап | Действия | Ворота |
|------|----------|--------|
| 6. Код-ревью | Review изменений | REVIEW_OK |
| 7. Валидация | RTM, проверка всех FR/NFR | ALL_GATES_PASSED |
| 8. Деплой | `make build && make up`, health checks | DEPLOYED |

---

## 11. Acceptance Criteria

### Критерии приёмки (общие)

- [ ] Все FR-* требования реализованы
- [ ] Все NFR-* требования выполнены
- [ ] Unit тесты покрывают ≥75% нового кода
- [ ] Integration тесты проходят
- [ ] Существующие тесты не сломаны (70+ passed)
- [ ] Код-ревью пройдено
- [ ] Документация обновлена
- [ ] Логи содержат rate limit события
- [ ] Процесс дедупликации завершается без зависания

### Критерии приёмки (специфичные)

**Rate Limit Handling:**
- [ ] HTTP 429 обрабатывается без retry: обновляется available_at и выполняется fallback
- [ ] Retry для 5xx/timeout: 10 попыток × 10s
- [ ] Retry-After parsing работает (или дефолтный cooldown)
- [ ] available_at обновляется при rate limit
- [ ] Модели с future available_at не выбираются
- [ ] Rate limit НЕ записывается как failure

**Fallback:**
- [ ] Автоматический fallback при rate limit
- [ ] Fallback модель выбирается из available + configured
- [ ] Fallback работает для всех доступных провайдеров

**Observability:**
- [ ] Логи `rate_limit_detected` появляются
- [ ] Логи `availability_updated/availability_skipped` появляются
- [ ] Логи `retry_attempt` показывают attempt number

**Performance:**
- [ ] Overhead на успешный запрос <10ms
- [ ] Fallback срабатывает за <500ms

---

## 12. Open Questions

| # | Вопрос | Ответственный | Статус |
|---|--------|---------------|--------|
| Q-1 | Нужно ли персистентное хранение availability state? | User | CLOSED (используем available_at в БД) |
| Q-2 | Какой default cooldown использовать? | User | CLOSED (RATE_LIMIT_DEFAULT_COOLDOWN=3600) |
| Q-3 | Нужно ли логировать X-RateLimit-Remaining? | User | CLOSED (не требуется) |

---

## 13. References

### Внутренние документы

- [Отчет об исследовании проблемы rate limit](/tmp/claude/.../cloudflare_rate_limit_investigation.md)
- [CLAUDE.md проекта](/home/bgs/Henry_Bud_GitHub/free-ai-selector/CLAUDE.md)
- [Architecture Decision Record: Reliability Scoring](../../docs/adr/0001-reliability-scoring.md)
- [F010 PRD: Rolling Window Reliability](2026-01-02_F010_rolling-window-reliability-_analysis.md)
- [F008 PRD: Provider Registry SSOT](2025-12-31_F008_provider-registry-ssot-_analysis.md)

### Внешние ресурсы

- [RFC 6585: HTTP Status Code 429 (Too Many Requests)](https://datatracker.ietf.org/doc/html/rfc6585#section-4)
- [Retry-After HTTP Header](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Retry-After)

---

## Changelog

| Версия | Дата | Автор | Изменения |
|--------|------|-------|-----------|
| 1.0 | 2026-01-29 | AI (Claude) | Initial draft based on rate limit investigation report |

---

**Статус**: DRAFT → Требуется review и approval от пользователя
