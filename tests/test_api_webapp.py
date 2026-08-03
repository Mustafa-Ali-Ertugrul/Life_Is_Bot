"""Telegram Mini App (WebApp) static serving tests."""

from httpx import AsyncClient


async def test_webapp_index_served(api_client: AsyncClient) -> None:
    response = await api_client.get("/webapp/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "telegram-web-app.js" in response.text
    assert "Rutinbot" in response.text


async def test_webapp_root_redirects_to_slash(api_client: AsyncClient) -> None:
    response = await api_client.get("/webapp")

    assert response.status_code == 307
    assert response.headers["location"].endswith("/webapp/")


async def test_webapp_served_without_auth(api_client: AsyncClient) -> None:
    response = await api_client.get("/webapp/")

    assert response.status_code == 200
    assert "/api/habits" in response.text
    assert "/api/reports/streak" in response.text
