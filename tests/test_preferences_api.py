import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_preferences_api(api_client: AsyncClient, api_key_headers: dict[str, str]) -> None:
    # List preferences
    res = await api_client.get("/api/preferences", headers=api_key_headers)
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) > 0

    # Toggle preference (using medication_bot)
    res = await api_client.patch(
        "/api/preferences/medication_bot",
        json={"enabled": True},
        headers=api_key_headers,
    )
    assert res.status_code == 200
    assert res.json()["enabled"] is True

    # Disable preference
    res = await api_client.patch(
        "/api/preferences/medication_bot",
        json={"enabled": False},
        headers=api_key_headers,
    )
    assert res.status_code == 200
    assert res.json()["enabled"] is False
