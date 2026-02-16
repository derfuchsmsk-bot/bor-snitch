import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple, Any
from google.cloud import firestore
from src.database import db
from src.models.agreement import AgreementModel
from src.utils.game_config import config

class AgreementRepository:
    def __init__(self):
        self.db = db

    def _get_agreements_ref(self, chat_id: str):
        return self.db.collection("chats").document(str(chat_id)).collection("agreements")

    async def save_agreement(self, chat_id: int, agreement_data: dict) -> None:
        """
        Saves a new agreement.
        """
        chat_id_str = str(chat_id)
        coll_ref = self._get_agreements_ref(chat_id_str)
        
        # Ensure critical fields are set if not present (logic moved from service/db but kept for safety)
        if 'status' not in agreement_data:
            agreement_data['status'] = 'active'
        if 'created_at' not in agreement_data:
            agreement_data['created_at'] = firestore.SERVER_TIMESTAMP
            
        await coll_ref.add(agreement_data)

    async def get_agreement(self, chat_id: int, agreement_id: str) -> Optional[dict]:
        """
        Fetches a specific agreement by ID.
        """
        doc_ref = self._get_agreements_ref(str(chat_id)).document(agreement_id)
        doc = await doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None

    async def update_agreement(self, chat_id: int, agreement_id: str, update_data: dict) -> None:
        """
        Updates an agreement.
        """
        doc_ref = self._get_agreements_ref(str(chat_id)).document(agreement_id)
        await doc_ref.update(update_data)

    async def get_active_agreements(self, chat_id: int) -> List[dict]:
        """
        Fetches active agreements for the chat.
        """
        coll_ref = self._get_agreements_ref(str(chat_id))
        query = coll_ref.where(
            filter=firestore.FieldFilter("status", "==", "active")
        ).order_by("created_at", direction=firestore.Query.ASCENDING)
        
        agreements = []
        async for doc in query.stream():
            data = doc.to_dict()
            data['id'] = doc.id
            agreements.append(data)
        
        return agreements

    async def dispute_agreement(self, chat_id: int, agreement_id: str) -> Tuple[bool, str]:
        """
        Marks an agreement as disputed if within the time window.
        Returns (success, message_code).
        """
        ag = await self.get_agreement(chat_id, agreement_id)
        if not ag or ag.get('status') != 'active':
            return False, "not_found"
        
        can_dispute_until = ag.get('can_be_disputed_until')
        if not can_dispute_until:
            return False, "too_late"
            
        # Ensure TZ awareness
        if can_dispute_until.tzinfo is None:
            can_dispute_until = can_dispute_until.replace(tzinfo=timezone.utc)
            
        if datetime.now(timezone.utc) > can_dispute_until:
            return False, "too_late"
            
        # Success: mark as disputed
        await self.update_agreement(chat_id, agreement_id, {"status": "disputed"})
        return True, "ok"

    async def get_last_agreement_check(self, chat_id: str) -> Optional[datetime]:
        """Gets the timestamp of the last agreement check."""
        doc = await self.db.collection("chats").document(chat_id).get()
        if doc.exists:
            data = doc.to_dict()
            return data.get('last_agreement_check')
        return None

    async def set_last_agreement_check(self, chat_id: str, ts: datetime) -> None:
        """Sets the timestamp of the last agreement check."""
        await self.db.collection("chats").document(chat_id).set({
            'last_agreement_check': ts
        }, merge=True)

agreement_repository = AgreementRepository()
