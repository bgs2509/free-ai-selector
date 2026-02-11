# План фичи: F018 — Удаление env_var из БД, SSOT через ProviderRegistry

**Feature ID**: F018
**Дата**: 2026-02-11
**Статус**: Ожидает утверждения

---

## 1. Обзор

Удаление колонки `env_var` из БД и переключение на ProviderRegistry/локальный dict как SSOT для имён env переменных API ключей. Исправление production бага (500 на VPS) и побочного бага Cloudflare.

**Связь с существующим функционалом**: F008 (Provider Registry SSOT), F013 (OpenAICompatibleProvider)

---

## 2. Анализ существующего кода

**Затронутые сервисы**: Data API, Business API, Health Worker

**Точки интеграции**:
- Data API response schema → Business API `data_api_client.py`
- Data API response schema → Health Worker `main.py`
- ProviderRegistry → `process_prompt.py`

---

## 3. План изменений

### Шаг 1: Business API — добавить ProviderRegistry.get_api_key_env()

**Файл**: `services/free-ai-selector-business-api/app/infrastructure/ai_providers/cloudflare.py`

```python
# Добавить class variable (после строки 21)
class CloudflareProvider(AIProviderBase):
    API_KEY_ENV = "CLOUDFLARE_API_TOKEN"
```

**Файл**: `services/free-ai-selector-business-api/app/infrastructure/ai_providers/registry.py`

```python
# Добавить classmethod в ProviderRegistry
@classmethod
def get_api_key_env(cls, name: str) -> str:
    """Получить имя env переменной без создания экземпляра провайдера."""
    provider_class = PROVIDER_CLASSES.get(name)
    if provider_class and hasattr(provider_class, 'API_KEY_ENV'):
        return provider_class.API_KEY_ENV
    return ""
```

### Шаг 2: Business API — переключить _filter_configured_models()

**Файл**: `services/free-ai-selector-business-api/app/application/use_cases/process_prompt.py`

Заменить `_filter_configured_models()` (строки 271-298):

```python
def _filter_configured_models(self, models: list[AIModelInfo]) -> list[AIModelInfo]:
    configured = []
    for model in models:
        env_var = ProviderRegistry.get_api_key_env(model.provider)
        if not env_var:
            continue
        api_key = os.getenv(env_var, "")
        if api_key:
            configured.append(model)
        else:
            logger.debug(
                "model_not_configured",
                model=model.name,
                env_var=env_var,
            )
    return configured
```

Добавить импорт: `from app.infrastructure.ai_providers.registry import ProviderRegistry`

### Шаг 3: Business API — удалить env_var из domain model и client

**Файл**: `services/free-ai-selector-business-api/app/domain/models.py` (строка 29)
- Удалить: `env_var: str = ""`

**Файл**: `services/free-ai-selector-business-api/app/infrastructure/http_clients/data_api_client.py` (строка 102)
- Удалить: `env_var=model.get("env_var", ""),`

### Шаг 4: Data API — удалить env_var из всех слоёв

**Файл**: `services/free-ai-selector-data-postgres-api/app/infrastructure/database/models.py` (строка 50)
- Удалить: `env_var: Mapped[str] = mapped_column(String(50), nullable=False, default="")`

**Файл**: `services/free-ai-selector-data-postgres-api/app/domain/models.py` (строка 38)
- Удалить: `env_var: str = ""`

**Файл**: `services/free-ai-selector-data-postgres-api/app/api/v1/schemas.py` (строка 74)
- Удалить: `env_var: str = Field(default="", description="ENV variable name for API key lookup")`

**Файл**: `services/free-ai-selector-data-postgres-api/app/api/v1/models.py` (строка 368)
- Удалить: `env_var=model.env_var,`

### Шаг 5: Data API — seed upsert + cleanup + удалить env_var

**Файл**: `services/free-ai-selector-data-postgres-api/app/infrastructure/database/seed.py`

1. Удалить `"env_var": "..."` из всех 14 записей SEED_MODELS
2. Заменить `continue` для существующих моделей на upsert:

```python
if existing_model is not None:
    updated = False
    for field in ("api_format", "api_endpoint", "is_active"):
        new_val = model_data.get(field)
        if new_val is not None and getattr(existing_model, field) != new_val:
            setattr(existing_model, field, new_val)
            updated = True
    if updated:
        existing_model.updated_at = datetime.utcnow()
        logger.info(f"Updated model: {model_data['name']}")
    else:
        logger.info(f"Model '{model_data['name']}' up to date, skipping...")
    continue
```

3. Добавить cleanup orphans в конце (после цикла, перед commit):

```python
# Cleanup orphan models
seed_names = {m["name"] for m in SEED_MODELS}
all_query = select(AIModelORM)
all_result = await session.execute(all_query)
for model in all_result.scalars():
    if model.name not in seed_names:
        logger.warning(f"Removing orphan model: {model.name}")
        await session.delete(model)
```

