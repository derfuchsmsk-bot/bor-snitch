from google.cloud import firestore
from src.database import db
from src.utils.game_config import config
from datetime import datetime, timezone

class UserRepository:
    def __init__(self):
        self.db = db

    def _get_user_ref(self, chat_id: str, user_id: str):
        return self.db.collection("chats").document(str(chat_id)).collection("user_stats").document(str(user_id))

    def calculate_rank(self, points: int) -> str:
        """
        Calculates the Snitch Rank based on total points.
        Theme: Prison Caste (Reverse/Ironic)
        """
        if points >= config.RANK_PIERCED[0]:
            return "Масть Проткнутая 👑"
        elif points >= config.RANK_OFFENDED[0]:
            return "Обиженный 🚽"
        elif points >= config.RANK_GOAT[0]:
            return "Козёл 🐐"
        elif points >= config.RANK_SHNYR[0]:
            return "Шнырь 🧹"
        else:
            return "Порядочный 😐"

    async def get_user_stats(self, chat_id: int, user_id: int) -> dict:
        """
        Fetches stats for a specific user.
        """
        doc = await self._get_user_ref(chat_id, user_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    async def update_user_last_active(self, chat_id: int, user_id: int, last_active_date, username=None, full_name=None):
        """
        Updates user's last active date and info.
        """
        data = {
            "last_active_date": last_active_date
        }
        if username:
            data["username"] = username
        if full_name:
            data["full_name"] = full_name
            
        await self._get_user_ref(chat_id, user_id).set(data, merge=True)

    async def add_points(self, chat_id: int, user_id: int, points: int) -> int:
        """
        Applies immediate points (penalty or reward) and returns new total.
        """
        ref = self._get_user_ref(chat_id, user_id)
        doc = await ref.get()
        current_points = 0
        
        if doc.exists:
            data = doc.to_dict()
            current_points = data.get("total_points", 0)
            
        new_points = current_points + points
        new_rank = self.calculate_rank(new_points)
        
        await ref.set({
            "total_points": new_points,
            "current_rank": new_rank
        }, merge=True)
        
        return new_points

    async def record_gamble_result(self, chat_id: int, user_id: int, new_points: int, date_key: str):
        """
        Updates user stats after a gamble.
        """
        new_rank = self.calculate_rank(new_points)
        await self._get_user_ref(chat_id, user_id).set({
            "total_points": new_points,
            "current_rank": new_rank,
            "last_gamble_date": date_key
        }, merge=True)

    async def increment_false_report_count(self, chat_id: int, user_id: int) -> int:
        """
        Increments the false report counter and returns the new value.
        """
        ref = self._get_user_ref(chat_id, user_id)
        doc = await ref.get()
        
        current_count = 0
        if doc.exists:
            data = doc.to_dict()
            current_count = data.get("false_report_count", 0)
            
        new_count = current_count + 1
        
        await ref.set({
            "false_report_count": new_count
        }, merge=True)
        
        return new_count

    async def get_chat_users(self, chat_id: int, limit: int = 100, cursor=None):
        """
        Fetches users who have stats in the chat with pagination.
        """
        chat_id = str(chat_id)
        stats_ref = self.db.collection("chats").document(chat_id).collection("user_stats")
        
        query = stats_ref.order_by("__name__").limit(limit)
        if cursor:
            query = query.start_after(cursor)
        
        users = []
        last_doc = None
        async for doc in query.stream():
            data = doc.to_dict()
            user_id = doc.id
            username = data.get('username')
            full_name = data.get('full_name', username)
            
            users.append({
                "user_id": user_id,
                "username": username,
                "full_name": full_name,
                "stats": data
            })
            last_doc = doc
        return users, last_doc

user_repository = UserRepository()
