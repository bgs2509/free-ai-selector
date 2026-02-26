# Research Report: F018 — Удаление env_var из БД

**Feature ID**: F018
**Дата**: 2026-02-11
**Статус**: RESEARCH_DONE

---

## 1. Анализ текущего состояния

### 1.1 Где определяется env_var

`env_var` существует в **2 независимых местах** (нарушение SSOT):

**Место 1 — БД (через seed.py → ORM → Data API response):**
- `seed.py`: 14 записей `"env_var": "PROVIDER_API_KEY"` (строки 38-151)
- ORM: `env_var: Mapped[str] = mapped_column(String(50))` (models.py:50)
- Domain: `env_var: str = ""` (domain/models.py:38)
- Schema: `env_var: str = Field(default="")` (schemas.py:74)
- API endpoint: `env_var=model.env_var` (api/v1/models.py:368)

**Место 2 — Классы провайдеров (class variable):**
- `OpenAICompatibleProvider`: `API_KEY_ENV: ClassVar[str] = ""` (base.py:89)
- 12 провайдеров наследуют и определяют `API_KEY_ENV`
- Cloudflare использует `os.getenv("CLOUDFLARE_API_TOKEN")` напрямую

### 1.2 Кто потребляет env_var из Data API

| Потребитель | Как использует | Будет затронут |
|-------------|----------------|----------------|
| Business API | `_filter_configured_models()` — фильтрует модели по `model.env_var` | Да — переключить на ProviderRegistry |
| Health Worker | `model.get("env_var", "")` — определяет API key для health check | Да — переключить на локальный dict |
| Telegram Bot | **НЕ использует** — работает через Business API stats endpoint | Нет |

### 1.3 Баг Cloudflare env_var

| Источник | Значение | Корректно? |
|----------|----------|------------|
| seed.py (строка 70) | `"CLOUDFLARE_API_KEY"` | **НЕТ** |
| CloudflareProvider.__init__ | `os.getenv("CLOUDFLARE_API_TOKEN")` | ДА |
| Ожидаемое | `"CLOUDFLARE_API_TOKEN"` | — |

Этот баг означает, что Cloudflare health check **всегда** выдаёт `provider_api_key_missing`, даже если `CLOUDFLARE_API_TOKEN` установлена.

---

## 2. Анализ провайдеров и API_KEY_ENV

### 2.1 Полная таблица провайдеров

| # | Provider | Класс | API_KEY_ENV | Наследует |
|---|----------|-------|-------------|-----------|
| 1 | Groq | GroqProvider | `GROQ_API_KEY` | OpenAICompatibleProvider |
| 2 | Cerebras | CerebrasProvider | `CEREBRAS_API_KEY` | OpenAICompatibleProvider |
| 3 | SambaNova | SambanovaProvider | `SAMBANOVA_API_KEY` | OpenAICompatibleProvider |
| 4 | HuggingFace | HuggingFaceProvider | `HUGGINGFACE_API_KEY` | OpenAICompatibleProvider |
| 5 | Cloudflare | CloudflareProvider | **НЕ ОПРЕДЕЛЁН** | AIProviderBase |
| 6 | DeepSeek | DeepSeekProvider | `DEEPSEEK_API_KEY` | OpenAICompatibleProvider |
| 7 | OpenRouter | OpenRouterProvider | `OPENROUTER_API_KEY` | OpenAICompatibleProvider |
| 8 | GitHubModels | GitHubModelsProvider | `GITHUB_TOKEN` | OpenAICompatibleProvider |
| 9 | Fireworks | FireworksProvider | `FIREWORKS_API_KEY` | OpenAICompatibleProvider |
| 10 | Hyperbolic | HyperbolicProvider | `HYPERBOLIC_API_KEY` | OpenAICompatibleProvider |
| 11 | Novita | NovitaProvider | `NOVITA_API_KEY` | OpenAICompatibleProvider |
| 12 | Scaleway | ScalewayProvider | `SCALEWAY_API_KEY` | OpenAICompatibleProvider |
| 13 | Kluster | KlusterProvider | `KLUSTER_API_KEY` | OpenAICompatibleProvider |

**Вывод**: 13 из 14 провайдеров имеют `API_KEY_ENV`. Cloudflare — единственное исключение.

### 2.2 ProviderRegistry (текущее состояние)

