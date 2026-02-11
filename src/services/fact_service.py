import logging
from datetime import datetime, timezone
from src.services.db import db

class FactService:
    @staticmethod
    async def get_facts(chat_id: int):
        """
        Fetches all verified facts for a specific chat.
        """
        chat_id_str = str(chat_id)
        facts_ref = db.collection("chats").document(chat_id_str).collection("verified_facts")
        
        facts = []
        try:
            async for doc in facts_ref.stream():
                facts.append(doc.to_dict())
            return facts
        except Exception as e:
            logging.error(f"Error fetching facts: {e}")
            return []

    @staticmethod
    async def get_facts_as_str(chat_id: int):
        """
        Returns facts as a formatted string for prompts.
        """
        facts = await FactService.get_facts(chat_id)
        if not facts:
            return "Нет проверенных фактов."
            
        facts_str = ""
        for i, fact in enumerate(facts, 1):
            text = fact.get('text', '')
            date = fact.get('date', '')
            date_str = f" ({date})" if date else ""
            facts_str += f"{i}. {text}{date_str}\n"
        return facts_str

    @staticmethod
    async def add_fact(chat_id: int, text: str, source: str = "system", confidence: float = 1.0):
        """
        Adds a new verified fact.
        """
        chat_id_str = str(chat_id)
        facts_ref = db.collection("chats").document(chat_id_str).collection("verified_facts")
        
        fact_data = {
            "text": text,
            "created_at": datetime.now(timezone.utc),
            "source": source,
            "confidence": confidence
        }
        
        try:
            await facts_ref.add(fact_data)
            logging.info(f"New fact added for chat {chat_id}: {text}")
            return True
        except Exception as e:
            logging.error(f"Error adding fact: {e}")
            return False

    @staticmethod
    async def remove_fact_by_text(chat_id: int, text_pattern: str):
        """
        Removes facts that match a pattern (e.g., when a user corrects a hallucination).
        """
        chat_id_str = str(chat_id)
        facts_ref = db.collection("chats").document(chat_id_str).collection("verified_facts")
        
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
