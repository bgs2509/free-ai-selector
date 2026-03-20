# PLAN-001: Унификация Docker-сетей: host network + порты 802x

**Task:** TASK-001
**Дата:** 2026-03-20
**Статус:** Draft

---

## Контекст

Health Worker падает в crash-loop, потому что Business API переведён на `network_mode: host` только в `docker-compose.override.yml`, а Health Worker остаётся на bridge-сети и пытается разрешить Docker DNS имя `free-ai-selector-business-api:8000`, которое недоступно для host-mode контейнера. Telegram Bot решает ту же проблему временным костылём через `extra_hosts: host.docker.internal`. Текущая схема из трёх compose-файлов (`docker-compose.yml`, `docker-compose.override.yml`, `docker-compose.vps.yml`) усложняет эксплуатацию и создаёт расхождение конфигурации между окружениями. Цель — перейти к единому `docker-compose.yml`, где все клиентские сервисы (Business API, Telegram Bot, Health Worker) работают на `network_mode: host` с явными портами серии 802x, а Data API остаётся на bridge с маппингом `8021:8001`.

---

## Содержание

1. Модификация `docker-compose.yml` — основное изменение сети и портов
2. Удаление `docker-compose.override.yml` и `docker-compose.vps.yml`
3. Обновление `Makefile` — упрощение после удаления MODE-логики
4. Обновление документации — `CLAUDE.md`, `README.md`, `docs/operations/*`
5. Обновление `CHANGELOG.md`
6. Верификация — проверка работоспособности после изменений

---

## Краткая версия плана

### Этап 1: Модификация `docker-compose.yml` и `Dockerfile` Business API

**Проблема.** Business API, Telegram Bot и Health Worker используют несовместимые настройки сети: кто-то на host, кто-то на bridge, из-за чего сервисы не могут общаться через localhost.

**Действие.** Добавить `network_mode: host` и переопределить порт Uvicorn через `command` (`--port 8020`) для Business API; добавить `network_mode: host` для Telegram Bot и Health Worker; сменить `ports` Data API на `8021:8001`; обновить все URL-переменные окружения на localhost-адреса; убрать ссылки на `networks:` у host-mode сервисов; актуализировать комментарии заголовка файла. Дополнительно обновить `services/free-ai-selector-business-api/Dockerfile`: изменить `EXPOSE 8000` на `EXPOSE 8020`, обновить HEALTHCHECK на порт 8020, обновить CMD на `--port 8020`.

**Результат.** Единый `docker-compose.yml` описывает полную рабочую конфигурацию без каких-либо override-файлов. Business API слушает на `:8020`, Data API доступен на `localhost:8021`. Dockerfile Business API синхронизирован с реальным портом сервиса.

**Зависимости.** Нет — это первый и ключевой этап. Изменения `docker-compose.yml` и `Dockerfile` выполняются как единое изменение в одном коммите (Этап 1 + Этап 2) без промежуточного `make up` между ними.

**Риски.** `network_mode: host` несовместим с `ports:` и `networks:` — если оставить эти поля для host-mode сервисов, Docker Compose выдаст ошибку при старте.

**Без этого.** Health Worker продолжает падать в crash-loop, Telegram Bot остаётся с `extra_hosts` костылём, fix не имеет смысла.

---

### Этап 2: Удаление `docker-compose.override.yml` и `docker-compose.vps.yml`

**Проблема.** Два файла переопределений становятся бесполезными и вводят в заблуждение после того, как всё нужное перенесено в базовый файл.

**Действие.** Удалить оба файла: `docker-compose.override.yml` и `docker-compose.vps.yml` из корня репозитория.

**Результат.** `docker compose up` без флагов `-f` больше не подгружает скрытый override; конфигурация однозначна.

**Зависимости.** Этап 1 должен быть завершён — в `docker-compose.yml` и `Dockerfile` Business API уже должно быть всё необходимое. Этап 2 выполняется в том же коммите, что и Этап 1.

**Риски.** Если CI/CD-скрипты или внешняя документация ссылаются на эти файлы, они сломаются. Файлы `docker-compose.vps.yml` задаёт `proxy-network: external`, которую теперь создавать не нужно — VPS nginx подключается к Business API через host network.

