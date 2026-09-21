import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from src.main import app
from src.utils.config import settings
from src.utils.game_config import config, DEFAULT_CONFIG_VALUES
from src.services.prompt_service import PromptService
from src.admin.auth import verify_admin_password, create_admin_token, decode_admin_token, COOKIE_NAME


client = TestClient(app)


def test_game_config_defaults_and_updates():
    config.reset_to_defaults()
    assert config.POINTS_TOXICITY == 25
    assert config.BOT_DISABLED is False
    assert config.AI_MODEL_ANALYSIS == "gemini-3.8-flash"

    # Test update from dict
    config.update_from_dict({
        "POINTS_TOXICITY": 45,
        "BOT_DISABLED": True,
        "CYNICAL_COMMENT_CHANCE": 0.05
    })
    assert config.POINTS_TOXICITY == 45
    assert config.BOT_DISABLED is True
    assert config.CYNICAL_COMMENT_CHANCE == 0.05

    # Test serialization to dict
    serialized = config.to_dict()
    assert serialized["POINTS_TOXICITY"] == 45
    assert serialized["BOT_DISABLED"] is True
    assert serialized["RANK_PIERCED"] == [1000, None]

    # Test reset
    config.reset_to_defaults()
    assert config.POINTS_TOXICITY == 25
    assert config.BOT_DISABLED is False


def test_prompt_service_formatting_and_reset():
    PromptService.reset_to_defaults = MagicMock()
    prompts_info = PromptService.get_all_prompts_info()
    assert len(prompts_info) >= 6

    # Test system prompt format
    sys_prompt = PromptService.format_system_prompt(
        lore_json="{}",
        verified_facts="Fact 1",
        current_context="Context 1",
        lessons_str=""
    )
    assert "Снитч-бот" in sys_prompt
    assert "Fact 1" in sys_prompt

    # Test report validation format
    rep_prompt = PromptService.format_report_validation_prompt()
    assert "Toxicity" in rep_prompt


def test_admin_auth_functions():
    # settings.effective_admin_password is set to "test-admin-password" in conftest
    assert verify_admin_password("test-admin-password") is True
    assert verify_admin_password("wrong-password") is False
    assert verify_admin_password("   ") is False

    # Test JWT token creation and decoding
    token = create_admin_token()
    payload = decode_admin_token(token)
    assert payload["sub"] == "admin"
    assert "exp" in payload


def test_admin_ui_serving():
    response = client.get("/admin")
    assert response.status_code == 200
    assert "Bor Snitch CMS" in response.text
    assert "<!DOCTYPE html>" in response.text

    response_login = client.get("/admin/login")
    assert response_login.status_code == 200


def test_unauthenticated_api_access_blocked():
    # Accessing config without auth must return 401
    resp = client.get("/api/admin/config")
    assert resp.status_code == 401

    resp = client.get("/api/admin/prompts")
    assert resp.status_code == 401

    resp = client.get("/api/admin/me")
    assert resp.status_code == 401


def test_admin_login_and_logout():
    # Wrong password
    resp = client.post("/api/admin/login", json={"password": "incorrect-password"})
    assert resp.status_code == 401

    # Correct password
    resp = client.post("/api/admin/login", json={"password": settings.effective_admin_password})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "token" in data
    assert COOKIE_NAME in resp.cookies

    # Test /api/admin/me with cookie
    me_resp = client.get("/api/admin/me", cookies=resp.cookies)
    assert me_resp.status_code == 200
    assert me_resp.json()["authenticated"] is True

    # Test logout
    logout_resp = client.post("/api/admin/logout")
    assert logout_resp.status_code == 200


