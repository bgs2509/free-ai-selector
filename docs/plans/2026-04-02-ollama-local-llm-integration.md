# PLAN: Интеграция Ollama (локальные LLM) в Free AI Selector

**Дата:** 2026-04-02
**Статус:** Draft

---

## Контекст

Free AI Selector маршрутизирует запросы к 12 облачным AI-провайдерам. Все они — бесплатные, но имеют rate limits и зависят от внешней сети. Цель — добавить **локальные LLM через Ollama** как 13-й провайдер (с 10 моделями), что даёт:

- **Нулевую задержку сети** — модели на localhost
- **Отсутствие rate limits** — ограничение только GPU
- **Автономность** — работа без интернета
- **Fallback** — если облако упало, локальные модели отвечают, и наоборот

---

## Конфигурация сервера

| Компонент | Значение |
|-----------|----------|
| CPU | Intel Core i5-13400F (10 ядер / 16 потоков) |
| RAM | 64 GB |
| GPU | NVIDIA GeForce RTX 4060 (8 GB VRAM) |
| Диск | 500 GB NVMe SSD (~354 GB свободно) |
| CUDA | 13.1 |

---

## Выбор моделей: почему именно эти 10

### Задачи
Модели подбирались для **быстрого chat-бота** на гуманитарные темы: рекомендации по еде, гадания на таро, советы по обучению, анализ коротких ответов пользователей, классификация промптов по сферам. **Главный приоритет — скорость отклика.**

### Критерии отбора (в порядке приоритета)
1. Скорость генерации (tokens/sec) — пользователи не должны ждать
2. Качество диалога — естественные, полезные ответы
3. Русский язык — модель должна хорошо понимать и генерировать на русском
4. Классификация промптов — способность быстро категоризировать запросы
5. Полное размещение в GPU — без CPU offload для гарантии скорости

### Ограничения железа
- **8 GB VRAM** — модели до ~9B (Q4_K_M) влезают целиком в GPU
- **64 GB RAM** — позволяет CPU offload для моделей 12B+ (но медленно)
- Оптимальная квантизация: **Q4_K_M** — баланс качества и размера

### 10 отобранных моделей

| #   | Модель            | Размер | VRAM    | Скорость    | Русский | Назначение                              |
| --- | ----------------- | ------ | ------- | ----------- | ------- | --------------------------------------- |
| 1   | Gemma 3 1B        | 1B     | ~1 GB   | 120-150 t/s | Хор.    | Классификация промптов, роутинг         |
| 2   | Qwen3.5-2B        | 2B     | ~2 GB   | 100-120 t/s | Отл.    | Быстрые короткие ответы                 |
| 3   | SmolLM2 1.7B      | 1.7B   | ~1.5 GB | 110-130 t/s | Слаб.   | Минимальная задержка (EN only)          |
| 4   | Phi-4-mini        | 3.8B   | ~3.5 GB | 80-100 t/s  | Сред.   | Анализ ответов, советы                  |
| 5   | Gemma 3 4B        | 4B     | ~3 GB   | 70-90 t/s   | Хор.    | Баланс скорость/качество + vision       |
| 6   | Mistral Small 3.1 | 7B     | ~5 GB   | 50-65 t/s   | Хор.    | Самый быстрый 7B chat                   |
| 7   | Qwen 3 8B         | 8B     | ~5.5 GB | 40-55 t/s   | Отл.    | Глубокий chat, лучший русский           |
| 8   | Llama 3.3 8B      | 8B     | ~5.5 GB | 40-55 t/s   | Сред.   | Стабильный универсал                    |
| 9   | Qwen3.5-9B        | 9B     | ~7 GB   | 54-58 t/s   | Отл.    | Макс. качество в 8GB VRAM               |
| 10  | Gemma 3 12B       | 12B    | ~10 GB  | 4-11 t/s    | Хор.    | Лучшая проза (с CPU offload, медленная) |

### Обоснование выбора каждой модели

