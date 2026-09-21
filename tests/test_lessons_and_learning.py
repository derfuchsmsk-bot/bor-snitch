import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from src.main import app
from src.utils.config import settings
from src.services.learning import LearningService
from src.services.prompt_service import PromptService
from src.utils.prompts import get_system_prompt
from src.repositories.lesson_repository import LessonRepository, lesson_repository
from src.models.ai import FeedbackAnalysisResult
from src.admin.auth import create_admin_token

client = TestClient(app)


def test_lesson_sort_key():
    repo = LessonRepository()
    d1 = {"created_at": datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)}
    d2 = {"date_key": "2026-09-16"}
    d3 = {}
    assert repo._sort_key(d1) == d1["created_at"].isoformat()
    assert repo._sort_key(d2) == "2026-09-16"
    assert repo._sort_key(d3) == ""


@pytest.mark.anyio
async def test_lesson_repository_crud():
    repo = LessonRepository()

    # Mock collection and document
    mock_coll = MagicMock()
    mock_doc_ref = MagicMock()
    mock_doc_ref.id = "lesson_123"
    mock_coll.add = AsyncMock(return_value=(None, mock_doc_ref))

    mock_doc = MagicMock()
    mock_doc.update = AsyncMock()
    mock_doc.delete = AsyncMock()

    get_doc_mock = MagicMock()
    get_doc_mock.exists = True
    get_doc_mock.id = "lesson_123"
    get_doc_mock.to_dict.return_value = {
        "learned_rule": "Test rule",
        "status": "active"
    }
    mock_doc.get = AsyncMock(return_value=get_doc_mock)
    mock_coll.document.return_value = mock_doc

    with patch.object(repo, "_get_lessons_ref", return_value=mock_coll):
        # Create
        created = await repo.create_lesson(12345, {
            "learned_rule": "Don't repeat jokes",
            "reasoning": "Users annoyed",
            "status": "active"
        })
        assert created["id"] == "lesson_123"
        assert created["learned_rule"] == "Don't repeat jokes"
        assert mock_coll.add.called

        # Get by id
        fetched = await repo.get_lesson_by_id(12345, "lesson_123")
        assert fetched["id"] == "lesson_123"
        assert fetched["learned_rule"] == "Test rule"

        # Update
        ok_upd = await repo.update_lesson(12345, "lesson_123", {"learned_rule": "Updated rule"})
        assert ok_upd is True
        assert mock_doc.update.called

        # Set status
        ok_status = await repo.set_lesson_status(12345, "lesson_123", "archived")
        assert ok_status is True

        # Delete
        ok_del = await repo.delete_lesson(12345, "lesson_123")
        assert ok_del is True
        assert mock_doc.delete.called


@pytest.mark.anyio
async def test_lesson_repository_sorting_and_active_rules():
    repo = LessonRepository()

    doc1 = MagicMock()
    doc1.id = "doc1"
    doc1.to_dict.return_value = {
        "learned_rule": "Older rule",
        "created_at": datetime(2026, 2, 10, 10, 0, tzinfo=timezone.utc),
        "status": "active"
    }

    doc2 = MagicMock()
    doc2.id = "doc2"
    doc2.to_dict.return_value = {
        "learned_rule": "Newer rule",
        "created_at": datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc),
        "status": "active"
    }

    doc3 = MagicMock()
    doc3.id = "doc3"
    doc3.to_dict.return_value = {
        "learned_rule": "Middle rule",
        "created_at": datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
        "status": "active"
    }

    async def fake_stream():
        for d in [doc1, doc2, doc3]:
            yield d

    mock_query = MagicMock()
    mock_query.stream = fake_stream
    mock_coll = MagicMock()
    mock_coll.where.return_value = mock_query

    with patch.object(repo, "_get_lessons_ref", return_value=mock_coll):
        lessons = await repo.get_lessons(12345, status="active")
        # Should be sorted newest first: doc2 (Sept), doc3 (May), doc1 (Feb)
        assert len(lessons) == 3
        assert lessons[0]["id"] == "doc2"
        assert lessons[1]["id"] == "doc3"
        assert lessons[2]["id"] == "doc1"

        # Active rules extracts just the strings
        rules = await repo.get_active_rules(12345, limit=2)
        assert rules == ["Newer rule", "Middle rule"]


@pytest.mark.anyio
async def test_prompt_service_lessons_formatting():
    # Prompt formatting with lessons
    prompt_with_lessons = get_system_prompt(
        lore_json="{}",
        verified_facts="",
        current_context="",
        lessons=["Rule A", "Rule B", "", None]
    )
    assert "<learned_lessons>" in prompt_with_lessons
    assert "1. Rule A" in prompt_with_lessons
    assert "2. Rule B" in prompt_with_lessons
    assert "None" not in prompt_with_lessons

    # Prompt formatting without lessons
    prompt_no_lessons = get_system_prompt(
        lore_json="{}",
        verified_facts="",
        current_context="",
        lessons=[]
    )
    assert "<learned_lessons>" not in prompt_no_lessons


@pytest.mark.anyio
async def test_learning_service_analyze_feedback_no_feedback():
    # When logs have no mentions of the bot
    logs = [
        {"username": "vanya", "text": "Привет всем, как дела?", "reply_to": None},
        {"username": "vlad", "text": None, "reply_to": None}  # Test None text safety
    ]

    with patch("src.services.learning.get_logs_for_time_range", new_callable=AsyncMock) as mock_logs:
        mock_logs.return_value = logs
        result = await LearningService.analyze_feedback(12345, "2026-09-17")
        assert result is None


