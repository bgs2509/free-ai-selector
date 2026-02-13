---
feature_id: "F021"
feature_name: "compose-nginx-local-modes"
title: "Два независимых compose-файла: nginx (VPS) и loc (local без nginx)"
created: "2026-02-13"
author: "AI (Analyst)"
type: "prd"
status: "Draft"
version: 1
mode: "FEATURE"

related_features: [F005, F011-C, F020]
services: [free-ai-selector-business-api, free-ai-selector-data-postgres-api, free-ai-selector-telegram-bot, free-ai-selector-health-worker]
requirements_count: 16

pipelines:
  business: true
  data: true
  integration: true
  modified: [deployment-mode-switching, root-path-routing]
---

# PRD: Режимы запуска `nginx` и `loc` для Docker Compose

**Feature ID**: F021  
**Версия**: 1.0  
**Дата**: 2026-02-13  
**Автор**: AI Agent (Аналитик)  
**Статус**: Draft

---

## 1. Обзор

### 1.1 Проблема
Текущая конфигурация Compose ориентирована на VPS-сценарий за внешним nginx-proxy:
- порты API не опубликованы на host;
- доступ ожидается через `ROOT_PATH` и внешний reverse proxy;
- локальный сценарий разработки (`http://localhost:8000/docs`) не работает напрямую.

Это создаёт путаницу и ломает быстрый локальный запуск для разработки/проверки.

### 1.2 Решение
Сделать два независимых compose-файла без override:
- `docker-compose.nginx.yml` — VPS-совместимый режим за nginx (без публикации портов);
- `docker-compose.loc.yml` — локальный режим без nginx (с публикацией портов и пустым `ROOT_PATH`).

Команды `make` явно выбирают один из файлов. Дополнительно унифицировать обработку `root_path` и ссылок UI, чтобы `/docs` корректно работал в обоих режимах.

### 1.3 Scope
**In scope:**
- переименование `docker-compose.yml` -> `docker-compose.nginx.yml`;
- создание отдельного `docker-compose.loc.yml` как независимой локальной конфигурации (не override);
- новые команды `make nginx`, `make loc` и адаптация существующих команд `make`;
- корректная обработка `ROOT_PATH/openapi_url` в Business API и Data API;
- корректное вычисление базового префикса в Web UI для API и `API Docs`;
- обновление документации запуска.

**Out of scope:**
- изменения бизнес-логики маршрутизации AI моделей;
- изменения Telegram Bot сценариев;
- изменения в reverse-proxy конфигурации на самом VPS.

---

## 2. Функциональные требования

### 2.1 Core Features (Must Have)

| ID | Название | Описание | Критерий приёмки |
|---|---|---|---|
| FR-001 | Переименование compose-файла | Текущий `docker-compose.yml` переименован в `docker-compose.nginx.yml` | Запуск VPS-режима возможен через новый файл без функциональных регрессий |
| FR-002 | Команда `make nginx` | Добавлена отдельная команда запуска nginx-режима | `make nginx` поднимает сервисы в текущей VPS-конфигурации |
| FR-003 | Независимый локальный compose-файл | Добавлен отдельный `docker-compose.loc.yml` для локального режима | `docker compose -f docker-compose.loc.yml up -d` поднимает локальный стек без зависимости от `docker-compose.nginx.yml` |
| FR-004 | Локальный запуск без proxy-network | Локальный режим не требует внешней сети `proxy-network` | `make loc` работает на машине разработчика без предварительного создания `proxy-network` |
| FR-005 | Локальный `ROOT_PATH` | В локальном режиме `ROOT_PATH` принудительно пустой для Business/Data API | В локальном режиме `/docs` и `/openapi.json` открываются по корню |
| FR-006 | Команда `make loc` | Добавлена отдельная команда локального запуска | `make loc` поднимает сервисы и проходит `make health` |
| FR-007 | Совместимость `make up` | `make up` остаётся рабочим алиасом | `make up` запускает режим `nginx` (backward compatibility) |
| FR-008 | Mode-aware команды Makefile | Команды (`down`, `logs`, `status`, `health`, `migrate`, `seed`, shell-команды) работают через выбранный compose-файл режима | Команды работают без `docker-compose.yml` в корне |
| FR-009 | Root path в Business API | Конфигурация OpenAPI/Docs корректна для `ROOT_PATH` и пустого пути | В `nginx` режиме docs доступны под префиксом; в `loc` режиме — по `/docs` |
| FR-010 | Root path в Data API | Data API использует динамический `openapi_url` с учётом `ROOT_PATH` | В обоих режимах swagger Data API открывается корректно |
| FR-011 | Корректный API_BASE в Web UI | UI динамически определяет base path без хардкода | Ссылки API и `API Docs` работают и в `/`, и в `/free-ai-selector/` |
| FR-012 | Документация режимов | Runbook/quick-start отражают два режима запуска | Инструкции однозначно показывают, какой URL использовать в каждом режиме |

### 2.2 Important Features (Should Have)

| ID | Название | Описание | Критерий приёмки |
|---|---|---|---|
| FR-020 | Ясная диагностика nginx-режима | При проблеме с внешней сетью в nginx-режиме пользователь получает понятную подсказку | Ошибка `proxy-network` объяснена в документации troubleshooting |
| FR-021 | Единая точка compose-конфига | В Makefile отсутствует дублирование длинных команд compose | Переиспользуется единый набор переменных/функций запуска |

### 2.3 Nice to Have (Could Have)

| ID | Название | Описание | Критерий приёмки |
|---|---|---|---|
| FR-030 | Вывод активного режима | Дополнительная команда/сообщение о текущем режиме | После запуска видно, в каком режиме поднят стек |

---

## 3. User Stories