1. **Gemma 3 1B** — ультра-быстрый классификатор. Определяет тему промпта (еда/таро/обучение) за доли секунды. 140+ языков.
2. **Qwen3.5-2B** — новейшая архитектура (Gated Delta Networks + MoE). Лучший русский среди моделей до 3B. 201 язык.
3. **SmolLM2 1.7B** — создана специально для real-time отклика. Минимальная задержка. Но русский слабый.
4. **Phi-4-mini** — сильна в рассуждениях. Умеет объяснить «почему». Хороша для анализа ответов на правильность.
5. **Gemma 3 4B** — мультимодальная (текст + изображения). Может анализировать фото еды или карт таро. 128K контекст.
6. **Mistral Small 3.1** — самая быстрая в 7B классе. Европейские языки — сильная сторона (включая русский). Vision-модель.
7. **Qwen 3 8B** — два режима: thinking (глубокий) и non-thinking (быстрый). Лучший русский среди 8B. 119 языков.
8. **Llama 3.3 8B** — самая протестированная модель 2026 года. Огромное community. Стабильные ответы.
9. **Qwen3.5-9B** — абсолютный чемпион для 8GB VRAM. Бьёт модели в 13x крупнее. Мультимодальная. 201 язык.
10. **Gemma 3 12B** — лучшая проза среди моделей до 14B. Идеальна для развёрнутых описаний. Но не влезает в GPU — partial CPU offload, 4-11 t/s.

---

## Что такое Ollama

**Ollama — это программа-запускатор** для LLM моделей. Не модель, а **инфраструктура**:
- Скачивает модели из реестра
- Загружает выбранную модель в GPU
- Выставляет **OpenAI-совместимое API** на `localhost:11434`
- Управляет жизненным циклом моделей в памяти

### Управление памятью GPU

```
1-й запрос к модели → Ollama загружает её в GPU (2-5 сек)
                    → Модель обрабатывает запросы мгновенно (~55 t/s)
5 мин без запросов  → Модель автоматически выгружается из GPU
Запрос к другой модели → текущая выгружается, новая загружается
```

Параметр `OLLAMA_KEEP_ALIVE` управляет временем жизни модели в GPU:
- `5m` (default) — выгрузка через 5 минут неактивности
- `30m` — 30 минут
- `-1` — держать вечно (до перезапуска Ollama)

**В GPU одновременно — только одна модель** (при условии что она занимает почти все 8 GB). Маленькие модели (1-4B) могут сосуществовать: Gemma 3 1B (~1 GB) + Qwen3.5-9B (~7 GB) = ~8 GB.

---

## Совместимость с архитектурой проекта

### API контракт Ollama

Ollama выставляет **полностью OpenAI-совместимое API**:

```
POST http://localhost:11434/v1/chat/completions
GET  http://localhost:11434/v1/models
```

Формат запроса — **идентичен** текущим облачным провайдерам:
```json
{
  "model": "qwen3.5:9b",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."}
  ],
  "max_tokens": 512,
  "temperature": 0.7
}
```

Формат ответа — **идентичен** OpenAI:
```json
{
  "choices": [
    {
      "message": {
        "content": "ответ модели"
      }
    }
  ]
}
```

### Параметр `model` — как задавать модель для Ollama

**Ключевое отличие от облачных провайдеров:** у Groq один провайдер = одна модель (DEFAULT_MODEL). У Ollama — **один сервер, 10 моделей**.

В текущей архитектуре:
```
DB модель (name="Llama 3.3 70B") → provider="Groq" → ProviderRegistry → GroqProvider (DEFAULT_MODEL="llama-3.3-70b-versatile")
```

Для Ollama нужно **10 записей в registry**, по одной на каждую модель:
```
DB модель (name="Qwen3.5-9B (Local)") → provider="Ollama-Qwen3.5-9B" → ProviderRegistry → OllamaProvider (model="qwen3.5:9b")
DB модель (name="Gemma 3 1B (Local)")  → provider="Ollama-Gemma3-1B"  → ProviderRegistry → OllamaProvider (model="gemma3:1b")
```

Каждая Ollama-модель регистрируется как **отдельный провайдер** с уникальным именем. Это вписывается в текущую архитектуру без изменения ядра.

### Имена моделей в Ollama

Ollama использует формат `name:tag`:
```
qwen3.5:9b      ← имя модели : размер/версия
gemma3:1b
gemma3:4b
phi4-mini       ← без тега = latest
mistral-small3.1
qwen3:8b
llama3.3:8b
qwen3.5:2b
smollm2:1.7b
gemma3:12b
```

Это значение передаётся в поле `"model"` HTTP-запроса и является `DEFAULT_MODEL` соответствующего провайдера.

---

## Техническая проблема: API Key

