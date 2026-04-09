# AI Providers

> Документация по AI-провайдерам Free AI Selector.

## Обзор

Free AI Selector интегрирован с 14 бесплатными AI-провайдерами (7 существующих + 7 F003). Все работают без кредитной карты.

### Система тегов

Каждый провайдер имеет набор тегов (`TAGS: ClassVar[set[str]]`) для фильтрации в API и Web UI:

| Тег | Значение |
|-----|----------|
| `fast` | Быстрый ответ |
| `json` | Поддержка JSON response_format |
| `code` | Хорошо генерирует код |
| `reasoning` | Reasoning модель (chain-of-thought) |
| `russian` | Хорошая поддержка русского языка |
| `tools` | Поддержка function calling / tools |
| `lightweight` | Лёгкая модель (8B и меньше) |

## Список провайдеров

### Существующие провайдеры (7 шт.)

#### 1. Groq

| Параметр | Значение |
|----------|----------|
| Класс | `GroqProvider` |
| Модель | Llama 3.3 70B Versatile |
| Rate Limit | 20 RPM |
| Скорость | Очень высокая (до 1800 tokens/sec) |
| Качество | Высокое |
| API Key | `GROQ_API_KEY` |

**Получение ключа:** [Groq Console](https://console.groq.com/keys)

#### 2. Cerebras

| Параметр | Значение |
|----------|----------|
| Класс | `CerebrasProvider` |
| Модель | Llama 3.1 8B |
| Rate Limit | 30 RPM, 1M tokens/day |
| Скорость | Очень высокая (2500+ tokens/sec) |
| Качество | Высокое |
| API Key | `CEREBRAS_API_KEY` |

**Получение ключа:** [Cerebras Cloud](https://cloud.cerebras.ai/)

#### 3. SambaNova

| Параметр | Значение |
|----------|----------|
| Класс | `SambanovaProvider` |
| Модель | Meta-Llama-3.3-70B-Instruct |
| Rate Limit | 20 RPM |
| Скорость | Высокая |
| Качество | Высокое |
| API Key | `SAMBANOVA_API_KEY` |

**Получение ключа:** [SambaNova Cloud](https://cloud.sambanova.ai/)

#### 4. HuggingFace

| Параметр | Значение |
|----------|----------|
| Класс | `HuggingFaceProvider` |
| Модель | Meta-Llama-3-8B-Instruct |
| Rate Limit | Переменный |
| Скорость | Средняя |
| Качество | Хорошее |
| API Key | `HUGGINGFACE_API_KEY` |

**Получение ключа:** [HuggingFace Settings](https://huggingface.co/settings/tokens)

#### 5. Cloudflare Workers AI

| Параметр | Значение |
|----------|----------|
| Класс | `CloudflareProvider` |
| Модель | Llama 3.3 70B Instruct FP8 Fast |
| Rate Limit | 10,000 Neurons/day |
| Скорость | Средняя |
| Качество | Высокое |
| API Keys | `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` |

**Получение ключей:** [Cloudflare Dashboard](https://dash.cloudflare.com/)

#### 6. Cloudflare Gemma 3

| Параметр | Значение |
|----------|----------|
| Класс | `CloudflareGemma3Provider` |
| Модель | Gemma 3 12B IT |
| Rate Limit | 10,000 Neurons/day |
| Теги | fast, json, code, russian |
| API Keys | `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` |

#### 7. Cloudflare Qwen3

| Параметр | Значение |
|----------|----------|
| Класс | `CloudflareQwen3Provider` |
| Модель | Qwen3 30B A3B FP8 |
| Rate Limit | 10,000 Neurons/day |
| Теги | fast, json, code, russian |
| API Keys | `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` |

### Новые провайдеры F003 (7 шт.)

#### 8. DeepSeek
- **Класс:** `DeepSeekProvider`
- **Модель:** DeepSeek Chat
- **Rate Limit:** 60 RPM
- **API Key:** `DEEPSEEK_API_KEY`
- **URL:** [DeepSeek Platform](https://platform.deepseek.com/)

#### 9. OpenRouter
- **Класс:** `OpenRouterProvider`
- **Модель:** DeepSeek R1 Free
- **Rate Limit:** 20 RPM
- **API Key:** `OPENROUTER_API_KEY`
- **URL:** [OpenRouter](https://openrouter.ai/)

#### 10. GitHub Models
- **Класс:** `GitHubModelsProvider`
- **Модель:** GPT-4o Mini
- **Rate Limit:** 15 RPM, 150 RPD
- **API Key:** `GITHUB_TOKEN`
- **URL:** [GitHub Models](https://github.com/marketplace/models)

#### 11. Fireworks
- **Класс:** `FireworksProvider`
- **Модель:** GPT-OSS-20B
- **Free Credits:** $1
- **API Key:** `FIREWORKS_API_KEY`
- **URL:** [Fireworks AI](https://fireworks.ai/)

#### 12. Hyperbolic
- **Класс:** `HyperbolicProvider`
- **Модель:** Llama 3.3 70B
- **Free Tier:** Available
- **API Key:** `HYPERBOLIC_API_KEY`
- **URL:** [Hyperbolic](https://hyperbolic.xyz/)

#### 13. Novita
- **Класс:** `NovitaProvider`
- **Модель:** Llama 3.1 8B Instruct
- **Free Tier:** Available
- **API Key:** `NOVITA_API_KEY`
- **URL:** [Novita AI](https://novita.ai/)

#### 14. Scaleway
- **Класс:** `ScalewayProvider`
- **Модель:** Llama 3.1 70B
- **Free Tier:** Available
- **API Key:** `SCALEWAY_API_KEY`
- **URL:** [Scaleway](https://www.scaleway.com/)

---

## Интерфейс провайдера

Все OpenAI-совместимые провайдеры наследуют от `OpenAICompatibleProvider` (base.py). Cloudflare имеет собственную реализацию.

Ключевые `ClassVar` атрибуты:
- `API_KEY_ENV` — имя env переменной для API ключа
- `MAX_OUTPUT_TOKENS` — максимум токенов вывода (per-provider, по умолчанию 2048)
- `TAGS` — набор тегов для фильтрации (`set[str]`)
- `SUPPORTS_RESPONSE_FORMAT` — поддержка JSON response_format

**Reasoning модели**: ответ может быть в `reasoning_content` вместо `content`. Метод `_parse_response()` автоматически использует `reasoning_content` как fallback.

---

## Добавление нового провайдера

### Шаг 1: Создать файл провайдера

```bash
# Путь
services/free-ai-selector-business-api/app/infrastructure/ai_providers/newprovider.py
```

```python
import os
import httpx
from app.infrastructure.ai_providers.base import AIProviderBase


class NewProvider(AIProviderBase):
    """
    New AI Provider.

    Free tier: описание лимитов
    """

    def __init__(self):
        self.api_key = os.getenv("NEW_PROVIDER_API_KEY")
        self.base_url = "https://api.newprovider.com/v1"

    async def generate(self, prompt: str, **kwargs) -> str:
        """Сгенерировать ответ."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": "model-name",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": kwargs.get("temperature", 0.7),
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def health_check(self) -> bool:
        """Проверить доступность."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return response.status_code == 200
        except Exception:
            return False

    def get_provider_name(self) -> str:
        return "NewProvider"
```

### Шаг 2: Зарегистрировать в Registry

```python
# services/free-ai-selector-business-api/app/infrastructure/ai_providers/registry.py

PROVIDER_CLASSES: dict[str, type[AIProviderBase]] = {
    # ... existing providers
    "NewProvider": NewProviderClass,  # Добавить сюда
}
```

### Шаг 3: Добавить модель в seed

```python
# services/free-ai-selector-data-postgres-api/app/infrastructure/database/seed.py

INITIAL_MODELS = [
    # ... existing models
    {
        "name": "New Model Name",
        "provider": "NewProvider",  # Должен совпадать с ключом в providers
        "api_endpoint": "https://api.newprovider.com/v1",
        "is_active": True,
    },
]
```

### Шаг 4: Добавить переменные окружения

```bash
# .env
NEW_PROVIDER_API_KEY=your_api_key_here

# docker-compose.yml (в секции environment для business_api)
- NEW_PROVIDER_API_KEY=${NEW_PROVIDER_API_KEY}
```

### Шаг 5: Добавить тесты

```python
# services/free-ai-selector-business-api/tests/unit/test_newprovider.py

import pytest
from unittest.mock import AsyncMock, patch
from app.infrastructure.ai_providers.newprovider import NewProvider


class TestNewProvider:
    @pytest.fixture
    def provider(self):
        with patch.dict(os.environ, {"NEW_PROVIDER_API_KEY": "test_key"}):
            return NewProvider()

    @pytest.mark.asyncio
    async def test_generate_success(self, provider):
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value.json.return_value = {
                "choices": [{"message": {"content": "Response"}}]
            }
            mock_post.return_value.raise_for_status = lambda: None

            result = await provider.generate("Test prompt")

            assert result == "Response"

    def test_get_provider_name(self, provider):
        assert provider.get_provider_name() == "NewProvider"
```

### Шаг 6: Обновить документацию

1. Добавить в этот файл (`docs/project/ai-providers.md`)
2. Обновить `docs/ai-context/SERVICE_MAP.md`
3. Обновить `docs/operations/api-keys.md`

---

## Troubleshooting

### Провайдер возвращает ошибку 429 (Rate Limit)

```
Причина: Превышен лимит запросов
Решение: Подождать или уменьшить частоту запросов
```

### Провайдер возвращает ошибку 401 (Unauthorized)

```
Причина: Неверный или отсутствующий API ключ
Решение: Проверить .env файл и docker-compose.yml
```

### Провайдер недоступен (Connection Error)

```
Причина: Проблемы с сетью или API недоступен
Решение: Проверить доступность API, система автоматически переключится на fallback
```

---

## Related Documentation

- [Reliability Formula](reliability-formula.md) - Как рассчитывается рейтинг
- [../operations/api-keys.md](../operations/api-keys.md) - Настройка API ключей
- [../ai-context/EXAMPLES.md](../ai-context/EXAMPLES.md) - Примеры кода провайдеров
