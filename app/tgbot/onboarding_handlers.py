"""Onboarding Telegram conversation handlers."""

from typing import Any

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.core.database import unit_of_work
from app.core.onboarding_questions import (
    ONBOARDING_QUESTIONS,
    OnboardingQuestion,
    QuestionType,
    get_next_question,
)
from app.models import BotKey
from app.services.onboarding_service import PROFILE_BOTS, finalize_onboarding, skip_onboarding
from app.tgbot.keyboards import (
    CB_ANS_PREFIX,
    CB_BEGIN,
    CB_MULTI_DONE,
    CB_SKIP,
    CB_TOGGLE_PREFIX,
    main_menu,
    onboarding_intro_keyboard,
    onboarding_question_keyboard,
)
from app.tgbot.messages import (
    BOT_ICONS,
    BOT_KEYS_TR,
    ONBOARDING_BOT_LINE,
    ONBOARDING_CANCELLED,
    ONBOARDING_CHOICE_HINT,
    ONBOARDING_COMPLETE_FOOTER,
    ONBOARDING_COMPLETE_HEADER,
    ONBOARDING_INTRO,
    ONBOARDING_INVALID_NUMBER,
    ONBOARDING_MULTI_HINT,
    ONBOARDING_PROFILE_LABELS,
    ONBOARDING_QUESTION,
    ONBOARDING_SKIPPED,
    ONBOARDING_STEP_GOAL_LINE,
    ONBOARDING_SUMMARY_HEADER,
)

ANSWER = 0

MIN_STEP_GOAL = 1000
MAX_STEP_GOAL = 100000


async def _ensure_user_id(context: ContextTypes.DEFAULT_TYPE, update: Update) -> int:
    user_data = context.user_data
    user_id = user_data.get("user_id") if user_data is not None else None
    if isinstance(user_id, int):
        return user_id
    from app.tgbot.callbacks import _ensure_user

    return await _ensure_user(context, update)