### Проблема
`OpenAICompatibleProvider.__init__` **требует API key** и бросает `ValueError` если его нет:
```python
self.api_key = api_key or os.getenv(self.API_KEY_ENV, "")
if not self.api_key:
    raise ValueError(f"{self.API_KEY_ENV} is required")
```

Ollama **не требует API key**. Но посылает заголовок `Authorization: Bearer {api_key}` — Ollama его просто игнорирует.

### Решение
Использовать **dummy API key**: `OLLAMA_API_KEY=ollama` в `.env`. Ollama примет запрос с любым Bearer токеном. Метод `_filter_configured_models` в `process_prompt.py` проверяет наличие env переменной — dummy key проходит эту проверку.

---

## Техническая проблема: таймаут первого запроса

### Проблема
Первый запрос к модели триггерит загрузку в GPU (2-5 сек для малых моделей, до 10 сек для 9B). Текущий `TIMEOUT = 30.0` достаточен, но для перестраховки:

### Решение
Установить `TIMEOUT = 120.0` для Ollama-провайдеров. Это покрывает:
- Загрузку модели в GPU (2-10 сек)
- Генерацию ответа (зависит от длины)
- Запас на нестандартные ситуации

---

## План реализации

### Этап 1: Установка Ollama и загрузка моделей

**Действие:**
```bash
# 1. Установить Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 2. Загрузить все 10 моделей
ollama pull gemma3:1b
ollama pull qwen3.5:2b
ollama pull smollm2:1.7b
ollama pull phi4-mini
ollama pull gemma3:4b
ollama pull mistral-small3.1
ollama pull qwen3:8b
ollama pull llama3.3:8b
ollama pull qwen3.5:9b
ollama pull gemma3:12b
```

**Результат:** Ollama запущен как systemd-сервис на `localhost:11434`. Все 10 моделей загружены на диск (~35-40 GB).

**Проверка:**
```bash
ollama list                    # все 10 моделей видны
curl http://localhost:11434/v1/models  # API отвечает
```

---

### Этап 2: Создание OllamaProvider

**Файл:** `services/free-ai-selector-business-api/app/infrastructure/ai_providers/ollama.py`

**Действие:** Создать базовый класс `OllamaProvider` + фабрику для генерации классов под каждую модель.

```python
"""
Ollama Local LLM Provider integration.

Integrates with local Ollama server for GPU-accelerated LLM inference.
10 models for humanitarian chat tasks: food, tarot, learning, classification.
No API key required. No rate limits. No network dependency.
"""

from typing import ClassVar

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider


class OllamaProvider(OpenAICompatibleProvider):
    """
    Base class for all Ollama local models.

    Ollama exposes OpenAI-compatible API at localhost:11434.
    API key is dummy (Ollama ignores Authorization header).
    Extended timeout for first-request model loading (2-10 sec).
    """

    BASE_URL: ClassVar[str] = "http://localhost:11434/v1/chat/completions"
    MODELS_URL: ClassVar[str] = "http://localhost:11434/v1/models"
    API_KEY_ENV: ClassVar[str] = "OLLAMA_API_KEY"
    SUPPORTS_RESPONSE_FORMAT: ClassVar[bool] = True
    TIMEOUT: ClassVar[float] = 120.0


def _make_ollama_provider(name: str, model: str) -> type[OllamaProvider]:
    """Factory: create OllamaProvider subclass for specific model."""
    return type(name, (OllamaProvider,), {
        "PROVIDER_NAME": name,
        "DEFAULT_MODEL": model,
    })


# 10 Ollama model providers
OllamaGemma3_1B = _make_ollama_provider("Ollama-Gemma3-1B", "gemma3:1b")
OllamaQwen35_2B = _make_ollama_provider("Ollama-Qwen3.5-2B", "qwen3.5:2b")
OllamaSmolLM2 = _make_ollama_provider("Ollama-SmolLM2-1.7B", "smollm2:1.7b")
OllamaPhi4Mini = _make_ollama_provider("Ollama-Phi4-Mini", "phi4-mini")
OllamaGemma3_4B = _make_ollama_provider("Ollama-Gemma3-4B", "gemma3:4b")
OllamaMistralSmall = _make_ollama_provider("Ollama-Mistral-Small-3.1", "mistral-small3.1")
OllamaQwen3_8B = _make_ollama_provider("Ollama-Qwen3-8B", "qwen3:8b")
OllamaLlama33_8B = _make_ollama_provider("Ollama-Llama3.3-8B", "llama3.3:8b")
OllamaQwen35_9B = _make_ollama_provider("Ollama-Qwen3.5-9B", "qwen3.5:9b")
OllamaGemma3_12B = _make_ollama_provider("Ollama-Gemma3-12B", "gemma3:12b")

# All Ollama providers for easy registration
OLLAMA_PROVIDERS: dict[str, type[OllamaProvider]] = {
    "Ollama-Gemma3-1B": OllamaGemma3_1B,
    "Ollama-Qwen3.5-2B": OllamaQwen35_2B,
    "Ollama-SmolLM2-1.7B": OllamaSmolLM2,
    "Ollama-Phi4-Mini": OllamaPhi4Mini,
    "Ollama-Gemma3-4B": OllamaGemma3_4B,
    "Ollama-Mistral-Small-3.1": OllamaMistralSmall,
    "Ollama-Qwen3-8B": OllamaQwen3_8B,
    "Ollama-Llama3.3-8B": OllamaLlama33_8B,
    "Ollama-Qwen3.5-9B": OllamaQwen35_9B,
    "Ollama-Gemma3-12B": OllamaGemma3_12B,
}
```