**Без этого.** Docker Compose продолжит автоматически подгружать `docker-compose.override.yml`, что может перезатереть настройки из исправленного базового файла и вернуть проблему.

---

### Этап 3: Обновление `Makefile`

**Проблема.** Makefile содержит `MODE ?= local / vps` логику на строках 27–39, переменную `LOCUST_HOST` с Docker DNS именем `:8000`, и `health-check` с условием `if MODE=local`. Всё это устарело.

**Действие.** Удалить блок `ifeq/else ifeq` и переменную `MODE`; заменить на `COMPOSE := docker compose`; убрать `make local` и `make vps` shortcuts или упростить их; обновить `LOCUST_HOST` на `http://localhost:8020`; заменить `--network free-ai-selector-network` на `--network host` в ОБОИХ местах запуска Locust-контейнера (цели `load-test` и `load-test-ui-up`); переписать `health-check` — убрать MODE-условие, проверять Business API на порту `8020` (`curl localhost:8020/health`), Data API на порту `8021`; обновить `help` текст.

**Результат.** `make up`, `make test`, `make health` работают без параметров и без MODE-флага. Единая простая команда.

**Зависимости.** Этап 1 завершён (порты уже зафиксированы в compose-файле).

**Риски.** Если кто-то передаёт `MODE=vps` в CI, команда сломается с ошибкой «undefined variable» вместо корректного сообщения. Нужно убрать проверку `$(error Unsupported MODE=...)` или оставить с понятным сообщением об устаревании.

**Без этого.** `make health` продолжит проверять порт `8000` вместо `8020` и давать ложные результаты; `make local` и `make vps` останутся сбивающими с толку артефактами.

---

### Этап 4: Обновление документации

**Проблема.** `CLAUDE.md`, `README.md` и файлы в `docs/operations/` ссылаются на удалённые compose-файлы, порты `8000`/`8001` и команды `MODE=vps`.

**Действие.** В `CLAUDE.md`: обновить таблицу портов (8020/8021), убрать упоминание `docker-compose.vps.yml` и `MODE=vps`. В `docs/operations/development.md`: обновить порты и описание compose-файлов. В `docs/operations/deployment.md`: переписать секцию VPS — убрать `docker compose -f ... -f ...`, описать новую схему с host network. В `docs/operations/troubleshooting.md`: обновить все упоминания порта 8000 на 8020. В `README.md`: обновить таблицу сервисов и порты. В `docs/ai-context/SERVICE_MAP.md`: обновить порты 8000→8020, убрать proxy-network из схемы. В `docs/ai-context/PROJECT_CONTEXT.md`: обновить пример `DATA_API_URL` (Docker DNS → `localhost:8021`). В `docs/operations/quick-start.md`: обновить порты в примерах `curl` и выводе `make health`. Также обновить `docs/api-tests/locustfile.py` строка 118: fallback `localhost:8000` → `localhost:8020`.

**Результат.** Вся документация консистентна с реальной конфигурацией; разработчик, читающий любой документ, получает актуальную информацию о портах и файлах. Locustfile использует правильный fallback-порт.

**Зависимости.** Этапы 1–3 завершены, чтобы документировать финальное состояние, а не промежуточное.

**Риски.** Велика вероятность пропустить один из файлов; нужно проверить через grep по `8000`, `override`, `vps.yml`, `MODE=vps` после правок.

**Без этого.** Документация вводит в заблуждение, разработчики будут запускать устаревшие команды и тратить время на отладку несуществующей конфигурации.

---

### Этап 5: Обновление `CHANGELOG.md`

**Проблема.** Изменение значительное (удаление файлов, смена портов, унификация сети) и должно быть отражено в истории изменений.

**Действие.** Добавить запись в секцию `## [Unreleased]` файла `CHANGELOG.md` по формату Keep a Changelog: Added (новые host-mode настройки), Changed (порты 8020/8021, упрощение Makefile), Removed (override и vps compose-файлы, MODE-логика).

**Результат.** `CHANGELOG.md` содержит запись с ссылкой на TASK-001.

**Зависимости.** Все предыдущие этапы должны быть выполнены (документируем финальное состояние).

**Риски.** Минимальные — только форматирование.

**Без этого.** История изменений будет неполной; при следующем релизе придётся восстанавливать что именно изменилось.

