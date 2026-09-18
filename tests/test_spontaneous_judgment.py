import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import json
from src.services.chat_service import ChatService
from src.models.ai import CynicalCommentResult
from src.models.points import PointEvent
from src.utils.game_config import config


class TestSpontaneousJudgment(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        ChatService._last_comment_time = {}
        ChatService._last_user_comment_time = {}
        ChatService._last_reaction_time = {}
        ChatService._last_spontaneous_judgment_time = {}

    @patch("src.services.chat_service.db.user_repository.get_chat_users")
    @patch("src.services.chat_service.LoreService.get_lore")
    async def test_resolve_user_via_context_and_lore(self, mock_lore, mock_users):
        mock_users.return_value = ([
            {"user_id": "991728230", "username": "ioann_thegreat", "full_name": "Ваня Любецкий"}
        ], None)
        mock_lore.return_value = {
            "core": {
                "characters": [
                    {"id": "991728230", "handle": "ioann_thegreat", "names": ["Мастецкий", "Ваня Любецкий"]}
                ]
            }
        }

        # Match by context username
        uid, name = await ChatService.resolve_user(-1001, "elisei", [{"user_id": 111, "username": "elisei"}])
        self.assertEqual(uid, 111)

        # Match by lore nickname (Мастецкий)
        uid, name = await ChatService.resolve_user(-1001, "Мастецкий", [])
        self.assertEqual(uid, 991728230)
        self.assertIn("ioann_thegreat", name)

    @patch("src.services.chat_service.db")
    @patch("src.services.chat_service.ai")
    async def test_process_cynical_comment_spontaneous_penalty(self, mock_ai, mock_db):
        mock_msg = MagicMock()
        mock_msg.chat.id = -100123
        mock_msg.from_user.id = 555
        mock_msg.from_user.username = "elisei"
        mock_msg.message_id = 42
        mock_msg.date = datetime.now(timezone.utc)
        mock_msg.text = "@snitch_sayonara_bot как тебе такие мувы от Мастецкого?"
        mock_msg.reply_to_message = None

        mock_bot = MagicMock()
        mock_bot.id = 999
        mock_bot.username = "snitch_sayonara_bot"
        mock_msg.bot.get_me = AsyncMock(return_value=mock_bot)

        mock_db.get_user_stats = AsyncMock(return_value={"total_points": 10})
        mock_db.get_recent_messages = AsyncMock(return_value=[
            {"user_id": 991728230, "username": "ioann_thegreat", "first_name": "Ваня", "text": "Я минус"}
        ])
        mock_db.user_repository.get_chat_users = AsyncMock(return_value=([], None))
        mock_db.user_repository.apply_point_event_transactional = AsyncMock(return_value={"applied": True})

        mock_ai.generate_cynical_comment = AsyncMock(return_value=CynicalCommentResult(
            comment="Классика: на словах готов рвать, а по факту слился.",
            award_points=True,
            target_username="ioann_thegreat",
            points_delta=50,
            reason="Слив с договоренности (масть)"
        ))

        reply = await ChatService.process_cynical_comment(mock_msg, mock_msg.text)

        self.assertIsNotNone(reply)
        self.assertIn("Классика: на словах готов рвать", reply)
        self.assertIn("Вердикт Смотрящего: +50 pts @ioann_thegreat", reply)
        self.assertIn("Слив с договоренности (масть)", reply)

        # Verify point event was applied
        mock_db.user_repository.apply_point_event_transactional.assert_called_once()
        call_event = mock_db.user_repository.apply_point_event_transactional.call_args[0][1]
        self.assertEqual(call_event.points_delta, 50)
        self.assertEqual(call_event.user_id, "991728230")
        self.assertEqual(call_event.event_type, "spontaneous_verdict")

    @patch("src.services.chat_service.db")
    @patch("src.services.chat_service.ai")
    async def test_process_cynical_comment_no_points_when_award_false(self, mock_ai, mock_db):
        mock_msg = MagicMock()
        mock_msg.chat.id = -100123
        mock_msg.from_user.id = 555
        mock_msg.from_user.username = "elisei"
        mock_msg.message_id = 43
        mock_msg.date = datetime.now(timezone.utc)
        mock_msg.text = "@snitch_sayonara_bot привет"
        mock_msg.reply_to_message = None

        mock_bot = MagicMock()
        mock_bot.id = 999
        mock_bot.username = "snitch_sayonara_bot"
        mock_msg.bot.get_me = AsyncMock(return_value=mock_bot)

        mock_db.get_user_stats = AsyncMock(return_value={"total_points": 10})
        mock_db.get_recent_messages = AsyncMock(return_value=[])

        mock_ai.generate_cynical_comment = AsyncMock(return_value=CynicalCommentResult(
            comment="Здорово, коль не шутишь.",
            award_points=False
        ))

        reply = await ChatService.process_cynical_comment(mock_msg, mock_msg.text)

        self.assertEqual(reply, "Здорово, коль не шутишь.")
        mock_db.user_repository.apply_point_event_transactional.assert_not_called()


if __name__ == "__main__":
    unittest.main()
