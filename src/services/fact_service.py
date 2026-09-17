import logging
from datetime import datetime, timezone
from cachetools import TTLCache
from src.database import db
from src.repositories.fact_repository import fact_repository

_facts_cache = TTLCache(maxsize=100, ttl=300)

class FactService:
    @staticmethod
    def invalidate_cache(chat_id: int | str):
        """Invalidates the in-memory facts cache for a chat."""
        _facts_cache.pop(str(chat_id), None)

    @staticmethod
    async def get_facts(chat_id: int):
        """
        Fetches all verified facts for a specific chat with in-memory caching.
        """
        chat_id_str = str(chat_id)
        if chat_id_str in _facts_cache:
            return _facts_cache[chat_id_str]

        facts = await fact_repository.get_facts(chat_id)
        _facts_cache[chat_id_str] = facts
        return facts

    @staticmethod
    async def get_facts_as_str(chat_id: int, limit: int = None):
        """
        Returns facts as a formatted string for prompts.
        Optionally limits to the most recent `limit` facts.
        """
        facts = await FactService.get_facts(chat_id)
        if not facts:
            return "Нет проверенных фактов."

        if limit and len(facts) > limit:
            facts = facts[-limit:]
            
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
        Adds a new verified fact and invalidates cache.
        """
        FactService.invalidate_cache(chat_id)
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
        Removes facts that match a pattern and invalidates cache.
        """
        FactService.invalidate_cache(chat_id)
        return await fact_repository.remove_facts_by_pattern(chat_id, text_pattern)
