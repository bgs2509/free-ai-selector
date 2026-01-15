---
feature_id: "F011-B"
feature_name: "system-prompts-json-response"
title: "Поддержка System Prompts и JSON Response"
created: "2026-01-15"
author: "AI (Analyst)"
type: "prd"
status: "Draft"
version: 1.2
mode: "FEATURE"

related_features: []
blocked_by: ["F011-A"]
f011a_status: "VALIDATED"
f011a_completed: "2026-01-15"
services: ["free-ai-selector-business-api"]
requirements_count: 7

pipelines:
  business: true
  data: false
  integration: true
  modified: ["prompt_processing", "provider_integration"]
---

# PRD: Поддержка System Prompts и JSON Response (F011-B)

**Feature ID**: F011-B
**Версия**: 1.1
**Дата**: 2026-01-15
**Автор**: AI Agent (Аналитик)
**Статус**: Draft
**Блокируется**: F011-A (Удаление GoogleGemini и Cohere)

**ВАЖНО**: Эта фича реализуется **ПОСЛЕ** завершения F011-A (удаление нестандартных провайдеров).

---

## 1. Обзор

### 1.1 Проблема

При использовании Cloudflare Workers AI (и других AI-провайдеров) через free-ai-selector API возникают три критические проблемы:

**Проблема 1: Модель игнорирует system prompt**

Даже при использовании всех best practices:
- ✅ Llama 3.3 special tokens (`<|begin_of_text|>`, `<|start_header_id|>system<|end_header_id|>`, `<|eot_id|>`)
- ✅ JSON Schema определения
- ✅ Императивные формулировки ("You MUST", "CRITICAL")
- ✅ Negative examples (примеры запрещённых форматов)
- ✅ Multi-shot examples (3+ примера корректного JSON)
- ✅ Response priming (начало ответа с `[`)

Модель **всегда** возвращает:
- Plain text или markdown (вместо JSON)
- На **русском языке** (даже для английских промптов!)
- С объяснениями и вежливыми фразами (вместо чистых данных)

**Проблема 2: User prompt доминирует над system prompt**

Модель отвечает на **содержание** user prompt (на русском), полностью игнорируя **инструкции формата** из system prompt.

Пример:
```
System: "You MUST return ONLY valid JSON array..."
User: "Распарси следующие заголовки..." (Parse these headers)
Response: "Вот результаты распарсивания заголовков:\n\n1. Источник:..."
```

**Проблема 3: response_format не поддерживается**

- Cloudflare Workers AI API **поддерживает** параметр `response_format` с типом `json_schema` (добавлен 25 февраля 2025)
- free-ai-selector API **НЕ ПОДДЕРЖИВАЕТ** этот параметр
- Параметр принимается но игнорируется
- Требуется прямое использование Cloudflare Workers AI API (обход free-ai-selector)

**Последствия:**
- Невозможно получить структурированные данные (JSON) через API
- Требуется сложный post-processing (regex, парсинг markdown таблиц)
- Ненадёжность (парсинг произвольного текста вместо валидного JSON)
- Пользователи вынуждены обращаться к Cloudflare API напрямую
- free-ai-selector теряет ценность как единый gateway для AI-провайдеров

### 1.2 Решение

Добавить поддержку system prompts и параметра `response_format` в free-ai-selector API:

**Компонент 1: Поддержка System Prompt**
- Разделение инструкций (system) и контента (user)
- Поддержка OpenAI-compatible messages формата
- Передача system prompt всем AI-провайдерам

**Компонент 2: Поддержка JSON Response Format**
- Параметр `response_format: {"type": "json_object" | "json_schema"}`
- Опциональная JSON Schema валидация ответов
- Graceful degradation для провайдеров без поддержки

**Компонент 3: Матрица возможностей провайдеров**
- Документация возможностей каждого провайдера
- Автоматическое определение поддерживаемых параметров
- Fallback стратегии для legacy провайдеров

**Ожидаемый результат:**
- Надёжное получение JSON-ответов от AI-моделей
- Правильное разделение инструкций и контента
- Обратная совместимость для существующих API-консьюмеров
- Единый интерфейс для всех 14 OpenAI-compatible провайдеров
- Упрощённая реализация благодаря **F011-A** (GoogleGemini и Cohere удалены, статус: VALIDATED, 2026-01-15)

### 1.3 Целевая аудитория

| Сегмент | Описание | Потребности |
|---------|----------|-------------|
| Разработчики интеграций | Используют free-ai-selector API для получения структурированных данных | Надёжный JSON output, system prompts для инструкций |
| Пользователи Telegram бота | Взаимодействуют через бота с AI-моделями | Более точные ответы благодаря system prompts |
| Администраторы систем | Настраивают и мониторят free-ai-selector | Понимание возможностей провайдеров, логи |

### 1.4 Ценностное предложение

**Для разработчиков:**
- Один API для 14 OpenAI-compatible провайдеров (Cloudflare, Groq, Cerebras, SambaNova, HuggingFace, DeepSeek, OpenRouter, GitHubModels, Fireworks, Hyperbolic, Novita, Scaleway, Kluster, Nebius)
- Гарантированный JSON output через `response_format`
- Чистое разделение инструкций (system) и данных (user)

