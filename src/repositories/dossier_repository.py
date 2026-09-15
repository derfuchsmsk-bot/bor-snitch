import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone
from src.database import db
from src.models.dossier import UserDossier

class DossierRepository:
    def __init__(self):
        self.db = db

    def _get_dossier_ref(self, chat_id: str, user_id: str):
        return self.db.collection("chats").document(str(chat_id)).collection("dossiers").document(str(user_id))

    async def get_dossier(self, chat_id: int | str, user_id: int | str) -> Optional[UserDossier]:
        doc = await self._get_dossier_ref(str(chat_id), str(user_id)).get()
        if doc.exists:
            data = doc.to_dict()
            return UserDossier(**data)
        return None

    async def save_dossier(self, chat_id: int | str, dossier: UserDossier) -> None:
        ref = self._get_dossier_ref(str(chat_id), str(dossier.user_id))
        data = dossier.model_dump()
        data["updated_at"] = datetime.now(timezone.utc)
        await ref.set(data, merge=True)

    async def get_all_dossiers(self, chat_id: int | str) -> List[UserDossier]:
        coll_ref = self.db.collection("chats").document(str(chat_id)).collection("dossiers")
        dossiers = []
        try:
            async for doc in coll_ref.stream():
                data = doc.to_dict()
                dossiers.append(UserDossier(**data))
        except Exception as e:
            logging.error(f"Error fetching dossiers for chat {chat_id}: {e}")
        return dossiers

dossier_repository = DossierRepository()
