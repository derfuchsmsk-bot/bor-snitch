from google.cloud import firestore
from src.database import db
from src.utils.game_config import config
from src.models.points import PointEvent
from datetime import datetime, timezone
import logging

class UserRepository:
    def __init__(self):
        self.db = db

    def _get_user_ref(self, chat_id: str, user_id: str):
        return self.db.collection("chats").document(str(chat_id)).collection("user_stats").document(str(user_id))

    def _get_points_ledger_ref(self, chat_id: str, event_id: str):
        return self.db.collection("chats").document(str(chat_id)).collection("points_ledger").document(str(event_id))

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

    async def update_user_last_active(self, chat_id: int, user_id: int, last_active_date, username=None, full_name=None, is_bot: bool = False):
        """
        Updates user's last active date and info.
        """
        data = {
            "last_active_date": last_active_date,
            "is_bot": is_bot
        }
        if username:
            data["username"] = username
        if full_name:
            data["full_name"] = full_name
            
        await self._get_user_ref(chat_id, user_id).set(data, merge=True)

    async def apply_point_event_transactional(self, chat_id: int, event: PointEvent) -> dict:
        """
        Applies a point transaction idempotently using a Firestore Transaction.
        Returns: { "applied": bool, "new_total": int, "rank": str, "already_processed": bool }
        """
        chat_id_str = str(chat_id)
        user_id_str = str(event.user_id)
        ledger_ref = self._get_points_ledger_ref(chat_id_str, event.event_id)
        user_ref = self._get_user_ref(chat_id_str, user_id_str)

        @firestore.async_transactional
        async def _txn(transaction):
            ledger_doc = await ledger_ref.get(transaction=transaction)
            if ledger_doc.exists:
                user_doc = await user_ref.get(transaction=transaction)
                total = user_doc.to_dict().get("total_points", 0) if user_doc.exists else 0
                return {
                    "applied": False,
                    "new_total": total,
                    "rank": self.calculate_rank(total),
                    "already_processed": True
                }

            user_doc = await user_ref.get(transaction=transaction)
            current_points = 0
            username = None
            if user_doc.exists:
                u_data = user_doc.to_dict()
                current_points = u_data.get("total_points", 0)
                username = u_data.get("username")

            new_points = max(0, current_points + event.points_delta)
            new_rank = self.calculate_rank(new_points)

            # Record event in ledger
            event_data = event.model_dump()
            event_data["created_at"] = firestore.SERVER_TIMESTAMP
            if not event_data.get("week_key"):
                event_data["week_key"] = PointEvent.current_week_key()
            transaction.set(ledger_ref, event_data)

            # Update user stats
            update_data = {
                "total_points": new_points,
                "current_rank": new_rank,
                "season_id": event.season_id or "global"
            }
            if username:
                update_data["username"] = username
            transaction.set(user_ref, update_data, merge=True)

            return {
                "applied": True,
                "new_total": new_points,
                "rank": new_rank,
                "already_processed": False
            }

        transaction = self.db.transaction()
        return await _txn(transaction)

    async def add_points(self, chat_id: int, user_id: int, points: int, reason: str = None, event_id: str = None, event_type: str = "direct_adjust") -> int:
        """
        Applies immediate points (penalty or reward) idempotently and returns new total.
        """
        if not event_id:
            import uuid
            event_id = f"{event_type}:{chat_id}:{user_id}:{uuid.uuid4().hex[:8]}"

        event = PointEvent(
            event_id=event_id,
            chat_id=str(chat_id),
            user_id=str(user_id),
            points_delta=points,
            event_type=event_type,
            reason=reason,
            season_id="global"
        )
        res = await self.apply_point_event_transactional(chat_id, event)
        return res["new_total"]

    async def play_casino_transactional(self, chat_id: int, user_id: int, date_key: str, is_win: bool, deduction: int, penalty: int) -> dict:
        """
        Executes casino play atomically: prevents double-play and race conditions.
        """
        chat_id_str = str(chat_id)
        user_id_str = str(user_id)
        event_id = f"gamble:{chat_id_str}:{user_id_str}:{date_key}"
        ledger_ref = self._get_points_ledger_ref(chat_id_str, event_id)
        user_ref = self._get_user_ref(chat_id_str, user_id_str)

        @firestore.async_transactional
        async def _txn(transaction):
            user_doc = await user_ref.get(transaction=transaction)
            if user_doc.exists:
                u_data = user_doc.to_dict()
                if u_data.get("last_gamble_date") == date_key:
                    return {"status": "already_played", "total_points": u_data.get("total_points", 0)}

            ledger_doc = await ledger_ref.get(transaction=transaction)
            if ledger_doc.exists:
                total = user_doc.to_dict().get("total_points", 0) if user_doc.exists else 0
                return {"status": "already_played", "total_points": total}

            current_points = 0
            if user_doc.exists:
                current_points = user_doc.to_dict().get("total_points", 0)

            delta = -deduction if is_win else penalty
            new_points = max(0, current_points + delta)
            new_rank = self.calculate_rank(new_points)

            # Record event in ledger
            event = PointEvent(
                event_id=event_id,
                chat_id=chat_id_str,
                user_id=user_id_str,
                points_delta=delta,
                event_type="gamble",
                reason="Казино победа" if is_win else "Казино проигрыш",
                season_id="global",
                week_key=PointEvent.current_week_key()
            )
            event_data = event.model_dump()
            event_data["created_at"] = firestore.SERVER_TIMESTAMP
            transaction.set(ledger_ref, event_data)

            # Update user stats
            transaction.set(user_ref, {
                "total_points": new_points,
                "current_rank": new_rank,
                "last_gamble_date": date_key,
                "season_id": "global"
            }, merge=True)

            return {"status": "success", "new_points": new_points, "rank": new_rank}

        transaction = self.db.transaction()
        return await _txn(transaction)

    async def record_gamble_result(self, chat_id: int, user_id: int, new_points: int, date_key: str):
        """
        Legacy fallback for gamble result, ensuring season_id is set.
        """
        new_rank = self.calculate_rank(new_points)
        await self._get_user_ref(chat_id, user_id).set({
            "total_points": new_points,
            "current_rank": new_rank,
            "last_gamble_date": date_key,
            "season_id": "global"
        }, merge=True)

    async def increment_false_report_count(self, chat_id: int, user_id: int) -> int:
        """
        Increments the false report counter atomically and returns the new value.
        """
        ref = self._get_user_ref(chat_id, user_id)
        
        @firestore.async_transactional
        async def _txn(transaction):
            doc = await ref.get(transaction=transaction)
            current_count = 0
            if doc.exists:
                current_count = doc.to_dict().get("false_report_count", 0)
            new_count = current_count + 1
            transaction.set(ref, {"false_report_count": new_count}, merge=True)
            return new_count

        transaction = self.db.transaction()
        return await _txn(transaction)

    async def get_weekly_points_for_chat(self, chat_id: int, week_key: str) -> dict:
        """
        Sums positive points received by users in the chat during the given week.
        Returns: { user_id_str: total_positive_points }
        """
        chat_id_str = str(chat_id)
        ledger_ref = self.db.collection("chats").document(chat_id_str).collection("points_ledger")
        query = ledger_ref.where(filter=firestore.FieldFilter("week_key", "==", week_key))\
                          .where(filter=firestore.FieldFilter("points_delta", ">", 0))
        
        weekly_points = {}
        async for doc in query.stream():
            data = doc.to_dict()
            uid = str(data.get("user_id"))
            pts = data.get("points_delta", 0)
            weekly_points[uid] = weekly_points.get(uid, 0) + pts
        return weekly_points

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

    async def set_user_points(self, chat_id: int, user_id: int, points: int) -> dict:
        """Sets the exact points for a user and re-calculates rank."""
        points = max(0, int(points))
        rank = self.calculate_rank(points)
        user_ref = self._get_user_ref(chat_id, user_id)
        await user_ref.set({
            "total_points": points,
            "current_rank": rank,
            "season_id": "global"
        }, merge=True)
        return {"total_points": points, "current_rank": rank}

    async def update_user_achievements(self, chat_id: int, user_id: int, achievements: list) -> list:
        """Updates the list of achievements for a user."""
        user_ref = self._get_user_ref(chat_id, user_id)
        await user_ref.set({"achievements": achievements}, merge=True)
        return achievements

    async def get_points_ledger(self, chat_id: int, limit: int = 50) -> list:
        """Fetches recent points ledger events for a chat."""
        chat_id_str = str(chat_id)
        ledger_ref = self.db.collection("chats").document(chat_id_str).collection("points_ledger")
        query = ledger_ref.order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit)
        events = []
        try:
            async for doc in query.stream():
                d = doc.to_dict()
                d["id"] = doc.id
                events.append(d)
        except Exception as e:
            logging.error(f"Error fetching points ledger: {e}")
        return events

    async def revert_point_event(self, chat_id: int, event_id: str) -> dict:
        """
        Reverts an existing point event: deducts the points delta from user and deletes the event.
        """
        chat_id_str = str(chat_id)
        ledger_ref = self._get_points_ledger_ref(chat_id_str, event_id)
        ledger_doc = await ledger_ref.get()
        if not ledger_doc.exists:
            return {"success": False, "error": "Event not found"}

        event_data = ledger_doc.to_dict()
        user_id = event_data.get("user_id")
        delta = event_data.get("points_delta", 0)

        # Reverse the delta
        reverse_delta = -delta
        if user_id:
            user_ref = self._get_user_ref(chat_id_str, user_id)
            user_doc = await user_ref.get()
            if user_doc.exists:
                current_points = user_doc.to_dict().get("total_points", 0)
                new_points = max(0, current_points + reverse_delta)
                new_rank = self.calculate_rank(new_points)
                await user_ref.update({
                    "total_points": new_points,
                    "current_rank": new_rank
                })

        await ledger_ref.delete()
        return {"success": True, "reverted_delta": delta, "user_id": user_id}

user_repository = UserRepository()
