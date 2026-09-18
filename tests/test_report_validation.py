import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import json
from src.services.prompt_service import PromptService
from src.services.report_service import ReportService
from src.services import ai
from src.models.ai import ReportValidationResult
from src.utils import messages
from src.repositories.user_repository import user_repository


class TestReportValidationEnhancements(unittest.IsolatedAsyncioTestCase):

    def test_prompt_format_includes_lore_and_agreements(self):
        lore_sample = json.dumps({"universe": "Test", "concepts": ["mast_vs_lyudskoe"]})
        agreements_sample = "- [ID: ag1] Vanya: навесик и фильм (Тип: action)"

        formatted = PromptService.format_report_validation_prompt(
            lore_json=lore_sample,
            active_agreements=agreements_sample
        )

        self.assertIn("<lore_core>", formatted)
        self.assertIn("mast_vs_lyudskoe", formatted)
        self.assertIn("<active_agreements>", formatted)
        self.assertIn("навесик и фильм", formatted)
        self.assertIn("СЛИВ С ДОГОВОРЕННОСТЕЙ ИЛИ СОВМЕСТНЫХ ПЛАНОВ", formatted)

    @patch("src.services.ai.GenerativeModel")
    @patch("src.services.ai.LoreService.get_lore")
    @patch("src.repositories.agreement_repository.agreement_repository.get_active_agreements")
    async def test_validate_report_fetches_lore_and_agreements(
        self, mock_get_agreements, mock_get_lore, mock_model_cls
    ):
        mock_get_lore.return_value = {
            "core": {
                "characters": [{"handle": "mastic", "names": ["Мастецкий", "Ваня Любецкий"]}],
                "concepts": [{"name": "mast_vs_lyudskoe", "mast": "слив с планов"}]
            }
        }
        mock_get_agreements.return_value = [
            {"id": "ag_1", "users": ["ioann_thegreat"], "text": "навесик в 15:00", "type": "action"}
        ]

        mock_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "thought_process": "Участник слился с согласованного навесика без объяснений, нарушив договоренность.",
            "valid": True,
            "category": "Snitching",
            "points": 75,
            "reason": "Слив с навесика и договоренности (масть)"
        })
        mock_instance.generate_content_async = AsyncMock(return_value=mock_response)
        mock_model_cls.return_value = mock_instance

        res = await ai.validate_report(
            target_text="Я минус",
            context_msgs=[
                {"username": "Elisei", "text": "в 15:00 идем на навесик и фильм?"},
                {"username": "ioann_thegreat", "text": "Я минус"}
            ],
            chat_id=-100123456,
            target_username="Ваня Любецкий",
            reporter_comment="слился с навесика"
        )

        self.assertTrue(res.valid)
        self.assertEqual(res.category, "Snitching")
        self.assertEqual(res.points, 75)
        self.assertEqual(res.status, "accepted")

        # Verify that get_lore and get_active_agreements were called with chat_id
        mock_get_lore.assert_called_once_with(-100123456)
        mock_get_agreements.assert_called_once_with(-100123456)

        # Verify the prompt sent to GenerativeModel
        call_args = mock_instance.generate_content_async.call_args
        contents = call_args.kwargs["contents"]
        system_instruction, user_prompt = contents[0], contents[1]

        self.assertIn("навесик в 15:00", system_instruction)
        self.assertIn("Мастецкий", system_instruction)
        self.assertIn("Ваня Любецкий", user_prompt)
        self.assertIn("слился с навесика", user_prompt)

    @patch("src.services.report_service.db")
    @patch("src.services.report_service.ai")
    async def test_process_report_forwards_target_username_and_comment(self, mock_ai, mock_db):
        mock_msg = MagicMock()
        mock_msg.chat.id = -100123
        mock_msg.from_user.id = 111
        mock_msg.text = "/report слился без объяснений"

        mock_reported_msg = MagicMock()
        mock_reported_msg.message_id = 9999
        mock_reported_msg.from_user.id = 222
        mock_reported_msg.from_user.username = "ioann_thegreat"
        mock_reported_msg.from_user.full_name = "Ваня Любецкий"
        mock_reported_msg.from_user.first_name = "Ваня"
        mock_reported_msg.date = "2026-09-18"

        mock_db.message_repository.get_message = AsyncMock(return_value=None)
        mock_db.get_recent_messages = AsyncMock(return_value=[])
        mock_db.get_subsequent_messages = AsyncMock(return_value=[])
        mock_db.user_repository.apply_point_event_transactional = AsyncMock(return_value={"applied": True})
        mock_db.mark_message_reported = AsyncMock()

        mock_ai.validate_report = AsyncMock(return_value=ReportValidationResult(
            valid=True,
            category="Snitching",
            reason="Слив с договоренности",
            points=75,
            status="accepted"
        ))

        reply_text, success = await ReportService.process_report(mock_msg, mock_reported_msg, "Я минус")

        self.assertTrue(success)
        self.assertIn("Донос принят", reply_text)
        self.assertIn("Snitching", reply_text)

        # Check call arguments to validate_report
        mock_ai.validate_report.assert_called_once_with(
            "Я минус",
            [],
            chat_id=-100123,
            target_username="ioann_thegreat",
            reporter_comment="слился без объяснений"
        )


if __name__ == "__main__":
    unittest.main()
