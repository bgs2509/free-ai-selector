---
feature_id: "F004"
feature_name: "dynamic-providers-list"
title: "План реализации: Динамический список провайдеров"
created: "2025-12-25"
author: "AI (Architect)"
type: "feature-plan"
status: "PLAN_READY"
version: 1
mode: "FEATURE"
related_features: ["F003"]
services: ["free-ai-selector-telegram-bot", "free-ai-selector-business-api", "free-ai-selector-health-worker"]
---

# План фичи: F004 - Динамический список провайдеров

## 1. Обзор

### 1.1 Краткое описание
Замена захардкоженных списков из 6 провайдеров на динамические во всех трёх сервисах. После F003 в системе 16 провайдеров, но TG бот, test_all_providers и health-worker показывают/тестируют только 6.

### 1.2 Связь с существующим функционалом
- **F003** добавил 10 новых провайдеров в `process_prompt.py`
- API `/api/v1/models/stats` уже возвращает все 16 моделей
- Все 16 провайдеров имеют метод `health_check()`

---

## 2. Анализ существующего кода

### 2.1 Затронутые сервисы

| Сервис | Файл | Проблема |
|--------|------|----------|
| telegram-bot | `app/main.py` | Строки 143-149: хардкод 6 провайдеров в /start |
| telegram-bot | `app/main.py` | Строка 183: "6 провайдерам" в /help |
| business-api | `app/.../test_all_providers.py` | Строки 52-60: dict 6 провайдеров |
| business-api | `app/.../test_all_providers.py` | Строки 237-245: model_names 6 записей |
| health-worker | `app/main.py` | Строки 308-322: if/elif для 6 провайдеров |
| health-worker | `app/main.py` | Строка 380: "6" в логе |

### 2.2 Точки интеграции

```
telegram-bot/main.py
       │
       ▼ HTTP GET
┌─────────────────────────────────────┐
│ Business API: /api/v1/models/stats  │ ◀── Уже возвращает 16 моделей
└─────────────────────────────────────┘
```

### 2.3 Существующие зависимости

**Telegram Bot**:
- Функция `get_models_stats()` уже существует (строка 73)
- Возвращает список всех моделей из API

**test_all_providers.py**:
- Импорты провайдеров (только 6 из 16)
- Использует тот же паттерн что и `process_prompt.py`

**health-worker**:
- Собственные check_* функции для каждого провайдера
- Не использует классы провайдеров из business-api

---

## 3. План изменений

### 3.1 Новые компоненты

Нет новых компонентов — только модификация существующих.

### 3.2 Модификации существующего кода

#### 3.2.1 Telegram Bot (`services/free-ai-selector-telegram-bot/app/main.py`)

| Строки | Изменение | Причина |
|--------|-----------|---------|
| 132-152 | Переписать `cmd_start` | Динамический список из API |
| 183 | Заменить "6 провайдерам" | Корректное число |

**Код cmd_start (новый):**
```python
@router.message(Command("start"))
async def cmd_start(message: Message):
    """Handle /start command."""
    # Получить список моделей из API
    stats = await get_models_stats()

    if stats and stats.get("models"):
        models = stats["models"]
        total = len(models)

        # Сортировка по reliability_score
        models.sort(key=lambda m: m.get("reliability_score", 0), reverse=True)

        # Формируем список провайдеров
        providers_lines = []
        for model in models:
            provider = model.get("provider", "Unknown")
            name = model.get("name", "Unknown")
            is_active = model.get("is_active", False)
            icon = "✅" if is_active else "⚠️"
            providers_lines.append(f"{icon} {provider} - {name}")

        providers_text = "\n".join(providers_lines)
        count_text = f"{total} бесплатных AI провайдеров"
    else:
        # Fallback если API недоступен
        providers_text = "⚠️ Не удалось загрузить список моделей"
        count_text = "AI провайдеры"

    welcome_text = f"""
👋 <b>Добро пожаловать в Free AI Selector!</b>

Я автоматически выбираю лучшую бесплатную AI модель...

<b>Как использовать:</b>
• Просто отправьте мне любой текст
• /stats — статистика моделей
• /test — проверка провайдеров
• /help — справка

<b>{count_text} (без кредитной карты):</b>
{providers_text}

Начните прямо сейчас!
"""
    await message.answer(welcome_text, parse_mode="HTML")
    logger.info(f"User {message.from_user.id} started the bot")
```

