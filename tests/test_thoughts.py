import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.thought_service import ThoughtService
from src.utils.game_config import config
from src.utils.config import settings
from src.main import scheduled_thought, sync_thoughts_jobs, scheduler


@pytest.mark.anyio
async def test_generate_thought_text():
    mock_candidate = MagicMock()
    mock_part = MagicMock()
    mock_part.text = "«Сегодня в хате все тихо, двигайтесь по-людски.»"
    mock_part.thought = False
    mock_candidate.content.parts = [mock_part]
    mock_resp = MagicMock()
    mock_resp.candidates = [mock_candidate]
    mock_resp.text = "«Сегодня в хате все тихо, двигайтесь по-людски.»"

    with patch("src.services.thought_service.LoreService.get_lore_as_json", new_callable=AsyncMock) as mock_lore, \
         patch("src.services.thought_service.thought_repository.get_recent_thoughts", new_callable=AsyncMock) as mock_recent, \
         patch("src.services.thought_service.thought_repository.save_thought", new_callable=AsyncMock) as mock_save, \
         patch("src.services.thought_service.GenerativeModel.generate_content_async", new_callable=AsyncMock) as mock_gen:

        mock_lore.return_value = '{"characters": []}'
        mock_recent.return_value = ["Старая мысль про занос"]
        mock_gen.return_value = mock_resp

        thought = await ThoughtService.generate_thought_text("-100123")
        assert "двигайтесь по-людски" in thought
        assert "— Снитч-бот" in thought
        assert "«" not in thought
        assert "»" not in thought
        mock_save.assert_called_once()


@pytest.mark.anyio
async def test_generate_thought_truncation_cleanup():
    # If model cut off trailing sentence, verify it trims to last complete sentence
    mock_candidate = MagicMock()
    mock_part = MagicMock()
    mock_part.text = "В хате все спокойно. Но Паштет опять пытается"
    mock_part.thought = False
    mock_candidate.content.parts = [mock_part]
    mock_resp = MagicMock()
    mock_resp.candidates = [mock_candidate]
    mock_resp.text = "В хате все спокойно. Но Паштет опять пытается"

    with patch("src.services.thought_service.LoreService.get_lore_as_json", new_callable=AsyncMock), \
         patch("src.services.thought_service.thought_repository.get_recent_thoughts", new_callable=AsyncMock) as mock_recent, \
         patch("src.services.thought_service.thought_repository.save_thought", new_callable=AsyncMock), \
         patch("src.services.thought_service.GenerativeModel.generate_content_async", new_callable=AsyncMock) as mock_gen:

        mock_recent.return_value = []
        mock_gen.return_value = mock_resp
        thought = await ThoughtService.generate_thought_text("-100123")
        assert "В хате все спокойно." in thought
        assert "— Снитч-бот" in thought
        assert "Но Паштет опять пытается" not in thought



@pytest.mark.anyio
async def test_create_and_send_thought_success():
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    with patch.object(ThoughtService, "generate_thought_text", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "Базар фильтруйте, братья."

        res = await ThoughtService.create_and_send_thought(
            source_chat_id="-100123",
            target_chat_id="@sayonarasquad",
            bot=mock_bot
        )
        assert res["status"] == "success"
        assert res["text"] == "Базар фильтруйте, братья."
        assert res["target_chat_id"] == "@sayonarasquad"
        mock_bot.send_message.assert_called_once_with(
            chat_id="@sayonarasquad",
            text="Базар фильтруйте, братья."
        )


@pytest.mark.anyio
async def test_create_and_send_thought_disabled():
    with patch.object(config, "THOUGHTS_ENABLED", False):
        res = await ThoughtService.create_and_send_thought(
            source_chat_id="-100123",
            target_chat_id="@sayonarasquad"
        )
        assert res["status"] == "skipped"


@pytest.mark.anyio
async def test_scheduled_thought_execution():
    with patch("src.services.thought_service.ThoughtService.create_and_send_thought", new_callable=AsyncMock) as mock_send, \
         patch.object(settings, "CHANNEL_ID", "@sayonarasquad"):
        await scheduled_thought()
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args.kwargs
        assert call_kwargs["target_chat_id"] == "@sayonarasquad"


def test_sync_thoughts_jobs():
    sync_thoughts_jobs()
    for i in range(1, 6):
        job = scheduler.get_job(f"thought_{i}")
        assert job is not None
