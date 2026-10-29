import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models.points import PointEvent
from src.repositories.user_repository import UserRepository
from src.services.db import apply_weekly_amnesty, save_daily_results
from src.utils.game_config import config


class TestPointsLedgerAndAmnesty(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repo = UserRepository()

    @patch("src.repositories.user_repository.db")
    async def test_apply_point_event_transactional_idempotency(self, mock_db):
        repo = UserRepository()
        repo.db = mock_db

        event = PointEvent(
            event_id="test_dup_1",
            chat_id="-1001",
            user_id="100",
            points_delta=50,
            event_type="test"
        )

        mock_transaction = MagicMock()
        mock_transaction._begin = AsyncMock()
        mock_transaction._rollback = AsyncMock()
        mock_transaction._commit = AsyncMock()
        mock_db.transaction.return_value = mock_transaction

        # Ledger doc already exists
        mock_ledger_doc = MagicMock()
        mock_ledger_doc.exists = True
        mock_ledger_doc.to_dict.return_value = {"points_delta": 50}

        # Mock async get on document reference
        mock_ledger_ref = MagicMock()
        mock_ledger_ref.get = AsyncMock(return_value=mock_ledger_doc)

        mock_user_ref = MagicMock()
        mock_user_doc = MagicMock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = {"total_points": 100, "season_id": "global"}
        mock_user_ref.get = AsyncMock(return_value=mock_user_doc)

        def mock_collection(col_name):
            col = MagicMock()
            if col_name == "chats":
                chat_doc = MagicMock()
                def chat_subcol(sub_name):
                    sub = MagicMock()
                    if sub_name == "points_ledger":
                        sub.document.return_value = mock_ledger_ref
                    elif sub_name == "user_stats":
                        sub.document.return_value = mock_user_ref
                    return sub
                chat_doc.collection = chat_subcol
                col.document.return_value = chat_doc
            return col

        mock_db.collection = mock_collection

        result = await repo.apply_point_event_transactional(-1001, event)
        self.assertFalse(result["applied"])
        self.assertTrue(result["already_processed"])
        mock_transaction.set.assert_not_called()

    @patch("src.services.db.db")
    @patch("src.services.db.user_repository")
    async def test_apply_weekly_amnesty_idempotency(self, mock_user_repo, mock_db):
        mock_run_ref = MagicMock()
        mock_run_doc = MagicMock()
        mock_run_doc.exists = True # Already ran this week
        mock_run_ref.get = AsyncMock(return_value=mock_run_doc)

        chat_doc = MagicMock()
        chat_doc.collection.return_value.document.return_value = mock_run_ref
        mock_db.collection.return_value.document.return_value = chat_doc

        result = await apply_weekly_amnesty(-1001, "2026-W38")
        self.assertFalse(result)
        mock_user_repo.get_weekly_points_for_chat.assert_not_called()

    @patch("src.services.db.db")
    @patch("src.services.db.user_repository")
    async def test_apply_weekly_amnesty_deducts_50_percent_of_weekly_points(self, mock_user_repo, mock_db):
        mock_run_ref = MagicMock()
        mock_run_doc = MagicMock()
        mock_run_doc.exists = False # First time this week
        mock_run_ref.get = AsyncMock(return_value=mock_run_doc)
        mock_run_ref.set = AsyncMock()

        chat_doc = MagicMock()
        chat_doc.collection.return_value.document.return_value = mock_run_ref
        mock_db.collection.return_value.document.return_value = chat_doc

        # User earned 100 points this week
        mock_user_repo.get_weekly_points_for_chat = AsyncMock(return_value={"100": 100})
        mock_user_repo.apply_point_event_transactional = AsyncMock(return_value={"applied": True})

        result = await apply_weekly_amnesty(-1001, "2026-W38")
        self.assertTrue(result)
        mock_user_repo.apply_point_event_transactional.assert_called_once()
        
        # Check event points_delta is -50
        call_args = mock_user_repo.apply_point_event_transactional.call_args[0]
        event_arg = call_args[1]
        self.assertEqual(event_arg.points_delta, -50)
        self.assertEqual(event_arg.event_type, "weekly_amnesty")

    @patch("src.services.db.db")
    async def test_save_daily_results_skips_pre_epoch_dates(self, mock_db):
        daily_ref = MagicMock()
        daily_ref.set = AsyncMock()
        chat_doc = MagicMock()
        chat_doc.collection.return_value.document.return_value = daily_ref
        mock_db.collection.return_value.document.return_value = chat_doc

        old_analysis = {
            "date_key": "2026-09-10", # Before ACCOUNTING_EPOCH_DATE = "2026-09-15"
            "offenders": [{"user_id": 111, "username": "alice", "points": 50}]
        }

        await save_daily_results(-1001, old_analysis)
        # Should set the daily result doc but NOT run transaction on user stats
        daily_ref.set.assert_called_once_with(old_analysis)
        mock_db.transaction.assert_not_called()

    @patch("src.repositories.user_repository.db")
    async def test_annul_point_event(self, mock_db):
        repo = UserRepository()
        repo.db = mock_db

        mock_transaction = MagicMock()
        mock_transaction._begin = AsyncMock()
        mock_transaction._rollback = AsyncMock()
        mock_transaction._commit = AsyncMock()
        mock_transaction._clean_up = MagicMock()
        mock_transaction._max_attempts = 1
        mock_db.transaction.return_value = mock_transaction

        # Mock ledger doc
        mock_ledger_doc = MagicMock()
        mock_ledger_doc.exists = True
        mock_ledger_doc.to_dict.return_value = {
            "user_id": "100",
            "points_delta": 50,
            "event_type": "report",
            "reason": "Toxicity: мат",
            "status": "active"
        }
        mock_ledger_ref = MagicMock()
        mock_ledger_ref.get = AsyncMock(return_value=mock_ledger_doc)

        # Mock user doc
        mock_user_doc = MagicMock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = {"total_points": 150, "username": "test_user"}
        mock_user_ref = MagicMock()
        mock_user_ref.get = AsyncMock(return_value=mock_user_doc)

        repo._get_points_ledger_ref = MagicMock(return_value=mock_ledger_ref)
        repo._get_user_ref = MagicMock(return_value=mock_user_ref)

        res = await repo.annul_point_event(-1001, "report:-1001:10:20", reason="Не было мата")
        self.assertTrue(res["success"])
        self.assertEqual(res["reverted_delta"], 50)
        self.assertEqual(res["new_total"], 100) # 150 - 50 = 100
        mock_transaction.update.assert_any_call(mock_user_ref, {
            "total_points": 100,
            "current_rank": "Шнырь 🧹"
        })


if __name__ == "__main__":
    unittest.main()
