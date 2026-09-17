import logging
from datetime import datetime, timezone
from typing import List, Optional, Any, Dict
from google.cloud import firestore
from src.database import db

logger = logging.getLogger(__name__)

class LessonRepository:
    def __init__(self):
        self.db = db

    def _get_lessons_ref(self, chat_id: str):
        return self.db.collection("chats").document(str(chat_id)).collection("lessons")

    @staticmethod
    def _sort_key(doc_data: dict) -> str:
        created_at = doc_data.get("created_at")
        if created_at:
            if hasattr(created_at, "isoformat"):
                return created_at.isoformat()
            return str(created_at)
        return str(doc_data.get("date_key") or "")

    async def get_lessons(self, chat_id: int | str, status: Optional[str] = None, limit: int = 100) -> List[dict]:
        """
        Fetches lessons for a chat, sorted by creation date descending.
        Optionally filters by status ('active', 'archived').
        """
        coll_ref = self._get_lessons_ref(str(chat_id))
        
        try:
            if status:
                query = coll_ref.where(filter=firestore.FieldFilter("status", "==", status))
            else:
                query = coll_ref

            lessons = []
            async for doc in query.stream():
                data = doc.to_dict() or {}
                data["id"] = doc.id
                lessons.append(data)

            lessons.sort(key=self._sort_key, reverse=True)
            return lessons[:limit]
        except Exception as e:
            logger.error(f"Error fetching lessons for chat {chat_id}: {e}")
            return []

    async def get_active_rules(self, chat_id: int | str, limit: int = 5) -> List[str]:
        """
        Fetches active lesson rule strings, newest first, for injection into AI system prompt.
        """
        active_lessons = await self.get_lessons(chat_id, status="active", limit=50)
        rules = []
        for l in active_lessons:
            rule = l.get("learned_rule")
            if rule and isinstance(rule, str) and rule.strip():
                rules.append(rule.strip())
            if len(rules) >= limit:
                break
        return rules

    async def get_lesson_by_id(self, chat_id: int | str, lesson_id: str) -> Optional[dict]:
        """
        Fetches a specific lesson by ID.
        """
        try:
            doc_ref = self._get_lessons_ref(str(chat_id)).document(str(lesson_id))
            doc = await doc_ref.get()
            if doc.exists:
                data = doc.to_dict() or {}
                data["id"] = doc.id
                return data
            return None
        except Exception as e:
            logger.error(f"Error fetching lesson {lesson_id} for chat {chat_id}: {e}")
            return None

    async def create_lesson(self, chat_id: int | str, lesson_data: dict) -> dict:
        """
        Saves a new learned rule / lesson.
        """
        coll_ref = self._get_lessons_ref(str(chat_id))
        data = dict(lesson_data)

        if "status" not in data:
            data["status"] = "active"
        if "created_at" not in data or data["created_at"] is None:
            data["created_at"] = datetime.now(timezone.utc)

        _, doc_ref = await coll_ref.add(data)
        data["id"] = doc_ref.id
        return data

    async def update_lesson(self, chat_id: int | str, lesson_id: str, update_data: dict) -> bool:
        """
        Updates an existing lesson.
        """
        try:
            doc_ref = self._get_lessons_ref(str(chat_id)).document(str(lesson_id))
            payload = dict(update_data)
            payload["updated_at"] = datetime.now(timezone.utc)
            await doc_ref.update(payload)
            return True
        except Exception as e:
            logger.error(f"Error updating lesson {lesson_id} for chat {chat_id}: {e}")
            return False

    async def set_lesson_status(self, chat_id: int | str, lesson_id: str, status: str) -> bool:
        """
        Updates status of a lesson ('active' or 'archived').
        """
        return await self.update_lesson(chat_id, lesson_id, {"status": status})

    async def delete_lesson(self, chat_id: int | str, lesson_id: str) -> bool:
        """
        Deletes a lesson document.
        """
        try:
            doc_ref = self._get_lessons_ref(str(chat_id)).document(str(lesson_id))
            await doc_ref.delete()
            return True
        except Exception as e:
            logger.error(f"Error deleting lesson {lesson_id} for chat {chat_id}: {e}")
            return False

lesson_repository = LessonRepository()
