"""
Тесты для проксируемой документации (Swagger/ReDoc) за nginx reverse proxy.

Встроенные /docs и /redoc зашивают абсолютный openapi_url="/openapi.json",
который за nginx (срезающим префикс /free-ai-selector/) браузер тянет из корня
-> 404. Кастомные роуты используют ОТНОСИТЕЛЬНЫЙ openapi_url, который браузер
резолвит относительно текущего пути и попадает в правильный prefix.
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
async def test_swagger_docs_use_relative_openapi_url(client: AsyncClient):
    """Swagger UI отдаётся с относительным openapi_url (без ведущего '/')."""
    response = await client.get("/docs")

    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    # Относительный путь работает за прокси; абсолютный — ломается (404).
    assert "url: 'openapi.json'" in response.text
    assert "url: '/openapi.json'" not in response.text


@pytest.mark.asyncio
async def test_redoc_uses_relative_openapi_url(client: AsyncClient):
    """ReDoc отдаётся с относительным spec-url (без ведущего '/')."""
    response = await client.get("/redoc")

    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert 'spec-url="openapi.json"' in response.text
    assert 'spec-url="/openapi.json"' not in response.text


@pytest.mark.asyncio
async def test_openapi_json_served_at_root(client: AsyncClient):
    """Спецификация доступна по /openapi.json (точка, куда резолвится относит. путь)."""
    response = await client.get("/openapi.json")

    assert response.status_code == 200
    data = response.json()
    assert "openapi" in data
    assert data["info"]["title"] == "Free AI Selector - Business API"
