# Code Examples for AI Code Generation

> Примеры кода из проекта Free AI Selector для Claude Code.

## 1. API Endpoint Example

### Business API - Process Prompt

```python
# services/free-ai-selector-business-api/app/api/v1/prompts.py

from fastapi import APIRouter, HTTPException, status
from app.api.v1.schemas import ProcessPromptRequest, ProcessPromptResponse
from app.application.use_cases.process_prompt import ProcessPromptUseCase
from app.domain.models import PromptRequest
from app.infrastructure.http_clients.data_api_client import DataAPIClient

router = APIRouter(prefix="/prompts", tags=["prompts"])


@router.post("/process", response_model=ProcessPromptResponse)
async def process_prompt(request: ProcessPromptRequest) -> ProcessPromptResponse:
    """
    Обработать промпт и получить ответ от лучшей AI-модели.

    Автоматически выбирает модель с наивысшим reliability_score.
    При ошибке пробует fallback модели.

    Args:
        request: Запрос с текстом промпта

    Returns:
        Ответ с текстом, информацией о модели и временем ответа

    Raises:
        HTTPException: 503 если все модели недоступны
    """
    client = DataAPIClient()
    use_case = ProcessPromptUseCase(data_api_client=client)

    domain_request = PromptRequest(
        user_id=request.user_id or "anonymous",
        prompt_text=request.prompt,
    )

    try:
        response = await use_case.execute(domain_request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"All AI providers failed: {str(e)}",
        )

    return ProcessPromptResponse(
        prompt_text=response.prompt_text,
        response_text=response.response_text,
        selected_model_name=response.selected_model_name,
        selected_model_provider=response.selected_model_provider,
        response_time_seconds=float(response.response_time),
        success=response.success,
        error_message=response.error_message,
    )
```

---

## 2. Use Case Example

### ProcessPromptUseCase

```python
# services/free-ai-selector-business-api/app/application/use_cases/process_prompt.py

from decimal import Decimal
import time
import logging

from app.domain.models import PromptRequest, PromptResponse, AIModelInfo
from app.infrastructure.http_clients.data_api_client import DataAPIClient
from app.infrastructure.ai_providers.base import AIProviderBase
from app.infrastructure.ai_providers.groq import GroqProvider
from app.infrastructure.ai_providers.deepseek import DeepSeekProvider
# ... other imports (14 total providers)

logger = logging.getLogger(__name__)


class ProcessPromptUseCase:
    """
    Use case для обработки пользовательских промптов.

    Отвечает за:
    - Получение активных моделей из Data API
    - Выбор лучшей модели по reliability_score
    - Генерацию ответа с fallback механизмом
    - Обновление статистики
    """

    def __init__(self, data_api_client: DataAPIClient):
        """
        Инициализация use case.

        Args:
            data_api_client: HTTP клиент для Data API
        """
        self.data_api_client = data_api_client
        # 14 verified free-tier providers (F003 + F008 SSOT)
        # Providers loaded from registry (see registry.py)
        # Existing: Groq, Cerebras, SambaNova, HuggingFace, Cloudflare
        # New F003: DeepSeek, OpenRouter, GitHubModels, Fireworks,
        #           Hyperbolic, Novita, Scaleway, Kluster, Nebius
        self.providers: dict[str, AIProviderBase] = ProviderRegistry.get_all_providers()

    async def execute(self, request: PromptRequest) -> PromptResponse:
        """
        Выполнить обработку промпта.

        Шаги:
            1. Получить активные модели из Data API
            2. Выбрать лучшую модель по reliability_score
            3. Сгенерировать ответ с выбранным провайдером
            4. При ошибке - попробовать fallback модель
            5. Обновить статистику в Data API
            6. Записать историю промпта

        Args:
            request: Запрос с user_id и prompt_text

        Returns:
            PromptResponse с ответом и метаданными

        Raises:
            Exception: Если все провайдеры недоступны
        """
        # Step 1: Fetch active models
        models = await self.data_api_client.get_all_models(active_only=True)

        if not models:
            raise Exception("No active AI models available")

        # Step 2: Select best model
        best_model = self._select_best_model(models)
        logger.info(f"Selected model: {best_model.name} (score: {best_model.reliability_score})")

        # Step 3: Try to generate with best model
        start_time = time.time()
        try:
            provider = self._get_provider_for_model(best_model)
            response_text = await provider.generate(request.prompt_text)
            response_time = Decimal(str(time.time() - start_time))

            # Update success stats
            await self.data_api_client.increment_success(best_model.id)

            return PromptResponse(
                prompt_text=request.prompt_text,
                response_text=response_text,
                selected_model_name=best_model.name,
                selected_model_provider=best_model.provider,
                response_time=response_time,
                success=True,
            )

        except Exception as e:
            logger.warning(f"Primary model failed: {e}, trying fallback")

            # Update failure stats
            await self.data_api_client.increment_failure(best_model.id)

            # Step 4: Try fallback
            fallback_model = self._select_fallback_model(models, exclude=best_model)
            if fallback_model:
                return await self._try_with_model(fallback_model, request)

            raise Exception(f"All models failed. Last error: {e}")

    def _select_best_model(self, models: list[AIModelInfo]) -> AIModelInfo:
        """Выбрать модель с максимальным reliability_score."""
        return max(models, key=lambda m: m.reliability_score)

    def _select_fallback_model(
        self,
        models: list[AIModelInfo],
        exclude: AIModelInfo,
    ) -> AIModelInfo | None:
        """Выбрать fallback модель (вторую по reliability_score)."""
        available = [m for m in models if m.id != exclude.id]
        return max(available, key=lambda m: m.reliability_score) if available else None

    def _get_provider_for_model(self, model: AIModelInfo) -> AIProviderBase:
        """Получить экземпляр провайдера для модели."""
        provider = self.providers.get(model.provider)
        if not provider:
            raise ValueError(f"Unknown provider: {model.provider}")
        return provider
```

