import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import time

from src.services.voice_chat_service import (
    VoiceChatService,
    KIZARU_GREETINGS,
    KIZARU_INACTIVITY_EXITS,
    KIZARU_LEAVE_EXITS
)
from src.utils.game_config import config


def test_kizaru_phrases_content():
    assert len(KIZARU_GREETINGS) >= 3
    assert any("Барселоны" in g or "Вассап" in g for g in KIZARU_GREETINGS)
    assert any("бамбук" in e for e in KIZARU_INACTIVITY_EXITS)
    assert any("бассейна" in l or "очки" in l for l in KIZARU_LEAVE_EXITS)


@pytest.mark.anyio
async def test_voice_chat_join_and_leave():
    chat_id = 999111
    config.VOICE_CHAT_ENABLED = True
    config.BOT_DISABLED = False

    with patch.object(VoiceChatService, "play_phrase_in_call", new_callable=AsyncMock) as mock_play, \
         patch.object(VoiceChatService, "ensure_started", new_callable=AsyncMock) as mock_start:

        mock_pytgcalls = MagicMock()
        mock_pytgcalls.leave_call = AsyncMock()
        VoiceChatService._pytgcalls = mock_pytgcalls
        VoiceChatService._is_running = True

        # Test join
        greeting = await VoiceChatService.join_voice_chat(chat_id)
        assert greeting in KIZARU_GREETINGS
        assert mock_play.called
        assert chat_id in VoiceChatService._active_calls

        # Test record activity
        old_time = VoiceChatService._last_activity.get(chat_id)
        time.sleep(0.01)
        VoiceChatService.record_activity(chat_id)
        assert VoiceChatService._last_activity.get(chat_id) > old_time

        # Test leave
        leave_phrase = await VoiceChatService.leave_voice_chat(chat_id, reason="manual")
        assert leave_phrase in KIZARU_LEAVE_EXITS
        assert mock_pytgcalls.leave_call.called
        assert chat_id not in VoiceChatService._active_calls
