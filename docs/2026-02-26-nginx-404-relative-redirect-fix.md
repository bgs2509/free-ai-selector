# 2026-02-26: Nginx 404 на /free-ai-selector/ — диагностика и фикс

## Проблема

При обращении к `http://localhost/free-ai-selector/` на домашнем сервере (gpu-1) nginx возвращал 404. На test_rus сервере (95.142.37.184) тот же код работал.

## Диагностика

### Шаг 1: Определение точки отказа

```bash
# Напрямую к backend — 307 редирект (ожидаемо)
docker exec free-ai-selector-business-api curl -s -D- -o /dev/null http://localhost:8000/free-ai-selector/

# Через nginx — 404
curl -s -D- -o /dev/null http://localhost/free-ai-selector/
```

### Шаг 2: Проблема server_name (первая причина)

Nginx конфиг имел `server_name 144.124.249.120`, а запросы через reverse tunnel приходили с `Host: localhost`. Nginx направлял их в `default_server` (из `00-default.conf`), где нет location `/free-ai-selector/`.

**Фикс:** В `.env` nginx-proxy на gpu-1 установлен `SERVER_IP=localhost`.

### Шаг 3: Проблема абсолютного редиректа (вторая причина)

После фикса server_name nginx стал проксировать запросы на backend. Но `/free-ai-selector/` возвращал 307 → `/static/index.html` (абсолютный путь). Nginx пытался обработать `/static/index.html` сам, но такого location не было → 404.

**Сравнение серверов:**

| Сервер | Location header | Результат |
|--------|----------------|-----------|
| test_rus (95.142.37.184) | `static/index.html` (относительный) | Браузер → `/free-ai-selector/static/index.html` → 200 |
| gpu-1 (localhost) | `/static/index.html` (абсолютный) | Браузер → `/static/index.html` → 404 |

### Шаг 4: Нахождение причины в коде

```bash
git log -p --follow -S '/static/index.html' -- services/free-ai-selector-business-api/app/main.py
```

**Коммит `a5eac17`** (25 дек 2025) — путь сделан относительным `url="static/index.html"` для работы за nginx-proxy.

**Коммит `2b514db`** (25 фев 2026) — путь изменён на абсолютный `url="/static/index.html"` чтобы починить тест `test_static_files.py`, который проверял `location == "/static/index.html"`.

Тест был починен, но production за nginx-proxy сломан.

## Фикс

**Коммит:** `5bb31e7`

### services/free-ai-selector-business-api/app/main.py:348

```python
# Было (абсолютный путь — ломает nginx-proxy)
return RedirectResponse(url="/static/index.html")

# Стало (относительный путь — работает за nginx-proxy)
return RedirectResponse(url="static/index.html")
```

### services/free-ai-selector-business-api/tests/unit/test_static_files.py:27

```python
# Было
assert response.headers.get("location") == "/static/index.html"

# Стало
assert response.headers.get("location") == "static/index.html"
```

## Почему это работает

С относительным редиректом браузер разрешает URL относительно текущего пути:

```
GET /free-ai-selector/
307 → static/index.html
Браузер: /free-ai-selector/ + static/index.html = /free-ai-selector/static/index.html
```

С абсолютным редиректом браузер идёт в корень:

```
GET /free-ai-selector/
307 → /static/index.html
Браузер: /static/index.html  ← вне location block nginx → 404
```

## Урок

При работе FastAPI за reverse proxy с `root_path`, все редиректы в коде должны быть **относительными** (без `/` в начале). Иначе они обходят nginx location block и возвращают 404. Тесты должны проверять относительные пути, а не абсолютные.