---

## 3. AI Provider Example

### DeepSeekProvider (F003)

```python
# services/free-ai-selector-business-api/app/infrastructure/ai_providers/deepseek.py

import os
import httpx
from app.infrastructure.ai_providers.base import AIProviderBase


class DeepSeekProvider(AIProviderBase):
    """
    DeepSeek AI провайдер.

    Free tier: 60 RPM, no credit card required.
    Model: DeepSeek Chat
    OpenAI-compatible API format.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """Инициализация провайдера."""
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.model = model or "deepseek-chat"
        self.api_url = "https://api.deepseek.com/v1/chat/completions"
        self.timeout = 30.0

    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Сгенерировать ответ с помощью DeepSeek.

        Args:
            prompt: Текст промпта
            **kwargs: Дополнительные параметры (max_tokens, temperature, system_prompt, response_format)

        Returns:
            Сгенерированный текст

        Raises:
            ValueError: Если API ключ отсутствует
            httpx.HTTPError: При ошибке API
        """
        if not self.api_key:
            raise ValueError("DeepSeek API ключ обязателен")

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        # F011-B: Support system_prompt and response_format
        messages = []
        if system_prompt := kwargs.get("system_prompt"):
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", 512),
            "temperature": kwargs.get("temperature", 0.7),
        }

        if response_format := kwargs.get("response_format"):
            payload["response_format"] = response_format

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()

    async def health_check(self) -> bool:
        """
        Проверить доступность DeepSeek API.

        Returns:
            True если API доступен
        """
        if not self.api_key:
            return False
        try:
            # Simple test request
            await self.generate("test", max_tokens=1)
            return True
        except Exception:
            return False

    def get_provider_name(self) -> str:
        """Вернуть имя провайдера."""
        return "DeepSeek"
```

---

## 4. Domain Model Example

### AIModel with Business Logic