**Код cmd_help (изменение строки 183):**
```python
# Было:
Отправляет тестовый запрос ко всем 6 провайдерам

# Стало:
Отправляет тестовый запрос ко всем провайдерам
```

#### 3.2.2 test_all_providers.py (`services/free-ai-selector-business-api/app/application/use_cases/test_all_providers.py`)

| Строки | Изменение | Причина |
|--------|-----------|---------|
| 15-21 | Добавить 10 импортов | Новые провайдеры |
| 52-60 | Расширить self.providers | 16 вместо 6 |
| 237-245 | Расширить model_names | 16 вместо 6 |

**Новые импорты:**
```python
from app.infrastructure.ai_providers.cohere import CohereProvider
from app.infrastructure.ai_providers.deepseek import DeepSeekProvider
from app.infrastructure.ai_providers.fireworks import FireworksProvider
from app.infrastructure.ai_providers.github_models import GitHubModelsProvider
from app.infrastructure.ai_providers.hyperbolic import HyperbolicProvider
from app.infrastructure.ai_providers.kluster import KlusterProvider
from app.infrastructure.ai_providers.nebius import NebiusProvider
from app.infrastructure.ai_providers.novita import NovitaProvider
from app.infrastructure.ai_providers.openrouter import OpenRouterProvider
from app.infrastructure.ai_providers.scaleway import ScalewayProvider
```

**Новый self.providers:**
```python
self.providers = {
    # Существующие (6)
    "GoogleGemini": GoogleGeminiProvider(),
    "Groq": GroqProvider(),
    "Cerebras": CerebrasProvider(),
    "SambaNova": SambanovaProvider(),
    "HuggingFace": HuggingFaceProvider(),
    "Cloudflare": CloudflareProvider(),
    # F003 Фаза 1 (4)
    "DeepSeek": DeepSeekProvider(),
    "Cohere": CohereProvider(),
    "OpenRouter": OpenRouterProvider(),
    "GitHubModels": GitHubModelsProvider(),
    # F003 Фаза 2 (4)
    "Fireworks": FireworksProvider(),
    "Hyperbolic": HyperbolicProvider(),
    "Novita": NovitaProvider(),
    "Scaleway": ScalewayProvider(),
    # F003 Фаза 3 (2)
    "Kluster": KlusterProvider(),
    "Nebius": NebiusProvider(),
}
```

**Новый model_names:**
```python
model_names = {
    "GoogleGemini": "Gemini 2.5 Flash",
    "Groq": "Llama 3.3 70B Versatile",
    "Cerebras": "Llama 3.3 70B",
    "SambaNova": "Meta-Llama-3.3-70B-Instruct",
    "HuggingFace": "Meta-Llama-3-8B-Instruct",
    "Cloudflare": "Llama 3.3 70B FP8 Fast",
    "DeepSeek": "DeepSeek-V3",
    "Cohere": "Command-R",
    "OpenRouter": "DeepSeek-R1 (free)",
    "GitHubModels": "GPT-4o-mini",
    "Fireworks": "Llama 3.3 70B",
    "Hyperbolic": "Llama 3.3 70B",
    "Novita": "Llama 3.3 70B",
    "Scaleway": "Llama 3.3 70B",
    "Kluster": "Llama-3.3-70B",
    "Nebius": "Llama-3.3-70B-Instruct",
}
```

#### 3.2.3 Health Worker (`services/free-ai-selector-health-worker/app/main.py`)

