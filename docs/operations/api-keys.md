# API Keys Setup

> Краткое руководство по получению API ключей для всех провайдеров.

Все 6 провайдеров **бесплатны и не требуют кредитную карту**.

---

## Сводная таблица

| Провайдер | URL | Переменная | Время |
|-----------|-----|------------|-------|
| Google AI Studio | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | `GOOGLE_AI_STUDIO_API_KEY` | 1 мин |
| Groq | [console.groq.com/keys](https://console.groq.com/keys) | `GROQ_API_KEY` | 2 мин |
| Cerebras | [cloud.cerebras.ai](https://cloud.cerebras.ai/) | `CEREBRAS_API_KEY` | 2 мин |
| SambaNova | [cloud.sambanova.ai](https://cloud.sambanova.ai/) | `SAMBANOVA_API_KEY` | 2 мин |
| HuggingFace | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) | `HUGGINGFACE_API_KEY` | 2 мин |
| Cloudflare | [dash.cloudflare.com](https://dash.cloudflare.com/) | `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_API_TOKEN` | 5 мин |

**Общее время:** ~15 минут на все провайдеры.

---

## 1. Google AI Studio

**Лимиты:** 10 RPM, 250 RPD

```bash
# 1. Откройте https://aistudio.google.com/apikey
# 2. Войдите через Google аккаунт
# 3. Нажмите "Create API Key"
# 4. Скопируйте ключ (начинается с AIzaSy...)

GOOGLE_AI_STUDIO_API_KEY=AIzaSy...
```

---

## 2. Groq

**Лимиты:** 20 RPM, 14,400 RPD, 1,800 tokens/sec

```bash
# 1. Откройте https://console.groq.com/keys
# 2. Sign Up / Login
# 3. Нажмите "Create API Key"
# 4. ВАЖНО: Скопируйте сразу - показывается один раз!

GROQ_API_KEY=gsk_...
```

---

## 3. Cerebras

**Лимиты:** 1M tokens/day, 30 RPM, 2,500+ tokens/sec (самый быстрый!)

```bash
# 1. Откройте https://cloud.cerebras.ai/
# 2. Sign Up / Login
# 3. API Keys → Create API Key
# 4. Скопируйте ключ

CEREBRAS_API_KEY=...
```

---

## 4. SambaNova

**Лимиты:** 20 RPM, 430 tokens/sec

```bash
# 1. Откройте https://cloud.sambanova.ai/
# 2. Sign Up / Login
# 3. Settings → API Keys → Create
# 4. Скопируйте ключ

SAMBANOVA_API_KEY=...
```

---

## 5. HuggingFace

**Лимиты:** Rate limited (достаточно для разработки)

```bash
# 1. Откройте https://huggingface.co/settings/tokens
# 2. Sign Up / Login
# 3. New token → Role: Read → Generate
# 4. Скопируйте токен (начинается с hf_...)

HUGGINGFACE_API_KEY=hf_...
```

---

## 6. Cloudflare (требует 2 значения!)

**Лимиты:** 10,000 Neurons/day

```bash
# 1. Откройте https://dash.cloudflare.com/
# 2. Sign Up / Login

# ACCOUNT ID:
# - На главной странице Dashboard справа
# - Скопируйте 32-символьный hex

# API TOKEN:
# - Profile → API Tokens → Create Token
# - Use template "Edit Cloudflare Workers"
# - ВАЖНО: Скопируйте сразу!

CLOUDFLARE_ACCOUNT_ID=1a2b3c4d...
CLOUDFLARE_API_TOKEN=...
```

---

## Итоговый .env

```bash
# === AI Providers ===

# Google AI Studio (10 RPM, 250 RPD)
GOOGLE_AI_STUDIO_API_KEY=AIzaSy...

# Groq (20 RPM, 14,400 RPD)
GROQ_API_KEY=gsk_...

# Cerebras (1M tokens/day, 30 RPM)
CEREBRAS_API_KEY=...

# SambaNova (20 RPM)
SAMBANOVA_API_KEY=...

# HuggingFace
HUGGINGFACE_API_KEY=hf_...

# Cloudflare (10,000 Neurons/day)
CLOUDFLARE_ACCOUNT_ID=...
CLOUDFLARE_API_TOKEN=...

# === Telegram Bot (опционально) ===
TELEGRAM_BOT_TOKEN=...
BOT_ADMIN_IDS=123456789
```

---

## Проверка

```bash
# 1. Запустить сервисы
make up

# 2. Подождать 30 сек

# 3. Проверить провайдеров
curl -X POST http://localhost:8000/api/v1/providers/test | jq
```

Ожидаемый вывод:

```json
{
  "results": [
    {"provider": "GoogleGemini", "success": true},
    {"provider": "Groq", "success": true},
    ...
  ],
  "successful": 6,
  "failed": 0
}
```

---

## Частые ошибки

| Ошибка | Причина | Решение |
|--------|---------|---------|
| `API key is required` | Ключ не в .env | Добавить в .env |
| `Invalid API key` | Неверный ключ | Проверить/пересоздать |
| `Rate limit exceeded` | Лимит превышен | Подождать, использовать fallback |
| `Account not found` (Cloudflare) | Неверный Account ID | Скопировать с Dashboard |

---

## Подробная инструкция

Полная пошаговая инструкция со скриншотами: [API_KEY_SETUP_GUIDE.md](../../API_KEY_SETUP_GUIDE.md)

---

## Related Documentation

- [Quick Start](quick-start.md) - Быстрый запуск
- [Troubleshooting](troubleshooting.md) - Решение проблем
- [../project/ai-providers.md](../project/ai-providers.md) - Детали провайдеров
