import logging
from typing import List, Optional
from src.database import db
from src.models.fact import FactModel

class FactRepository:
    def __init__(self):
        self.db = db

    def _get_facts_ref(self, chat_id: str):
        return self.db.collection("chats").document(str(chat_id)).collection("verified_facts")

    async def get_facts(self, chat_id: int) -> List[dict]:
        """
        Fetches all verified facts for a specific chat.
        """
        facts_ref = self._get_facts_ref(str(chat_id))
        
        facts = []
        try:
            async for doc in facts_ref.stream():
                data = doc.to_dict()
                data['id'] = doc.id
                facts.append(data)
            return facts
        except Exception as e:
            logging.error(f"Error fetching facts: {e}")
            return []

    async def add_fact(self, chat_id: int, fact_data: dict) -> bool:
        """
        Adds a new verified fact.
        """
        facts_ref = self._get_facts_ref(str(chat_id))
        try:
            await facts_ref.add(fact_data)
            return True
        except Exception as e:
            logging.error(f"Error adding fact: {e}")
            return False

    async def remove_facts_by_pattern(self, chat_id: int, text_pattern: str) -> int:
        """
        Removes facts that match a pattern.
        """
        facts_ref = self._get_facts_ref(str(chat_id))
        
        removed_count = 0
        try:
            async for doc in facts_ref.stream():
                fact_text = doc.to_dict().get('text', '')
                if text_pattern.lower() in fact_text.lower():
                    await doc.reference.delete()
                    removed_count += 1
            return removed_count
        except Exception as e:
            logging.error(f"Error removing fact: {e}")
            return 0

fact_repository = FactRepository()
