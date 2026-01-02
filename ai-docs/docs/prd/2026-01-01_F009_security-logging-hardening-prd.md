# PRD: F009 Security Hardening & Reverse Proxy Alignment

---
feature_id: F009
feature_name: security-logging-hardening
title: "Security Hardening & Reverse Proxy Alignment"
version: 1.0
status: DRAFT
created: 2026-01-01
author: AI Agent (Analyst)
---

## 1. Обзор

### 1.1 Проблема

После обновления .aidd Framework (Dec 31, 2025 - Jan 1, 2026) выявлены следующие gaps в проекте free-ai-selector:

1. **Ручная санитизация логов** — функция `sanitize_error_message()` вызывается вручную в 36+ местах. Риск: разработчик может забыть вызвать → утечка секретов в логи.

2. **Data API без ROOT_PATH** — после добавления best practice для reverse proxy в .aidd framework, Data API не поддерживает ROOT_PATH, что создаёт инконсистентность с Business API.

3. **Hardcoded mount в Business API** — двойной mount StaticFiles (`/static` и `/free-ai-selector/static`) нарушает DRY и не следует best practice.

### 1.2 Решение

Внедрить defensive-in-depth подход к безопасности логирования и привести конфигурацию reverse proxy к новым стандартам .aidd Framework:

1. **SensitiveDataFilter** — structlog processor, автоматически фильтрующий секреты из ВСЕХ логов
2. **ROOT_PATH в Data API** — унификация подхода к reverse proxy
3. **Удаление hardcoded mount** — один mount `/static`, root_path обрабатывает префикс

### 1.3 Scope

| В scope | Вне scope |
|---------|-----------|
| SensitiveDataFilter для 4 сервисов | Pre-commit hooks |
| ROOT_PATH для Data API | nginx config template |
| Удаление двойного mount | Pipeline State v2 migration |
| Unit тесты для фильтра | |

### 1.4 Метрики успеха

| Метрика | Цель |
|---------|------|
| Ручных вызовов sanitize_error_message() | 0 новых (legacy сохраняется) |
| Автоматическая фильтрация секретов | 100% логов |
| ROOT_PATH support | Data API + Business API |
| Hardcoded mounts | 0 |

---

## 2. Функциональные требования

### 2.1 Must Have (Обязательные)

| ID | Требование | Критерий приёмки |
|----|------------|------------------|
| FR-001 | SensitiveDataFilter processor в structlog всех 4 сервисов | Файл `sensitive_filter.py` создан в каждом сервисе, добавлен в chain processors |
| FR-002 | Data API: поддержка ROOT_PATH env var | `root_path=os.getenv("ROOT_PATH", "")` в FastAPI app |
| FR-003 | Business API: удалить hardcoded mount `/free-ai-selector/static` | Один mount `/static`, без дублирования |
| FR-004 | ROOT_PATH в docker-compose.yml для Data API | `ROOT_PATH: ${DATA_API_ROOT_PATH:-}` в environment |
| FR-005 | Unit тесты для SensitiveDataFilter | ≥3 теста: фильтрация по имени поля, по паттерну значения, nested dict |

### 2.2 Should Have (Желательные)

| ID | Требование | Критерий приёмки |
|----|------------|------------------|
| FR-006 | Список SENSITIVE_FIELD_NAMES включает все env vars проекта | 16+ API keys из .env.example покрыты |
| FR-007 | Паттерны SENSITIVE_VALUE_PATTERNS покрывают форматы API keys | Google, OpenAI, Anthropic, HuggingFace patterns |

### 2.3 Could Have (Опционально)

| ID | Требование | Критерий приёмки |
|----|------------|------------------|
| FR-008 | Документация deployment с reverse proxy | Секция в docs/operations/ |

---

## 3. User Stories

### US-001: Автоматическая защита логов

**Как** DevOps инженер,
**Я хочу** чтобы все секреты автоматически маскировались в логах,
**Чтобы** исключить риск утечки при случайном логировании.

**Acceptance Criteria:**
- [ ] API keys в логах заменяются на `***REDACTED***`
- [ ] Работает для nested dicts и lists
- [ ] Не требует явного вызова функции санитизации

### US-002: Единообразная работа за reverse proxy

**Как** разработчик,
**Я хочу** чтобы Data API работал за nginx reverse proxy так же как Business API,
**Чтобы** иметь консистентную конфигурацию для всех сервисов.

**Acceptance Criteria:**
- [ ] Data API принимает ROOT_PATH env var
- [ ] OpenAPI docs работают с любым prefix path
- [ ] Health endpoint доступен по prefix path

### US-003: Чистый код без hardcode

**Как** разработчик,
**Я хочу** чтобы Business API не имел hardcoded путей для static files,
**Чтобы** следовать DRY и упростить поддержку.

**Acceptance Criteria:**
- [ ] Один mount `/static` без дублирования
- [ ] root_path автоматически обрабатывает prefix
- [ ] Web UI работает как на localhost, так и за nginx

---

## 4. UI/UX требования

Не применимо — изменения только в backend инфраструктуре.

---

## 5. Нефункциональные требования

