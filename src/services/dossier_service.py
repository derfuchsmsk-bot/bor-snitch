import logging
import json
from typing import List, Optional
from datetime import datetime, timezone
from src.models.dossier import UserDossier
from src.repositories.dossier_repository import dossier_repository

class DossierService:
    @staticmethod
    async def get_dossier(chat_id: int | str, user_id: int | str) -> Optional[UserDossier]:
        return await dossier_repository.get_dossier(chat_id, user_id)

    @staticmethod
    async def save_or_update(chat_id: int | str, dossier: UserDossier):
        await dossier_repository.save_dossier(chat_id, dossier)

    @staticmethod
    async def get_all_dossiers(chat_id: int | str) -> List[UserDossier]:
        return await dossier_repository.get_all_dossiers(chat_id)

    @staticmethod
    async def get_social_graph_context(chat_id: int | str) -> str:
        """
        Builds a concise summary of user relationships and communication styles
        to inject into prompts for roasting vs toxicity resolution.
        """
        dossiers = await dossier_repository.get_all_dossiers(chat_id)
        if not dossiers:
            return "Досье участников пока не сформированы."

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
