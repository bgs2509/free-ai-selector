# PRD: F011-A — Удаление нестандартных AI провайдеров

**Feature ID**: F011-A
**Название**: Удаление GoogleGemini и Cohere провайдеров
**Дата создания**: 2026-01-15
**Автор**: AI Product Manager
**Статус**: Draft
**Приоритет**: HIGH (блокирует F011-B)

---

## 1. Метаданные

```yaml
feature_id: F011-A
name: remove-non-openai-providers
title: Удаление нестандартных AI провайдеров (GoogleGemini и Cohere)
created: 2026-01-15
status: DRAFT
priority: HIGH
services:
  - free-ai-selector-business-api
  - free-ai-selector-data-postgres-api
requirements_count: 7
estimated_effort: 2-3 hours
risk_level: low
blocking: F011-B
```

---

## 2. Executive Summary

### 2.1 Проблема

В проекте free-ai-selector присутствуют **2 провайдера с нестандартными API форматами**:
- **GoogleGemini** — использует Gemini-specific формат (`systemInstruction` вместо messages array)
- **Cohere** — использует собственный API формат, несовместимый с OpenAI

Эти провайдеры усложняют кодовую базу:
1. **Дополнительная сложность** при добавлении новых параметров (system prompts, response_format)
2. **Специфичная реализация** для каждого провайдера
3. **Увеличение технического долга** из-за поддержки 3 разных API форматов
4. **Затруднённое масштабирование** — каждое изменение требует 3 варианта реализации

### 2.2 Предлагаемое решение

**Удалить GoogleGemini и Cohere провайдеров из проекта**, оставив только **14 OpenAI-compatible провайдеров**.

**Обоснование**:
- ✅ **Упрощение кода**: Единый API формат для всех провайдеров
- ✅ **Ускорение разработки**: Новые фичи реализуются одинаково для всех
- ✅ **Снижение технического долга**: Меньше кода = меньше багов
- ✅ **Подготовка к F011-B**: Упрощает добавление system prompts и response_format

### 2.3 Затронутые провайдеры

**Удаляются:**
- ~~GoogleGemini~~ (Gemini-specific API)
- ~~Cohere~~ (proprietary API)

**Остаются (14 OpenAI-compatible):**
- Cloudflare, Groq, Cerebras, SambaNova, HuggingFace
- DeepSeek, OpenRouter, GitHub Models

---

## 3. Цели и успех

### 3.1 Бизнес-цели

| Цель | Метрика | Целевое значение |
|------|---------|------------------|
| Упрощение кодовой базы | Строк кода | -200 строк |
| Унификация API форматов | Количество форматов | 3 → 1 (только OpenAI) |
| Ускорение разработки фичей | Время на реализацию | -30% (одна реализация вместо трёх) |
| Снижение количества багов | Потенциальные точки отказа | -2 провайдера |

### 3.2 Технические цели

- [x] Удалить файлы провайдеров (google_gemini.py, cohere.py)
- [x] Удалить записи из ProviderRegistry
- [x] Удалить модели из seed.py (Data API)
- [x] Удалить env переменные из docker-compose.yml
- [x] Обновить документацию
- [x] Убедиться, что все тесты проходят

### 3.3 Критерии успеха

| Критерий | Измерение |
|----------|-----------|
| **Функциональность** | Все существующие endpoints работают без ошибок |
| **Тесты** | ≥75% coverage, все тесты проходят |
| **Чистота** | Нет упоминаний GoogleGemini/Cohere в коде |
| **Документация** | Все ссылки обновлены |
| **Деплой** | `make up && make health` успешны |

---

## 4. Требования (Must Have)

### FR-001: Удаление файла GoogleGemini провайдера

**Описание**: Удалить файл `services/free-ai-selector-business-api/app/infrastructure/ai_providers/google_gemini.py`

**Acceptance Criteria**:
- [ ] Файл `google_gemini.py` удалён из репозитория
- [ ] Класс `GoogleGeminiProvider` недоступен в кодовой базе

---

### FR-002: Удаление файла Cohere провайдера

**Описание**: Удалить файл `services/free-ai-selector-business-api/app/infrastructure/ai_providers/cohere.py`