| ID | Категория | Требование |
|----|-----------|------------|
| NF-001 | Производительность | SensitiveDataFilter добавляет ≤1ms к обработке лога |
| NF-002 | Совместимость | Обратная совместимость с существующим sanitize_error_message() |
| NF-003 | Покрытие тестами | ≥80% покрытие для sensitive_filter.py |
| NF-004 | Миграция | Без downtime, без изменения API |

---

## 6. Технические ограничения

| ID | Ограничение | Обоснование |
|----|-------------|-------------|
| TC-001 | structlog только | Все 4 сервиса уже используют structlog (F006) |
| TC-002 | Python 3.12+ | Текущая версия проекта |
| TC-003 | Не удалять sanitize_error_message() | Legacy код использует, постепенная миграция |
| TC-004 | HTTP-only архитектура | Data API доступ только через HTTP |

---

## 7. Архитектура изменений

### 7.1 Новые файлы

| Файл | Назначение |
|------|------------|
| `services/free-ai-selector-business-api/app/utils/sensitive_filter.py` | SensitiveDataFilter processor |
| `services/free-ai-selector-data-postgres-api/app/utils/sensitive_filter.py` | SensitiveDataFilter processor |
| `services/free-ai-selector-telegram-bot/app/utils/sensitive_filter.py` | SensitiveDataFilter processor |
| `services/free-ai-selector-health-worker/app/utils/sensitive_filter.py` | SensitiveDataFilter processor |
| `services/free-ai-selector-business-api/tests/unit/test_sensitive_filter.py` | Unit тесты |

### 7.2 Изменяемые файлы

| Файл | Изменение |
|------|-----------|
| `services/*/app/utils/logger.py` × 4 | Добавить sanitize_sensitive_data в processors chain |
| `services/free-ai-selector-data-postgres-api/app/main.py` | Добавить ROOT_PATH support |
| `services/free-ai-selector-business-api/app/main.py` | Удалить второй StaticFiles mount |
| `docker-compose.yml` | Добавить ROOT_PATH для Data API |

### 7.3 SensitiveDataFilter Design

```python
# sensitive_filter.py

SENSITIVE_FIELD_NAMES: set[str] = {
    "password", "api_key", "token", "secret", "key",
    "authorization", "bearer", "credential", "database_url",
    # Все API keys из .env.example
    "google_ai_studio_api_key", "groq_api_key", "cerebras_api_key",
    "sambanova_api_key", "huggingface_api_key", "cloudflare_api_key",
    "openrouter_api_key", "together_api_key", "deepseek_api_key",
    "hyperbolic_api_key", "novita_api_key", "chutes_api_key",
    "glhf_api_key", "openai_api_key", "github_models_api_key",
    "nebiusai_api_key",
}

SENSITIVE_VALUE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"AIza[A-Za-z0-9_-]{35}"),       # Google AI
    re.compile(r"sk-[A-Za-z0-9]{48,}"),          # OpenAI-style
    re.compile(r"gsk_[A-Za-z0-9]{50,}"),         # Groq
    re.compile(r"hf_[A-Za-z0-9]{34,}"),          # HuggingFace
    re.compile(r"[A-Za-z0-9]{32,}"),             # Generic long tokens (last resort)
]

REDACTED = "***REDACTED***"

def sanitize_sensitive_data(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Structlog processor для автоматической фильтрации секретов."""
    return _sanitize_dict(event_dict)
```

---

## 8. Риски

| ID | Риск | Вероятность | Влияние | Митигация |
|----|------|-------------|---------|-----------|
| R-001 | False positive — полезные данные маскируются | Средняя | Низкое | Whitelist для известных safe полей |
| R-002 | Performance degradation | Низкая | Среднее | Benchmark перед merge |
| R-003 | Breaking change в nginx config | Низкая | Высокое | Документация текущего nginx config |

---

## 9. Открытые вопросы

| ID | Вопрос | Статус | Ответ |
|----|--------|--------|-------|
| Q-001 | Нужно ли мигрировать legacy вызовы sanitize_error_message()? | Closed | Нет, оставить для обратной совместимости |
| Q-002 | Какие API key patterns ещё добавить? | Open | — |
| Q-003 | Нужен ли nginx config template в проекте? | Closed | Вне scope F009, можно в будущей фиче |

---

## 10. Глоссарий

| Термин | Определение |
|--------|-------------|
| SensitiveDataFilter | structlog processor для автоматической маскировки секретов в логах |
| ROOT_PATH | Env var для указания prefix path при работе за reverse proxy |
| Defensive-in-depth | Стратегия многослойной защиты безопасности |
| SSOT | Single Source of Truth — единый источник правды |

---

## 11. История изменений

| Дата | Версия | Автор | Изменения |
|------|--------|-------|-----------|
| 2026-01-01 | 1.0 | AI Agent | Первоначальная версия |

---

## Качественные ворота

### PRD_READY Checklist

- [x] Все секции заполнены
- [x] Требования имеют уникальные ID (FR-001..FR-008, NF-001..NF-004)
- [x] Приоритеты определены (Must/Should/Could)
- [x] Критерии приёмки для всех FR
- [x] User Stories связаны с требованиями
- [x] Архитектурные решения описаны
- [x] Нет блокирующих открытых вопросов

**Результат**: ✅ PRD_READY

---

## Следующий шаг

```bash
/aidd-research
```
