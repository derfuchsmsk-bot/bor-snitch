import logging
from datetime import datetime, timezone
from typing import List, Optional, Any
from google.cloud import firestore
from src.database import db
from src.models.message import MessageModel

class MessageRepository:
    def __init__(self):
        self.db = db

    def _get_messages_ref(self, chat_id: str):
        return self.db.collection("chats").document(str(chat_id)).collection("messages")

    async def log_message(self, chat_id: int, message_data: dict) -> None:
        """
        Logs a message to Firestore.
        """
        chat_id_str = str(chat_id)
        msg_id = str(message_data.get("message_id"))
        
        # Ensure message_id is not in the data dict if we are setting it as document ID
        data_to_save = {k: v for k, v in message_data.items() if k != "message_id"}
        
        doc_ref = self._get_messages_ref(chat_id_str).document(msg_id)
        
        logging.debug(f"Writing message {msg_id} to Firestore (Chat: {chat_id_str})...")
        await doc_ref.set(data_to_save)
        logging.debug(f"Message {msg_id} written successfully.")

    async def get_message(self, chat_id: int, message_id: int) -> Optional[dict]:
        """
        Fetches a specific message by ID.
        """
        doc_ref = self._get_messages_ref(str(chat_id)).document(str(message_id))
        doc = await doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            data['message_id'] = doc.id
            return data
        return None

    async def update_message(self, chat_id: int, message_id: int, update_data: dict) -> None:
        """
        Updates an existing message.
        """
        doc_ref = self._get_messages_ref(str(chat_id)).document(str(message_id))
        await doc_ref.set(update_data, merge=True)

    async def get_logs_for_time_range(self, chat_id: int, start_dt: datetime, end_dt: datetime) -> List[dict]:
        """
        Fetches messages within a specific time range [start_dt, end_dt).
        """
        messages_ref = self._get_messages_ref(str(chat_id))
        
        query = messages_ref.where(filter=firestore.FieldFilter("timestamp", ">=", start_dt))\
                            .where(filter=firestore.FieldFilter("timestamp", "<", end_dt))\
                            .order_by("timestamp", direction=firestore.Query.ASCENDING)
        
        logs = []
        async for doc in query.stream():
            data = doc.to_dict()
            data['message_id'] = doc.id
            logs.append(data)
            
        return logs

    async def get_recent_messages(self, chat_id: int, before_timestamp: datetime, limit: int = 5) -> List[dict]:
        """
        Fetches the last N messages before a specific timestamp for context.
        """
        messages_ref = self._get_messages_ref(str(chat_id))
        
        query = messages_ref.where(filter=firestore.FieldFilter("timestamp", "<", before_timestamp))\
                            .order_by("timestamp", direction=firestore.Query.DESCENDING)\
                            .limit(limit)
        
        logs = []
        async for doc in query.stream():
            data = doc.to_dict()
            data['message_id'] = doc.id
            logs.append(data)
            
        logs.reverse()
        return logs

    async def get_subsequent_messages(self, chat_id: int, after_timestamp: datetime, limit: int = 5) -> List[dict]:
        """
        Fetches the next N messages after a specific timestamp.
        """
        messages_ref = self._get_messages_ref(str(chat_id))
        
        query = messages_ref.where(filter=firestore.FieldFilter("timestamp", ">", after_timestamp))\
                            .order_by("timestamp", direction=firestore.Query.ASCENDING)\
                            .limit(limit)
        
        logs = []
        async for doc in query.stream():
            data = doc.to_dict()
            data['message_id'] = doc.id
            logs.append(data)
            
        return logs

    async def mark_message_reported(self, chat_id: int, msg_id: int, reporter_id: int, reason: str, points_awarded: int = 0, ai_thought_process: str = None) -> None:
        """
        Flags a message as reported.
        """
        update_data = {
            "is_reported": True,
            "reported_by": reporter_id,
            "report_reason": reason,
            "report_timestamp": firestore.SERVER_TIMESTAMP,
            "points_awarded": points_awarded
        }
        if ai_thought_process:
            update_data["ai_thought_process"] = ai_thought_process

        await self.update_message(chat_id, msg_id, update_data)

    async def log_reaction(self, chat_id: int, reaction_data: dict) -> None:
        """
        Logs a reaction as a message entry.
        """
        # Reaction ID construction logic needs to be preserved or handled by caller.
        # Here we assume the caller handles ID generation if it's special, 
        # but for reactions the ID is usually composite.
        
        # We will use the generic log_message but we need the ID.
        # If reaction_data doesn't have an ID, we might need to generate one? 
        # The service layer logic `reaction_id = ...` handles this.
        
        # Let's assume log_message handles it if passed in data.
        await self.log_message(chat_id, reaction_data)

message_repository = MessageRepository()