def _format_thousands(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _format_question(question: OnboardingQuestion, index: int, total: int) -> str:
    return ONBOARDING_QUESTION.format(index=index, total=total, text=question.text)


def _bots_to_enable(profile_type: str, flags: dict[str, bool]) -> list[BotKey]:
    bots = set(PROFILE_BOTS.get(profile_type, []))
    if flags.get("uses_supplements"):
        bots.add(BotKey.SUPPLEMENT)
    if flags.get("wants_steps"):
        bots.add(BotKey.STEP)
    if flags.get("wants_medication"):
        bots.add(BotKey.MEDICATION)
    if flags.get("wants_sport"):
        bots.add(BotKey.SPORT)
    return sorted(bots, key=lambda bot_key: BOT_KEYS_TR[bot_key])


def _completion_text(answers: dict[str, str], profile_type: str, flags: dict[str, bool]) -> str:
    profile_label = ONBOARDING_PROFILE_LABELS.get(profile_type, profile_type)
    lines = [ONBOARDING_COMPLETE_HEADER.format(profile_label=profile_label), ""]
    lines.append(ONBOARDING_SUMMARY_HEADER)
    for bot_key in _bots_to_enable(profile_type, flags):
        lines.append(ONBOARDING_BOT_LINE.format(icon=BOT_ICONS[bot_key], name=BOT_KEYS_TR[bot_key]))
    step_goal = answers.get("c4a_step_goal")
    if step_goal:
        try:
            goal = int(step_goal)
        except ValueError:
            goal = 0
        lines.append(ONBOARDING_STEP_GOAL_LINE.format(goal=_format_thousands(goal)))
    lines.append(ONBOARDING_COMPLETE_FOOTER)
    return "\n".join(lines)


async def onboarding_offer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_message is not None
    await update.effective_message.reply_text(
        ONBOARDING_INTRO, reply_markup=onboarding_intro_keyboard()
    )


async def _send_question(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    question: OnboardingQuestion,
    index: int,
) -> None:
    text = _format_question(question, index + 1, len(ONBOARDING_QUESTIONS))
    keyboard = onboarding_question_keyboard(question)
    if update.callback_query is not None:
        await update.callback_query.edit_message_text(text, reply_markup=keyboard)
        await update.callback_query.answer()
        return
    assert update.effective_message is not None
    await update.effective_message.reply_text(text, reply_markup=keyboard)


async def onboarding_begin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.callback_query is not None
    await _ensure_user_id(context, update)
    context.user_data["ob_index"] = 0  # type: ignore[index]
    context.user_data["ob_answers"] = {}  # type: ignore[index]
    context.user_data["ob_multi"] = set()  # type: ignore[index]
    await _send_question(update, context, ONBOARDING_QUESTIONS[0], 0)
    return ANSWER


async def onboarding_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.callback_query is not None
    user_id = await _ensure_user_id(context, update)
    async with unit_of_work() as session:
        await skip_onboarding(session, user_id)
    await update.callback_query.edit_message_text(ONBOARDING_SKIPPED)
    await update.callback_query.answer()
    return ConversationHandler.END


async def onboarding_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.callback_query is not None
    assert update.callback_query.data is not None
    option = update.callback_query.data.split(":", 3)[-1]
    return await _advance(update, context, option)


async def onboarding_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.callback_query is not None
    assert update.callback_query.data is not None
    option = update.callback_query.data.split(":", 3)[-1]
    multi = context.user_data["ob_multi"]  # type: ignore[index]
    if option in multi:
        multi.remove(option)
        await update.callback_query.answer(f"Kaldırıldı: {option}")
    else:
        multi.add(option)
        await update.callback_query.answer(f"Seçildi: {option}")
    return ANSWER


async def onboarding_multi_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.callback_query is not None
    multi = context.user_data["ob_multi"]  # type: ignore[index]
    if not multi:
        await update.callback_query.answer(ONBOARDING_MULTI_HINT)
        return ANSWER
    value = ",".join(sorted(multi))
    return await _advance(update, context, value)


async def onboarding_number_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    index = int(context.user_data["ob_index"])  # type: ignore[index]
    question = ONBOARDING_QUESTIONS[index]
    if question.question_type is not QuestionType.NUMBER_INPUT:
        await update.effective_message.reply_text(ONBOARDING_CHOICE_HINT)
        return ANSWER

    raw = (update.effective_message.text or "").strip()
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        await update.effective_message.reply_text(ONBOARDING_INVALID_NUMBER)
        return ANSWER
    value = int(digits)
    if not MIN_STEP_GOAL <= value <= MAX_STEP_GOAL:
        await update.effective_message.reply_text(ONBOARDING_INVALID_NUMBER)
        return ANSWER
    return await _advance(update, context, str(value))


async def _advance(update: Update, context: ContextTypes.DEFAULT_TYPE, value: str) -> int:
    index = int(context.user_data["ob_index"])  # type: ignore[index]
    question = ONBOARDING_QUESTIONS[index]
    answers = context.user_data["ob_answers"]  # type: ignore[index]
    answers[question.key] = value
    context.user_data["ob_multi"] = set()  # type: ignore[index]

    next_step = get_next_question(index, answers)
    if next_step is None:
        return await _finalize(update, context)

    next_index, next_question = next_step
    context.user_data["ob_index"] = next_index  # type: ignore[index]
    await _send_question(update, context, next_question, next_index)
    return ANSWER


async def _finalize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    user_id = await _ensure_user_id(context, update)
    answers = dict(context.user_data["ob_answers"])  # type: ignore[index]
    async with unit_of_work() as session:
        profile_type, flags = await finalize_onboarding(session, user_id, answers)
    await update.effective_message.reply_text(
        _completion_text(answers, profile_type, flags), reply_markup=main_menu()
    )
    return ConversationHandler.END


async def onboarding_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_message is not None
    await update.effective_message.reply_text(ONBOARDING_CANCELLED)
    return ConversationHandler.END


def onboarding_conversation() -> ConversationHandler[Any]:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(onboarding_begin, pattern=f"^{CB_BEGIN}$"),
            CallbackQueryHandler(onboarding_skip, pattern=f"^{CB_SKIP}$"),
        ],
        states={
            ANSWER: [
                CallbackQueryHandler(onboarding_answer, pattern=f"^{CB_ANS_PREFIX}"),
                CallbackQueryHandler(onboarding_toggle, pattern=f"^{CB_TOGGLE_PREFIX}"),
                CallbackQueryHandler(onboarding_multi_done, pattern=f"^{CB_MULTI_DONE}$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding_number_input),
            ],
        },
        fallbacks=[CommandHandler("iptal", onboarding_cancel)],
    )


__all__ = [
    "ANSWER",
    "onboarding_answer",
    "onboarding_begin",
    "onboarding_cancel",
    "onboarding_conversation",
    "onboarding_multi_done",
    "onboarding_number_input",
    "onboarding_offer",
    "onboarding_skip",
    "onboarding_toggle",
]