**Для free-ai-selector как продукта:**
- Конкурентное преимущество перед прямым обращением к Cloudflare API
- Поддержка современных LLM capabilities (structured outputs)
- Сохранение роли единого gateway для multiple AI providers
- Упрощённая реализация благодаря **F011-A** (GoogleGemini и Cohere уже удалены, только OpenAI-compatible формат)

---

## 2. Функциональные требования

### 2.1 Core Features (Must Have)

| ID | Название | Описание | Критерий приёмки |
|----|----------|----------|------------------|
| FR-001 | Поддержка System Prompt | API принимает опциональный параметр `system_prompt: str \| null` | POST /api/v1/prompt с `system_prompt` возвращает 200 OK |
| FR-002 | Внедрение System Message | Провайдеры передают system prompt в API как отдельное сообщение с role="system" | Логи показывают `messages: [{"role": "system", ...}, {"role": "user", ...}]` |
| FR-003 | Параметр Response Format | API принимает `response_format: {"type": "json_object" \| "json_schema"}` | POST с `response_format` возвращает 200 OK |
| FR-004 | Поддержка JSON в Cloudflare | Cloudflare provider передаёт `response_format` в Workers AI API | HTTP payload содержит `response_format` |
| FR-005 | Валидация JSON | Опциональная валидация JSON-ответов при использовании `response_format` | Invalid JSON логируется с уровнем WARNING |
| FR-006 | Обратная совместимость | Существующие запросы без `system_prompt` работают как раньше | Legacy тесты проходят без изменений |
| FR-007 | Поддержка OpenAI-compatible провайдеров | Все 14 OpenAI-compatible провайдеров поддерживают system prompts через messages array | Тесты для каждого провайдера с system_prompt проходят |

**Примечание**: GoogleGemini и Cohere провайдеры удалены в **F011-A** (prerequisite фича). Данная фича работает только с 14 OpenAI-compatible провайдерами.

---

## 3. User Stories

### US-001: Разработчик хочет получить JSON от AI модели

**Как** разработчик интеграции
**Я хочу** получить гарантированный JSON-ответ от AI модели
**Чтобы** использовать данные в своём приложении без сложного парсинга

**Критерии приёмки:**
- [ ] API принимает `response_format: {"type": "json_object"}`
- [ ] Cloudflare Workers AI возвращает валидный JSON
- [ ] Response валидируется как JSON (опционально)
- [ ] Документация содержит примеры использования

**Связанные требования:** FR-003, FR-004, FR-005

---

### US-002: Администратор хочет разделять инструкции и контент

**Как** администратор системы
**Я хочу** передавать system prompt отдельно от user prompt
**Чтобы** модель следовала инструкциям формата

**Критерии приёмки:**
- [ ] API endpoint принимает `system_prompt` поле
- [ ] System prompt передаётся провайдеру в messages[0] с role="system"
- [ ] User prompt передаётся в messages[1] с role="user"
- [ ] Логи показывают оба сообщения

**Связанные требования:** FR-001, FR-002

---

### US-003: Существующий API-консьюмер не хочет breaking changes

**Как** текущий пользователь API
**Я хочу** продолжать использовать API без изменений
**Чтобы** мой код не сломался после обновления

**Критерии приёмки:**
- [ ] Запросы без `system_prompt` работают как раньше
- [ ] Запросы без `response_format` работают как раньше
- [ ] Все существующие тесты проходят
- [ ] Версия API не меняется (backward compatible)

**Связанные требования:** FR-006

---

**ПРИМЕЧАНИЕ**: US-004 "Упрощение реализации" перенесено в **F011-A** (удаление GoogleGemini и Cohere). После завершения F011-A, данная фича (F011-B) будет работать только с 14 OpenAI-compatible провайдерами.

---

## 4. Пайплайны

### 4.0 Тип изменений

| Параметр | Значение |
|----------|----------|
| Режим | FEATURE (изменение существующей системы) |
| Затрагиваемые пайплайны | Обработка промптов, Интеграция с провайдерами |

### 4.1 Бизнес-пайплайн

> Последовательность обработки AI-запроса с system prompt и response format

**Текущий flow (AS-IS):**

```
[Запрос пользователя] → [API] → [Use Case] → [Provider] → [LLM API]
     ↓                    ↓          ↓            ↓            ↓
   prompt              prompt   prompt_text   messages:    response
                                             [{"role":"user"}]
```

**Новый flow (TO-BE):**

```
[Запрос пользователя] → [API] → [Use Case] → [Provider] → [LLM API]
     ↓                    ↓          ↓            ↓            ↓
   prompt              prompt   prompt_text   messages:    response
system_prompt     system_prompt system_prompt [{"role":"system"},  (JSON)
response_format   response_format response_fmt {"role":"user"}]
                                              + response_format
```

