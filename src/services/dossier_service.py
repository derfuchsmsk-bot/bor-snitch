import logging
import json
from typing import List, Optional, Set
from datetime import datetime, timezone
from cachetools import TTLCache
from src.models.dossier import UserDossier
from src.repositories.dossier_repository import dossier_repository

_dossiers_cache = TTLCache(maxsize=100, ttl=300)

class DossierService:
    @staticmethod
    def invalidate_cache(chat_id: int | str):
        _dossiers_cache.pop(str(chat_id), None)

    @staticmethod
    async def get_dossier(chat_id: int | str, user_id: int | str) -> Optional[UserDossier]:
        return await dossier_repository.get_dossier(chat_id, user_id)

    @staticmethod
    async def save_or_update(chat_id: int | str, dossier: UserDossier):
        DossierService.invalidate_cache(chat_id)
        await dossier_repository.save_dossier(chat_id, dossier)

    @staticmethod
    async def get_all_dossiers(chat_id: int | str) -> List[UserDossier]:
        chat_id_str = str(chat_id)
        if chat_id_str in _dossiers_cache:
            return _dossiers_cache[chat_id_str]
        dossiers = await dossier_repository.get_all_dossiers(chat_id)
        _dossiers_cache[chat_id_str] = dossiers
        return dossiers

    @staticmethod
    async def get_social_graph_context(chat_id: int | str, filter_user_ids: Optional[Set[str]] = None) -> str:
        """
        Builds a concise summary of user relationships and communication styles
        to inject into prompts for roasting vs toxicity resolution.
        Optionally filters to active participants in the current conversation thread.
        """
        dossiers = await DossierService.get_all_dossiers(chat_id)
        if not dossiers:
            return "Досье участников пока не сформированы."

        if filter_user_ids:
            filtered = [
                d for d in dossiers 
                if str(d.user_id) in filter_user_ids or (d.username and d.username.lstrip('@') in filter_user_ids)
            ]
            if filtered:
                dossiers = filtered

        lines = ["КАРТА ОТНОШЕНИЙ И ДОСЬЕ УЧАСТНИКОВ (ДЛЯ ОЦЕНКИ ROASTING VS TOXICITY):"]
        for d in dossiers:
            name = d.username or d.full_name or f"User_{d.user_id}"
            friends = ", ".join(d.friends_roasting) if d.friends_roasting else "нет отмеченных"
            topics = ", ".join(d.favorite_topics) if d.favorite_topics else "любые"
            lines.append(
                f"- @{name.lstrip('@')}: стиль='{d.communication_style}'. "
                f"Взаимный стеб (roasting) разрешен с: [{friends}]. "
                f"Любимые темы: [{topics}]. {d.summary}"
            )
        return "\n".join(lines)
