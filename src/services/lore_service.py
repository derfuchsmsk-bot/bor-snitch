import json
import logging
from datetime import datetime, timezone
from google.cloud import firestore
from .db import db
from ..utils.lore import LORE_DATA

class LoreService:
    @staticmethod
    async def get_lore(chat_id: int):
        """
        Fetches lore for a specific chat.
        Falls back to default lore if not found in DB.
        """
        chat_id_str = str(chat_id)
        doc_ref = db.collection("chats").document(chat_id_str).collection("lore").document("current")
        
        try:
            doc = await doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                return data.get("data", LORE_DATA)
            else:
                logging.info(f"Lore not found for chat {chat_id}, using default.")
                return LORE_DATA
        except Exception as e:
            logging.error(f"Error fetching lore from DB: {e}")
            return LORE_DATA

    @staticmethod
    async def get_lore_as_json(chat_id: int):
        """Returns lore as a formatted JSON string for prompts."""
        lore_data = await LoreService.get_lore(chat_id)
        return json.dumps(lore_data, ensure_ascii=False, indent=2)

    @staticmethod
    async def update_lore(chat_id: int, new_lore_data: dict, generated_by: str = "system"):
        """Updates the lore in Firestore."""
        chat_id_str = str(chat_id)
        doc_ref = db.collection("chats").document(chat_id_str).collection("lore").document("current")
        
        # Get current version to increment
        doc = await doc_ref.get()
        version = 1
        if doc.exists:
            version = doc.to_dict().get("version", 0) + 1

        payload = {
            "data": new_lore_data,
            "version": version,
            "updated_at": datetime.now(timezone.utc),
            "generated_by": generated_by
        }
        
        await doc_ref.set(payload)
        logging.info(f"Lore updated to version {version} for chat {chat_id}")
        return version
