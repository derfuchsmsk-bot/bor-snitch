from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.prompt_service import PromptService
from src.services.chat_service import ChatService
from src.services.report_service import ReportService
from src.services.mood_service import MoodService
from src.models.ai import CynicalCommentResult, ReportValidationResult
from src.utils.game_config import config
from src.utils import messages
from src.utils.tone import FRIENDLY_POLICY


@pytest.fixture(autouse=True)
def restore_state():
    previous = config.to_dict()
    config.reset_to_defaults()
    yield
    config.update_from_dict(previous)


@pytest.mark.parametrize("key,render", [
    ("system_prompt", lambda: PromptService.format_system_prompt("{}", "", "", "старое правило")),
    ("cynical_comment_prompt", lambda: PromptService.format_cynical_comment_prompt("{}", lessons=["старое правило"])),
    ("report_validation_prompt", lambda: PromptService.format_report_validation_prompt(lessons=["старое правило"])),
    ("voice_digest_prompt", lambda: PromptService.format_voice_digest_prompt("Вечер")),
    ("scheduled_thought_prompt", lambda: PromptService.format_scheduled_thought_prompt()),
    ("memory_summarization_prompt", lambda: PromptService.format_memory_summarization_prompt()),
    ("feedback_analysis_prompt", lambda: PromptService.format_feedback_analysis_prompt()),
])
def test_friendly_policy_applies_after_legacy_saved_templates_and_lessons(monkeypatch, key, render):
    monkeypatch.setattr(PromptService, "_prompts", {key: "Старый резкий шаблон {lessons_str}"})
    result = render()
    assert result.endswith(FRIENDLY_POLICY)
    # Editing/reading CMS templates does not inject or repeatedly save the policy.
    assert "<friendly_policy>" not in PromptService.get_template(key)


def test_system_prompt_substitutes_current_values_and_agreement_switch(monkeypatch):
    monkeypatch.setattr(PromptService, "_prompts", {})
    config.POINTS_TOXICITY = 37
    config.ENABLE_AGREEMENTS = False
    result = PromptService.format_system_prompt("{}", "", "", "")
    assert "37 очков" in result
    assert "Учёт договорённостей отключён" in result
    assert "{points_toxicity}" not in result
    assert "{agreements_policy}" not in result


def test_old_reaction_palette_cannot_enable_mockery(monkeypatch):
    ChatService._last_reaction_time.clear()
    config.REACTION_CHANCE = 1
    config.REACTION_ALLOWED_EMOJIS = ["🤡", "🚽", "🍿"]
    assert ChatService.should_react(1, "Устал, тяжело", {"total_points": 999}) == (False, "")
    config.REACTION_ALLOWED_EMOJIS += ["❤"]
    assert ChatService.should_react(1, "Устал, тяжело", {"total_points": 999}) == (True, "❤")


def test_old_score_does_not_increase_reaction_chance(monkeypatch):
    ChatService._last_reaction_time.clear()
    config.REACTION_CHANCE = 0
    monkeypatch.setattr("src.services.chat_service.random.random", lambda: 0.03)
    assert ChatService.should_react(1, "Обычное сообщение", {"total_points": 0}) == (False, "")
    assert ChatService.should_react(1, "Обычное сообщение", {"total_points": 1000}) == (False, "")


def test_old_score_does_not_increase_comment_chance(monkeypatch):
    config.CYNICAL_COMMENT_CHANCE = 0
    monkeypatch.setattr("src.services.chat_service.random.random", lambda: 0.03)
    assert ChatService.should_comment("Обычное сообщение", {"total_points": 0}) is False
    assert ChatService.should_comment("Обычное сообщение", {"total_points": 1000}) is False


@pytest.mark.asyncio
async def test_afk_does_not_read_or_penalize_users_by_default(monkeypatch):
    from src.services import db
    fake_db = MagicMock()
    monkeypatch.setattr(db, "db", fake_db)
    assert await db.check_afk_users(1) == []
    fake_db.collection.assert_not_called()