**Результат:** Один файл, 10 провайдеров. Каждый — отдельный класс с уникальным `PROVIDER_NAME` и `DEFAULT_MODEL`.

---

### Этап 3: Регистрация в ProviderRegistry

**Файл:** `services/free-ai-selector-business-api/app/infrastructure/ai_providers/registry.py`

**Действие:** Добавить импорт и регистрацию 10 Ollama-провайдеров.

```python
from app.infrastructure.ai_providers.ollama import OLLAMA_PROVIDERS

PROVIDER_CLASSES: dict[str, type[AIProviderBase]] = {
    # Существующие провайдеры (12 шт.)
    "Groq": GroqProvider,
    ...
    "Scaleway": ScalewayProvider,
    # Локальные провайдеры — Ollama (10 шт.)
    **OLLAMA_PROVIDERS,
}
```

**Результат:** ProviderRegistry знает о всех 10 Ollama-моделях. `get_provider("Ollama-Qwen3.5-9B")` возвращает инстанс с `model="qwen3.5:9b"`.

---

### Этап 4: Seed данные в БД

**Файл:** `services/free-ai-selector-data-postgres-api/app/infrastructure/database/seed.py`

**Действие:** Добавить 10 записей в `SEED_MODELS`:

```python
# ═══════════════════════════════════════════════════════════════════════
# Локальные модели — Ollama (10 шт.)
# ═══════════════════════════════════════════════════════════════════════
{
    "name": "Gemma 3 1B (Local)",
    "provider": "Ollama-Gemma3-1B",
    "api_endpoint": "http://localhost:11434/v1/chat/completions",
    "is_active": True,
    "api_format": "openai",
},
{
    "name": "Qwen3.5 2B (Local)",
    "provider": "Ollama-Qwen3.5-2B",
    "api_endpoint": "http://localhost:11434/v1/chat/completions",
    "is_active": True,
    "api_format": "openai",
},
{
    "name": "SmolLM2 1.7B (Local)",
    "provider": "Ollama-SmolLM2-1.7B",
    "api_endpoint": "http://localhost:11434/v1/chat/completions",
    "is_active": True,
    "api_format": "openai",
},
{
    "name": "Phi-4 Mini (Local)",
    "provider": "Ollama-Phi4-Mini",
    "api_endpoint": "http://localhost:11434/v1/chat/completions",
    "is_active": True,
    "api_format": "openai",
},
{
    "name": "Gemma 3 4B (Local)",
    "provider": "Ollama-Gemma3-4B",
    "api_endpoint": "http://localhost:11434/v1/chat/completions",
    "is_active": True,
    "api_format": "openai",
},
{
    "name": "Mistral Small 3.1 (Local)",
    "provider": "Ollama-Mistral-Small-3.1",
    "api_endpoint": "http://localhost:11434/v1/chat/completions",
    "is_active": True,
    "api_format": "openai",
},
{
    "name": "Qwen 3 8B (Local)",
    "provider": "Ollama-Qwen3-8B",
    "api_endpoint": "http://localhost:11434/v1/chat/completions",
    "is_active": True,
    "api_format": "openai",
},
{
    "name": "Llama 3.3 8B (Local)",
    "provider": "Ollama-Llama3.3-8B",
    "api_endpoint": "http://localhost:11434/v1/chat/completions",
    "is_active": True,
    "api_format": "openai",
},
{
    "name": "Qwen3.5 9B (Local)",
    "provider": "Ollama-Qwen3.5-9B",
    "api_endpoint": "http://localhost:11434/v1/chat/completions",
    "is_active": True,
    "api_format": "openai",
},
{
    "name": "Gemma 3 12B (Local)",
    "provider": "Ollama-Gemma3-12B",
    "api_endpoint": "http://localhost:11434/v1/chat/completions",
    "is_active": True,
    "api_format": "openai",
},
```