| # | Этап | Описание | Условия перехода | Результат |
|---|------|----------|------------------|-----------|
| 1 | Парсинг API-запроса | FastAPI парсит request body, извлекает `prompt`, `system_prompt`, `response_format` | Запрос валиден | PromptRequest DTO |
| 2 | Оркестрация Use Case | ProcessPromptUseCase выбирает provider, передаёт параметры | Provider найден | PromptResponse DTO |
| 3 | Построение сообщений провайдера | Provider строит messages array с system и user ролями | system_prompt не None | messages: [{system}, {user}] |
| 4 | Вызов LLM API | HTTP POST к Cloudflare Workers AI с response_format | API доступен | Raw response text |
| 5 | Валидация ответа | Опциональная валидация JSON если response_format задан | response_format != null | Valid/Invalid JSON status |
| 6 | Возврат ответа | Возврат response клиенту | — | JSON response клиенту |

**Состояния запроса:**

| Сущность | Состояния | Переходы |
|----------|-----------|----------|
| PromptRequest | received → processing → completed / failed | received→processing (provider найден), processing→completed (валидный response), processing→failed (ошибка API) |

### 4.2 Data Pipeline

> Поток данных между компонентами

**Диаграмма потока данных:**

```
┌─────────┐     HTTP      ┌─────────────┐     HTTP     ┌──────────────┐
│ Client  │ ────────────▶ │ Business API│ ───────────▶ │ Cloudflare   │
│         │               │             │              │ Workers AI   │
│         │  POST /prompt │ (FastAPI)   │  messages[]  │              │
└─────────┘               └─────────────┘  +resp_fmt   └──────────────┘
     │                           │                             │
     │ JSON                      │ HTTP                        │ JSON
     ↓                           ↓                             ↓
{                          PromptRequest              { "messages": [
  "prompt": "...",           ├── prompt_text            {"role": "system",
  "system_prompt": "...",    ├── system_prompt          "content": "..."},
  "response_format": {...}   └── response_format        {"role": "user",
}                                                        "content": "..."}
                                                       ],
                                                       "response_format": {
                                                         "type": "json_object"
                                                       }
                                                     }
                                                            ↓
                                                       JSON response
```

| # | Источник | Назначение | Данные | Формат | Синхронность |
|---|----------|------------|--------|--------|--------------|
| 1 | Client | Business API | prompt, system_prompt, response_format | JSON (ProcessPromptRequest) | sync |
| 2 | Business API | Cloudflare API | messages array, response_format | JSON (OpenAI-compatible) | async (httpx) |
| 3 | Cloudflare API | Business API | сгенерированный текст (JSON или plain text) | JSON (response.result) | async |
| 4 | Business API | Client | текст ответа | JSON (ProcessPromptResponse) | sync |

**Трансформации данных:**

| # | Точка | Входные данные | Преобразование | Выходные данные |
|---|-------|----------------|----------------|-----------------|
| 1 | API Layer | `ProcessPromptRequest` | Pydantic validation | `PromptRequest` domain model |
| 2 | Provider Layer | `prompt: str, system_prompt: str \| None` | Построение messages array | `messages: [{"role": "system"}, {"role": "user"}]` |
| 3 | Provider Layer | `response_format: dict \| None` | Добавление в payload если не None | Cloudflare API payload с `response_format` |
| 4 | Response Parsing | Raw response string | Извлечение JSON из markdown если нужно | Clean JSON string |

### 4.3 Интеграционный пайплайн

> Взаимодействие между сервисами

**Карта сервисов:**

```
┌─────────────────────────────────────────────────────────────┐
│                    FREE-AI-SELECTOR                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐              ┌──────────────────┐     │
│  │  Business API    │◄────────────►│    Data API      │     │
│  │  (FastAPI:8000)  │  HTTP        │  (FastAPI:8001)  │     │
│  │                  │  (stats)     │                  │     │
│  └────────┬─────────┘              └──────────────────┘     │
│           │                                                 │
│           │ HTTP (AI requests)                              │
│           ▼                                                 │
│  ┌──────────────────┐                                       │
│  │  AI Провайдеры   │                                       │
│  │  - Cloudflare    │ ← ИЗМЕНЕНИЕ: +system_prompt           │
│  │  - Groq          │               +response_format        │
│  │  - Cerebras      │                                       │
│  │  - SambaNova     │                                       │
│  │  - HuggingFace   │                                       │
│  │  - DeepSeek      │                                       │
│  │  - OpenRouter    │                                       │
│  │  - GitHubModels  │                                       │
│  │  + 6 других      │                                       │
│  └──────────────────┘                                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
          │
          │ HTTP (OpenAI-compatible)
          ▼
    ┌────────────────────┐
    │ Cloudflare Workers │
    │       AI API       │
    │  (Внешний)         │
    └────────────────────┘
```

**Точки интеграции:**

| ID | От | К | Протокол | Endpoint | Описание |
|----|----|----|----------|----------|----------|
| INT-001 | Business API | Cloudflare Workers AI | HTTPS/REST | `https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}` | AI generation с system prompt и response_format |
| INT-002 | Business API | Data API | HTTP/REST | POST /api/v1/models/statistics | Обновление статистики (без изменений) |
| INT-003 | Business API | Groq/Cerebras/etc APIs | HTTPS/REST | Специфичные для провайдера | Аналогично INT-001 для других 13 провайдеров |

