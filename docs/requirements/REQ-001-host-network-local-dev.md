# REQ-001: Требования для TASK-001

## Task
TASK-001: Унификация Docker-сетей: host network + порты 802x для всех окружений

## Статус
Draft

## Функциональные требования (FR)

| ID   | Требование | Приоритет |
|------|-----------|-----------|
| FR-1 | Business API переводится на `network_mode: host`, команда Uvicorn переопределяется через `command` с `--port 8020`, healthcheck обновляется на `localhost:8020`, переменная `DATA_API_URL=http://localhost:8021` — всё в базовом `docker-compose.yml` | Must |
| FR-2 | Telegram Bot переводится на `network_mode: host`, переменная `BUSINESS_API_URL=http://localhost:8020` — в базовом `docker-compose.yml`; костыль `extra_hosts` удаляется | Must |
| FR-3 | Health Worker переводится на `network_mode: host`, переменные `BUSINESS_API_URL=http://localhost:8020` и `DATA_API_URL=http://localhost:8021` — в базовом `docker-compose.yml`; устраняет crash loop из-за неразрешимого Docker DNS имени хоста на bridge-сети | Must |
| FR-4 | Data API пробрасывает порт `8021:8001` вместо `8001:8001` в базовом `docker-compose.yml`, остаётся на bridge-сети `free-ai-selector-network` без изменений сетевой модели | Must |
| FR-5 | PostgreSQL остаётся на bridge-сети без каких-либо изменений | Must |
| FR-6 | `docker-compose.override.yml` удаляется — вся конфигурация (host network, порты, переменные окружения) переносится в базовый `docker-compose.yml` | Must |
| FR-7 | `docker-compose.vps.yml` удаляется — host network mode делает отдельный VPS-файл с proxy-network избыточным | Must |
| FR-8 | `Makefile` обновляется: убирается логика `MODE=local/vps` и все ссылки на несуществующие compose-файлы; остаётся один `docker-compose.yml` для всех окружений | Must |
| FR-9 | Все файлы, ссылающиеся на `docker-compose.override.yml` или `docker-compose.vps.yml` (документация, скрипты деплоя, CLAUDE.md), обновляются или очищаются от устаревших ссылок | Must |

## Нефункциональные требования (NFR)

| ID    | Требование | Категория | Приоритет |
|-------|-----------|-----------|-----------|
| NFR-1 | ~~Dockerfile'ы сервисов не модифицируются~~ — **ОТМЕНЕНО**: `Dockerfile` Business API модифицируется (`EXPOSE`, `HEALTHCHECK`, `CMD` синхронизируются с портом 8020) | — | — |
| NFR-2 | Различия между локальным и VPS окружениями достигаются только через значения переменных в `.env` файлах, без разных compose-файлов | Compatibility | Must |
| NFR-3 | Business API доступен другим проектам на этой же машине через `localhost:8020` (host-сеть открывает порт напрямую на хосте) | Accessibility | Should |
| NFR-4 | Результирующая конфигурация — один `docker-compose.yml` вместо трёх файлов, что упрощает поддержку и онбординг | Simplicity | Should |