**Результат:** После `make seed` в БД появляются 10 локальных моделей. Они участвуют в reliability scoring наравне с облачными.

---

### Этап 5: Конфигурация окружения

**Файл:** `.env` и `.env.example`

**Действие:** Добавить:
```bash
# Ollama Local LLM (dummy key — Ollama ignores Authorization header)
OLLAMA_API_KEY=ollama

# Ollama keep-alive: how long models stay loaded in GPU after last request
# Options: 5m (default), 30m, -1 (forever)
OLLAMA_KEEP_ALIVE=30m
```

**Файл:** `docker-compose.yml`

**Действие:** Добавить `OLLAMA_API_KEY` в environment Business API:
```yaml
environment:
  ...
  OLLAMA_API_KEY: ${OLLAMA_API_KEY:-ollama}
```

**Результат:** Business API видит `OLLAMA_API_KEY` → `_filter_configured_models` пропускает Ollama-модели.

---

### Этап 6: Health Worker — поддержка Ollama

Health Worker выполняет синтетический мониторинг каждый час. Для Ollama-моделей health check (`GET /v1/models`) покажет какие модели установлены, но **не** какая загружена в GPU.

**Действие:** Никаких изменений не нужно — существующий `health_check()` из `OpenAICompatibleProvider` вызывает `GET http://localhost:11434/v1/models` и проверяет статус 200. Это работает из коробки.

**Нюанс:** Health check не загружает модель в GPU. Загрузка происходит только при первом `generate()` запросе.

---

## Как будет работать загрузка и выгрузка моделей

### Жизненный цикл модели

```
                    ┌──────────────────────────────┐
                    │  Ollama Server (localhost)    │
                    │  Все 10 моделей на ДИСКЕ      │
                    │  (~35-40 GB SSD)              │
                    └──────────┬───────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
   Запрос к              Запрос к               Запрос к
   Gemma 3 1B            Qwen3.5 9B             Qwen 3 8B
        │                      │                      │
        ▼                      ▼                      ▼
   Загрузка               Выгрузка              Выгрузка
   в GPU (~1 сек)         Gemma 1B,             Qwen3.5 9B,
                          Загрузка              Загрузка
                          Qwen3.5 9B            Qwen 3 8B
                          (~3-5 сек)            (~3-5 сек)
        │                      │                      │
        ▼                      ▼                      ▼
   Ответ мгновенно        Ответ мгновенно        Ответ мгновенно
   (120-150 t/s)          (54-58 t/s)           (40-55 t/s)
        │                      │                      │
        ▼                      ▼                      ▼
   KEEP_ALIVE=30m          KEEP_ALIVE=30m        KEEP_ALIVE=30m
   (ждёт запросов)         (ждёт запросов)       (ждёт запросов)
        │                      │                      │
        ▼                      ▼                      ▼
   30 мин без              30 мин без            30 мин без
   запросов →              запросов →            запросов →
   ВЫГРУЗКА из GPU         ВЫГРУЗКА из GPU       ВЫГРУЗКА из GPU
```

### Сценарии работы в проекте

**Сценарий 1: Пользователь запрашивает конкретную локальную модель**
```
POST /api/v1/prompts/process
  { "prompt": "Расскажи про карту Башня", "model_id": 15 }
                         │
                         ▼
  model_id=15 → "Qwen3.5 9B (Local)" → provider="Ollama-Qwen3.5-9B"
                         │
                         ▼
  ProviderRegistry.get_provider("Ollama-Qwen3.5-9B")
                         │
                         ▼
  POST http://localhost:11434/v1/chat/completions
    { "model": "qwen3.5:9b", "messages": [...] }
                         │
                         ▼
  Ollama: модель уже в GPU? → ДА → ответ за ~0.5 сек
                              → НЕТ → загрузка 3-5 сек, потом ответ
```