```
registry.py:
  PROVIDER_CLASSES: dict[str, type[AIProviderBase]]  # 14 записей
  ProviderRegistry:
    _instances: dict[str, AIProviderBase]  # Singleton cache
    get_provider(name) → Optional[AIProviderBase]  # Lazy init + cache
    get_all_provider_names() → list[str]
    has_provider(name) → bool
    reset() → None
```

**Нет метода `get_api_key_env()`** — нужно добавить. Метод должен работать **без инстанцирования** провайдера, т.к. `__init__` бросает `ValueError` если ключ отсутствует.

---

## 3. Blast Radius

### 3.1 Полный список изменений по файлам

**Data API (6 файлов):**

| Файл | Строки | Тип изменения |
|------|--------|---------------|
| `infrastructure/database/models.py` | 50 | Удалить колонку ORM |
| `domain/models.py` | 38 | Удалить поле dataclass |
| `api/v1/schemas.py` | 74 | Удалить поле Pydantic |
| `api/v1/models.py` | 368 | Удалить из `_model_to_response()` |
| `infrastructure/database/seed.py` | 38,46,54,62,70,81,89,97,108,116,124,132,143,151,188 | Удалить env_var + upsert + cleanup |
| `alembic/versions/NEW_0004_drop_env_var.py` | новый | DROP COLUMN |

**Data API Tests (1 файл):**

| Файл | Строки | Тип изменения |
|------|--------|---------------|
| `tests/unit/test_f015_dry_refactoring.py` | 38 | Удалить `env_var="TEST_API_KEY"` |

**Business API (4 файла):**

| Файл | Строки | Тип изменения |
|------|--------|---------------|
| `infrastructure/ai_providers/registry.py` | новый метод | Добавить `get_api_key_env()` |
| `infrastructure/ai_providers/cloudflare.py` | новая строка | Добавить `API_KEY_ENV = "CLOUDFLARE_API_TOKEN"` |
| `application/use_cases/process_prompt.py` | 286,289,296 | Использовать registry вместо model.env_var |
| `domain/models.py` | 29 | Удалить `env_var` поле |
| `infrastructure/http_clients/data_api_client.py` | 102 | Удалить парсинг env_var |

**Business API Tests (3 файла):**

| Файл | Строки | Тип изменения |
|------|--------|---------------|
| `tests/conftest.py` | 33,45 | Удалить `env_var` из фикстур |
| `tests/unit/test_process_prompt_use_case.py` | 109,148 | Mock registry вместо env_var |
| `tests/unit/test_f012_rate_limit_handling.py` | 58,68,114,124 | Удалить env_var из mock-моделей |

**Health Worker (1 файл):**

| Файл | Строки | Тип изменения |
|------|--------|---------------|
| `app/main.py` | 55-65,219,238,243,305,319,416,418 | PROVIDER_ENV_VARS dict + замена model.get("env_var") |

**Итого: 15 файлов (11 code + 4 tests) + 1 новый (миграция)**

### 3.2 Telegram Bot — НЕ затрагивается

Telegram Bot:
- Общается только с Business API (не Data API)
- Получает stats через `/api/v1/models/stats`
- Response schema `AIModelStatsResponse` **не содержит** `env_var`
- 0 вхождений `env_var` в коде бота

---

## 4. Alembic миграция

### 4.1 Цепочка миграций

```
0001_initial_schema (base)
    ↓
0002_add_api_format_env_var  ← добавила env_var
    ↓
0003_add_available_at        ← текущий HEAD
    ↓
0004_drop_env_var            ← новая миграция
```

### 4.2 Структура новой миграции

```python
# Revision: 0004_drop_env_var
# Revises: 0003_add_available_at

def upgrade():
    op.drop_column("ai_models", "env_var")

def downgrade():
    op.add_column("ai_models",
        sa.Column("env_var", sa.String(50), nullable=False, server_default=""))
```

---

## 5. Архитектурное решение: get_api_key_env()

### 5.1 Проблема инстанцирования

Нельзя вызвать `ProviderRegistry.get_provider(name)` для получения `API_KEY_ENV`, потому что `OpenAICompatibleProvider.__init__()` бросает `ValueError` если API ключ отсутствует в env:

