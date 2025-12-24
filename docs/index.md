# Free AI Selector Documentation

> Документация проекта Free AI Selector - платформы маршрутизации AI на основе надёжности.

---

## Быстрый старт

| Задача | Документ |
|--------|----------|
| Запустить проект за 5 минут | [operations/quick-start.md](operations/quick-start.md) |
| Настроить API ключи | [operations/api-keys.md](operations/api-keys.md) |
| Решить проблему | [operations/troubleshooting.md](operations/troubleshooting.md) |

---

## Для разработчиков

### Архитектура и дизайн

| Документ | Описание |
|----------|----------|
| [project/overview.md](project/overview.md) | Обзор проекта и бизнес-логика |
| [project/ai-providers.md](project/ai-providers.md) | 6 AI-провайдеров и как добавить нового |
| [project/reliability-formula.md](project/reliability-formula.md) | Формула расчёта надёжности |
| [project/database-schema.md](project/database-schema.md) | Схема базы данных |

### API Reference

| API | Документ | OpenAPI |
|-----|----------|---------|
| Business API (8000) | [api/business-api.md](api/business-api.md) | http://localhost:8000/docs |
| Data API (8001) | [api/data-api.md](api/data-api.md) | http://localhost:8002/docs |
| Коды ошибок | [api/errors.md](api/errors.md) | - |
| Примеры использования | [api/examples.md](api/examples.md) | - |

### Architecture Decision Records

| ADR | Название |
|-----|----------|
| [0001](adr/0001-reliability-scoring.md) | Reliability Scoring Formula |
| [0002](adr/0002-free-ai-providers.md) | Free AI Providers Selection |
| [template](adr/template.md) | Шаблон для новых ADR |

---

## Для Claude Code (AI)

> Эти файлы оптимизированы для использования Claude Code при генерации кода.

| Документ | Назначение |
|----------|------------|
| [ai-context/PROJECT_CONTEXT.md](ai-context/PROJECT_CONTEXT.md) | Quick facts, правила, примеры CORRECT/WRONG |
| [ai-context/SERVICE_MAP.md](ai-context/SERVICE_MAP.md) | Карта сервисов, endpoints, env vars |
| [ai-context/EXAMPLES.md](ai-context/EXAMPLES.md) | Примеры кода: endpoints, use cases, tests |

### Общие паттерны (в .aidd/)

Общие архитектурные паттерны документированы в фреймворке `.aidd/`:

| Тема | Файл |
|------|------|
| DDD/Hexagonal архитектура | `.aidd/knowledge/architecture/ddd-hexagonal.md` |
| HTTP-only доступ к данным | `.aidd/knowledge/architecture/data-access.md` |
| Coding standards | `.aidd/conventions.md` |
| Testing guidelines | `.aidd/knowledge/quality/testing/` |
| FastAPI patterns | `.aidd/knowledge/services/fastapi/` |

---

## Operations

| Документ | Описание |
|----------|----------|
| [operations/quick-start.md](operations/quick-start.md) | Быстрый запуск |
| [operations/deployment.md](operations/deployment.md) | Развёртывание |
| [operations/troubleshooting.md](operations/troubleshooting.md) | Решение проблем |
| [operations/api-keys.md](operations/api-keys.md) | Настройка API ключей |
| [operations/development.md](operations/development.md) | Руководство для разработчиков |

---

## Структура документации

```
docs/
├── index.md                    # ← Вы здесь
├── project/                    # Специфика проекта
│   ├── overview.md
│   ├── ai-providers.md
│   ├── reliability-formula.md
│   └── database-schema.md
├── api/                        # API Reference
│   ├── business-api.md
│   ├── data-api.md
│   ├── errors.md
│   └── examples.md
├── operations/                 # Runbooks
│   ├── quick-start.md
│   ├── deployment.md
│   ├── troubleshooting.md
│   ├── api-keys.md
│   └── development.md
├── adr/                        # Architecture Decisions
│   ├── template.md
│   ├── 0001-reliability-scoring.md
│   └── 0002-free-ai-providers.md
└── ai-context/                 # AI Context Files
    ├── PROJECT_CONTEXT.md
    ├── SERVICE_MAP.md
    └── EXAMPLES.md
```

---

## Связанные ресурсы

| Ресурс | Описание |
|--------|----------|
| [README.md](../README.md) | Главный README проекта |
| [CLAUDE.md](../CLAUDE.md) | Инструкции для Claude Code |
| [.aidd/CLAUDE.md](../.aidd/CLAUDE.md) | AIDD Framework guide |

---

## Поддержка

- **Issues:** [GitHub Issues](https://github.com/yourusername/free-ai-selector/issues)
- **Framework:** [.aidd/docs/](../.aidd/docs/) - документация AIDD-MVP