---

### Этап 6: Верификация

**Проблема.** После структурных изменений нужно убедиться, что все сервисы запускаются и Health Worker больше не падает в crash-loop.

**Действие.** Запустить `make up`; проверить `make health` (Business API на 8020, Data API на 8021); проверить логи Health Worker на отсутствие ошибок подключения; запустить `make test` для базовой проверки тестов; выполнить grep-проверку репозитория на оставшиеся ссылки на `8000`, `override.yml`, `vps.yml`, `MODE=vps` по путям `docker-compose.yml Makefile docs/ CLAUDE.md README.md scripts/ services/free-ai-selector-business-api/Dockerfile`; проверить nginx на VPS командой `ssh user@host "grep proxy_pass /etc/nginx/conf.d/free-ai-selector.conf"` — убедиться что `proxy_pass` указывает на `localhost:8020`.

**Результат.** Все 5 сервисов здоровы, Health Worker не перезапускается, тесты проходят, grep ничего лишнего не находит, nginx на VPS подтверждённо проксирует на `localhost:8020`.

**Зависимости.** Все предыдущие этапы.

**Риски.** На VPS может потребоваться `docker network rm proxy-network` если она осталась от старой конфигурации и мешает. Locust load-test сценарии могут обращаться к старому порту — нужно проверить `docs/api-tests/locustfile.py`.

**Без этого.** Изменение считается незавершённым; возможна регрессия, обнаруженная только в production.

---

## Полная версия плана

---

## Этап 1: Модификация `docker-compose.yml` и `Dockerfile` Business API

Файлы: `docker-compose.yml` (корень репозитория), `services/free-ai-selector-business-api/Dockerfile`.

Этап 1 и Этап 2 выполняются в одном коммите — без промежуточного `make up` между ними.

### Dockerfile Business API

Файл: `services/free-ai-selector-business-api/Dockerfile`.

Изменения:
- `EXPOSE 8000` → `EXPOSE 8020`
- HEALTHCHECK: заменить `http://localhost:8000/health` на `http://localhost:8020/health`
- CMD: добавить или обновить аргумент `--port 8020`

```dockerfile
EXPOSE 8020

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8020/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8020"]
```

### Заголовочный комментарий

Заменить текущий комментарий (строки 1–16), описывающий три compose-файла, на:

```yaml
# =============================================================================
# Free AI Selector - Docker Compose (единая конфигурация)
# =============================================================================
# Единый файл конфигурации для всех окружений (локальная разработка, VPS).
#
# Запуск:
#   docker compose up -d
#   make up
#
# Сеть:
#   Business API, Telegram Bot, Health Worker — network_mode: host
#   Data API, PostgreSQL — bridge-сеть (free-ai-selector-network)
#
# Порты (доступны на хосте):
#   Business API: localhost:8020
#   Data API:     localhost:8021
# =============================================================================
```

### PostgreSQL

Без изменений. Остаётся на bridge-сети.

### Data API (`free-ai-selector-data-postgres-api`)

Изменения:
- Добавить `ports: ["8021:8001"]` (убрать комментарий "Порты не публикуются")
- Убрать комментарий про override-файл

```yaml
free-ai-selector-data-postgres-api:
  # ... (build, container_name, environment без изменений)
  ports:
    - "8021:8001"
  depends_on:
    postgres:
      condition: service_healthy
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 40s
  networks:
    - free-ai-selector-network
  restart: unless-stopped
  # ... volumes без изменений
```

### Business API (`free-ai-selector-business-api`)

Ключевые изменения:
- Добавить `network_mode: host`
- Добавить `command` для переопределения порта Uvicorn на 8020
- Обновить healthcheck на порт 8020
- Обновить `DATA_API_URL` на `http://localhost:8021`
- Убрать `networks:` (несовместимо с `network_mode: host`)
- Оставить `depends_on` с `condition: service_healthy` для data-api — он работает независимо от `network_mode` и обеспечивает корректный порядок запуска