4. Удалить `env_var` из создания AIModelORM (строка 188)

### Шаг 6: Alembic миграция

**Новый файл**: `services/free-ai-selector-data-postgres-api/alembic/versions/20260211_0004_drop_env_var.py`

```python
"""Drop env_var column from ai_models table.

F018: env_var moved to ProviderRegistry (SSOT).

Revision ID: 0004_drop_env_var
Revises: 0003_add_available_at
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_drop_env_var"
down_revision = "0003_add_available_at"

def upgrade():
    op.drop_column("ai_models", "env_var")

def downgrade():
    op.add_column("ai_models",
        sa.Column("env_var", sa.String(length=50), nullable=False, server_default=""))
```

### Шаг 7: Health Worker — PROVIDER_ENV_VARS dict

**Файл**: `services/free-ai-selector-health-worker/app/main.py`

1. Добавить dict после секции Configuration (после строки 40):

```python
PROVIDER_ENV_VARS: dict[str, str] = {
    "Groq": "GROQ_API_KEY",
    "Cerebras": "CEREBRAS_API_KEY",
    "SambaNova": "SAMBANOVA_API_KEY",
    "HuggingFace": "HUGGINGFACE_API_KEY",
    "Cloudflare": "CLOUDFLARE_API_TOKEN",
    "DeepSeek": "DEEPSEEK_API_KEY",
    "OpenRouter": "OPENROUTER_API_KEY",
    "GitHubModels": "GITHUB_TOKEN",
    "Fireworks": "FIREWORKS_API_KEY",
    "Hyperbolic": "HYPERBOLIC_API_KEY",
    "Novita": "NOVITA_API_KEY",
    "Scaleway": "SCALEWAY_API_KEY",
    "Kluster": "KLUSTER_API_KEY",
    "Nebius": "NEBIUS_API_KEY",
}
```

2. Заменить `model.get("env_var", "")` на `PROVIDER_ENV_VARS.get(provider, "")` в:
   - `run_health_checks()` (строка 305)
   - `main()` (строка 416)

3. Убрать `env_var` из сигнатуры `universal_health_check()` — заменить на lookup по provider name

### Шаг 8: Обновить тесты

**Business API тесты:**

| Файл | Изменение |
|------|-----------|
| `tests/conftest.py` (строки 33, 45) | Удалить `env_var=...` из фикстур |
| `tests/unit/test_process_prompt_use_case.py` (строки 109, 148) | Удалить `env_var=...`, добавить mock `ProviderRegistry.get_api_key_env` |
| `tests/unit/test_f012_rate_limit_handling.py` (строки 58, 68, 114, 124) | Удалить `env_var=...`, добавить mock |

**Data API тесты:**

| Файл | Изменение |
|------|-----------|
| `tests/unit/test_f015_dry_refactoring.py` (строка 38) | Удалить `env_var="TEST_API_KEY"` |

---

## 4. Новые зависимости

Нет новых зависимостей.

---

## 5. Breaking changes

- Data API response schema: поле `env_var` удалено из GET `/api/v1/models`
- Это НЕ breaking для внешних потребителей — только Business API и Health Worker используют этот endpoint, и оба переключаются на локальные источники

---

## 6. План интеграции (порядок выполнения)

| # | Шаг | Зависимости | Описание |
|---|-----|-------------|----------|
| 1 | Cloudflare API_KEY_ENV | — | Добавить class variable |
| 2 | ProviderRegistry.get_api_key_env() | Шаг 1 | Новый classmethod |
| 3 | _filter_configured_models() | Шаг 2 | Переключить на registry |
| 4 | Business API domain/client | Шаг 3 | Удалить env_var |
| 5 | Data API layers | — | Удалить env_var из ORM/domain/schema/endpoint |
| 6 | Seed upsert + cleanup | Шаг 5 | Обновить seed скрипт |
| 7 | Alembic миграция | Шаг 5 | DROP COLUMN |
| 8 | Health Worker | — | PROVIDER_ENV_VARS dict |
| 9 | Тесты | Шаги 1-8 | Обновить все тесты |

---

## 7. Риски и митигация

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| DROP COLUMN на production DB | Low | downgrade() в миграции, backup перед деплоем |
| Health Worker dict рассинхронизация | Med | Комментарий в коде с инструкцией |
| Тесты сломаются промежуточно | High | Все изменения в одном коммите |

---

## 8. Верификация

```bash
# Локально
make build && make test-business && make test-data

# На VPS после деплоя
curl -X POST http://localhost:8000/api/v1/prompts/process \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "prompt_text": "Hello"}'
# Ожидаемый результат: 200 OK
```
