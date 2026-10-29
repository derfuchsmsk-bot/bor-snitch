import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import os
import sys

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models.points import PointEvent
from src.models.user import UserStats
from src.models.ai import ReportValidationResult
from src.repositories.user_repository import UserRepository
from src.services.report_service import ReportService
from src.utils.game_config import config
from src.utils import messages


class TestPointEventModel(unittest.TestCase):
    def test_point_event_creation(self):
        event = PointEvent(
            event_id="test_evt_1",
            chat_id="-100123456",
            user_id="999",
            points_delta=25,
            event_type="report",
            reason="Toxicity"
        )
        self.assertEqual(event.event_id, "test_evt_1")
        self.assertEqual(event.chat_id, "-100123456")
        self.assertEqual(event.user_id, "999")
        self.assertEqual(event.points_delta, 25)
        self.assertEqual(event.event_type, "report")
        self.assertEqual(event.season_id, "global")
        self.assertTrue(len(event.week_key) > 4)

    def test_current_week_key_format(self):
        wk = PointEvent.current_week_key()
        parts = wk.split("-W")
        self.assertEqual(len(parts), 2)
        self.assertTrue(parts[0].isdigit())
        self.assertTrue(parts[1].isdigit())


class TestUserRepositoryLogic(unittest.TestCase):
    def setUp(self):
        self.repo = UserRepository()

    def test_calculate_rank(self):
        self.assertEqual(self.repo.calculate_rank(0), "Порядочный 😐")
        self.assertEqual(self.repo.calculate_rank(49), "Порядочный 😐")
        self.assertEqual(self.repo.calculate_rank(50), "Шнырь 🧹")
        self.assertEqual(self.repo.calculate_rank(249), "Шнырь 🧹")
        self.assertEqual(self.repo.calculate_rank(250), "Козёл 🐐")
        self.assertEqual(self.repo.calculate_rank(499), "Козёл 🐐")
        self.assertEqual(self.repo.calculate_rank(500), "Обиженный 🚽")
        self.assertEqual(self.repo.calculate_rank(999), "Обиженный 🚽")
        self.assertEqual(self.repo.calculate_rank(1000), "Масть Проткнутая 👑")
        self.assertEqual(self.repo.calculate_rank(2000), "Масть Проткнутая 👑")

    def test_user_stats_defaults(self):
        stats = UserStats(user_id="123", chat_id="456")
        self.assertEqual(stats.is_bot, False)
        self.assertEqual(stats.season_id, "global")
        self.assertEqual(stats.total_points, 0)


class TestReportService(unittest.IsolatedAsyncioTestCase):
    @patch("src.services.report_service.db")
    @patch("src.services.report_service.ai")
    async def test_duplicate_report_already_reported(self, mock_ai, mock_db):
        mock_msg = MagicMock()
        mock_msg.chat.id = -100123
        mock_msg.from_user.id = 111

        mock_reported_msg = MagicMock()
        mock_reported_msg.message_id = 999
        mock_reported_msg.from_user.id = 222
        mock_reported_msg.date = "2026-09-16"

        mock_db.message_repository.get_message = AsyncMock(return_value={"is_reported": True, "points_awarded": 25})

        reply_text, success = await ReportService.process_report(mock_msg, mock_reported_msg, "toxic comment")
        
        self.assertFalse(success)
        self.assertEqual(reply_text, messages.REPORT_ALREADY_PROCESSED)
        mock_ai.validate_report.assert_not_called()

    @patch("src.services.report_service.db")
    @patch("src.services.report_service.ai")
    async def test_technical_error_does_not_penalize_user(self, mock_ai, mock_db):
        mock_msg = MagicMock()
        mock_msg.chat.id = -100123
        mock_msg.from_user.id = 111

        mock_reported_msg = MagicMock()
        mock_reported_msg.message_id = 1001
        mock_reported_msg.from_user.id = 222
        mock_reported_msg.date = "2026-09-16"

        mock_db.message_repository.get_message = AsyncMock(return_value=None)
        mock_db.get_recent_messages = AsyncMock(return_value=[])
        mock_db.get_subsequent_messages = AsyncMock(return_value=[])

        mock_ai.validate_report = AsyncMock(return_value=ReportValidationResult(
            valid=False,
            category="System",
            reason="AI Model timeout",
            points=0,
            status="technical_error"
        ))

        reply_text, success = await ReportService.process_report(mock_msg, mock_reported_msg, "bad comment")

        self.assertFalse(success)
        self.assertEqual(reply_text, messages.REPORT_TECH_ERROR)
        mock_db.increment_false_report_count.assert_not_called()

    @patch("src.services.report_service.db")
    @patch("src.services.report_service.ai")
    async def test_valid_report_accepted_and_recorded(self, mock_ai, mock_db):
        mock_msg = MagicMock()
        mock_msg.chat.id = -100123
        mock_msg.from_user.id = 111

        mock_reported_msg = MagicMock()
        mock_reported_msg.message_id = 1002
        mock_reported_msg.from_user.id = 222
        mock_reported_msg.date = "2026-09-16"

        mock_db.message_repository.get_message = AsyncMock(return_value=None)
        mock_db.get_recent_messages = AsyncMock(return_value=[])
        mock_db.get_subsequent_messages = AsyncMock(return_value=[])
        mock_db.user_repository.apply_point_event_transactional = AsyncMock(return_value={"applied": True})
        mock_db.mark_message_reported = AsyncMock()

        mock_ai.validate_report = AsyncMock(return_value=ReportValidationResult(
            valid=True,
            category="Toxicity",
            reason="Severe insult",
            points=25,
            status="accepted"
        ))

        reply_text, success = await ReportService.process_report(mock_msg, mock_reported_msg, "insult")

        self.assertTrue(success)
        self.assertIn("Донос принят", reply_text)
        mock_db.user_repository.apply_point_event_transactional.assert_called_once()
        mock_db.mark_message_reported.assert_called_once()

    @patch("src.services.report_service.db")
    @patch("src.services.report_service.ai")
    async def test_genuine_rejection_increments_strikes_and_penalizes_at_limit(self, mock_ai, mock_db):
        mock_msg = MagicMock()
        mock_msg.chat.id = -100123
        mock_msg.from_user.id = 111

        mock_reported_msg = MagicMock()
        mock_reported_msg.message_id = 1003
        mock_reported_msg.from_user.id = 222
        mock_reported_msg.date = "2026-09-16"

        mock_db.message_repository.get_message = AsyncMock(return_value=None)
        mock_db.get_recent_messages = AsyncMock(return_value=[])
        mock_db.get_subsequent_messages = AsyncMock(return_value=[])

        mock_db.increment_false_report_count = AsyncMock(return_value=config.FALSE_REPORT_LIMIT)
        mock_db.user_repository.apply_point_event_transactional = AsyncMock(return_value={"applied": True})

        mock_ai.validate_report = AsyncMock(return_value=ReportValidationResult(
            valid=False,
            category="Normal",
            reason="Totally benign phrase",
            points=0,
            status="rejected"
        ))

        reply_text, success = await ReportService.process_report(mock_msg, mock_reported_msg, "hello")

        self.assertFalse(success)
        mock_db.increment_false_report_count.assert_called_once_with(-100123, 111)
        mock_db.user_repository.apply_point_event_transactional.assert_called_once()
        self.assertIn("Ложных доносов подряд", reply_text)


if __name__ == "__main__":
    unittest.main()

