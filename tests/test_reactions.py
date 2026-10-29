import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from src.utils.game_config import config
from src.services.chat_service import ChatService


def test_should_react_disabled():
    config.REACTIONS_ENABLED = False
    should, emoji = ChatService.should_react(12345, "я так устал от всего", {})
    assert should is False
    assert emoji == ""
    config.REACTIONS_ENABLED = True


def test_should_react_triggers():
    ChatService._last_reaction_time.clear()
    config.REACTIONS_ENABLED = True
    config.REACTION_CHANCE = 1.0  # 100% chance for test
    config.REACTION_COOLDOWN_SECONDS = 0

    # Whining trigger
    should, emoji = ChatService.should_react(12345, "Ой, я так устал, все плохо и тяжело", {})
    assert should is True
    assert emoji == "🤡"

    # Drama / snitching trigger
    should, emoji = ChatService.should_react(12345, "Он крыса и предатель, это донос", {})
    assert should is True
    assert emoji in ["🍿", "👀"]

    # Sigma / agreement trigger
    should, emoji = ChatService.should_react(12345, "По рукам, договорились пацаны", {})
    assert should is True
    assert emoji in ["🗿", "👑"]

    # High points sinner
    should, emoji = ChatService.should_react(12345, "Обычный текст ни о чем", {"total_points": 500})
    assert should is True
    assert emoji in ["🚽", "🤡"]


def test_reaction_cooldown():
    config.REACTIONS_ENABLED = True
    config.REACTION_CHANCE = 1.0
    config.REACTION_COOLDOWN_SECONDS = 300
    ChatService._last_reaction_time[999] = datetime.now()

    should, _ = ChatService.should_react(999, "кринж и нытье", {})
    assert should is False


@pytest.mark.anyio
async def test_process_reaction_success():
    config.REACTIONS_ENABLED = True
    config.REACTION_CHANCE = 1.0
    config.REACTION_COOLDOWN_SECONDS = 0
    ChatService._last_reaction_time.clear()

    mock_msg = MagicMock()
    mock_msg.chat.id = 8888
    mock_msg.message_id = 101
    mock_msg.from_user.id = 777
    mock_msg.from_user.is_bot = False
    mock_msg.react = AsyncMock()

    with patch("src.services.chat_service.db.get_user_stats", new_callable=AsyncMock) as mock_stats:
        mock_stats.return_value = {"total_points": 0}
        reacted = await ChatService.process_reaction(mock_msg, "жесть какой кринж")
        assert reacted is True
        assert mock_msg.react.called
        call_args = mock_msg.react.call_args[1]["reaction"]
        assert len(call_args) == 1
        assert call_args[0].emoji == "🤡"
