import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import os
import sys
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.main import app
from src.utils.config import settings


class TestWebhookSecurityAndIdempotency(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("src.main.db")
    def test_webhook_rejects_invalid_secret_token(self, mock_db):
        with patch.object(settings, "SECRET_TOKEN", "super-secret"):
            response = self.client.post(
                "/webhook",
                json={"update_id": 12345},
                headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"}
            )
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()["detail"], "Invalid secret token")

    @patch("src.main.dp")
    @patch("src.main.db")
    def test_webhook_accepts_valid_secret_token(self, mock_db, mock_dp):
        mock_dp.feed_update = AsyncMock()
        mock_update_ref = MagicMock()
        mock_update_ref.create = AsyncMock()
        mock_db.collection.return_value.document.return_value = mock_update_ref

        with patch.object(settings, "SECRET_TOKEN", "super-secret"):
            response = self.client.post(
                "/webhook",
                json={"update_id": 12345, "message": {"message_id": 1, "date": 1234567890, "chat": {"id": -1, "type": "supergroup"}}},
                headers={"X-Telegram-Bot-Api-Secret-Token": "super-secret"}
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "ok")
            mock_dp.feed_update.assert_called_once()

    @patch("src.main.dp")
    @patch("src.main.db")
    def test_webhook_skips_duplicate_update_id(self, mock_db, mock_dp):
        mock_dp.feed_update = AsyncMock()
        mock_update_ref = MagicMock()
        # Simulate google.api_core.exceptions.AlreadyExists
        mock_update_ref.create = AsyncMock(side_effect=Exception("Document already exists"))
        mock_db.collection.return_value.document.return_value = mock_update_ref

        with patch.object(settings, "SECRET_TOKEN", "super-secret"):
            response = self.client.post(
                "/webhook",
                json={"update_id": 99999, "message": {"message_id": 2, "date": 1234567890, "chat": {"id": -1, "type": "supergroup"}}},
                headers={"X-Telegram-Bot-Api-Secret-Token": "super-secret"}
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"status": "ok", "message": "duplicate"})
            # Should NOT pass duplicate update to dispatcher
            mock_dp.feed_update.assert_not_called()


if __name__ == "__main__":
    unittest.main()
