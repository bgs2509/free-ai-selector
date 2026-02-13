# Инцидент: Docker build падал из-за DNS при активном VPN (Hiddify)

Дата: 2026-02-13  
Проект: `free-ai-selector`  
Контекст: локальная разработка на Ubuntu, запуск через `make up` / `docker compose up -d`

## 1. Краткое описание проблемы

При запуске `make up` сборка образов периодически зависала и завершалась ошибкой на шаге установки Python-зависимостей:

- `RUN pip install --no-cache-dir -r requirements.txt`

Падали минимум сервисы:

- `free-ai-selector-telegram-bot`
- `free-ai-selector-health-worker`

Симптом в логах выглядел как «пакет не найден», но это было следствием сетевой проблемы.

## 2. Симптомы и факты из логов

В `docker compose` логах фиксировались повторы:

- `Temporary failure in name resolution`
- `Retry(total=4..0) ... /simple/<package>/`
- `Could not find a version that satisfies the requirement ... (from versions: none)`
- `No matching distribution found ...`

Ключевой признак: ошибки резолвинга DNS внутри контейнера во время build-шага.

Дополнительно:

- `make: *** [Makefile:42: up] Error 1` — каскадное завершение `make`, так как `docker compose up -d` вернул non-zero код.
- Предупреждение `FromAsCasing` в Dockerfile не являлось причиной падения.

## 3. Диагностика (пошагово)

### 3.1 Проверка DNS, который выдал VPN

Команда:

```bash
resolvectl status tun0
```

Результат:

- `Current DNS Server: 172.19.0.2`
- `DNS Servers: 172.19.0.2`

Вывод: VPN-интерфейс `tun0` использует DNS `172.19.0.2`.

### 3.2 Проверка DNS в контейнере (bridge-сеть Docker)

Команды:

```bash
docker run --rm busybox nslookup pypi.org
docker run --rm busybox nslookup files.pythonhosted.org
```

Результат:

- `;; connection timed out; no servers could be reached`

Вывод: внутри контейнера DNS недоступен.

### 3.3 Проверка DNS через сеть хоста

Команда:

```bash
docker run --rm --network host busybox nslookup pypi.org 172.19.0.2
```

Результат: успешный ответ с IP-адресами `pypi.org`.

Вывод: DNS-сервер доступен с хоста, но недоступен из bridge-сетей Docker.

### 3.4 Проверка бэкенда firewall и подсетей Docker

Команды:

```bash
docker info | grep -i "Firewall"
docker network inspect $(docker network ls -q) --format '{{range .IPAM.Config}}{{.Subnet}}{{"\n"}}{{end}}' | sort -u
```

Изначально наблюдались подсети:

- `172.17.0.0/16`
- `172.18.0.0/16`
- `172.19.0.0/16`

При этом VPN DNS был `172.19.0.2`.

Вывод: пересечение адресного пространства (overlap) между Docker и VPN.

## 4. Первопричина

Первопричина — конфликт подсетей:

- Docker bridge использовал диапазон `172.19.0.0/16`.
- VPN DNS находился по адресу `172.19.0.2` (тот же диапазон).

Из-за пересечения маршрут к `172.19.0.2` из контейнера интерпретировался как локальный docker-сегмент, а не как DNS через VPN, что приводило к таймаутам DNS-запросов.

## 5. Первичный фикс (исправил build)

Первый рабочий вариант в `/etc/docker/daemon.json` состоял из двух частей:

1. Увести Docker-сети из конфликтного диапазона:
   - `default-address-pools` с базой `10.66.0.0/16`.
2. Явно указать DNS с приоритетом VPN:
   - `172.19.0.2`, затем fallback (`1.1.1.1`, `8.8.8.8`).

Использованная конфигурация (первый этап):

```json
{
    "userland-proxy": true,
    "iptables": true,
    "dns": ["172.19.0.2", "1.1.1.1", "8.8.8.8"],
    "default-address-pools": [
        { "base": "10.66.0.0/16", "size": 24 }
    ]
}
```

Почему это помогло `pip install` при сборке:

1. Build-контейнеры снова получили маршрут к DNS без overlap с `172.19.0.0/16`.
2. `pypi.org` и `files.pythonhosted.org` начали резолвиться.
3. Ошибки вида `No matching distribution found` исчезли, так как корень был в DNS, а не в пакетах.

## 6. Выявленная коллизия после первичного фикса