**Acceptance Criteria**:
- [ ] Файл `cohere.py` удалён из репозитория
- [ ] Класс `CohereProvider` недоступен в кодовой базе

---

### FR-003: Удаление из ProviderRegistry

**Описание**: Удалить записи GoogleGemini и Cohere из `PROVIDER_CLASSES` в `registry.py`

**Файл**: `services/free-ai-selector-business-api/app/infrastructure/ai_providers/registry.py`

**Acceptance Criteria**:
- [ ] Ключи `"GoogleGemini"` и `"Cohere"` удалены из `PROVIDER_CLASSES` dict
- [ ] Импорты `GoogleGeminiProvider` и `CohereProvider` удалены из файла
- [ ] ProviderRegistry возвращает только 14 провайдеров

**Тест**:
```python
assert len(ProviderRegistry.get_all_provider_names()) == 14
assert "GoogleGemini" not in ProviderRegistry.get_all_provider_names()
assert "Cohere" not in ProviderRegistry.get_all_provider_names()
```

---

### FR-004: Удаление моделей из seed.py

**Описание**: Удалить GoogleGemini и Cohere модели из seed данных Data API

**Файл**: `services/free-ai-selector-data-postgres-api/app/infrastructure/database/seed.py`

**Acceptance Criteria**:
- [ ] Записи с `provider="GoogleGemini"` удалены из `INITIAL_MODELS` list
- [ ] Записи с `provider="Cohere"` удалены из `INITIAL_MODELS` list
- [ ] `make seed` выполняется успешно
- [ ] В таблице `ai_models` нет записей с этими провайдерами

**Тест**:
```bash
docker compose exec free-ai-selector-data-postgres-api python -m app.infrastructure.database.seed
# Проверить, что моделей только 14 провайдеров
```

---

### FR-005: Удаление env переменных

**Описание**: Удалить API ключи GoogleGemini и Cohere из конфигурации

**Файлы**:
- `docker-compose.yml`
- `.env.example` (если существует)

**Acceptance Criteria**:
- [ ] `GOOGLE_GEMINI_API_KEY` удалён из environment секции Business API
- [ ] `COHERE_API_KEY` удалён из environment секции Business API
- [ ] Комментарии и примеры для этих переменных удалены

**Примечание**: `.env` файл НЕ изменяется (он в .gitignore), но пользователь может удалить ключи вручную.

---

### FR-006: Обновление документации

**Описание**: Обновить документацию для отражения удаления провайдеров

**Файлы для обновления**:
- `README.md` — обновить список провайдеров (16 → 14)
- `docs/ai-context/SERVICE_MAP.md` — удалить упоминания GoogleGemini/Cohere
- `docs/ai-context/PROJECT_CONTEXT.md` — обновить количество провайдеров
- `CLAUDE.md` — обновить раздел "AI-провайдеры"

**Acceptance Criteria**:
- [ ] Все упоминания "16 провайдеров" заменены на "14 провайдеров"
- [ ] GoogleGemini и Cohere НЕ упоминаются в списках провайдеров
- [ ] Добавлена заметка о причине удаления (упрощение кода)

---

### FR-007: Проверка тестов

**Описание**: Убедиться, что все тесты проходят после удаления провайдеров

**Acceptance Criteria**:
- [ ] `make test` выполняется успешно
- [ ] Coverage ≥75% (не ухудшается)
- [ ] Нет failing tests, связанных с GoogleGemini или Cohere
- [ ] `make health` показывает все сервисы healthy

**Команды для проверки**:
```bash
make test
make test-business
make test-data
make health
```

---

## 5. Пользовательские истории

### US-001: Разработчик удаляет нестандартные провайдеры

**Как** разработчик проекта
**Я хочу** удалить GoogleGemini и Cohere провайдеров
**Чтобы** упростить кодовую базу перед добавлением новых параметров (system prompts, response_format)

**Acceptance Criteria**:
- Файлы провайдеров удалены
- Registry обновлён
- Seed данные не содержат удалённых провайдеров
- Документация обновлена

---

### US-002: Пользователь использует оставшиеся провайдеры

**Как** пользователь free-ai-selector
**Я хочу** продолжать использовать систему
**Чтобы** получать ответы от 14 OpenAI-compatible провайдеров