**Контракты API:**

**INT-001: Cloudflare Workers AI (ИЗМЕНЕНИЯ)**

**Request (TO-BE):**
```json
{
  "messages": [
    {
      "role": "system",
      "content": "Вы полезный ассистент. Отвечайте в формате JSON."
    },
    {
      "role": "user",
      "content": "Перечисли 3 основных цвета"
    }
  ],
  "response_format": {
    "type": "json_object"
  },
  "max_tokens": 512,
  "temperature": 0.7
}
```

**Response:**
```json
{
  "result": {
    "response": "{\"colors\": [\"красный\", \"синий\", \"жёлтый\"]}"
  }
}
```

**Ошибки:**
- `401 Unauthorized` - Невалидный API token
- `429 Too Many Requests` - Rate limit
- `500 Internal Server Error` - Ошибка Cloudflare API

### 4.4 Влияние на существующие пайплайны

**Режим:** FEATURE

**Изменяемые пайплайны:**

| Пайплайн | Тип изменения | Затрагиваемые этапы | Обратная совместимость |
|----------|---------------|---------------------|------------------------|
| Обработка промптов | modify | API → Use Case → Provider (добавление параметров) | ✅ Да (параметры опциональные) |
| Интеграция с провайдерами | modify | Все 14 провайдеров (новые поля в payload) | ✅ Да (graceful degradation) |
| Сбор статистики | unchanged | — | ✅ Да (без изменений) |

**Breaking changes:**
- [ ] ✅ Нет breaking changes
- Все новые параметры опциональные (`system_prompt: str | None`, `response_format: dict | None`)
- Существующие запросы без новых полей работают как раньше
- Провайдеры, не поддерживающие `response_format`, игнорируют параметр

**Требования к миграции:**
- ❌ Миграция БД не требуется (схема не меняется)
- ❌ Изменение API version не требуется (backward compatible)
- ✅ Обновление документации обязательно

---

## 5. UI/UX требования

### 5.1 Экраны и интерфейсы

| ID | Экран | Описание | Приоритет |
|----|-------|----------|-----------|
| UI-001 | Swagger UI (API Docs) | Обновить `/docs` с новыми параметрами `system_prompt` и `response_format` | Must |
| UI-002 | Страница возможностей провайдеров | Новая страница `/providers` с таблицей возможностей | Should |

### 5.2 User Flows

**Flow 1: Отправка запроса с system prompt**

```
[Разработчик] → [Читает API docs]
                   ↓
          [Видит параметр system_prompt]
                   ↓
          [Формирует POST запрос:]
          {
            "prompt": "Перечисли 3 цвета",
            "system_prompt": "Отвечай в JSON",
            "response_format": {"type": "json_object"}
          }
                   ↓
          [Отправляет → /api/v1/prompt]
                   ↓
          [Получает JSON ответ]
                   ↓ Успех
          [Использует JSON в приложении]
                   ↓ Ошибка (invalid JSON)
          [Смотрит логи WARNING]
```

### 5.3 Требования к доступности

- [ ] API документация доступна на русском и английском
- [ ] Примеры кода для curl, Python, JavaScript
- [ ] Error messages информативные и actionable

---

## 6. Нефункциональные требования

### 6.1 Производительность

| ID | Метрика | Требование | Измерение |
|----|---------|------------|-----------|
| NF-001 | Время отклика API | < 200ms overhead (до вызова LLM API) | Prometheus metrics |
| NF-002 | Overhead валидации JSON | < 10ms для responses до 10KB | pytest benchmarks |
| NF-003 | Время Failover на провайдера | < 2s при fallback на другой provider | Integration tests |

### 6.2 Масштабируемость

| ID | Требование | Описание |
|----|------------|----------|
| NF-010 | Concurrent Requests | Поддержка 100 одновременных запросов с system_prompt | Load testing |
| NF-011 | Расширяемость провайдеров | Добавление нового провайдера без изменения base interface | Architecture review |

### 6.3 Безопасность

| ID | Требование | Описание |
|----|------------|----------|
| NF-020 | Маскирование API Token | System prompts и responses не должны содержать API tokens в логах | Log sanitization |
| NF-021 | Валидация входных данных | Валидация `response_format` schema для предотвращения injection | Pydantic validators |
| NF-022 | Rate Limiting | System prompts учитываются в rate limits наравне с обычными промптами | Rate limiter config |

### 6.4 Надёжность

| ID | Метрика | Требование |
|----|---------|------------|
| NF-030 | Uptime API | ≥ 99.9% (без изменений) |
| NF-031 | Обработка ошибок | Graceful degradation если provider не поддерживает response_format |
| NF-032 | Обратная совместимость | 100% существующих тестов проходят после изменений |

---

## 7. Технические ограничения

### 7.1 Обязательные технологии