```python
# services/free-ai-selector-data-postgres-api/app/domain/models.py

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass
class AIModel:
    """
    Domain Entity для AI-модели.

    Содержит бизнес-логику расчёта метрик надёжности.
    """

    id: Optional[int]
    name: str
    provider: str
    api_endpoint: str
    success_count: int = 0
    failure_count: int = 0
    total_response_time: Decimal = Decimal("0.0")
    request_count: int = 0
    last_checked: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime = None
    updated_at: datetime = None

    @property
    def success_rate(self) -> float:
        """
        Рассчитать процент успешных запросов.

        Returns:
            Значение от 0.0 до 1.0
        """
        if self.request_count == 0:
            return 0.0
        return self.success_count / self.request_count

    @property
    def average_response_time(self) -> Decimal:
        """
        Рассчитать среднее время ответа.

        Returns:
            Среднее время в секундах
        """
        if self.request_count == 0:
            return Decimal("0.0")
        return self.total_response_time / self.request_count

    @property
    def speed_score(self) -> float:
        """
        Рассчитать оценку скорости (0.0 - 1.0).

        Baseline: 10 секунд = score 0.0
        """
        avg_time = float(self.average_response_time)
        return max(0.0, 1.0 - avg_time / 10.0)

    @property
    def reliability_score(self) -> float:
        """
        Рассчитать итоговый reliability score.

        Formula: (success_rate * 0.6) + (speed_score * 0.4)

        Returns:
            Значение от 0.0 до 1.0
        """
        return (self.success_rate * 0.6) + (self.speed_score * 0.4)
```

---

## 5. Repository Example

### AIModelRepository

```python
# services/free-ai-selector-data-postgres-api/app/infrastructure/repositories/ai_model_repository.py

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import AIModel
from app.infrastructure.database.models import AIModelORM


class AIModelRepository:
    """
    Repository для работы с AI-моделями в БД.

    Реализует паттерн Repository для изоляции domain от infrastructure.
    """

    def __init__(self, session: AsyncSession):
        """
        Args:
            session: Асинхронная сессия SQLAlchemy
        """
        self.session = session

    async def get_all(self, active_only: bool = False) -> list[AIModel]:
        """
        Получить все модели.

        Args:
            active_only: Фильтровать только активные

        Returns:
            Список domain моделей
        """
        query = select(AIModelORM)
        if active_only:
            query = query.where(AIModelORM.is_active == True)

        result = await self.session.execute(query)
        orm_models = result.scalars().all()

        return [self._to_domain(orm) for orm in orm_models]

    async def increment_success(self, model_id: int, response_time: float) -> None:
        """
        Увеличить счётчик успешных запросов.

        Args:
            model_id: ID модели
            response_time: Время ответа в секундах
        """
        stmt = (
            update(AIModelORM)
            .where(AIModelORM.id == model_id)
            .values(
                success_count=AIModelORM.success_count + 1,
                request_count=AIModelORM.request_count + 1,
                total_response_time=AIModelORM.total_response_time + response_time,
            )
        )
        await self.session.execute(stmt)
        await self.session.commit()

    def _to_domain(self, orm: AIModelORM) -> AIModel:
        """Конвертировать ORM в domain model."""
        return AIModel(
            id=orm.id,
            name=orm.name,
            provider=orm.provider,
            api_endpoint=orm.api_endpoint,
            success_count=orm.success_count,
            failure_count=orm.failure_count,
            total_response_time=orm.total_response_time,
            request_count=orm.request_count,
            last_checked=orm.last_checked,
            is_active=orm.is_active,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )
```

---

## 6. Test Example

### Unit Test for Use Case