**Acceptance Criteria**:
- API endpoints работают без изменений
- Model selection выбирает из 14 провайдеров
- Ответы возвращаются успешно
- Никаких ошибок, связанных с удалёнными провайдерами

---

## 6. Архитектурные решения

### 6.1 Затронутые компоненты

```
Business API:
├── infrastructure/ai_providers/
│   ├── google_gemini.py    ❌ УДАЛИТЬ
│   ├── cohere.py            ❌ УДАЛИТЬ
│   └── registry.py          ✏️ ИЗМЕНИТЬ (удалить 2 записи)

Data API:
└── infrastructure/database/
    └── seed.py              ✏️ ИЗМЕНИТЬ (удалить модели)

DevOps:
└── docker-compose.yml       ✏️ ИЗМЕНИТЬ (удалить env vars)

Documentation:
├── README.md                ✏️ ИЗМЕНИТЬ
├── CLAUDE.md                ✏️ ИЗМЕНИТЬ
└── docs/ai-context/         ✏️ ИЗМЕНИТЬ
```

### 6.2 Backward Compatibility

**Вопрос**: Могут ли существующие запросы сломаться?

**Ответ**: Потенциально ДА, если:
1. Пользователи явно запрашивали GoogleGemini или Cohere через API
2. В БД остались записи с этими провайдерами

**Митигация**:
1. **Data API**: Удалить модели из БД через seed.py
2. **Business API**: Model selection автоматически выберет другой провайдер из оставшихся 14
3. **Документация**: Объявить deprecation (если нужно)

**Риск**: LOW — провайдеры выбираются автоматически по reliability_score

---

## 7. Изменения кода (Code Changes)

### 7.1 Файлы для удаления (2 файла)

| Файл | Строк | Комментарий |
|------|-------|-------------|
| `google_gemini.py` | ~120 | Gemini-specific provider |
| `cohere.py` | ~100 | Cohere-specific provider |
| **ИТОГО** | **~220** | **Полное удаление** |

### 7.2 Файлы для изменения (4 файла)

| Файл | Изменение | Строк |
|------|-----------|-------|
| `registry.py` | Удалить 2 импорта + 2 записи из dict | -6 |
| `seed.py` | Удалить модели GoogleGemini и Cohere | -20 |
| `docker-compose.yml` | Удалить 2 env переменные | -4 |
| `README.md`, `CLAUDE.md`, docs | Обновить количество провайдеров | ~10 изменений |

**Total Impact**: ~220 строк удалено, ~40 строк изменено

---

## 8. Тестирование

### 8.1 Unit Tests

**Существующие тесты**:
- Тесты для GoogleGemini и Cohere (если есть) будут удалены
- Тесты для ProviderRegistry должны пройти с 14 провайдерами

**Новые тесты** (опционально):
```python
# test_registry.py
def test_provider_count_after_removal():
    """Проверить, что осталось 14 провайдеров"""
    assert len(ProviderRegistry.get_all_provider_names()) == 14

def test_removed_providers_not_available():
    """Проверить, что GoogleGemini и Cohere недоступны"""
    providers = ProviderRegistry.get_all_provider_names()
    assert "GoogleGemini" not in providers
    assert "Cohere" not in providers
```

### 8.2 Integration Tests

**Тест**: Model selection работает без удалённых провайдеров

```bash
curl -X POST http://localhost:8000/api/v1/prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Test prompt"}'

# Ожидаемый результат: модель выбрана из 14 оставшихся провайдеров
```

### 8.3 Manual Testing

1. **Запуск проекта**:
   ```bash
   make down
   make build
   make up
   make health
   ```

2. **Проверка seed данных**:
   ```bash
   make db-shell
   SELECT COUNT(DISTINCT provider) FROM ai_models WHERE is_active = true;
   -- Ожидается: 14
   ```

3. **Проверка API**:
   ```bash
   curl http://localhost:8000/api/v1/models
   # Должно вернуть только 14 провайдеров
   ```

---

