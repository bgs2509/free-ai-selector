# ADR-0002: Free AI Providers Selection

> Выбор бесплатных AI-провайдеров для платформы.

## Статус

**Accepted** (2025-01-17)

---

## Контекст

Free AI Selector позиционируется как **бесплатный** сервис маршрутизации AI. Необходимо выбрать провайдеров, которые:

**Требования:**

1. **100% бесплатный tier** - без требования кредитной карты
2. **Достаточные лимиты** для разработки и небольшого production
3. **Качественные модели** (минимум Llama 3 8B уровня)
4. **Стабильный API** с документацией
5. **Минимум 3 провайдера** для надёжного fallback

**Ограничения:**

- OpenAI, Anthropic, Cohere требуют кредитную карту
- Некоторые бесплатные провайдеры нестабильны
- Лимиты бесплатных tier ограничены

---

## Решение

Выбрано **6 провайдеров** с бесплатным доступом:

| Провайдер | Модель | Free Tier | Скорость |
|-----------|--------|-----------|----------|
| Google AI Studio | Gemini 2.5 Flash | 10 RPM, 250 RPD | Быстрая |
| Groq | Llama 3.3 70B | 20 RPM, 14,400 RPD | 1,800 t/s |
| Cerebras | Llama 3.3 70B | 1M tokens/day | 2,500+ t/s |
| SambaNova | Llama 3.3 70B | 20 RPM | 430 t/s |
| HuggingFace | Llama 3 8B | Rate limited | Средняя |
| Cloudflare | Llama 3.3 70B | 10K Neurons/day | Быстрая |

### Обоснование каждого провайдера

#### 1. Google AI Studio (Gemini)

- **Почему:** Ведущая модель от Google, высокое качество
- **Модель:** Gemini 2.5 Flash - быстрая и точная
- **Лимиты:** 10 RPM достаточно для демо/разработки
- **Особенность:** Отличная документация, стабильный API

#### 2. Groq (LPU)

- **Почему:** Самый быстрый inference благодаря LPU
- **Модель:** Llama 3.3 70B Versatile - мощная open-source модель
- **Лимиты:** Щедрые (14,400 RPD)
- **Особенность:** До 1,800 токенов/сек

#### 3. Cerebras

- **Почему:** Рекордная скорость inference
- **Модель:** Llama 3.3 70B
- **Лимиты:** 1M токенов/день - очень щедро
- **Особенность:** 2,500+ токенов/сек (мировой рекорд)

#### 4. SambaNova

- **Почему:** Доступ к большим моделям (до Llama 405B!)
- **Модель:** Meta-Llama-3.3-70B-Instruct
- **Лимиты:** 20 RPM
- **Особенность:** Можно протестировать Llama 405B

#### 5. HuggingFace

- **Почему:** Экосистема open-source моделей
- **Модель:** Meta-Llama-3-8B-Instruct (и тысячи других)
- **Лимиты:** Rate limited, но достаточно для fallback
- **Особенность:** Возможность выбора из тысяч моделей

#### 6. Cloudflare Workers AI

- **Почему:** Edge inference, низкая латентность
- **Модель:** Llama 3.3 70B FP8 Fast
- **Лимиты:** 10,000 Neurons/день
- **Особенность:** Serverless, без cold start

---

## Альтернативы

### Отклонённые провайдеры

#### OpenAI

**Причина отклонения:** Требует кредитную карту для API доступа

#### Anthropic Claude

**Причина отклонения:** Нет бесплатного API tier

#### Cohere

**Причина отклонения:** Free tier требует верификацию карты

#### Together AI

**Причина отклонения:** $25 free credits, но потом требует оплату

#### Replicate

**Причина отклонения:** Pay-per-use модель без бесплатного tier

### Рассмотренные, но не включённые

#### Perplexity

- Free tier есть, но API ограничен
- Может быть добавлен в будущем

#### Fireworks AI

- $1 free credits
- Слишком маленький лимит

---

## Последствия

### Положительные

- **Доступность:** 0$ для начала работы
- **Разнообразие:** 6 провайдеров = высокая доступность
- **Качество:** Все модели минимум Llama 3 уровня
- **Скорость:** Groq/Cerebras обеспечивают быстрый response

### Отрицательные

- **Лимиты:** Free tier имеет ограничения на RPM/RPD
- **Стабильность:** Бесплатные сервисы менее приоритетны для провайдеров
- **Нет GPT-4/Claude:** Топовые модели недоступны бесплатно
- **Cold start:** HuggingFace может загружать модель (20-60 сек)

### Риски

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Провайдер закроет free tier | Средняя | 6 провайдеров обеспечивают fallback |
| Rate limit в пиковые часы | Высокая | Автоматический fallback |
| Качество ответов ниже GPT-4 | Высокая | Llama 3.3 70B достаточно для большинства задач |
| Провайдер станет платным | Низкая | Мониторим изменения, добавляем новых |

---

## Совокупные лимиты

При использовании всех 6 провайдеров:

| Метрика | Значение |
|---------|----------|
| Суммарный RPM | ~120 запросов/мин |
| Суммарный RPD | ~15,000+ запросов/день |
| Токенов/день | 1M+ (Cerebras) + другие |
| Fallback уровни | 6 |

---

## Архитектура интеграции

```python
# services/free-ai-selector-business-api/app/infrastructure/ai_providers/

ai_providers/
├── base.py              # AIProviderBase (интерфейс)
├── google_gemini.py     # GoogleGeminiProvider
├── groq.py              # GroqProvider
├── cerebras.py          # CerebrasProvider
├── sambanova.py         # SambaNovaProvider
├── huggingface.py       # HuggingFaceProvider
└── cloudflare.py        # CloudflareProvider
```

### Добавление нового провайдера

1. Создать `newprovider.py` наследующий `AIProviderBase`
2. Реализовать `generate()`, `health_check()`, `get_provider_name()`
3. Зарегистрировать в ProcessPromptUseCase
4. Добавить seed данные
5. Добавить env переменные

---

## Мониторинг провайдеров

Health Worker каждый час:
1. Отправляет тестовый промпт каждому провайдеру
2. Записывает success/failure
3. Обновляет reliability_score
4. Помечает недоступных

```bash
# Проверить статус провайдеров
curl -X POST http://localhost:8000/api/v1/providers/test
```

---

## Ссылки

- [AI Providers](../project/ai-providers.md) - Детальная документация
- [API Keys Setup](../operations/api-keys.md) - Получение ключей
- Provider docs:
  - [Google AI Studio](https://ai.google.dev/docs)
  - [Groq](https://console.groq.com/docs)
  - [Cerebras](https://cloud.cerebras.ai/docs)
  - [SambaNova](https://cloud.sambanova.ai/docs)
  - [HuggingFace](https://huggingface.co/docs)
  - [Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai/)