```yaml
free-ai-selector-business-api:
  build:
    context: ./services/free-ai-selector-business-api
    dockerfile: Dockerfile
  container_name: free-ai-selector-business-api
  network_mode: host
  command: ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8020"]
  environment:
    BUSINESS_API_HOST: ${BUSINESS_API_HOST}
    BUSINESS_API_PORT: "8020"
    BUSINESS_API_LOG_LEVEL: ${BUSINESS_API_LOG_LEVEL}
    LOG_LEVEL: ${BUSINESS_API_LOG_LEVEL:-INFO}
    DATA_API_URL: "http://localhost:8021"
    # ... остальные env-переменные без изменений
    ROOT_PATH: ""
  depends_on:
    free-ai-selector-data-postgres-api:
      condition: service_healthy
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8020/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 40s
  restart: unless-stopped
  volumes:
    - ./services/free-ai-selector-business-api:/app
    - /app/__pycache__
    - ./docs/api-tests/results/audit:/audit
```

Примечание: `command` должен соответствовать точному entrypoint Dockerfile. Проверить текущий `CMD` в `services/free-ai-selector-business-api/Dockerfile` — если там уже вызывается `uvicorn app.main:app`, команда переопределяет только аргументы.

### Telegram Bot (`free-ai-selector-telegram-bot`)

Изменения:
- Добавить `network_mode: host`
- Убрать `networks:` и `extra_hosts:`
- Обновить `BUSINESS_API_URL` на `http://localhost:8020`

```yaml
free-ai-selector-telegram-bot:
  build:
    context: ./services/free-ai-selector-telegram-bot
    dockerfile: Dockerfile
  container_name: free-ai-selector-telegram-bot
  network_mode: host
  environment:
    TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN:-}
    TELEGRAM_BOT_LOG_LEVEL: ${TELEGRAM_BOT_LOG_LEVEL}
    LOG_LEVEL: ${TELEGRAM_BOT_LOG_LEVEL:-INFO}
    BUSINESS_API_URL: "http://localhost:8020"
    BOT_ADMIN_IDS: ${BOT_ADMIN_IDS}
    BOT_MAX_MESSAGE_LENGTH: ${BOT_MAX_MESSAGE_LENGTH}
    ENVIRONMENT: ${ENVIRONMENT}
    REQUEST_ID_HEADER: ${REQUEST_ID_HEADER}
  depends_on:
    free-ai-selector-business-api:
      condition: service_healthy
  restart: unless-stopped
  volumes:
    - ./services/free-ai-selector-telegram-bot:/app
    - /app/__pycache__
```

### Health Worker (`free-ai-selector-health-worker`)

Изменения:
- Добавить `network_mode: host`
- Убрать `networks:`
- Обновить `BUSINESS_API_URL` на `http://localhost:8020`
- Обновить `DATA_API_URL` (если сейчас Docker DNS) на `http://localhost:8021`

```yaml
free-ai-selector-health-worker:
  build:
    context: ./services/free-ai-selector-health-worker
    dockerfile: Dockerfile
  container_name: free-ai-selector-health-worker
  network_mode: host
  environment:
    WORKER_LOG_LEVEL: ${WORKER_LOG_LEVEL}
    LOG_LEVEL: ${WORKER_LOG_LEVEL:-INFO}
    HEALTH_CHECK_INTERVAL: ${HEALTH_CHECK_INTERVAL}
    DATA_API_URL: "http://localhost:8021"
    BUSINESS_API_URL: "http://localhost:8020"
    ENVIRONMENT: ${ENVIRONMENT}
    REQUEST_ID_HEADER: ${REQUEST_ID_HEADER}
    # ... audit env-переменные без изменений
  depends_on:
    free-ai-selector-data-postgres-api:
      condition: service_healthy
    free-ai-selector-business-api:
      condition: service_healthy
  restart: unless-stopped
  volumes:
    - ./services/free-ai-selector-health-worker:/app
    - /app/__pycache__
    - ./docs/api-tests/results/audit:/audit
```

### Networks секция

Убрать секцию `networks:` на уровне compose-файла после проверки, что Data API и PostgreSQL всё ещё её используют. Секция остаётся — она нужна для bridge-сервисов:

```yaml
networks:
  free-ai-selector-network:
    driver: bridge
    name: free-ai-selector-network
```

---

## Этап 2: Удаление override и vps файлов

```bash
git rm docker-compose.override.yml
git rm docker-compose.vps.yml
```

После удаления убедиться, что `docker compose config` не выдаёт предупреждений о несуществующих файлах.

