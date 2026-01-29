---
feature_id: "F004"
feature_name: "dynamic-providers-list"
type: "_research"
created: "2025-12-25"
status: "RESEARCH_DONE"
---

# Research: F004 - Динамический список провайдеров

## 1. Анализ текущего состояния

### 1.1 Провайдеры в системе

**Всего: 16 провайдеров** (файлы в `services/free-ai-selector-business-api/app/infrastructure/ai_providers/`)

| Группа | Провайдеры | Статус |
|--------|------------|--------|
| Оригинальные (6) | GoogleGemini, Groq, Cerebras, SambaNova, HuggingFace, Cloudflare | Поддержаны везде |
| F003 Фаза 1 (4) | DeepSeek, Cohere, OpenRouter, GitHubModels | Только в process_prompt |
| F003 Фаза 2 (4) | Fireworks, Hyperbolic, Novita, Scaleway | Только в process_prompt |
| F003 Фаза 3 (2) | Kluster, Nebius | Только в process_prompt |

### 1.2 Места с хардкодом

| Файл | Строки | Провайдеров | Проблема |
|------|--------|-------------|----------|
| `telegram-bot/app/main.py` | 143-149 | 6 | Текст /start |
| `telegram-bot/app/main.py` | 183 | 6 | Текст /help |
| `business-api/.../test_all_providers.py` | 52-60 | 6 | providers dict |
| `business-api/.../test_all_providers.py` | 237-245 | 6 | model_names dict |
| `health-worker/app/main.py` | 308-322 | 6 | if/elif chain |
| `health-worker/app/main.py` | 367-378 | 6 | Логирование ключей |

---

## 2. Ключевые паттерны

### 2.1 Архитектура провайдеров

```python
# Все провайдеры наследуют от AIProviderBase
class AIProviderBase(ABC):
    @abstractmethod
    async def generate(self, prompt: str) -> str: ...

    @abstractmethod
    async def health_check(self) -> bool: ...

    @abstractmethod
    def get_provider_name(self) -> str: ...
```

### 2.2 Важное открытие: встроенный health_check()

Все 16 провайдеров **уже имеют** метод `health_check()`:

```python
# Пример из DeepSeekProvider
async def health_check(self) -> bool:
    if not self.api_key:
        return False
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(models_url, headers=headers)
        return response.status_code == 200
```

**Вывод:** Health-worker может использовать классы провайдеров напрямую!

### 2.3 API формат провайдеров

| Формат | Провайдеры |
|--------|------------|
| OpenAI-совместимый | Groq, Cerebras, SambaNova, DeepSeek, OpenRouter, GitHubModels, Fireworks, Hyperbolic, Novita, Scaleway, Kluster, Nebius |
| Google-специфичный | GoogleGemini |
| HuggingFace-специфичный | HuggingFace |
| Cohere-специфичный | Cohere |
| Cloudflare-специфичный | Cloudflare |

---

## 3. Точки интеграции

### 3.1 Telegram Bot

**Существующий API:** `GET /api/v1/models/stats`

Ответ содержит всё необходимое:
```json
{
  "models": [
    {
      "id": "uuid",
      "name": "Gemini 2.5 Flash",
      "provider": "GoogleGemini",
      "is_active": true,
      "reliability_score": 0.85
    }
  ],
  "total_models": 16
}
```

### 3.2 test_all_providers.py

**Источник провайдеров:** `process_prompt.py:63-84`

Можно импортировать dict провайдеров или синхронизировать вручную.

### 3.3 Health Worker

**Два варианта:**

**Вариант A: Использовать provider classes**
```python
from app.infrastructure.ai_providers.deepseek import DeepSeekProvider

providers = {
    "DeepSeek": DeepSeekProvider(),
    # ...
}

# В run_health_checks():
provider = providers.get(provider_name)
if provider:
    is_healthy = await provider.health_check()
```

**Вариант B: Создать check_* функции (текущий подход)**
- Дублирование логики
- Отдельные env переменные
- Больше кода

**Рекомендация:** Вариант A (provider classes)

---

## 4. Технические ограничения

### 4.1 Зависимости health-worker

Сейчас health-worker **не импортирует** provider classes:
```
services/free-ai-selector-health-worker/
├── app/
│   ├── main.py          # Только httpx, нет provider imports
│   └── utils/security.py
└── requirements.txt     # httpx, apscheduler
```

Для Варианта A нужно:
- Либо добавить provider код в health-worker
- Либо использовать Business API endpoint `/api/v1/providers/test`

### 4.2 Простейший подход

Health-worker может вызывать Business API:
```python
# Вместо 16 check_* функций:
async with httpx.AsyncClient() as client:
    response = await client.post(f"{BUSINESS_API_URL}/api/v1/providers/test")
```

Но это меняет логику: тест происходит в business-api, а не в worker.

---

## 5. Рекомендации

### 5.1 Telegram Bot (приоритет 1)

**Изменения:**
1. В `cmd_start`: вызвать `get_models_stats()`, построить динамический список
2. В `cmd_help`: заменить "6 провайдерам" → "всем провайдерам"

**Сложность:** Низкая (изменить текст)

### 5.2 test_all_providers.py (приоритет 2)

**Изменения:**
1. Добавить импорты 10 провайдеров
2. Расширить `self.providers` dict
3. Расширить `model_names` dict

**Сложность:** Низкая (копирование паттерна)

### 5.3 Health Worker (приоритет 3)

**Рекомендуемый подход:** Dispatch-словарь + новые check_* функции

```python
PROVIDER_CHECK_FUNCTIONS = {
    "GoogleGemini": check_google_gemini,
    "Groq": check_groq,
    # ... существующие
    "DeepSeek": check_deepseek,
    "Cohere": check_cohere,
    # ... новые
}

# Заменить if/elif на:
check_func = PROVIDER_CHECK_FUNCTIONS.get(provider)
if check_func:
    is_healthy, response_time = await check_func(endpoint)
```

**Сложность:** Средняя (10 новых функций)

---

## 6. Риски

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Timeout на /start при медленном API | Low | Cache + fallback |
| Отсутствие API ключа для нового провайдера | Med | Graceful skip + warning |
| Несовпадение model_names с БД | Low | Получать из БД через API |

---

## 7. Checklist RESEARCH_DONE

- [x] Код проанализирован
- [x] Архитектурные паттерны выявлены (AIProviderBase, health_check)
- [x] Технические ограничения определены
- [x] Рекомендации сформулированы
- [x] Риски идентифицированы
