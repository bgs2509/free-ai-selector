# План фичи: Расширение AI провайдеров (F003)

**ID:** F003
**Название:** expand-ai-providers
**Дата:** 2025-12-25
**Статус:** DRAFT

---

## 1. Обзор

### 1.1 Краткое описание

Расширение платформы Free AI Selector с 6 до 16 AI провайдеров.
Добавляются только провайдеры **без требования кредитной карты и верификации телефона**.

### 1.2 Связь с существующим функционалом

- Все новые провайдеры наследуют от `AIProviderBase`
- Интегрируются в `ProcessPromptUseCase.providers`
- Модели добавляются через `seed.py`
- Существующий код не модифицируется (кроме регистрации)

---

## 2. Анализ существующего кода

### 2.1 Затронутые сервисы

| Сервис | Изменения |
|--------|-----------|
| `free-ai-selector-business-api` | Новые провайдеры, регистрация |
| `free-ai-selector-data-postgres-api` | Seed данные |

### 2.2 Точки интеграции

```
services/free-ai-selector-business-api/
├── app/
│   ├── infrastructure/
│   │   └── ai_providers/
│   │       ├── base.py              # Базовый класс (не менять)
│   │       ├── [existing].py        # Существующие (не менять)
│   │       └── [new].py             # ДОБАВИТЬ: 10 новых файлов
│   └── application/
│       └── use_cases/
│           └── process_prompt.py    # ИЗМЕНИТЬ: регистрация провайдеров

services/free-ai-selector-data-postgres-api/
└── app/
    └── infrastructure/
        └── database/
            └── seed.py              # ИЗМЕНИТЬ: новые модели
```

### 2.3 Существующие зависимости

- `httpx` — уже установлен, используется для HTTP запросов
- `AIProviderBase` — базовый класс в `base.py`

---

## 3. План изменений

### 3.1 Новые компоненты

| # | Компонент | Расположение | Описание |
|---|-----------|--------------|----------|
| 1 | `deepseek.py` | `ai_providers/` | DeepSeek провайдер (5M токенов бесплатно) |
| 2 | `cohere.py` | `ai_providers/` | Cohere провайдер (1K calls/месяц) |
| 3 | `openrouter.py` | `ai_providers/` | OpenRouter агрегатор (30+ бесплатных моделей) |
| 4 | `github_models.py` | `ai_providers/` | GitHub Models (PAT токен) |
| 5 | `fireworks.py` | `ai_providers/` | Fireworks ($1 кредитов) |
| 6 | `hyperbolic.py` | `ai_providers/` | Hyperbolic ($1 кредитов) |
| 7 | `novita.py` | `ai_providers/` | Novita AI ($10 + 5 бесплатных моделей) |
| 8 | `scaleway.py` | `ai_providers/` | Scaleway (1M токенов, EU) |
| 9 | `kluster.py` | `ai_providers/` | Kluster AI ($5 кредитов) |

### 3.2 Модификации существующего кода

| # | Файл | Изменение | Причина |
|---|------|-----------|---------|
| 1 | `process_prompt.py` | Добавить импорты и регистрацию 10 провайдеров | Интеграция |
| 2 | `seed.py` | Добавить 14 новых моделей | Данные для выбора |
| 3 | `.env.example` | Добавить 10 env переменных | Документация |
| 4 | `docker-compose.yml` | Добавить env переменные для business-api | Деплой |

### 3.3 Новые зависимости

| Зависимость | Версия | Назначение |
|-------------|--------|------------|
| — | — | Новых зависимостей не требуется (httpx уже есть) |

---

## 4. API контракты

### 4.1 Базовый интерфейс (без изменений)

```python
class AIProviderBase(ABC):
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str: ...

    @abstractmethod
    async def health_check(self) -> bool: ...

    @abstractmethod
    def get_provider_name(self) -> str: ...
```

### 4.2 Новые провайдеры

#### DeepSeek (OpenAI-совместимый)
```python
class DeepSeekProvider(AIProviderBase):
    api_url = "https://api.deepseek.com/v1/chat/completions"
    model = "deepseek-chat"
    env_key = "DEEPSEEK_API_KEY"
```

#### Cohere (свой формат)
```python
class CohereProvider(AIProviderBase):
    api_url = "https://api.cohere.com/v2/chat"
    model = "command-r-plus"
    env_key = "COHERE_API_KEY"
```

#### OpenRouter (агрегатор)
```python
class OpenRouterProvider(AIProviderBase):
    api_url = "https://openrouter.ai/api/v1/chat/completions"
    model = "deepseek/deepseek-r1:free"  # По умолчанию бесплатная
    env_key = "OPENROUTER_API_KEY"
```

---

## 5. Влияние на существующие тесты

### 5.1 Существующие тесты

| Тест | Статус | Влияние |
|------|--------|---------|
| `test_process_prompt_use_case.py` | ✅ Без изменений | Мокает провайдеры |
| `test_ai_providers.py` | ✅ Без изменений | Тесты существующих |
| `test_static_files.py` (F002) | ✅ Без изменений | Не связано |

### 5.2 Новые тесты