def example_message():
    message = MagicMock()
    message.chat.id = 123
    message.from_user.id = 1
    message.from_user.username = "alice"
    message.message_id = 10
    message.text = "@snitch_bot привет"
    message.reply_to_message = None
    message.bot.get_me = AsyncMock(return_value=SimpleNamespace(id=999, username="snitch_bot"))
    return message


@pytest.mark.asyncio
async def test_legacy_spontaneous_judgment_flag_cannot_enable_penalties(monkeypatch):
    from src.services import chat_service
    fake_db = MagicMock()
    fake_db.get_user_stats = AsyncMock(return_value={})
    fake_db.get_recent_messages = AsyncMock(return_value=[])
    monkeypatch.setattr(chat_service, "db", fake_db)
    monkeypatch.setattr(chat_service.ai, "generate_cynical_comment", AsyncMock(return_value=CynicalCommentResult(
        comment="Давайте спокойно разберёмся.", award_points=True, target_username="alice", points_delta=50,
    )))
    config.SPONTANEOUS_JUDGMENT_ENABLED = True
    message = example_message()
    assert await ChatService.process_cynical_comment(message, message.text) == "Давайте спокойно разберёмся."
    fake_db.user_repository.apply_point_event_transactional.assert_not_called()
    fake_db.message_repository.mark_message_reported.assert_not_called()


@pytest.mark.parametrize("enabled,status", [(False, "rejected"), (False, "insufficient_data"), (True, "insufficient_data")])
@pytest.mark.asyncio
async def test_rejected_or_uncertain_report_is_not_automatically_a_false_report(monkeypatch, enabled, status):
    from src.services import report_service
    fake_db = MagicMock()
    fake_db.message_repository.get_message = AsyncMock(return_value=None)
    fake_db.get_recent_messages = AsyncMock(return_value=[])
    fake_db.get_subsequent_messages = AsyncMock(return_value=[])
    monkeypatch.setattr(report_service, "db", fake_db)
    monkeypatch.setattr(report_service.ai, "validate_report", AsyncMock(return_value=ReportValidationResult(
        valid=False, status=status, reason="Недостаточно контекста",
    )))
    config.FALSE_REPORT_PENALTIES_ENABLED = enabled
    reply, accepted = await ReportService.process_report(example_message(), example_message(), "текст")
    assert accepted is False
    assert "Недостаточно контекста" in reply
    assert "клоун" not in reply
    fake_db.increment_false_report_count.assert_not_called()
    fake_db.user_repository.apply_point_event_transactional.assert_not_called()


@pytest.mark.asyncio
async def test_legacy_rank_is_recomputed_without_rewriting_user_data(monkeypatch):
    from src.repositories.user_repository import UserRepository
    repo = UserRepository()
    ref = MagicMock()
    ref.get = AsyncMock(return_value=SimpleNamespace(
        exists=True, to_dict=lambda: {"total_points": 550, "current_rank": "Старое унизительное звание"},
    ))
    monkeypatch.setattr(repo, "_get_user_ref", lambda *args: ref)
    result = await repo.get_user_stats(1, 2)
    assert result["current_rank"] == "Уровень 3 ☕"
    assert result["total_points"] == 550
    ref.set.assert_not_called()


def test_rules_reflect_live_settings_and_default_to_non_punitive():
    assert "Автоматические штрафы в диалоге: отключены" in messages.get_rules_text()
    config.POINTS_TOXICITY = 42
    config.ENABLE_AFK_PENALTIES = True
    config.POINTS_AFK_BASE = 12
    result = messages.get_rules_text()
    assert "42 игровых очков" in result
    assert "Штрафы за молчание: 12 очков" in result


def test_monday_mood_is_supportive():
    mood = MoodService.get_current_mood(datetime(2026, 10, 26, 12, tzinfo=timezone(timedelta(hours=3))))
    assert "поддержка" in mood.title.lower()
    assert "Не высмеивай усталость" in mood.tone_instruction
    assert mood.cynicism_multiplier <= 1
