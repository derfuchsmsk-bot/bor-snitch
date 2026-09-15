import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.repositories.user_repository import UserRepository
from src.services.db import save_daily_results
from src.utils.game_config import config


class TestCasinoAndDaily(unittest.IsolatedAsyncioTestCase):
    @patch("src.repositories.user_repository.db")
    async def test_play_casino_already_played_today(self, mock_db):
        repo = UserRepository()
        repo.db = mock_db

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        mock_transaction = MagicMock()
        mock_transaction._begin = AsyncMock()
        mock_transaction._rollback = AsyncMock()
        mock_transaction._commit = AsyncMock()
        mock_db.transaction.return_value = mock_transaction

        mock_user_ref = MagicMock()
        mock_user_doc = MagicMock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = {
            "total_points": 100,
            "last_gamble_date": today_str
        }
        mock_user_ref.get = AsyncMock(return_value=mock_user_doc)

        mock_ledger_ref = MagicMock()
        mock_ledger_doc = MagicMock()
        mock_ledger_doc.exists = False
        mock_ledger_ref.get = AsyncMock(return_value=mock_ledger_doc)

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

        result = await repo.play_casino_transactional(
            chat_id=-1001,
            user_id=555,
            date_key=today_str,
            is_win=True,
            deduction=50,
            penalty=60
        )
        self.assertEqual(result.get("status"), "already_played")
        mock_transaction.set.assert_not_called()

    @patch("src.services.db.db")
    async def test_save_daily_results_aggregates_multiple_infractions_per_user(self, mock_db):
        daily_ref = MagicMock()
        mock_daily_doc = MagicMock()
        mock_daily_doc.exists = False
        daily_ref.get = AsyncMock(return_value=mock_daily_doc)
        daily_ref.set = MagicMock()

        user_ref = MagicMock()
        mock_user_doc = MagicMock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = {
            "total_points": 20,
            "snitch_count": 1,
            "season_id": "global",
            "username": "charlie"
        }
        user_ref.get = AsyncMock(return_value=mock_user_doc)

        ledger_ref = MagicMock()

        mock_transaction = MagicMock()
        mock_transaction._begin = AsyncMock()
        mock_transaction._rollback = AsyncMock()
        mock_transaction._commit = AsyncMock()
        mock_db.transaction.return_value = mock_transaction

        def mock_collection(col_name):
            col = MagicMock()
            if col_name == "chats":
                chat_doc = MagicMock()
                def chat_subcol(sub_name):
                    sub = MagicMock()
                    if sub_name == "daily_results":
                        sub.document.return_value = daily_ref
                    elif sub_name == "user_stats":
                        sub.document.return_value = user_ref
                    elif sub_name == "points_ledger":
                        sub.document.return_value = ledger_ref
                    return sub
                chat_doc.collection = chat_subcol
                col.document.return_value = chat_doc
            return col

        mock_db.collection = mock_collection

        # User 999 has TWO distinct offenses on the same day
        analysis_data = {
            "date_key": "2026-09-16",
            "offenders": [
                {"user_id": 999, "username": "charlie", "points": 25, "reason": "toxicity"},
                {"user_id": 999, "username": "charlie", "points": 50, "reason": "snitching"}
            ]
        }

        await save_daily_results(-1001, analysis_data)

        # Verify transaction.set was called for user_ref with 20 + 25 + 50 = 95 points
        # Find calls to transaction.set with user_ref
        user_set_calls = [call for call in mock_transaction.set.call_args_list if call[0][0] == user_ref]
        self.assertEqual(len(user_set_calls), 1)
        saved_stats = user_set_calls[0][0][1]
        self.assertEqual(saved_stats["total_points"], 95)
        self.assertEqual(saved_stats["snitch_count"], 3) # 1 prior + 2 infractions


if __name__ == "__main__":
    unittest.main()
