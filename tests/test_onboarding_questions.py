"""Onboarding question definition tests."""

from app.core.onboarding_questions import (
    ONBOARDING_QUESTIONS,
    QuestionType,
    get_next_question,
)


def test_twenty_questions_defined() -> None:
    assert len(ONBOARDING_QUESTIONS) == 20


def test_all_keys_unique() -> None:
    keys = [q.key for q in ONBOARDING_QUESTIONS]
    assert len(keys) == len(set(keys))


def test_c4a_conditional_on_wants_steps() -> None:
    c4a = next(q for q in ONBOARDING_QUESTIONS if q.key == "c4a_step_goal")
    assert c4a.condition is not None
    assert c4a.condition({"c4_wants_steps": "Evet"}) is True
    assert c4a.condition({"c4_wants_steps": "Hayır"}) is False


def test_next_question_skips_c4a_when_no_steps() -> None:
    result = get_next_question(13, {"c4_wants_steps": "Hayır"})
    assert result is not None
    _, question = result
    assert question.key == "d1_supplements"


def test_next_question_shows_c4a_when_steps_wanted() -> None:
    result = get_next_question(13, {"c4_wants_steps": "Evet"})
    assert result is not None
    _, question = result
    assert question.key == "c4a_step_goal"


def test_number_input_only_c4a() -> None:
    number_inputs = [
        q for q in ONBOARDING_QUESTIONS if q.question_type is QuestionType.NUMBER_INPUT
    ]
    assert [q.key for q in number_inputs] == ["c4a_step_goal"]
