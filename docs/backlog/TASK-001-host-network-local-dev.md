# TASK-001: Унификация Docker-сетей: host network + порты 802x для всех окружений

## Статус

New

## Описание

Health Worker падает в crash-loop, потому что Business API переведён на `network_mode: host`, а сам Health Worker остаётся на bridge-сети — Docker DNS не может разрешить имя хоста `business-api`. Telegram Bot решает ту же проблему костылём через `extra_hosts`.

Исходно планировалось решить это через `docker-compose.override.yml` только для локальной разработки. Расширенный scope: вместо трёх compose-файлов (`docker-compose.yml`, `docker-compose.override.yml`, `docker-compose.vps.yml`) переходим к одному базовому файлу с host network для клиентских сервисов.

Все клиентские сервисы (Business API, Telegram Bot, Health Worker) переводятся на `network_mode: host` с явными портами серии 802x непосредственно в `docker-compose.yml`. Data API и PostgreSQL остаются на bridge-сети. `docker-compose.override.yml` и `docker-compose.vps.yml` удаляются. Makefile и вся документация обновляются под новую однофайловую схему.

**Основные изменяемые файлы:**
- `docker-compose.yml` — основная конфигурация, получает всё
- `Makefile` — убирается MODE логика
- `docker-compose.override.yml` — удаляется
- `docker-compose.vps.yml` — удаляется
- Документация и скрипты, ссылающиеся на удалённые файлы

## Приоритет

Critical

## Соглашение о портах

| Сервис | Порт | Сеть |
|--------|------|------|
| Business API | 8020 (Uvicorn `--port 8020`) | host |
| Telegram Bot | — (нет входящих портов) | host |
| Health Worker | — (нет входящих портов) | host |
| Data API | 8021:8001 (bridge, порт-маппинг) | bridge |
| PostgreSQL | 5432 (bridge) | bridge |

## Ограничения

- Dockerfile'ы сервисов не модифицируются.
- Различия между окружениями — только через `.env` файлы, не через разные compose-файлы.

## Связанные артефакты

- Требования: [REQ-001](../requirements/REQ-001-host-network-local-dev.md)
- План: [PLAN-001](../plans/PLAN-001-host-network-unification.md)
- ADR: Нет
- Отчёт: Нет
