import logging
from datetime import datetime, timezone
from typing import List
from google.cloud import firestore
from src.database import db

logger = logging.getLogger(__name__)

class ThoughtRepository:
    def __init__(self):
        self.db = db

    def _get_thoughts_ref(self, chat_id: str):
        return self.db.collection("chats").document(str(chat_id)).collection("channel_thoughts")

    async def get_recent_thoughts(self, chat_id: int | str, limit: int = 15) -> List[str]:
        try:
            thoughts_ref = self._get_thoughts_ref(str(chat_id))
            query = thoughts_ref.order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit)
            results = []
            async for doc in query.stream():
                data = doc.to_dict()
                text = data.get("text", "").strip()
                if text:
                    results.append(text)
            return results
        except Exception as e:
            logger.warning(f"Error fetching recent thoughts from DB for chat {chat_id}: {e}")
            return []

    async def save_thought(self, chat_id: int | str, text: str, theme: str = "") -> bool:
        try:
            thoughts_ref = self._get_thoughts_ref(str(chat_id))
            data = {
                "text": text,
                "theme": theme,
                "created_at": datetime.now(timezone.utc)
            }
            await thoughts_ref.add(data)
            return True
        except Exception as e:
            logger.error(f"Error saving thought for chat {chat_id}: {e}")
            return False

thought_repository = ThoughtRepository()
