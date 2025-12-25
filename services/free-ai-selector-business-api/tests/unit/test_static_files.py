"""
Тесты для статических файлов и веб-интерфейса.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    """Асинхронный HTTP клиент для тестов."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_root_redirects_to_static(client: AsyncClient):
    """Тест: корневой endpoint перенаправляет на /static/index.html."""
    response = await client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers.get("location") == "/static/index.html"


@pytest.mark.asyncio
async def test_static_index_html_accessible(client: AsyncClient):
    """Тест: статический файл index.html доступен."""
    response = await client.get("/static/index.html")

    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "Рейтинг бесплатных ИИ моделей" in response.text


@pytest.mark.asyncio
async def test_static_css_accessible(client: AsyncClient):
    """Тест: статический файл style.css доступен."""
    response = await client.get("/static/style.css")

    assert response.status_code == 200
    assert "text/css" in response.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_static_js_accessible(client: AsyncClient):
    """Тест: статический файл app.js доступен."""
    response = await client.get("/static/app.js")

    assert response.status_code == 200
    assert "javascript" in response.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_api_info_endpoint(client: AsyncClient):
    """Тест: эндпоинт /api возвращает информацию о сервисе."""
    response = await client.get("/api")

    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert "version" in data
    assert "docs" in data
    assert "health" in data
