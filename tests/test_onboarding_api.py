import pytest
from httpx import AsyncClient

CHOICES = {
    "a1_gender": "Kadın",
    "a2_age": "26-35",
    "a3_height": "160-175 cm",
    "a4_weight": "60-80 kg",
    "a5_work": "Masa başı",
    "b1_chronic": "Hayır",
    "b2_medication": "Hayır",
    "b3_doctor": "Hayır",
    "b4_sleep": "Düzenli",
    "b5_stress": "Orta",
    "c1_sport_freq": "Haftada 3+",
    "c2_sport_type": "Koşu-Yürüyüş",
    "c3_steps_avg": "7.000-10.000",
    "c4_wants_steps": "Evet",
    "c4a_step_goal": "8000",
    "d1_supplements": "Evet",
    "d2_nutrition": "Düzenli",
    "d3_water": "2-3 litre",
    "e1_goals": "Rutin takibi,Adım",
    "e2_reminder_freq": "Günde 1-2",
}


@pytest.mark.asyncio
async def test_onboarding_status_initial(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    res = await api_client.get("/api/onboarding", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["completed"] is False
    assert data["skipped"] is False
    assert data["question"]["index"] == 0
    assert data["question"]["key"] == "a1_gender"
    assert data["question"]["total"] == 20


@pytest.mark.asyncio
async def test_onboarding_full_flow(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    answered = 0
    done = False
    result = None

    res = await api_client.get("/api/onboarding", headers=auth_headers)
    question = res.json()["question"]

    while question is not None:
        key = question["key"]
        if question["question_type"] == "multi":
            value = CHOICES[key]
        elif question["question_type"] == "number":
            value = CHOICES[key]
        else:
            value = CHOICES.get(key, question["options"][0])
        res = await api_client.post(
            "/api/onboarding/answer",
            json={"question_key": key, "answer_value": value},
            headers=auth_headers,
        )
        assert res.status_code == 200, res.text
        body = res.json()
        answered += 1
        done = body["done"]
        question = body["next"]
        if body["result"] is not None:
            result = body["result"]
        if not done:
            assert question is not None

    assert done is True
    assert answered == 20
    assert result is not None
    assert result["profile_type"] == "athlete"
    assert "sport_bot" in result["enabled_bots"]
    assert "supplement_bot" in result["enabled_bots"]
    assert result["step_goal"] == 8000

    res = await api_client.get("/api/onboarding", headers=auth_headers)
    data = res.json()
    assert data["completed"] is True
    assert data["question"] is None
    assert data["answers"]["a1_gender"] == "Kadın"

    res = await api_client.get("/api/preferences", headers=auth_headers)
    prefs = {p["bot_key"]: p["enabled"] for p in res.json()}
    assert prefs["sport_bot"] is True
    assert prefs["supplement_bot"] is True


@pytest.mark.asyncio
async def test_onboarding_skip(api_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    res = await api_client.post("/api/onboarding/skip", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["skipped"] is True

    res = await api_client.get("/api/onboarding", headers=auth_headers)
    data = res.json()
    assert data["skipped"] is True
    assert data["question"] is None


@pytest.mark.asyncio
async def test_onboarding_invalid_input(
    api_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    res = await api_client.post(
        "/api/onboarding/answer",
        json={"question_key": "nope", "answer_value": "x"},
        headers=auth_headers,
    )
    assert res.status_code == 400

    res = await api_client.post(
        "/api/onboarding/answer",
        json={"question_key": "c4a_step_goal", "answer_value": "abc"},
        headers=auth_headers,
    )
    assert res.status_code == 422

    res = await api_client.post(
        "/api/onboarding/answer",
        json={"question_key": "c4a_step_goal", "answer_value": "500"},
        headers=auth_headers,
    )
    assert res.status_code == 422