После стабилизации build обнаружился второй эффект в runtime:

1. Внутренние сервисы (`business-api` ↔ `data-api`) оставались healthy.
2. Внешние вызовы из контейнеров (Telegram/API провайдеров) периодически падали по DNS.
3. Симптом: `Temporary failure in name resolution` в `telegram-bot` и `health-worker`.

Причина коллизии:

1. Статический `dns: ["172.19.0.2", ...]` жёстко привязывал Docker к DNS конкретного VPN-состояния.
2. При переподключении VPN/смене DNS/недоступности `172.19.0.2` контейнеры начинали деградировать по внешнему резолвингу.
3. Внутрикластерный DNS Docker продолжал работать, поэтому внутренние health-check не падали.

Дополнительный фактор диагностики:

1. По умолчанию `make` использует `MODE=nginx`.
2. После `make loc` команды вроде `make logs` без `MODE=loc` могут смотреть не тот compose-файл.

## 7. Финальное решение

Для локального режима (`docker-compose.loc.yml`) зафиксирована финальная схема:

1. Оставить `default-address-pools` (устранение первопричины overlap).
2. Удалить статический ключ `dns` из `/etc/docker/daemon.json`.
3. Перезапустить Docker и пересоздать проектные сети.

Рекомендуемая конфигурация `daemon.json`:

```json
{
    "userland-proxy": true,
    "iptables": true,
    "default-address-pools": [
        { "base": "10.66.0.0/16", "size": 24 }
    ]
}
```

Применение:

```bash
sudo systemctl restart docker
make down MODE=loc
make loc
```

## 8. Проверка после финального решения

### 8.1 Проверка подсетей

После изменений подсети должны оставаться вне конфликтного диапазона VPN:

- `10.66.0.0/24`
- `10.66.1.0/24`
- legacy-сети допустимы, если не пересекаются с актуальным VPN DNS/маршрутами

### 8.2 Проверка функциональности

Ожидаемое поведение:

1. Сборка образов проходит (`pip install` без DNS-ошибок).
2. В runtime нет `Temporary failure in name resolution` для внешних доменов.
3. `telegram-bot` не уходит в цикл перезапусков по DNS.

## 9. Почему финальное решение корректное

1. Сохраняет исправление первопричины (overlap подсетей Docker и VPN).
2. Убирает хрупкую привязку к конкретному VPN DNS (`172.19.0.2`).
3. Делает поведение предсказуемым для `loc`-разработки и после переподключений VPN.
4. Не требует костылей вроде `build.network: host` в каждом сервисе.

## 10. Когда статический `dns` всё же нужен

Явно задавать `dns` в Docker daemon стоит только если есть подтверждённая необходимость:

1. Корпоративный split-DNS (внутренние домены доступны только через конкретный резолвер).
2. Нестабильное наследование DNS от хоста, подтверждённое диагностикой.

Если `dns` задаётся вручную, его нужно сопровождать:

1. Проверять актуальность адреса при каждом изменении VPN.
2. Не использовать fallback, заблокированные политикой сети.
3. Регулярно валидировать резолв из контейнера.

## 11. Риски и что учитывать в будущем

1. Не добавлять Docker-пулы, пересекающиеся с VPN/корпоративными диапазонами.
2. При смене VPN-клиента проверять:
   - `resolvectl status <vpn_if>`
   - `docker network inspect ...`
3. Для локального режима всегда явно указывать режим в командах диагностики:
   - `make logs MODE=loc`
   - `make health MODE=loc`

## 12. Команды для быстрой самопроверки

```bash
# DNS VPN
resolvectl status tun0

# Подсети Docker
docker network inspect $(docker network ls -q) --format '{{range .IPAM.Config}}{{.Subnet}}{{"\n"}}{{end}}' | sort -u

# DNS из контейнера
docker run --rm busybox nslookup pypi.org
docker run --rm busybox nslookup api.telegram.org

# Запуск и проверка в локальном режиме
make loc
make health MODE=loc
make logs MODE=loc
```

## 13. Краткий итог

Проблема с `pip` действительно была DNS/маршрутизацией из-за overlap `172.19.0.0/16`.  
Перенос Docker address pool в `10.66.0.0/16` устранил корень проблемы.  
Статический `dns` помог на первом этапе, но для `loc`-режима создал дополнительную хрупкость в runtime; финально его удалили.