- **Backend**: Python 3.11+, FastAPI
- **HTTP Client**: httpx (async)
- **Validation**: Pydantic v2
- **Testing**: pytest, pytest-asyncio
- **No DB Changes**: Схема PostgreSQL не меняется

### 7.2 Интеграции

| Система | Тип интеграции | Описание |
|---------|---------------|----------|
| Cloudflare Workers AI | REST API | Основной провайдер с full support |
| Groq API | REST API | Поддержка system prompts, возможно без response_format |
| Cerebras / SambaNova / HuggingFace | REST API | Varying support levels, требуется тестирование |
| DeepSeek / OpenRouter / GitHubModels | REST API | Приоритетные новые провайдеры F003 |
| Fireworks / Hyperbolic / Novita / Scaleway / Kluster / Nebius | REST API | Дополнительные провайдеры F003, требуется исследование |

### 7.3 Ограничения

**Технические ограничения:**
- Не все провайдеры поддерживают `response_format` (требуется graceful degradation)
- Cloudflare Workers AI может игнорировать `response_format` для некоторых моделей
- JSON Schema validation (full spec) может быть ресурсоёмкой (отложить на FR-020)

**Архитектурные ограничения:**
- Base interface `AIProviderBase.generate()` меняется (добавление параметров)
- Все 14 провайдеров требуют обновления (не может быть постепенно)

---

## 8. Допущения и риски

### 8.1 Допущения

| # | Допущение | Влияние если неверно |
|---|-----------|---------------------|
| 1 | Cloudflare Workers AI правильно обрабатывает `response_format` | Придётся добавлять fallback JSON extraction |
| 2 | Другие провайдеры поддерживают system messages | Требуется адаптация для провайдеров без поддержки |
| 3 | Существующие API consumers не ломаются при добавлении опциональных полей | Требуется более тщательное тестирование backward compatibility |
| 4 | JSON validation overhead < 10ms | Требуется оптимизация или отключение по умолчанию |

### 8.2 Риски

| # | Риск | Вероятность | Влияние | Митигация |
|---|------|-------------|---------|-----------|
| 1 | Модели всё равно не возвращают JSON | Medium | High | Добавить regex-based JSON extraction fallback |
| 2 | Провайдеры по-разному обрабатывают system prompts | High | Medium | Provider-specific адаптеры, документация возможностей |
| 3 | Breaking change для старых клиентов | Low | High | Тщательное тестирование, версионирование API если нужно |
| 4 | Performance degradation из-за JSON validation | Low | Medium | Сделать validation опциональным (feature flag) |
| 5 | Cloudflare изменит формат API | Low | High | Мониторинг changelog Cloudflare, версионирование API |

---

## 9. Открытые вопросы

| # | Вопрос | Статус | Ответственный | Решение |
|---|--------|--------|--------------|---------|
| 1 | Должна ли JSON validation быть включена по умолчанию? | Open | Команда | TBD: возможно сделать opt-in через query param `validate_json=true` |
| 2 | Нужен ли отдельный endpoint для provider capabilities или хватит документации? | Open | Product | TBD: начать с документации, endpoint добавить позже если нужен |
| 3 | Как обрабатывать модели, которые игнорируют response_format? | Open | Tech Lead | Предложение: логировать WARNING, вернуть как есть (не fail) |
| 4 | Нужна ли поддержка full JSON Schema validation (FR-020) в v1? | Open | Tech Lead | Предложение: отложить на v2, в v1 только `{"type": "json_object"}` |

---

## 10. Глоссарий

| Термин | Определение |
|--------|-------------|
| **System Prompt** | Инструкции для AI модели, передаваемые отдельно от user content в messages array с role="system" |
| **Response Format** | Параметр LLM API, указывающий желаемый формат ответа (json_object, json_schema, text) |
| **Messages Array** | OpenAI-compatible формат: `[{"role": "system"/"user"/"assistant", "content": "..."}]` |
| **Graceful Degradation** | Игнорирование unsupported параметров без ошибки, возврат best-effort результата |
| **JSON Extraction** | Fallback механизм: regex парсинг JSON из markdown code blocks если модель вернула ```json...``` |
| **Provider Capability** | Набор поддерживаемых features конкретного AI провайдера (system_prompts, response_format, etc.) |
| **Backward Compatibility** | Гарантия что существующие API requests работают после изменений |

---

## 11. История изменений

| Версия | Дата | Автор | Изменения |
|--------|------|-------|-----------|
| 1.0 | 2026-01-15 | AI Analyst | Первоначальная версия PRD |
| 1.1 | 2026-01-15 | AI (via Claude Code) | Обновление после завершения F011-A: удалены GoogleGemini и Cohere из всех секций, обновлены счётчики провайдеров (6→14), добавлены 6 новых провайдеров F003 в матрицу |

---

## 12. Исследование API провайдеров (2026-01-15)

> **Цель исследования**: Детально проверить в официальной документации какие параметры поддерживают конкретные модели, используемые в проекте.

### 12.1 Cloudflare Workers AI — Llama 3.3 70B Instruct FP8 Fast