| Строки | Изменение | Причина |
|--------|-----------|---------|
| 38-46 | Добавить 10 env переменных | API ключи новых провайдеров |
| После 272 | Добавить 10 check_* функций | Проверки новых провайдеров |
| 308-322 | Заменить if/elif на dispatch | Масштабируемость |
| 366-380 | Обновить логирование | 16 вместо 6 |

**Новые env переменные:**
```python
# Новые провайдеры F003
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
COHERE_API_KEY = os.getenv("COHERE_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY", "")
HYPERBOLIC_API_KEY = os.getenv("HYPERBOLIC_API_KEY", "")
NOVITA_API_KEY = os.getenv("NOVITA_API_KEY", "")
SCALEWAY_API_KEY = os.getenv("SCALEWAY_API_KEY", "")
KLUSTER_API_KEY = os.getenv("KLUSTER_API_KEY", "")
NEBIUS_API_KEY = os.getenv("NEBIUS_API_KEY", "")
```

**Dispatch-словарь (заменяет if/elif):**
```python
PROVIDER_CHECK_FUNCTIONS = {
    "GoogleGemini": check_google_gemini,
    "Groq": check_groq,
    "Cerebras": check_cerebras,
    "SambaNova": check_sambanova,
    "HuggingFace": check_huggingface,
    "Cloudflare": check_cloudflare,
    "DeepSeek": check_deepseek,
    "Cohere": check_cohere,
    "OpenRouter": check_openrouter,
    "GitHubModels": check_github_models,
    "Fireworks": check_fireworks,
    "Hyperbolic": check_hyperbolic,
    "Novita": check_novita,
    "Scaleway": check_scaleway,
    "Kluster": check_kluster,
    "Nebius": check_nebius,
}

# В run_health_checks():
check_func = PROVIDER_CHECK_FUNCTIONS.get(provider)
if check_func:
    is_healthy, response_time = await check_func(endpoint)
else:
    logger.warning(f"Unknown provider: {provider}, skipping")
    continue
```

### 3.3 Новые зависимости

Нет новых зависимостей — всё уже установлено.

---

## 4. API контракты

Изменений в API нет. Используются существующие:

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/api/v1/models/stats` | GET | Список всех моделей |
| `/api/v1/providers/test` | POST | Тест всех провайдеров |

---

## 5. Влияние на существующие тесты

### 5.1 Тесты которые нужно обновить

| Файл | Изменение |
|------|-----------|
| `tests/unit/test_all_providers_use_case.py` | Ожидать 16 провайдеров вместо 6 |

### 5.2 Новые тесты

Не требуются — логика не меняется, только расширяется.

---

## 6. План интеграции

| # | Шаг | Файлы | Зависимости |
|---|-----|-------|-------------|
| 1 | Обновить test_all_providers.py | business-api | Нет |
| 2 | Добавить check_* функции в health-worker | health-worker | Нет |
| 3 | Обновить dispatch в health-worker | health-worker | Шаг 2 |
| 4 | Обновить cmd_start в TG боте | telegram-bot | Нет |
| 5 | Обновить cmd_help в TG боте | telegram-bot | Нет |
| 6 | Запустить тесты | Все | Шаги 1-5 |
| 7 | Деплой и проверка | - | Шаг 6 |

---

## 7. Риски и митигация

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Timeout /start при медленном API | Low | Low | Fallback сообщение уже есть |
| Новый провайдер без check_* | Med | Low | Warning в логе, skip |
| Отсутствие API ключа | Med | Low | Graceful skip с warning |

---

## 8. Checklist готовности плана

- [x] Все файлы для изменения идентифицированы
- [x] Код изменений описан детально
- [x] Зависимости между шагами определены
- [x] Риски идентифицированы
- [x] План обратно совместим (старый код работает)

---

## Ожидание утверждения

**Требуется явное подтверждение от пользователя для прохождения ворот PLAN_APPROVED.**