## 9. Риски и митигации

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| **Breaking changes для пользователей** | Низкая | Средняя | Model selection автоматически выберет другой провайдер |
| **Остаточные данные в БД** | Средняя | Низкая | Запустить seed.py для пересоздания моделей |
| **Упоминания в документации** | Высокая | Низкая | Поиск по кодовой базе: `grep -r "GoogleGemini\|Cohere"` |
| **Тесты падают** | Низкая | Средняя | Удалить тесты для удалённых провайдеров |
| **Забытые env переменные** | Средняя | Низкая | Проверить все конфигурационные файлы |

---

## 10. План миграции

### Phase 1: Подготовка (5 мин)
1. Создать feature branch: `git checkout -b feature/F011-A-remove-non-openai-providers`
2. Сделать поиск всех упоминаний:
   ```bash
   grep -r "GoogleGemini" services/
   grep -r "Cohere" services/
   grep -r "google_gemini" services/
   grep -r "cohere" services/
   ```

### Phase 2: Удаление файлов (10 мин)
3. Удалить файлы провайдеров:
   ```bash
   rm services/free-ai-selector-business-api/app/infrastructure/ai_providers/google_gemini.py
   rm services/free-ai-selector-business-api/app/infrastructure/ai_providers/cohere.py
   ```
4. Обновить `registry.py` (удалить импорты и записи)
5. Обновить `seed.py` (удалить модели)

### Phase 3: Конфигурация (5 мин)
6. Обновить `docker-compose.yml` (удалить env vars)
7. Запустить проект:
   ```bash
   make down
   make build
   make up
   ```

### Phase 4: Тестирование (10 мин)
8. Запустить тесты:
   ```bash
   make test
   make health
   ```
9. Проверить seed данных:
   ```bash
   make seed
   make db-shell
   SELECT provider, COUNT(*) FROM ai_models GROUP BY provider;
   ```

### Phase 5: Документация (10 мин)
10. Обновить `README.md`, `CLAUDE.md`, `docs/ai-context/`
11. Запустить финальную проверку:
    ```bash
    grep -r "GoogleGemini\|Cohere" .
    # Должны остаться только упоминания в PRD/_research (историческая справка)
    ```

### Phase 6: Commit & Deploy (5 мин)
12. Закоммитить изменения:
    ```bash
    git add .
    git commit -m "feat(F011-A): remove GoogleGemini and Cohere providers

    - Remove google_gemini.py and cohere.py
    - Update ProviderRegistry (14 providers)
    - Remove models from seed.py
    - Remove env vars from docker-compose.yml
    - Update documentation

    BREAKING CHANGE: GoogleGemini and Cohere providers no longer available"
    ```
13. Push и создать PR (если используется)

**Total Time**: ~45 минут

---

## 11. Definition of Done

- [x] GoogleGemini и Cohere файлы удалены
- [x] ProviderRegistry содержит только 14 провайдеров
- [x] Seed.py не содержит удалённых провайдеров
- [x] Docker-compose.yml не содержит env vars удалённых провайдеров
- [x] Документация обновлена (14 провайдеров)
- [x] Все тесты проходят (≥75% coverage)
- [x] `make health` успешен
- [x] Нет упоминаний GoogleGemini/Cohere в активном коде
- [x] Код зарелизен в master
- [x] Pipeline state обновлён (F011-A DEPLOYED)

---

## 12. Следующие шаги

После успешного завершения F011-A:

1. **F011-B (System Prompts & JSON Response)**:
   - Добавить `system_prompt` и `response_format` параметры
   - Реализовать для 14 OpenAI-compatible провайдеров
   - Единая реализация для всех (упрощено благодаря F011-A)

2. **Обновить F011-B PRD**:
   - Подтвердить, что scope = 14 провайдеров
   - Убрать упоминания о GoogleGemini и Cohere

---

## 13. Связанные документы

| Документ | Путь |
|----------|------|
| **F011-B PRD** | `ai-docs/docs/_analysis/2026-01-15_F011-B_system-prompts-json-response-_analysis.md` |
| **F011-B Research** | `ai-docs/docs/_research/2026-01-15_F011-B_system-prompts-json-response-_research.md` |
| **CLAUDE.md** | `./CLAUDE.md` |
| **Pipeline State** | `./.pipeline-state.json` |

---

**Создано**: 2026-01-15
**Версия**: 1.0
**Статус**: Draft → Ready for Implementation
**Блокирует**: F011-B (System Prompts & JSON Response)