```python
# base.py:105-107
self.api_key = api_key or os.getenv(self.API_KEY_ENV, "")
if not self.api_key:
    raise ValueError(f"{self.PROVIDER_NAME} API key is required")
```

### 5.2 Решение: classmethod без инстанцирования

```python
@classmethod
def get_api_key_env(cls, name: str) -> str:
    """Получить имя env переменной без создания экземпляра."""
    provider_class = PROVIDER_CLASSES.get(name)
    if provider_class and hasattr(provider_class, 'API_KEY_ENV'):
        return provider_class.API_KEY_ENV
    return ""
```

Этот метод:
- Работает без инстанцирования (доступ к class variable)
- Безопасен (не бросает исключения)
- Возвращает пустую строку для неизвестных провайдеров

### 5.3 Cloudflare: добавить API_KEY_ENV

CloudflareProvider наследует AIProviderBase, не OpenAICompatibleProvider. Нужно добавить class variable:

```python
class CloudflareProvider(AIProviderBase):
    API_KEY_ENV = "CLOUDFLARE_API_TOKEN"
```

---

## 6. Seed скрипт: upsert + cleanup

### 6.1 Текущая проблема

`seed_database()` пропускает существующие записи:
```python
if existing_model is not None:
    logger.info(f"Model '{model_data['name']}' already exists, skipping...")
    continue  # ← ПРОБЛЕМА: не обновляет поля
```

### 6.2 Решение: upsert

Для существующих моделей обновлять `api_format`, `api_endpoint`, `is_active`:
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
    continue
```

### 6.3 Cleanup orphans

Удалить модели, которых нет в SEED_MODELS (GoogleGemini, Cohere — удалены в F011-A):
```python
seed_names = {m["name"] for m in SEED_MODELS}
all_models = await session.execute(select(AIModelORM))
for model in all_models.scalars():
    if model.name not in seed_names:
        await session.delete(model)
```

---

## 7. Health Worker: PROVIDER_ENV_VARS

Health Worker — отдельный микросервис, не может импортировать из Business API. Решение — локальный dict:

```python
PROVIDER_ENV_VARS: dict[str, str] = {
    "Groq": "GROQ_API_KEY",
    "Cerebras": "CEREBRAS_API_KEY",
    "SambaNova": "SAMBANOVA_API_KEY",
    "HuggingFace": "HUGGINGFACE_API_KEY",
    "Cloudflare": "CLOUDFLARE_API_TOKEN",  # Исправлен баг
    "DeepSeek": "DEEPSEEK_API_KEY",
    "OpenRouter": "OPENROUTER_API_KEY",
    "GitHubModels": "GITHUB_TOKEN",
    "Fireworks": "FIREWORKS_API_KEY",
    "Hyperbolic": "HYPERBOLIC_API_KEY",
    "Novita": "NOVITA_API_KEY",
    "Scaleway": "SCALEWAY_API_KEY",
    "Kluster": "KLUSTER_API_KEY",
}
```

**Риск**: при добавлении нового провайдера нужно обновить и Business API (класс), и Health Worker (dict). Это приемлемый компромисс — провайдеры добавляются редко.

---

## 8. Порядок деплоя на VPS

```
1. git pull                    # Новый код
2. make build                  # Собрать образы (код без env_var)
3. make migrate                # DROP COLUMN env_var
4. make seed                   # Upsert + cleanup
5. make up                     # Запустить сервисы
6. make health                 # Проверить здоровье
```

**Безопасность**: Новый код не зависит от `env_var` в response — использует registry/dict. Миграция DROP COLUMN безопасна т.к. колонка уже не используется.

---

## 9. Риски и ограничения

| # | Риск | Вероятность | Митигация |
|---|------|-------------|-----------|
| 1 | Рассинхронизация Health Worker dict | Med | Документация в комментариях |
| 2 | Неизвестный потребитель env_var | Low | Полный grep показал только 3 потребителя |
| 3 | Тесты сломаются при переходе | High | Все тесты обновляются в одном коммите |
| 4 | DROP COLUMN на production | Low | downgrade() в миграции, backup |

---

## 10. Рекомендации

1. **Реализовать в одном коммите** — все изменения атомарны
2. **Cloudflare API_KEY_ENV** — добавить до удаления env_var из БД
3. **Seed upsert** — предотвращает будущие баги с пустыми полями
4. **Тестировать локально** через Docker перед VPS деплоем