---

## Этап 3: Обновление `Makefile`

### Удалить MODE-логику (строки 27–39)

Заменить:
```makefile
MODE ?= local

ifeq ($(MODE),local)
COMPOSE := docker compose
else ifeq ($(MODE),vps)
COMPOSE := docker compose -f docker-compose.yml -f docker-compose.vps.yml
else
$(error Unsupported MODE='$(MODE)'. Use MODE=local or MODE=vps)
endif
```

На:
```makefile
COMPOSE := docker compose
```

### Обновить `.PHONY` и комментарии заголовка

Убрать `local vps` из `.PHONY`, обновить описание Makefile в шапке — убрать упоминания MODE.

### Обновить `LOCUST_HOST` и сеть Locust-контейнера

```makefile
LOCUST_HOST ?= http://localhost:8020
```

В целях `load-test` и `load-test-ui-up` заменить флаг `--network free-ai-selector-network` на `--network host`. После этого `LOCUST_HOST=http://localhost:8020` будет разрешаться корректно из Locust-контейнера на host-сети.

### Обновить `help` текст

Убрать строки:
```
make local                 - Запуск всех сервисов (порты 8000/8001)
make vps                   - VPS режим (за nginx reverse proxy)
make <target> MODE=local   - Выполнить target в локальном режиме
make <target> MODE=vps     - Выполнить target в VPS режиме
```

### Удалить `local:` и `vps:` targets

Удалить:
```makefile
local:
    @$(MAKE) up MODE=local RUN_SOURCE=make:local RUN_SCENARIO=infra:local

vps:
    @$(MAKE) up MODE=vps RUN_SOURCE=make:vps RUN_SCENARIO=infra:vps
```

### Обновить `health-check` target

Убрать условие `if [ "$(MODE)" = "local" ]`. Новая версия:

```makefile
health-check:
    @echo "Checking service health..."
    @echo ""
    @echo "PostgreSQL:"
    @$(COMPOSE) exec postgres pg_isready -U free_ai_selector_user >/dev/null && echo "  OK Ready" || echo "  FAIL Not ready"
    @echo ""
    @echo "Data API (localhost:8021/health):"
    @curl -f -s http://localhost:8021/health >/dev/null && echo "  OK Healthy" || echo "  FAIL Unhealthy"
    @echo ""
    @echo "Business API (localhost:8020/health):"
    @curl -f -s http://localhost:8020/health >/dev/null && echo "  OK Healthy" || echo "  FAIL Unhealthy"
```

### Убрать `MODE=$(MODE)` из всех внутренних вызовов `$(MAKE)`

Например, `@$(MAKE) ensure-up-with-context MODE=$(MODE)` → `@$(MAKE) ensure-up-with-context`.

### Убрать `ensure-up-with-context: ... MODE=$(MODE)` ссылки

Все вызовы вида `@$(MAKE) ensure-up-with-context MODE=$(MODE) RUN_SOURCE=...` упростить, убрав `MODE=$(MODE)`.

---

## Этап 4: Обновление документации

### `CLAUDE.md` (корень репозитория)

- Обновить таблицу портов (8020 для Business API, 8021 для Data API)
- Убрать упоминание `docker-compose.vps.yml` из секции VPS деплой
- Обновить команды в секции "Основные команды" — убрать `make vps`
- Убрать `make local` / `make vps` из секции команд

### `docs/operations/development.md`

- Обновить порты 8000→8020, 8001→8021
- Убрать описание `docker-compose.override.yml`
- Обновить URL для OpenAPI docs: `http://localhost:8020/docs`, `http://localhost:8021/docs`

### `docs/operations/deployment.md`

- Переписать секцию VPS: убрать `docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d`
- Заменить на `docker compose up -d`
- Убрать секцию про `proxy-network` (больше не нужна)
- Описать, что VPS nginx подключается к `localhost:8020` на хосте через host network

### `docs/operations/troubleshooting.md`

- Обновить все port-ссылки: `8000`→`8020`, `8001`→`8021`
- Убрать секции про `extra_hosts` и `host.docker.internal`

### `README.md`

- Обновить таблицу сервисов и портов
- Убрать ссылки на `docker-compose.override.yml` и `docker-compose.vps.yml`