```python
# services/free-ai-selector-business-api/tests/unit/test_process_prompt_use_case.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal

from app.application.use_cases.process_prompt import ProcessPromptUseCase
from app.domain.models import PromptRequest, AIModelInfo


class TestProcessPromptUseCase:
    """Тесты для ProcessPromptUseCase."""

    @pytest.fixture
    def mock_data_api_client(self):
        """Мок Data API клиента."""
        client = AsyncMock()
        client.get_all_models = AsyncMock(return_value=[
            AIModelInfo(
                id=1,
                name="Model A",
                provider="DeepSeek",
                api_endpoint="https://api.example.com",
                reliability_score=0.8,
                is_active=True,
            ),
            AIModelInfo(
                id=2,
                name="Model B",
                provider="Groq",
                api_endpoint="https://api.example.com",
                reliability_score=0.9,
                is_active=True,
            ),
        ])
        client.increment_success = AsyncMock()
        client.increment_failure = AsyncMock()
        return client

    @pytest.fixture
    def use_case(self, mock_data_api_client):
        """Use case с мокнутыми зависимостями."""
        uc = ProcessPromptUseCase(data_api_client=mock_data_api_client)
        # Mock providers
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value="AI response")
        uc.providers = {"Groq": mock_provider, "DeepSeek": mock_provider}
        return uc

    def test_select_best_model(self, use_case, mock_data_api_client):
        """Тест выбора лучшей модели по reliability_score."""
        models = [
            AIModelInfo(id=1, name="A", provider="P", api_endpoint="", reliability_score=0.8, is_active=True),
            AIModelInfo(id=2, name="B", provider="P", api_endpoint="", reliability_score=0.9, is_active=True),
        ]

        best = use_case._select_best_model(models)

        assert best.id == 2  # Model B has higher reliability

    @pytest.mark.asyncio
    async def test_execute_success(self, use_case, mock_data_api_client):
        """Тест успешного выполнения промпта."""
        request = PromptRequest(user_id="test_user", prompt_text="Hello")

        response = await use_case.execute(request)

        assert response.success is True
        assert response.response_text == "AI response"
        assert response.selected_model_provider == "Groq"  # Best model
        mock_data_api_client.increment_success.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_fallback(self, use_case, mock_data_api_client):
        """Тест fallback при ошибке primary модели."""
        # Setup: first provider fails, second succeeds
        failing_provider = AsyncMock()
        failing_provider.generate = AsyncMock(side_effect=Exception("API Error"))

        working_provider = AsyncMock()
        working_provider.generate = AsyncMock(return_value="Fallback response")

        use_case.providers = {
            "Groq": failing_provider,
            "DeepSeek": working_provider,
        }

        request = PromptRequest(user_id="test_user", prompt_text="Hello")

        response = await use_case.execute(request)

        assert response.success is True
        assert response.response_text == "Fallback response"
        mock_data_api_client.increment_failure.assert_called_once()
```

---

## 7. HTTP Client Example

### DataAPIClient

```python
# services/free-ai-selector-business-api/app/infrastructure/http_clients/data_api_client.py

import os
import httpx
from typing import Optional

from app.domain.models import AIModelInfo


class DataAPIClient:
    """
    HTTP клиент для взаимодействия с Data API.

    Инкапсулирует все HTTP вызовы к Data API.
    """

    def __init__(self):
        """Инициализация клиента."""
        self.base_url = os.getenv("DATA_API_URL", "http://localhost:8001")
        self.timeout = httpx.Timeout(30.0)

    async def get_all_models(self, active_only: bool = False) -> list[AIModelInfo]:
        """
        Получить список AI-моделей.

        Args:
            active_only: Только активные модели

        Returns:
            Список AIModelInfo
        """
        params = {"active_only": str(active_only).lower()}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/api/v1/models",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            return [
                AIModelInfo(
                    id=m["id"],
                    name=m["name"],
                    provider=m["provider"],
                    api_endpoint=m["api_endpoint"],
                    reliability_score=m["reliability_score"],
                    is_active=m["is_active"],
                )
                for m in data["models"]
            ]

    async def increment_success(self, model_id: int) -> None:
        """Увеличить счётчик успешных запросов."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/models/{model_id}/increment-success",
            )
            response.raise_for_status()

    async def increment_failure(self, model_id: int) -> None:
        """Увеличить счётчик неудачных запросов."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/models/{model_id}/increment-failure",
            )
            response.raise_for_status()
```

---

## Related Documentation

- [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) - Общий контекст проекта
- [SERVICE_MAP.md](SERVICE_MAP.md) - Карта сервисов
- [.aidd/knowledge/quality/testing/](../../.aidd/knowledge/quality/testing/) - Гайды по тестированию