**Модель:** `@cf/meta/llama-3.3-70b-instruct-fp8-fast`
**Документация:** [llama-3.3-70b-instruct-fp8-fast](https://developers.cloudflare.com/workers-ai/models/llama-3.3-70b-instruct-fp8-fast/)

**System Prompt:**
- ✅ **ПОДДЕРЖИВАЕТСЯ** через messages array
- Формат: `{"role": "system", "content": "..."}`
- Пример из официальной документации:
  ```json
  {
    "messages": [
      {"role": "system", "content": "You are a friendly assistant"},
      {"role": "user", "content": "Why is pizza so good"}
    ]
  }
  ```

**Response Format:**
- ✅ **ПОДДЕРЖИВАЕТСЯ** параметр `response_format`
- Типы: `{"type": "json_object"}` и `{"type": "json_schema"}`
- Добавлен в Cloudflare Workers AI 25 февраля 2025
- Документировано в официальной спецификации модели

**Дополнительные параметры:**
- `max_tokens` (default: 256)
- `temperature` (0-5, default: 0.6)
- `top_p` (0.001-1), `top_k` (1-50)
- `stream` (boolean)
- `seed`, `repetition_penalty`, `frequency_penalty`, `presence_penalty`
- `functions`, `tools` (function calling support)

**OpenAI Compatibility:**
- ✅ Поддерживает `/v1/chat/completions` endpoint

**Вывод:** **Полная совместимость** с планируемыми изменениями. Cloudflare — reference implementation.

---

### 12.2 HuggingFace — Meta-Llama-3-8B-Instruct

**Модель:** `meta-llama/Meta-Llama-3-8B-Instruct`
**API:** `https://router.huggingface.co/v1/chat/completions` (OpenAI-compatible)
**Документация:** [Chat templates](https://huggingface.co/docs/transformers/en/chat_templating), [Serverless Inference API](https://huggingface.co/learn/cookbook/en/enterprise_hub_serverless_inference_api)

**System Prompt:**
- ✅ **ПОДДЕРЖИВАЕТСЯ** через messages array (с router.huggingface.co)
- Формат: `{"role": "system", "content": "..."}`
- **ВАЖНО:** Проект уже использует OpenAI-compatible endpoint!
- Текущий код `huggingface.py:38`: `self.api_url = "https://router.huggingface.co/v1/chat/completions"`
- При использовании этого endpoint форматирование с токенами происходит автоматически

**Chat Template (для справки):**
```
<|begin_of_text|><|start_header_id|>system<|end_header_id|>
{{ system_prompt }}<|eot_id|><|start_header_id|>user<|end_header_id|>
{{ user_msg }}<|eot_id|>
```
(Применяется автоматически при использовании OpenAI-compatible API)

**Response Format:**
- ❓ **НЕТ ИНФОРМАЦИИ** о поддержке `response_format` в документации HuggingFace Inference API
- Возможно не поддерживается
- Требует тестирования

**Дополнительные параметры:**
- `max_tokens`, `temperature`, `top_p`

**Вывод:** System prompt работает **"из коробки"** через OpenAI-compatible endpoint. Response format требует проверки в тестах.

---

### 12.3 SambaNova Cloud — Meta-Llama-3.3-70B-Instruct

**Модель:** `Meta-Llama-3.3-70B-Instruct`
**API:** `https://api.sambanova.ai/v1/chat/completions`
**Документация:** [OpenAI compatible API](https://docs.sambanova.ai/sambastudio/latest/open-ai-api.html), [Function calling](https://docs.sambanova.ai/cloud/docs/capabilities/function-calling)

**System Prompt:**
- ✅ **ПОДДЕРЖИВАЕТСЯ** через messages array
- Формат: `{"role": "system", "content": "..."}`
- Пример из официальной документации SambaNova:
  ```json
  {
    "model": "Meta-Llama-3.3-70B-Instruct",
    "messages": [
      {"role": "system", "content": "You are intelligent"},
      {"role": "user", "content": "Tell me a story"}
    ]
  }
  ```

**Response Format:**
- ✅ **ПОДДЕРЖИВАЕТСЯ** параметр `response_format`
- Тип: `{"type": "json_object"}` (JSON mode)
- Явно упоминается в документации по Function calling
- ❌ `json_schema` не документирован (вероятно не поддерживается)

**Дополнительные параметры:**
- `max_tokens`, `temperature`, `top_p`, `stream`

**Context Length:** 128k tokens

**Вывод:** **Полная совместимость** с system prompts и `json_object` response format.

---

### 12.4 GitHub Models — GPT-4o Mini

**Модель:** `gpt-4o-mini-2024-07-18` или `openai/gpt-4o-mini`
**API:** `https://models.github.ai/inference/chat/completions`
**Документация:** [REST API endpoints](https://docs.github.com/en/rest/models/inference), [Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs)

**System Prompt:**
- ✅ **ПОДДЕРЖИВАЕТСЯ** через messages array
- Формат: `{"role": "system", "content": "..."}`
- Поддерживаемые роли: `system`, `user`, `assistant`, `developer`

**Response Format:**
- ✅ **ПОДДЕРЖИВАЕТСЯ** параметр `response_format`
- Типы: `{"type": "json_schema", "json_schema": {...}}`
- **Structured Outputs** работают с GPT-4o Mini (начиная с snapshot 2024-07-18)
- Полная поддержка JSON Schema validation

**Дополнительные параметры:**
- `max_tokens`, `temperature`
- `frequency_penalty`, `presence_penalty`

**Вывод:** **Полная поддержка**, включая продвинутые возможности `json_schema`.

---

### 12.5 OpenRouter — DeepSeek R1

**Модель:** `deepseek/deepseek-r1` (или `deepseek/deepseek-r1:free`)
**API:** `https://openrouter.ai/api/v1` (OpenAI-compatible)
**Документация:** [DeepSeek R1 API](https://openrouter.ai/deepseek/deepseek-r1/api), [Usage Guide](https://syntackle.com/blog/deepseek-ai-model-and-openrouter/)

**System Prompt:**
- ✅ **ПОДДЕРЖИВАЕТСЯ** через messages array
- Формат: `{"role": "system", "content": "..."}`
- Пример из официальной документации OpenRouter:
  ```javascript
  messages: [
    { role: "system", content: '<the-system-prompt>' },
    { role: "user", content: '<user-prompt>' }
  ]
  ```

**Response Format:**
- ⚠️ **ЧАСТИЧНАЯ ПОДДЕРЖКА** параметра `response_format`
- Параметр присутствует в API, но документация рекомендует:
  > "To get JSON output, you need to do more than just define a response_format as json_object - it works by specifying in the user prompt: 'IMP: give the output in a valid JSON string'"
- **Лучше работает** через явное указание JSON format в промпте

**Дополнительные параметры:**
- `reasoning`, `include_reasoning` (специфично для R1 reasoning model)
- `max_tokens`, `temperature`, `top_p`, `stop`
- `frequency_penalty`, `presence_penalty`, `repetition_penalty`
- `top_k`, `seed`, `min_p`
- `tools`, `tool_choice`

**Параметры модели:** 671B total, 37B active (MoE architecture)

**Вывод:** System prompt работает **отлично**. Response format требует **workaround** через инструкции в промпте.

---

### 12.6 Provider Capability Matrix (Итоговая таблица)

| Провайдер | Модель | System Prompt | response_format | json_object | json_schema | Примечания |
|-----------|--------|---------------|-----------------|-------------|-------------|-----------|
| **Cloudflare** | Llama 3.3 70B FP8 Fast | ✅ | ✅ | ✅ | ✅ | Полная поддержка, reference impl |
| **HuggingFace** | Meta-Llama-3-8B-Instruct | ✅ | ❓ | ❓ | ❓ | OpenAI-compatible endpoint, response_format неизвестен |
| **SambaNova** | Meta-Llama-3.3-70B-Instruct | ✅ | ✅ | ✅ | ❌ | Только json_object, без json_schema |
| **GitHub Models** | GPT-4o Mini | ✅ | ✅ | ✅ | ✅ | Полная поддержка Structured Outputs |
| **OpenRouter** | DeepSeek R1 | ✅ | ⚠️ | ⚠️ | ❌ | Лучше работает с JSON инструкциями в промпте |
| **Groq** | (не исследовано) | ✅* | ❓ | ❓ | ❓ | *OpenAI-compatible, вероятно поддерживает |
| **Cerebras** | (не исследовано) | ✅* | ❓ | ❓ | ❓ | *OpenAI-compatible, вероятно поддерживает |
| **Fireworks** | Llama 3.1 70B (Fireworks) | ✅* | ❓ | ❓ | ❓ | *OpenAI-compatible, требует исследования |
| **Hyperbolic** | Llama 3.3 70B (Hyperbolic) | ✅* | ❓ | ❓ | ❓ | *OpenAI-compatible, требует исследования |
| **Novita** | Llama 3.1 70B (Novita) | ✅* | ❓ | ❓ | ❓ | *OpenAI-compatible, требует исследования |
| **Scaleway** | Llama 3.1 70B (Scaleway) | ✅* | ❓ | ❓ | ❓ | *OpenAI-compatible, требует исследования |
| **Kluster** | Llama 3.3 70B Turbo (Kluster) | ✅* | ❓ | ❓ | ❓ | *OpenAI-compatible, требует исследования |
| **Nebius** | Llama 3.1 70B (Nebius) | ✅* | ❓ | ❓ | ❓ | *OpenAI-compatible, требует исследования |

**Легенда:**
- ✅ Полная поддержка (подтверждено документацией)
- ⚠️ Частичная поддержка / требует workaround
- ❓ Неизвестно / требует тестирования
- ❌ Не поддерживается
- ✅* Вероятная поддержка (OpenAI-compatible, но не проверено в документации)

---

### 12.7 Обновлённые рекомендации

#### Фаза 1: System Prompt (Высокий приоритет)

**Выводы:**
- ✅ Все 5 исследованных провайдеров (из 14) ПОДДЕРЖИВАЮТ system prompts через messages array
- ❓ Остальные 9 провайдеров (Groq, Cerebras, Fireworks, Hyperbolic, Novita, Scaleway, Kluster, Nebius, DeepSeek) требуют исследования
- ✅ HuggingFace уже использует OpenAI-compatible endpoint (router.huggingface.co)
- ✅ Изменения минимальны: добавить system message в начало messages array

**Универсальная реализация (подходит для всех провайдеров):**
```python
messages = []
if system_prompt:
    messages.append({"role": "system", "content": system_prompt})
messages.append({"role": "user", "content": prompt})

payload = {
    "messages": messages,
    # ... остальные параметры
}
```

#### Фаза 2: Response Format (Средний приоритет)

**Требует provider-specific logic:**

1. **Cloudflare (приоритет 1):** Добавить напрямую
   ```python
   if response_format:
       payload["response_format"] = response_format
   ```

2. **SambaNova (приоритет 2):** Поддержка `json_object`
   ```python
   if response_format and response_format.get("type") == "json_object":
       payload["response_format"] = response_format
   ```

3. **GitHub Models (приоритет 3):** Полная поддержка
   ```python
   if response_format:
       payload["response_format"] = response_format
   ```

4. **OpenRouter (приоритет 4):** Workaround через system prompt
   ```python
   if response_format:
       json_instruction = "IMPORTANT: You MUST respond with valid JSON format only."
       system_prompt = f"{system_prompt}\n\n{json_instruction}" if system_prompt else json_instruction
   ```

5. **HuggingFace (приоритет 5):** Требует тестирования
   ```python
   if response_format:
       payload["response_format"] = response_format  # May be ignored, test needed
   ```

---

### 12.8 Источники исследования

1. **Cloudflare:** [llama-3.3-70b-instruct-fp8-fast](https://developers.cloudflare.com/workers-ai/models/llama-3.3-70b-instruct-fp8-fast/)
2. **HuggingFace:** [Chat templates](https://huggingface.co/docs/transformers/en/chat_templating), [Serverless Inference API](https://huggingface.co/learn/cookbook/en/enterprise_hub_serverless_inference_api)
3. **SambaNova:** [OpenAI compatible API](https://docs.sambanova.ai/sambastudio/latest/open-ai-api.html), [liteLLM provider docs](https://docs.litellm.ai/docs/providers/sambanova)
4. **GitHub Models:** [REST API endpoints](https://docs.github.com/en/rest/models/inference), [Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs)
5. **OpenRouter:** [DeepSeek R1 API](https://openrouter.ai/deepseek/deepseek-r1/api), [Usage Guide](https://syntackle.com/blog/deepseek-ai-model-and-openrouter/)

---

### 12.9 Статус F011-A (2026-01-15)

**Feature F011-A завершена** (статус: VALIDATED)

| Показатель | Значение |
|------------|----------|
| Дата завершения | 2026-01-15 |
| Коммит | b4fd6ec |
| Удалено провайдеров | 2 (GoogleGemini, Cohere) |
| Осталось провайдеров | 14 (все OpenAI-compatible) |
| Качественные ворота | 8/9 пройдено (VALIDATED) |
| Готовность к F011-B | ✅ Да |

**Удалённые провайдеры**:
1. **GoogleGemini** (`google_gemini.py`, 123 строки)
   - Причина: специфичный non-OpenAI формат
   - Модель: Gemini 1.5 Flash

2. **Cohere** (`cohere.py`, 124 строки)
   - Причина: специфичный non-OpenAI формат
   - Модель: Command R

**Результат**: Унифицированная кодовая база с единым OpenAI-compatible интерфейсом для всех 14 провайдеров.

**Следующий шаг**: Реализация F011-B (System Prompts и JSON Response) теперь значительно упрощена.

---

## Качественные ворота

### PRD_READY Checklist

- [x] Все секции заполнены
- [x] Требования имеют уникальные ID (FR-001...FR-022, NF-001...NF-032, UI-001...UI-002, INT-001...INT-003)
- [x] Критерии приёмки определены для каждого требования
- [x] User stories связаны с требованиями (US-001→FR-003/004/005, US-002→FR-001/002, US-003→FR-006, US-004→FR-010/011)
- [x] Бизнес-пайплайн описан (6-этапный flow обработки промпта, состояния PromptRequest)
- [x] Data Pipeline описан (диаграмма Client→Business API→Cloudflare API, 4 трансформации)
- [x] Интеграционный пайплайн описан (карта сервисов, 3 точки интеграции INT-001/002/003, контракты)
- [x] Раздел "Влияние на существующие пайплайны" заполнен (FEATURE режим, 2 изменяемых пайплайна, backward compatible)
- [x] Нет блокирующих открытых вопросов (4 вопроса Open, но не блокирующие — можно начинать implementation)
- [x] Риски идентифицированы и имеют план митигации (5 рисков, все с mitigation стратегиями)
- [x] Документ готов к согласованию с заинтересованными сторонами