### `docs/ai-context/SERVICE_MAP.md`

- Обновить все вхождения порта `8000` на `8020` для Business API
- Убрать `proxy-network` из схемы сетевого взаимодействия (внешняя Docker-сеть больше не используется)

### `docs/ai-context/PROJECT_CONTEXT.md`

- Обновить пример `DATA_API_URL`: Docker DNS-имя (`free-ai-selector-data-postgres-api:8001`) → `localhost:8021`

### `docs/operations/quick-start.md`

- Обновить порты в примерах `curl`: `8000` → `8020`, `8001` → `8021`
- Обновить вывод `make health` — показывать порты `8020`/`8021`

### `docs/api-tests/locustfile.py`

- Строка 118: изменить fallback-хост с `localhost:8000` на `localhost:8020`

### Проверочный grep после правок

```bash
grep -rn "8000" docker-compose.yml Makefile docs/ CLAUDE.md README.md scripts/ services/free-ai-selector-business-api/Dockerfile
grep -rn "override.yml\|vps.yml\|MODE=vps" docker-compose.yml Makefile docs/ CLAUDE.md README.md scripts/ services/free-ai-selector-business-api/Dockerfile
```

---

## Этап 5: Обновление `CHANGELOG.md`

Добавить в секцию `## [Unreleased]`:

```markdown
### Added
- `network_mode: host` для Business API (порт 8020), Telegram Bot и Health Worker — все клиентские сервисы теперь работают на host network (TASK-001)

### Changed
- Data API переведён на port-mapping `8021:8001` вместо внутреннего bridge-only (TASK-001)
- `BUSINESS_API_URL` и `DATA_API_URL` для Health Worker и Telegram Bot теперь `localhost`-адреса (TASK-001)
- `Makefile` упрощён: удалена `MODE`-логика, `COMPOSE := docker compose` без условий (TASK-001)
- `health-check` в Makefile проверяет порты 8020/8021 напрямую на хосте (TASK-001)

### Removed
- `docker-compose.override.yml` — конфигурация перенесена в `docker-compose.yml` (TASK-001)
- `docker-compose.vps.yml` — VPS-режим унифицирован с локальным (TASK-001)
- `proxy-network` (external Docker network) — больше не требуется при host network (TASK-001)
- `make local` и `make vps` targets в Makefile (TASK-001)
```

---

## Этап 6: Верификация

### Функциональная проверка

```bash
# Запуск
make up

# Health-check
make health

# Проверка портов напрямую
curl http://localhost:8020/health
curl http://localhost:8021/health

# Логи Health Worker (не должно быть ошибок подключения)
make logs-worker

# Базовые тесты
make test-data
make test-business
```

### Grep-проверка остаточных ссылок

```bash
# Поиск старых портов во всех конфигурационных файлах и документации
grep -rn "8000" docker-compose.yml Makefile docs/ CLAUDE.md README.md scripts/ services/free-ai-selector-business-api/Dockerfile

# Поиск удалённых файлов
grep -rn "override.yml\|vps.yml" docker-compose.yml Makefile docs/ CLAUDE.md README.md scripts/ services/free-ai-selector-business-api/Dockerfile

# Поиск устаревших MODE-ссылок
grep -rn "MODE=vps\|MODE=local" docker-compose.yml Makefile docs/ CLAUDE.md README.md scripts/ services/free-ai-selector-business-api/Dockerfile

# Поиск Docker DNS имён для host-mode сервисов
grep -rn "free-ai-selector-business-api:8" docker-compose.yml
```

### Проверка `docker compose config`

```bash
docker compose config
```

Команда должна выполниться без ошибок и показать итоговую конфигурацию с `network_mode: host` для трёх сервисов.

### Проверка на VPS (если применимо)

Убедиться, что после `docker compose up -d` на VPS:
- Business API доступен по `http://localhost:8020/health` на хосте
- nginx reverse proxy настроен на `proxy_pass http://localhost:8020`
- `proxy-network` больше не создаётся (удалить вручную если осталась: `docker network rm proxy-network`)

Верификация nginx конфигурации на VPS:

```bash
ssh user@host "grep proxy_pass /etc/nginx/conf.d/free-ai-selector.conf"
```

Ожидаемый результат: `proxy_pass http://localhost:8020;`
