# AI Providers

> Документация по AI-провайдерам Free AI Selector.

## Обзор

Free AI Selector интегрирован с 14 бесплатными AI-провайдерами. Все работают без кредитной карты.

## Список провайдеров

### Существующие провайдеры (5 шт.)

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
| Модель | Llama 3.3 70B |
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

### Новые провайдеры F003 (9 шт.)

#### 6. DeepSeek
- **Класс:** `DeepSeekProvider`
- **Модель:** DeepSeek Chat
- **Rate Limit:** 60 RPM
- **API Key:** `DEEPSEEK_API_KEY`
- **URL:** [DeepSeek Platform](https://platform.deepseek.com/)

#### 7. OpenRouter
- **Класс:** `OpenRouterProvider`
- **Модель:** DeepSeek R1 Free
- **Rate Limit:** 20 RPM
- **API Key:** `OPENROUTER_API_KEY`
- **URL:** [OpenRouter](https://openrouter.ai/)

#### 8. GitHub Models
- **Класс:** `GitHubModelsProvider`
- **Модель:** GPT-4o Mini
- **Rate Limit:** 15 RPM, 150 RPD
- **API Key:** `GITHUB_TOKEN`
- **URL:** [GitHub Models](https://github.com/marketplace/models)

#### 9. Fireworks
- **Класс:** `FireworksProvider`
- **Модель:** Llama 3.1 70B
- **Free Credits:** $1
- **API Key:** `FIREWORKS_API_KEY`
- **URL:** [Fireworks AI](https://fireworks.ai/)

#### 10. Hyperbolic
- **Класс:** `HyperbolicProvider`
- **Модель:** Llama 3.1 70B
- **Free Tier:** Available
- **API Key:** `HYPERBOLIC_API_KEY`
- **URL:** [Hyperbolic](https://hyperbolic.xyz/)

#### 11. Novita
- **Класс:** `NovitaProvider`
- **Модель:** Llama 3.3 70B
- **Free Tier:** Available
- **API Key:** `NOVITA_API_KEY`
- **URL:** [Novita AI](https://novita.ai/)

#### 12. Scaleway
- **Класс:** `ScalewayProvider`
- **Модель:** Llama 3.3 70B
- **Free Tier:** Available
- **API Key:** `SCALEWAY_API_KEY`
- **URL:** [Scaleway](https://www.scaleway.com/)

#### 13. Kluster
- **Класс:** `KlusterProvider`
- **Модель:** Llama 3.3 70B
- **Free Tier:** Available
- **API Key:** `KLUSTER_API_KEY`
- **URL:** [Kluster AI](https://kluster.ai/)

#### 14. Nebius
- **Класс:** `NebiusProvider`
- **Модель:** Llama 3.3 70B
- **Free Tier:** Available
- **API Key:** `NEBIUS_API_KEY`
- **URL:** [Nebius](https://nebius.ai/)

---

## Интерфейс провайдера

Все провайдеры реализуют `AIProviderBase`:

```python
# services/free-ai-selector-business-api/app/infrastructure/ai_providers/base.py

from abc import ABC, abstractmethod


class AIProviderBase(ABC):
    """Базовый класс для AI-провайдеров."""

    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Сгенерировать ответ.

        Args:
            prompt: Текст промпта
            **kwargs: temperature, max_tokens, etc.

        Returns:
            Сгенерированный текст

        Raises:
            Exception: При ошибке API
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Проверить доступность API.

        Returns:
            True если API доступен
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Получить имя провайдера.

        Returns:
            Строка с именем (для статистики)
        """
        pass
```

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

### Шаг 2: Зарегистрировать в Use Case

```python
# services/free-ai-selector-business-api/app/application/use_cases/process_prompt.py

from app.infrastructure.ai_providers.newprovider import NewProvider

class ProcessPromptUseCase:
    def __init__(self, data_api_client: DataAPIClient):
        self.providers = {
            # ... existing providers
            "NewProvider": NewProvider(),  # Добавить сюда
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