@pytest.mark.anyio
async def test_learning_service_analyze_feedback_success():
    logs = [
        {"username": "user1", "text": "Бот ты душнила сегодня с игнором", "reply_to": 999}
    ]

    mock_ai_response = MagicMock()
    mock_ai_response.text = '{"verdict": "mistake", "reasoning": "Bot penalized normal banter", "learned_rule": "Do not count quick banter as toxic"}'

    with patch("src.services.learning.get_logs_for_time_range", new_callable=AsyncMock) as mock_logs, \
         patch("src.services.learning.GenerativeModel") as mock_model_cls, \
         patch("src.services.learning.lesson_repository.create_lesson", new_callable=AsyncMock) as mock_create:

        mock_logs.return_value = logs
        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_ai_response)
        mock_model_cls.return_value = mock_model

        result = await LearningService.analyze_feedback(12345, "2026-09-17")

        assert result is not None
        assert isinstance(result, FeedbackAnalysisResult)
        assert result.verdict == "mistake"
        assert result.learned_rule == "Do not count quick banter as toxic"
        assert mock_create.called
        created_data = mock_create.call_args[0][1]
        assert created_data["learned_rule"] == "Do not count quick banter as toxic"
        assert created_data["status"] == "active"


@pytest.mark.anyio
async def test_admin_cms_lessons_api_crud():
    token = create_admin_token()
    headers = {"Authorization": f"Bearer {token}"}
    chat_id = str(settings.MAIN_CHAT_ID)

    mock_lessons_data = [
        {
            "id": "les_1",
            "learned_rule": "Сохранять локальные мемы",
            "reasoning": "Одобрение аудитории",
            "verdict": "fair",
            "status": "active",
            "date_key": "2026-09-17"
        }
    ]

    with patch("src.admin.router.lesson_repository.get_lessons", new_callable=AsyncMock) as mock_get, \
         patch("src.admin.router.lesson_repository.create_lesson", new_callable=AsyncMock) as mock_add, \
         patch("src.admin.router.lesson_repository.update_lesson", new_callable=AsyncMock) as mock_upd, \
         patch("src.admin.router.lesson_repository.set_lesson_status", new_callable=AsyncMock) as mock_status, \
         patch("src.admin.router.lesson_repository.delete_lesson", new_callable=AsyncMock) as mock_del:

        mock_get.return_value = mock_lessons_data
        mock_add.return_value = {"id": "les_new", "learned_rule": "Новый урок", "status": "active"}
        mock_upd.return_value = True
        mock_status.return_value = True
        mock_del.return_value = True

        # 1. GET lessons
        resp = client.get(f"/api/admin/chats/{chat_id}/lessons", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()["lessons"]) == 1
        assert resp.json()["lessons"][0]["id"] == "les_1"

        # 2. POST create lesson - success
        post_resp = client.post(
            f"/api/admin/chats/{chat_id}/lessons",
            json={
                "learned_rule": "Новый урок",
                "reasoning": "Тестовая причина",
                "verdict": "fair",
                "status": "active"
            },
            headers=headers
        )
        assert post_resp.status_code == 200
        assert post_resp.json()["status"] == "created"

        # 3. POST create lesson - empty rule validation error
        empty_resp = client.post(
            f"/api/admin/chats/{chat_id}/lessons",
            json={"learned_rule": "   "},
            headers=headers
        )
        assert empty_resp.status_code == 400

        # 4. PUT update lesson
        put_resp = client.put(
            f"/api/admin/chats/{chat_id}/lessons/les_1",
            json={"learned_rule": "Обновленный урок"},
            headers=headers
        )
        assert put_resp.status_code == 200
        assert put_resp.json()["status"] == "updated"

        # 5. POST toggle status
        status_resp = client.post(
            f"/api/admin/chats/{chat_id}/lessons/les_1/status",
            json={"status": "archived"},
            headers=headers
        )
        assert status_resp.status_code == 200
        assert status_resp.json()["new_status"] == "archived"

        # 6. DELETE lesson
        del_resp = client.delete(f"/api/admin/chats/{chat_id}/lessons/les_1", headers=headers)
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "deleted"


@pytest.mark.anyio
async def test_admin_cms_action_analyze_feedback():
    token = create_admin_token()
    headers = {"Authorization": f"Bearer {token}"}
    chat_id = str(settings.MAIN_CHAT_ID)

    with patch("src.admin.router.LearningService.analyze_feedback", new_callable=AsyncMock) as mock_analyze:
        mock_analyze.return_value = FeedbackAnalysisResult(
            verdict="fair",
            reasoning="Отличный вердикт",
            learned_rule="Продолжать в том же духе"
        )

        resp = client.post(
            "/api/admin/actions/analyze_feedback",
            json={"chat_id": chat_id, "date_key": "2026-09-17"},
            headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["learned"] is True
        assert data["result"]["learned_rule"] == "Продолжать в том же духе"


def test_admin_ui_contains_lessons_elements():
    resp = client.get("/admin")
    assert resp.status_code == 200
    html = resp.text

    # Tab navigation button
    assert 'data-tab="lessons"' in html
    assert "Уроки и Обучение" in html

    # Lessons tab content section
    assert 'id="tab-content-lessons"' in html
    assert "stat-lessons-total" in html
    assert "stat-lessons-active" in html
    assert "stat-lessons-archived" in html
    assert "stat-lessons-mistakes" in html

    # Modals
    assert 'id="modal-lesson"' in html
    assert 'id="modal-feedback-analysis"' in html

    # JS functions
    assert "async function loadLessons()" in html
    assert "function renderLessons()" in html
    assert "async function saveLessonForm()" in html
    assert "async function executeFeedbackAnalysis()" in html

    # XSS escape check on lessons
    assert "escapeHtml(lesson.learned_rule" in html