### US-001: Локальная разработка без nginx
Как разработчик, я хочу запустить стек локально командой `make loc`, чтобы сразу открыть `http://localhost:8000/docs` и `http://localhost:8001/docs`.

### US-002: VPS-совместимый запуск
Как DevOps-инженер, я хочу запускать стек через `make nginx`, чтобы сохранить текущую модель работы за внешним nginx-proxy и `ROOT_PATH`.

### US-003: Быстрое переключение режимов
Как участник команды, я хочу иметь два явных режима в `Makefile`, чтобы не менять compose-файлы вручную и не ломать окружение коллег.

---

## 4. Пайплайны

### 4.1 Бизнес-пайплайн
`Developer -> make (nginx|loc) -> docker compose (selected file) -> services up -> health checks -> docs/ui access`

### 4.2 Data pipeline
- В `nginx` режиме: Data API и Business API работают с `ROOT_PATH` из env.
- В `loc` режиме: `ROOT_PATH=""`, доступ к `openapi.json/docs` идёт по корневым путям.
- Передача данных между сервисами не меняется (HTTP Data API как SSOT).

### 4.3 Интеграционный пайплайн

| ID | От | К | Контракт | Изменение |
|---|---|---|---|---|
| INT-001 | Developer CLI | Docker Compose | `-f docker-compose.nginx.yml` | Новый явный nginx-режим |
| INT-002 | Developer CLI | Docker Compose | `-f docker-compose.loc.yml` | Новый локальный режим (независимый файл) |
| INT-003 | Browser | Business API | `/docs`, `/openapi.json`, `/api/v1/*` | Корректный путь в двух режимах |
| INT-004 | Browser | Data API | `/docs`, `/openapi.json` | Корректный путь в двух режимах |

### 4.4 Влияние на существующие пайплайны
- Пайплайн деплоя на VPS сохраняется (через nginx-режим).
- Локальный developer pipeline упрощается.
- Бизнес- и data-эндпоинты не меняют контракт.

---

## 5. UI/UX требования

| ID | Название | Описание | Приоритет |
|---|---|---|---|
| UI-001 | Ссылка API Docs в Web UI | Ссылка ведёт на корректный docs path в обоих режимах | Must |
| UI-002 | Префикс API вызовов | JS формирует API base из фактического URL-префикса | Must |
| UI-003 | Предсказуемые URL в документации | Для каждого режима описаны точные адреса сервисов | Must |

---

## 6. Нефункциональные требования

| ID | Метрика | Требование |
|---|---|---|
| NF-001 | Обратная совместимость | Поведение VPS-режима не деградирует относительно текущего состояния |
| NF-002 | Локальная доступность | В режиме `loc` API docs доступны с host-машины без proxy |
| NF-003 | Поддерживаемость | Конфигурация режимов прозрачна, без override-магии и без ручных патчей compose-файлов перед запуском |
| NF-004 | Безопасность | В nginx-режиме сервисы по-прежнему не публикуют внутренние порты наружу |
| NF-005 | Простота | Без добавления новых зависимостей и без усложнения архитектуры |

### 6.5 Требования к тестированию

#### Smoke тесты (обязательно)
- TRQ-001: `make nginx` поднимает сервисы, `make health` показывает healthy.
- TRQ-002: В режиме `nginx` с хоста `localhost:8000` недоступен напрямую (ожидаемое поведение).
- TRQ-003: `make loc` поднимает сервисы, `http://localhost:8000/docs` и `http://localhost:8001/docs` открываются.
- TRQ-004: В режиме `loc` `GET /health` на 8000/8001 возвращает `200`.
- TRQ-005: В режиме `nginx` Web UI и docs корректно работают под `ROOT_PATH` (например `/free-ai-selector/`).
- TRQ-006: Ссылка `API Docs` в UI корректна в обоих режимах.

---

## 7. Технические ограничения
- Не добавлять новые внешние зависимости.
- Сохранить текущую архитектуру микросервисов и HTTP-only доступ к Data API.
- Изменения только в рамках текущего репозитория (`$PWD`).

---

## 8. Допущения и риски

| Риск | Вероятность | Влияние | Митигация |
|---|---|---|---|
| Переименование `docker-compose.yml` ломает скрипты/привычки | Medium | High | `make up` как алиас на `make nginx`, обновить документацию |
| Расхождение compose-файлов `nginx` и `loc` со временем | Medium | Medium | Явно документировать различия и держать комментарии в обоих файлах |
| Ошибка в вычислении UI base path | Medium | Medium | Проверка URL в root и в prefix-режиме |
| `proxy-network` отсутствует на локальной машине | High | Low | В `docker-compose.loc.yml` полностью исключить `proxy-network` |

---

## 9. Открытые вопросы
1. Нужен ли отдельный алиас `make local` помимо `make loc` (рекомендация: пока нет, чтобы не расширять API Makefile без необходимости).

---

## 10. Глоссарий
- `nginx mode`: режим запуска контейнеров для VPS с внешним reverse proxy.
- `loc mode`: локальный режим разработки без reverse proxy.
- `ROOT_PATH`: URL-префикс приложения за proxy (например `/free-ai-selector`).
- `independent compose`: самостоятельный compose-файл для отдельного режима запуска.

---

## 11. История изменений
- v1.0 (2026-02-13): первоначальный Draft.

---

## Качественные ворота

### PRD_READY Checklist

- [x] PRD создан в `ai-docs/docs/_analysis/2026-02-13_F021_compose-nginx-local-modes.md`
- [x] Все FR-* требования определены
- [x] NFR-* требования определены
- [x] `.pipeline-state.json` обновлён (gate `PRD_READY`)
- [x] Scope границы определены
- [x] Нет блокирующих открытых вопросов
