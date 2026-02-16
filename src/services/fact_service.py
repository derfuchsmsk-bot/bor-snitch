import logging
from datetime import datetime, timezone
from src.database import db
from src.repositories.fact_repository import fact_repository

class FactService:
    @staticmethod
    async def get_facts(chat_id: int):
        """
        Fetches all verified facts for a specific chat.
        """
        return await fact_repository.get_facts(chat_id)

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
        fact_data = {
            "text": text,
            "created_at": datetime.now(timezone.utc),
            "source": source,
            "confidence": confidence
        }
        
        success = await fact_repository.add_fact(chat_id, fact_data)
        if success:
             logging.info(f"New fact added for chat {chat_id}: {text}")
        return success

    @staticmethod
    async def remove_fact_by_text(chat_id: int, text_pattern: str):
        """
        Removes facts that match a pattern (e.g., when a user corrects a hallucination).
        """
        return await fact_repository.remove_facts_by_pattern(chat_id, text_pattern)
