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

        # Match by Russian inflected name ("Сене" -> "Сеня" / "Паштет")
        mock_lore.return_value = {
            "core": {
                "characters": [
                    {"id": "383998331", "handle": "arsinov", "names": ["Паштет", "Сеня"]}
                ]
            }
        }
        mock_users.return_value = ([
            {"user_id": "383998331", "username": "arsinov", "full_name": "Паштет 🍷 воздух"}
        ], None)
        uid, name = await ChatService.resolve_user(-1001, "Сене", [])
        self.assertEqual(uid, 383998331)

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
            {"message_id": 101, "user_id": 991728230, "username": "ioann_thegreat", "first_name": "Ваня", "text": "Я минус"}
        ])
        mock_db.user_repository.get_chat_users = AsyncMock(return_value=([], None))
        mock_db.user_repository.apply_point_event_transactional = AsyncMock(return_value={"applied": True})
        mock_db.message_repository.get_message = AsyncMock(return_value=None)
        mock_db.message_repository.mark_message_reported = AsyncMock()

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

        # Verify message was flagged in message_repository so /report and daily analysis will not double-score
        mock_db.message_repository.mark_message_reported.assert_called_once()

    @patch("src.services.chat_service.db")
    @patch("src.services.chat_service.ai")
    async def test_process_cynical_comment_deduplicates_if_already_scored(self, mock_ai, mock_db):
        mock_msg = MagicMock()
        mock_msg.chat.id = -100123
        mock_msg.from_user.id = 555
        mock_msg.from_user.username = "elisei"
        mock_msg.message_id = 45
        mock_msg.date = datetime.now(timezone.utc)
        mock_msg.text = "@snitch_sayonara_bot как тебе такие мувы от Мастецкого?"
        mock_msg.reply_to_message = None

        mock_bot = MagicMock()
        mock_bot.id = 999
        mock_bot.username = "snitch_sayonara_bot"
        mock_msg.bot.get_me = AsyncMock(return_value=mock_bot)

        mock_db.get_user_stats = AsyncMock(return_value={"total_points": 10})
        mock_db.get_recent_messages = AsyncMock(return_value=[
            {"message_id": 101, "user_id": 991728230, "username": "ioann_thegreat", "text": "Я минус"}
        ])
        mock_db.user_repository.get_chat_users = AsyncMock(return_value=([], None))

        # Simulate that message 101 was ALREADY scored
        mock_db.message_repository.get_message = AsyncMock(return_value={
            "is_reported": True,
            "points_awarded": 50
        })

        mock_ai.generate_cynical_comment = AsyncMock(return_value=CynicalCommentResult(
            comment="Классика, он всегда так делает.",
            award_points=True,
            target_username="ioann_thegreat",
            points_delta=50,
            reason="Слив с планов"
        ))

        reply = await ChatService.process_cynical_comment(mock_msg, mock_msg.text)

        # Should return only comment text WITHOUT awarding points again
        self.assertEqual(reply, "Классика, он всегда так делает.")
        mock_db.user_repository.apply_point_event_transactional.assert_not_called()
        mock_db.message_repository.mark_message_reported.assert_not_called()

    @patch("src.services.report_service.db")
    async def test_subsequent_report_is_blocked_after_spontaneous_judgment(self, mock_report_db):
        from src.services.report_service import ReportService
        from src.utils import messages

        # Message already marked by spontaneous judgment
        mock_report_db.message_repository.get_message = AsyncMock(return_value={
            "is_reported": True,
            "points_awarded": 50,
            "report_reason": "Спонтанный вердикт: Слив с договоренности"
        })

        mock_msg = MagicMock()
        mock_msg.chat.id = -100123
        mock_msg.from_user.id = 555
        mock_msg.text = "/report"

        mock_reported_msg = MagicMock()
        mock_reported_msg.message_id = 101
        mock_reported_msg.from_user.id = 991728230

        reply, success = await ReportService.process_report(mock_msg, mock_reported_msg, "Я минус")

        self.assertFalse(success)
        self.assertEqual(reply, messages.REPORT_ALREADY_PROCESSED)

    @patch("src.services.chat_service.db")
    @patch("src.services.chat_service.ai")
    @patch("src.services.chat_service.LoreService.get_lore")
    async def test_process_cynical_comment_spontaneous_reward_deduction(self, mock_lore, mock_ai, mock_db):
        mock_msg = MagicMock()
        mock_msg.chat.id = -100123
        mock_msg.from_user.id = 555
        mock_msg.from_user.username = "elisei"
        mock_msg.message_id = 99
        mock_msg.date = datetime.now(timezone.utc)
        mock_msg.text = "А ты Сене не хочешь снять очки? @snitch_sayonara_bot он все по факту зарепортил"
        mock_msg.reply_to_message = None

        mock_bot = MagicMock()
        mock_bot.id = 999
        mock_bot.username = "snitch_sayonara_bot"
        mock_msg.bot.get_me = AsyncMock(return_value=mock_bot)

        mock_lore.return_value = {
            "core": {
                "characters": [
                    {"id": "383998331", "handle": "arsinov", "names": ["Паштет", "Сеня"]}
                ]
            }
        }

        mock_db.get_user_stats = AsyncMock(return_value={"total_points": 50})
        mock_db.get_recent_messages = AsyncMock(return_value=[])
        mock_db.user_repository.get_chat_users = AsyncMock(return_value=([
            {"user_id": "383998331", "username": "arsinov", "full_name": "Паштет 🍷 воздух"}
        ], None))
        mock_db.user_repository.apply_point_event_transactional = AsyncMock(return_value={"applied": True})

        mock_ai.generate_cynical_comment = AsyncMock(return_value=CynicalCommentResult(
            comment="Списал по красоте. Сеня, с тебя пиво на навесе за такой царский подгон.",
            award_points=True,
            target_username="Сене",
            points_delta=-25,
            reason="За верный донос и правильные движения"
        ))

        reply = await ChatService.process_cynical_comment(mock_msg, mock_msg.text)

        self.assertIsNotNone(reply)
        self.assertIn("Списал по красоте", reply)
        self.assertIn("Людской поступок: -25 pts @arsinov", reply)
        self.assertIn("За верный донос", reply)

        # Verify negative points were applied
        mock_db.user_repository.apply_point_event_transactional.assert_called_once()
        call_event = mock_db.user_repository.apply_point_event_transactional.call_args[0][1]
        self.assertEqual(call_event.points_delta, -25)
        self.assertEqual(call_event.user_id, "383998331")
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

    @patch("src.services.chat_service.debt_repository.update_debts", new_callable=AsyncMock)
    @patch("src.services.chat_service.db")
    @patch("src.services.chat_service.ai")
    async def test_process_cynical_comment_records_debts(self, mock_ai, mock_db, mock_update_debts):
        from src.models.ai import DebtTransaction
        mock_msg = MagicMock()
        mock_msg.chat.id = -100123
        mock_msg.from_user.id = 555
        mock_msg.from_user.username = "elisei"
        mock_msg.message_id = 44
        mock_msg.date = datetime.now(timezone.utc)
        mock_msg.text = "@snitch_sayonara_bot я скинул за Паштета 500 за такси"
        mock_msg.reply_to_message = None

        mock_bot = MagicMock()
        mock_bot.id = 999
        mock_bot.username = "snitch_sayonara_bot"
        mock_msg.bot.get_me = AsyncMock(return_value=mock_bot)

        mock_db.get_user_stats = AsyncMock(return_value={"total_points": 10})
        mock_db.get_recent_messages = AsyncMock(return_value=[])

        mock_ai.generate_cynical_comment = AsyncMock(return_value=CynicalCommentResult(
            comment="Опять спонсируешь бродягу.",
            award_points=False,
            debt_transactions=[
                DebtTransaction(
                    debtor="паштет",
                    creditor="elisei",
                    amount=500,
                    reason="такси",
                    is_settled=False
                )
            ]
        ))

        reply = await ChatService.process_cynical_comment(mock_msg, mock_msg.text)

        self.assertIn("Опять спонсируешь бродягу.", reply)
        self.assertIn("Кстати, я зафиксировал долги:", reply)
        self.assertIn("Паштет торчит 500 Elisei (такси)", reply)
        mock_update_debts.assert_called_once()
        call_txs = mock_update_debts.call_args[0][1]
        self.assertEqual(len(call_txs), 1)
        self.assertEqual(call_txs[0]["debtor"], "паштет")
        self.assertEqual(call_txs[0]["creditor"], "elisei")
        self.assertEqual(call_txs[0]["amount"], 500)
        self.assertFalse(call_txs[0]["is_settled"])


if __name__ == "__main__":
    unittest.main()
