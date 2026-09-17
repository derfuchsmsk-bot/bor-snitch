import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from src.main import app
from src.services.tts_service import TTSService
from src.services.voice_digest_service import VoiceDigestService
from src.utils.game_config import config
from src.admin.auth import create_admin_token

client = TestClient(app)


def test_clean_text_for_speech():
    raw = "Привет, **@derfuchz**! Смотри сюда: https://example.com/link `код` и _курсив_."
    cleaned = TTSService.clean_text_for_speech(raw)
    assert "@" not in cleaned
    assert "https://" not in cleaned
    assert "*" not in cleaned
    assert "`" not in cleaned
    assert "_" not in cleaned
    assert "Привет, derfuchz! Смотри сюда: код и курсив." in cleaned


@pytest.mark.anyio
async def test_tts_synthesize_mocked():
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.audio_content = b"OggS_fake_audio_bytes_123"
    mock_client.synthesize_speech = AsyncMock(return_value=mock_resp)

    with patch.object(TTSService, "_get_client", return_value=mock_client):
        audio = await TTSService.synthesize_voice_ogg("Добрый день, граждане подсудимые.")
        assert audio == b"OggS_fake_audio_bytes_123"
        assert mock_client.synthesize_speech.called


@pytest.mark.anyio
async def test_voice_digest_creation_and_send():
    mock_gemini_resp = MagicMock()
    mock_gemini_resp.text = "В эфире выпуск криминальной хроники Сайонары. Сегодня день прошел тихо."

    mock_bot = MagicMock()
    mock_bot.send_voice = AsyncMock()

    with patch("src.services.voice_digest_service.GenerativeModel") as mock_model_cls, \
         patch.object(TTSService, "synthesize_voice_ogg", new_callable=AsyncMock) as mock_tts, \
         patch("src.services.voice_digest_service.message_repository.get_logs_for_time_range", new_callable=AsyncMock) as mock_logs, \
         patch("src.services.voice_digest_service.agreement_repository.get_active_agreements", new_callable=AsyncMock) as mock_ag, \
         patch("src.services.voice_digest_service.user_repository.get_points_ledger", new_callable=AsyncMock) as mock_ledger, \
         patch("src.services.voice_digest_service.LoreService.get_lore_as_json", new_callable=AsyncMock) as mock_lore:

        mock_logs.return_value = [{"username": "user1", "text": "hello"}]
        mock_ag.return_value = []
        mock_ledger.return_value = []
        mock_lore.return_value = "{}"

        mock_instance = MagicMock()
        mock_instance.generate_content_async = AsyncMock(return_value=mock_gemini_resp)
        mock_model_cls.return_value = mock_instance
        mock_tts.return_value = b"FAKE_OGG_BYTES"

        result = await VoiceDigestService.create_and_send_voice_digest(
            chat_id=123456,
            edition_type="Дневной выпуск (14:00)",
            bot=mock_bot,
            send_to_telegram=True
        )

        assert result["status"] == "success"
        assert "криминальной хроники" in result["script"]
        assert mock_bot.send_voice.called
        assert mock_bot.send_voice.call_args[1]["chat_id"] == 123456


@pytest.mark.anyio
async def test_voice_digest_api_endpoint():
    token = create_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    with patch.object(VoiceDigestService, "create_and_send_voice_digest", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = {
            "status": "success",
            "chat_id": 123456,
            "script": "Тестовый выпуск.",
            "audio_bytes_length": 500
        }

        resp = client.post(
            "/api/admin/actions/voice_digest",
            json={"chat_id": "123456", "edition_type": "Дневной выпуск (14:00)", "send_telegram": False},
            headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert resp.json()["result"]["script"] == "Тестовый выпуск."