| # | Файл | Описание |
|---|------|----------|
| 1 | `test_deepseek_provider.py` | Unit тесты DeepSeek |
| 2 | `test_cohere_provider.py` | Unit тесты Cohere |
| 3 | `test_openrouter_provider.py` | Unit тесты OpenRouter |
| 4 | `test_github_models_provider.py` | Unit тесты GitHub Models |
| 5 | `test_fireworks_provider.py` | Unit тесты Fireworks |
| 6 | `test_hyperbolic_provider.py` | Unit тесты Hyperbolic |
| 7 | `test_novita_provider.py` | Unit тесты Novita |
| 8 | `test_scaleway_provider.py` | Unit тесты Scaleway |
| 9 | `test_kluster_provider.py` | Unit тесты Kluster |

---

## 6. План интеграции

### Фаза 1: Приоритетные провайдеры (4 шт.)

| # | Шаг | Зависимости | Файлы |
|---|-----|-------------|-------|
| 1.1 | Создать `deepseek.py` | base.py | ai_providers/deepseek.py |
| 1.2 | Создать `cohere.py` | base.py | ai_providers/cohere.py |
| 1.3 | Создать `openrouter.py` | base.py | ai_providers/openrouter.py |
| 1.4 | Создать `github_models.py` | base.py | ai_providers/github_models.py |
| 1.5 | Unit тесты для Фазы 1 | 1.1-1.4 | tests/unit/test_*_provider.py |
| 1.6 | Регистрация в process_prompt.py | 1.1-1.4 | use_cases/process_prompt.py |
| 1.7 | Seed данные Фазы 1 | — | seed.py |
| 1.8 | Env переменные | — | .env.example, docker-compose.yml |

### Фаза 2: Дополнительные провайдеры (4 шт.)

| # | Шаг | Зависимости | Файлы |
|---|-----|-------------|-------|
| 2.1 | Создать `fireworks.py` | base.py | ai_providers/fireworks.py |
| 2.2 | Создать `hyperbolic.py` | base.py | ai_providers/hyperbolic.py |
| 2.3 | Создать `novita.py` | base.py | ai_providers/novita.py |
| 2.4 | Создать `scaleway.py` | base.py | ai_providers/scaleway.py |
| 2.5 | Unit тесты для Фазы 2 | 2.1-2.4 | tests/unit/test_*_provider.py |
| 2.6 | Регистрация + Seed Фазы 2 | 2.1-2.4 | process_prompt.py, seed.py |

### Фаза 3: Резервные провайдеры (2 шт.)

| # | Шаг | Зависимости | Файлы |
|---|-----|-------------|-------|
| 3.1 | Создать `kluster.py` | base.py | ai_providers/kluster.py |
| 3.3 | Unit тесты для Фазы 3 | 3.1-3.2 | tests/unit/test_*_provider.py |
| 3.4 | Финальная регистрация + Seed | 3.1-3.2 | process_prompt.py, seed.py |
| 3.5 | Обновить документацию | Все | CLAUDE.md |

---

## 7. Риски и митигация

| # | Риск | Вероятность | Влияние | Митигация |
|---|------|-------------|---------|-----------|
| 1 | API провайдера изменится | Средняя | Среднее | Версионирование, мониторинг |
| 2 | Лимиты будут снижены | Высокая | Среднее | Множественный fallback |
| 3 | API ключ истечёт | Средняя | Высокое | Уведомления, ротация |
| 4 | Провайдер станет недоступен | Низкая | Высокое | OpenRouter как fallback |
| 5 | Тесты не пройдут | Низкая | Среднее | Мокирование API |

---

## 8. Временные метки (условные)

| Фаза | Задачи |
|------|--------|
| Фаза 1 | 4 провайдера + тесты + регистрация |
| Фаза 2 | 4 провайдера + тесты + регистрация |
| Фаза 3 | 2 провайдера + тесты + документация |

---

## 9. Environment переменные

```bash
# Фаза 1: Приоритетные
DEEPSEEK_API_KEY=sk-...
COHERE_API_KEY=...
OPENROUTER_API_KEY=sk-or-...
GITHUB_TOKEN=ghp_...

# Фаза 2: Дополнительные
FIREWORKS_API_KEY=...
HYPERBOLIC_API_KEY=...
NOVITA_API_KEY=...
SCALEWAY_API_KEY=...

# Фаза 3: Резервные
KLUSTER_API_KEY=...
```

---

## 10. Критерии готовности

| # | Критерий | Проверка |
|---|----------|----------|
| 1 | 10 новых провайдеров созданы | ls ai_providers/*.py |
| 2 | Все провайдеры зарегистрированы | grep -c "Provider()" process_prompt.py |
| 3 | 14 новых моделей в seed | grep -c "provider" seed.py |
| 4 | Все unit тесты проходят | make test-business |
| 5 | Health check проходит для всех | make health |
| 6 | Документация обновлена | CLAUDE.md содержит новые провайдеры |

---

## 11. Чек-лист для ревью

- [ ] Все провайдеры наследуют от `AIProviderBase`
- [ ] Все методы реализованы (`generate`, `health_check`, `get_provider_name`)
- [ ] Timeout установлен (30 сек)
- [ ] Логирование ошибок через `sanitize_error_message`
- [ ] Docstrings на русском языке
- [ ] Unit тесты с мокированием HTTP
- [ ] Env переменные документированы