@pytest.mark.anyio
async def test_admin_config_api():
    token = create_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    with patch("src.services.config_service.db") as mock_db, \
         patch("src.main.sync_bot_commands", new_callable=AsyncMock):
        mock_doc = MagicMock()
        mock_doc.set = AsyncMock()
        mock_coll = MagicMock()
        mock_coll.document.return_value = mock_doc
        mock_db.collection.return_value = mock_coll

        # GET config
        resp = client.get("/api/admin/config", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "config" in data
        assert "defaults" in data

        # PUT config
        put_resp = client.put("/api/admin/config", json={
            "POINTS_TOXICITY": 33,
            "BOT_DISABLED": True
        }, headers=headers)
        assert put_resp.status_code == 200
        assert put_resp.json()["config"]["POINTS_TOXICITY"] == 33
        assert config.POINTS_TOXICITY == 33
        assert config.BOT_DISABLED is True

        # Reset config back
        config.reset_to_defaults()


@pytest.mark.anyio
async def test_admin_prompts_api():
    token = create_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    with patch("src.services.prompt_service.db") as mock_db:
        mock_doc = MagicMock()
        mock_doc.set = AsyncMock()
        mock_coll = MagicMock()
        mock_coll.document.return_value = mock_doc
        mock_db.collection.return_value = mock_coll

        # GET all prompts
        resp = client.get("/api/admin/prompts", headers=headers)
        assert resp.status_code == 200
        prompts = resp.json()["prompts"]
        assert len(prompts) >= 6

        # GET single prompt
        resp_single = client.get("/api/admin/prompts/report_validation_prompt", headers=headers)
        assert resp_single.status_code == 200
        assert resp_single.json()["key"] == "report_validation_prompt"

        # PUT single prompt
        custom_template = "Custom report validation: {points_toxicity}"
        put_resp = client.put(
            "/api/admin/prompts/report_validation_prompt",
            json={"template": custom_template},
            headers=headers
        )
        assert put_resp.status_code == 200
        assert PromptService.get_template("report_validation_prompt") == custom_template

        # POST reset single prompt
        reset_resp = client.post(
            "/api/admin/prompts/report_validation_prompt/reset",
            headers=headers
        )
        assert reset_resp.status_code == 200
        assert PromptService.get_template("report_validation_prompt") != custom_template


@pytest.mark.anyio
async def test_admin_chats_and_users_api():
    token = create_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    with patch("src.repositories.user_repository.user_repository.get_chat_users", new_callable=AsyncMock) as mock_get_users, \
         patch("src.repositories.user_repository.user_repository.add_points", new_callable=AsyncMock) as mock_add_points, \
         patch("src.repositories.user_repository.user_repository.set_user_points", new_callable=AsyncMock) as mock_set_points:

        mock_get_users.return_value = ([
            {
                "user_id": "111",
                "username": "snitcher",
                "full_name": "Snitcher Bob",
                "stats": {"total_points": 75, "current_rank": "Шнырь 🧹"}
            }
        ], None)

        mock_add_points.return_value = 100
        mock_set_points.return_value = {"total_points": 120, "current_rank": "Шнырь 🧹"}

        # GET chat users
        resp = client.get(f"/api/admin/chats/{settings.MAIN_CHAT_ID}/users", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["users"][0]["user_id"] == "111"

        # POST adjust points by delta
        delta_resp = client.post(
            f"/api/admin/chats/{settings.MAIN_CHAT_ID}/users/111/points",
            json={"points_delta": 25, "reason": "Test penalty"},
            headers=headers
        )
        assert delta_resp.status_code == 200
        assert delta_resp.json()["total_points"] == 100

        # POST set exact points
        exact_resp = client.post(
            f"/api/admin/chats/{settings.MAIN_CHAT_ID}/users/111/points",
            json={"exact_points": 120},
            headers=headers
        )
        assert exact_resp.status_code == 200
        assert exact_resp.json()["total_points"] == 120


def test_config_validation_rules():
    token = create_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Reject gamble win chance > 1.0
    resp_invalid_chance = client.put(
        "/api/admin/config",
        json={"GAMBLE_WIN_CHANCE": 1.5},
        headers=headers
    )
    assert resp_invalid_chance.status_code == 422

    # Reject negative points
    resp_negative_points = client.put(
        "/api/admin/config",
        json={"POINTS_TOXICITY": -10},
        headers=headers
    )
    assert resp_negative_points.status_code == 422


def test_admin_ui_contains_xss_protection():
    resp = client.get("/admin")
    assert resp.status_code == 200
    assert "function escapeHtml(str)" in resp.text
    assert "escapeHtml(u.full_name || username)" in resp.text
    assert "escapeHtml(f.text)" in resp.text
    assert "escapeHtml(ag.text || '—')" in resp.text
    assert "cfg-SPONTANEOUS_JUDGMENT_ENABLED" in resp.text
    assert "resetFalseReports" in resp.text


def test_reset_user_false_reports_endpoint():
    token = create_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    with patch("src.admin.router.user_repository.reset_false_report_count", new_callable=AsyncMock) as mock_reset:
        mock_reset.return_value = 0
        resp = client.post(
            f"/api/admin/chats/{settings.MAIN_CHAT_ID}/users/12345/reset_false_reports",
            headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert resp.json()["false_report_count"] == 0
        mock_reset.assert_called_once_with(int(settings.MAIN_CHAT_ID), 12345)


def test_config_spontaneous_judgment_update():
    token = create_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    with patch("src.admin.router.ConfigService.save_config", new_callable=AsyncMock) as mock_save:
        async def fake_save(updates):
            config.update_from_dict(updates)
            return config.to_dict()
        mock_save.side_effect = fake_save

        resp = client.put(
            "/api/admin/config",
            json={
                "SPONTANEOUS_JUDGMENT_ENABLED": True,
                "SPONTANEOUS_JUDGMENT_COOLDOWN_SECONDS": 240,
                "REPORT_CONTEXT_LIMIT": 40,
                "REPORT_NEXT_CONTEXT_LIMIT": 10
            },
            headers=headers
        )
        assert resp.status_code == 200
        assert config.SPONTANEOUS_JUDGMENT_ENABLED is True
        assert config.SPONTANEOUS_JUDGMENT_COOLDOWN_SECONDS == 240
        assert config.REPORT_CONTEXT_LIMIT == 40
        assert config.REPORT_NEXT_CONTEXT_LIMIT == 10


def test_get_and_send_chat_messages_endpoint():
    token = create_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Test GET messages
    with patch("src.admin.router.message_repository.get_latest_chat_messages", new_callable=AsyncMock) as mock_get_msgs:
        mock_get_msgs.return_value = [
            {"message_id": "1", "username": "elisei", "text": "Привет", "timestamp": "2026-09-18T12:00:00Z"},
            {"message_id": "2", "username": "YOU (Snitch Bot)", "text": "Здорово", "is_bot": True}
        ]
        resp = client.get(
            f"/api/admin/chats/{settings.MAIN_CHAT_ID}/messages",
            headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["messages"]) == 2
        assert data["messages"][0]["text"] == "Привет"

    # Test POST send message
    with patch("src.main.bot.send_message", new_callable=AsyncMock) as mock_send, \
         patch("src.services.db.log_message", new_callable=AsyncMock) as mock_log:
        
        mock_msg = MagicMock()
        mock_msg.message_id = 999
        mock_msg.date = MagicMock()
        mock_msg.date.isoformat.return_value = "2026-09-18T12:05:00Z"
        mock_send.return_value = mock_msg

        resp = client.post(
            f"/api/admin/chats/{settings.MAIN_CHAT_ID}/messages",
            json={"text": "<b>Привет от бота!</b>", "parse_mode": "HTML"},
            headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "sent"
        assert resp.json()["message_id"] == 999
        mock_send.assert_called_once_with(
            chat_id=int(settings.MAIN_CHAT_ID),
            text="<b>Привет от бота!</b>",
            parse_mode="HTML"
        )
        mock_log.assert_called_once_with(mock_msg)


def test_admin_ui_contains_chat_tab():
    resp = client.get("/admin")
    assert resp.status_code == 200
    assert "tab-content-chat" in resp.text
    assert "loadChatMessages" in resp.text
    assert "sendChatMessageFromAdmin" in resp.text


def test_get_points_ledger_and_annul_verdict():
    token = create_admin_token()
    headers = {"Authorization": f"Bearer {token}"}
    chat_id = settings.MAIN_CHAT_ID

    # 1. Test GET points ledger
    with patch("src.admin.router.user_repository.get_points_ledger", new_callable=AsyncMock) as mock_get_ledger:
        mock_get_ledger.return_value = [
            {
                "id": "report:-1001:42:555",
                "user_id": "123",
                "username": "arsinov",
                "full_name": "Паштет",
                "points_delta": 50,
                "event_type": "report",
                "reason": "Toxicity: Оскорбления",
                "status": "active",
                "is_annulled": False,
                "created_at": "2026-09-21T12:00:00Z"
            }
        ]
        resp = client.get(f"/api/admin/chats/{chat_id}/points_ledger", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["events"]) == 1
        assert data["events"][0]["username"] == "arsinov"
        assert data["events"][0]["points_delta"] == 50

    # 2. Test POST annul verdict with self-learning
    with patch("src.admin.router.user_repository.annul_point_event", new_callable=AsyncMock) as mock_annul, \
         patch("src.admin.router.LearningService.create_lesson_from_annulment", new_callable=AsyncMock) as mock_learn:

        mock_annul.return_value = {
            "success": True,
            "reverted_delta": 50,
            "new_total": 0,
            "rank": "Бродяга",
            "user_id": "123",
            "username": "arsinov",
            "event": {
                "id": "report:-1001:42:555",
                "event_type": "report",
                "reason": "Toxicity: Оскорбления",
                "points_delta": 50,
                "username": "arsinov"
            }
        }
        mock_learn.return_value = {
            "id": "lesson_123",
            "learned_rule": "Не считать дружеский сарказм токсичностью",
            "verdict": "mistake",
            "status": "active"
        }

        resp = client.post(
            f"/api/admin/chats/{chat_id}/points_ledger/report:-1001:42:555/annul",
            json={
                "reason": "Это дружеская ирония, а не токсичность",
                "learn_lesson": True,
                "custom_rule": "Не считать дружеский сарказм токсичностью"
            },
            headers=headers
        )
        assert resp.status_code == 200
        res_data = resp.json()
        assert res_data["status"] == "annulled"
        assert res_data["reverted_delta"] == 50
        assert res_data["new_total"] == 0
        assert res_data["lesson"]["learned_rule"] == "Не считать дружеский сарказм токсичностью"

        mock_annul.assert_called_once_with(
            int(chat_id),
            "report:-1001:42:555",
            reason="Это дружеская ирония, а не токсичность"
        )
        mock_learn.assert_called_once()


def test_admin_ui_contains_verdicts_tab():
    resp = client.get("/admin")
    assert resp.status_code == 200
    assert "tab-content-verdicts" in resp.text
    assert "loadVerdicts" in resp.text
    assert "modal-annul-verdict" in resp.text
    assert "submitAnnulVerdict" in resp.text


def test_admin_debts_endpoints_and_ui():
    token = create_admin_token()
    headers = {"Authorization": f"Bearer {token}"}
    chat_id = settings.MAIN_CHAT_ID

    # 1. Test GET debts
    with patch("src.admin.router.debt_repository.get_debts_summary", new_callable=AsyncMock) as mock_summary:
        mock_summary.return_value = {
            "balances": {"паштет": {"сеня": 500}},
            "items": [{"debtor": "паштет", "creditor": "сеня", "amount": 500}],
            "total_debt_amount": 500,
            "debts_count": 1,
            "top_debtor": "паштет",
            "top_debtor_amount": 500,
            "top_creditor": "сеня",
            "top_creditor_amount": 500
        }
        resp = client.get(f"/api/admin/chats/{chat_id}/debts", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_debt_amount"] == 500
        assert len(data["items"]) == 1
        assert data["items"][0]["debtor"] == "паштет"

    # 2. Test POST create/update debt
    with patch("src.admin.router.debt_repository.set_debt", new_callable=AsyncMock) as mock_set, \
         patch("src.admin.router.debt_repository.get_debts_summary", new_callable=AsyncMock) as mock_summary:
        mock_summary.return_value = {
            "balances": {"паштет": {"сеня": 1000}},
            "items": [{"debtor": "паштет", "creditor": "сеня", "amount": 1000}],
            "total_debt_amount": 1000,
            "debts_count": 1
        }
        resp = client.post(
            f"/api/admin/chats/{chat_id}/debts",
            json={"debtor": "паштет", "creditor": "сеня", "amount": 1000, "is_delta": False},
            headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "updated"
        mock_set.assert_called_once_with(int(chat_id), "паштет", "сеня", 1000)

    # 3. Test POST settle debt
    with patch("src.admin.router.debt_repository.delete_debt", new_callable=AsyncMock) as mock_del, \
         patch("src.admin.router.debt_repository.get_debts_summary", new_callable=AsyncMock) as mock_summary:
        mock_summary.return_value = {
            "balances": {},
            "items": [],
            "total_debt_amount": 0,
            "debts_count": 0
        }
        resp = client.post(
            f"/api/admin/chats/{chat_id}/debts/settle",
            json={"debtor": "паштет", "creditor": "сеня"},
            headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "settled"
        mock_del.assert_called_once_with(int(chat_id), "паштет", "сеня")

    # 4. Test UI contains debts tab and modals
    resp = client.get("/admin")
    assert resp.status_code == 200
    assert "tab-content-debts" in resp.text
    assert "loadDebts" in resp.text
    assert "modal-debt-edit" in resp.text
    assert "modal-debt-settle" in resp.text