**Сценарий 2: Автоматический выбор (reliability scoring)**
```
POST /api/v1/prompts/process
  { "prompt": "Рецепт борща" }
                         │
                         ▼
  Все модели отсортированы по effective_reliability_score
  Локальные и облачные — в одном списке
                         │
                         ▼
  Лучшая модель: Groq (score=0.95) → пробуем
                         │
                         ▼
  Groq 429 (rate limit) → fallback
                         │
                         ▼
  Следующая: Qwen3.5 9B Local (score=0.90) → пробуем
                         │
                         ▼
  Ollama загружает модель, отвечает → УСПЕХ
```

**Сценарий 3: Облако недоступно (нет интернета)**
```
Все облачные провайдеры → timeout/error → reliability_score падает
Локальные модели → всегда доступны → reliability_score растёт
                         │
                         ▼
  Система автоматически переключается на локальные модели
```

### Влияние на reliability scoring

Первый запрос к модели (cold start):
- Время ответа: 5-15 сек (загрузка + генерация)
- `speed_score` будет низким из-за этого одного запроса
- После 5-10 запросов — `average_response_time` нормализуется

Последующие запросы (warm):
- Время ответа: 0.3-2 сек (только генерация)
- `speed_score` будет высоким
- `success_rate` = 1.0 (локальные модели почти никогда не падают)

**Итого:** после набора статистики локальные модели получат высокий `reliability_score` за счёт 100% `success_rate` и отсутствия rate limits.

---

## Файлы для модификации

| # | Файл | Действие |
|---|------|----------|
| 1 | `services/free-ai-selector-business-api/app/infrastructure/ai_providers/ollama.py` | **Создать** — OllamaProvider + 10 моделей |
| 2 | `services/free-ai-selector-business-api/app/infrastructure/ai_providers/registry.py` | **Изменить** — добавить OLLAMA_PROVIDERS |
| 3 | `services/free-ai-selector-data-postgres-api/app/infrastructure/database/seed.py` | **Изменить** — добавить 10 seed-записей |
| 4 | `.env.example` | **Изменить** — добавить OLLAMA_API_KEY |
| 5 | `.env` | **Изменить** — добавить OLLAMA_API_KEY=ollama |
| 6 | `docker-compose.yml` | **Изменить** — добавить OLLAMA_API_KEY в environment |

**Не изменяются:**
- `base.py` — OllamaProvider наследует OpenAICompatibleProvider без изменений
- `process_prompt.py` — fallback, scoring, filtering работают как есть
- `data_api_client.py` — HTTP-клиент не меняется
- `models.py` (ORM) — схема БД не меняется

---

## Верификация

### Шаг 1: Проверить Ollama
```bash
ollama list                                    # 10 моделей
curl http://localhost:11434/v1/models          # API отвечает
curl -X POST http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gemma3:1b","messages":[{"role":"user","content":"Привет"}]}'
```

### Шаг 2: Пересобрать и запустить сервисы
```bash
make build && make up && make seed
```

### Шаг 3: Проверить через Business API
```bash
# Автовыбор (может выбрать локальную или облачную)
curl -X POST http://localhost:8020/api/v1/prompts/process \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Расскажи про карту Таро Башня"}'

# Форсированный выбор конкретной локальной модели (подставить id из БД)
curl -X POST http://localhost:8020/api/v1/prompts/process \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Рецепт борща","model_id":15}'
```

### Шаг 4: Проверить статистику
```bash
curl http://localhost:8020/api/v1/models/stats | python3 -m json.tool
# Должны быть видны 10 локальных моделей с "(Local)" в имени
```

### Шаг 5: Проверить VRAM
```bash
nvidia-smi
# VRAM не должен превышать 8 GB при загруженной модели
```

---

## Риски и митигация

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Cold start 5-15 сек на первый запрос | Высокая | `KEEP_ALIVE=30m` держит модель в GPU. Health Worker прогревает. |
| GPU занят другим процессом | Средняя | `nvidia-smi` показывает 2.6 GB занято Python. Останется ~5.4 GB — хватит для моделей до 4B. Для 9B нужно освободить GPU. |
| Ollama не стартует после reboot | Низкая | Ollama устанавливается как systemd-сервис, стартует автоматически. |
| Модель отвечает некорректно (галлюцинации) | Средняя | `reliability_score` понизится, система переключится на облачные модели. |
