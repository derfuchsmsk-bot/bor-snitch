from google.cloud import firestore
from datetime import datetime, timezone
import logging

def get_current_season_id():
    """Returns the current season ID (YYYY-MM)."""
    return datetime.now(timezone.utc).strftime("%Y-%m")

# Initialize Firestore Async Client
# Note: Requires GOOGLE_APPLICATION_CREDENTIALS env var or running in GCP
db = firestore.AsyncClient()

async def log_message(message):
    """
    Logs a telegram message to Firestore.
    Structure: chats/{chat_id}/messages/{msg_id}
    """
    chat_id = str(message.chat.id)
    user_id = str(message.from_user.id)
    msg_id = str(message.message_id)
    
    # Date key for partitioning/querying by day
    date_key = message.date.strftime("%Y-%m-%d")
    
    doc_ref = db.collection("chats").document(chat_id).collection("messages").document(msg_id)
    
    text_content = message.text or message.caption
    if not text_content and message.sticker:
        text_content = f"[STICKER] {message.sticker.emoji or 'Unknown'}"

    if not text_content:
        return # Skip non-text messages for now
        
    data = {
        "user_id": int(user_id),
        "username": message.from_user.username or message.from_user.first_name,
        "full_name": message.from_user.full_name,
        "text": text_content,
        "timestamp": message.date,
        "date_key": date_key,
        "reply_to": message.reply_to_message.message_id if message.reply_to_message else None
    }
    
    await doc_ref.set(data)
    # logging.info(f"Logged message {msg_id} for chat {chat_id}")

async def get_logs_for_date(chat_id: int, date_key: str):
    """
    Fetches messages for a specific date.
    """
    chat_ref = db.collection("chats").document(str(chat_id))
    messages_ref = chat_ref.collection("messages")
    
    # Query: where date_key == date_key
    # Note: You might need a composite index in Firestore for complex queries, 
    # but strictly equality on one field is fine.
    query = messages_ref.where(filter=firestore.FieldFilter("date_key", "==", date_key))
    
    logs = []
    async for doc in query.stream():
        data = doc.to_dict()
        data['message_id'] = doc.id
        logs.append(data)
        
    # Sort by timestamp
    logs.sort(key=lambda x: x['timestamp'])
    return logs

async def save_daily_winner(chat_id: int, winner_data: dict):
    """
    Saves the result of the daily analysis.
    winner_data should contain: user_id, username, title, reason, date_key
    """
    str_chat_id = str(chat_id)
    date_key = winner_data['date_key']
    
    # 1. Save the daily result record
    daily_ref = db.collection("chats").document(str_chat_id).collection("daily_results").document(date_key)
    await daily_ref.set(winner_data)
    
    # 2. Update user stats (increment counter and points)
    if winner_data.get('user_id'):
        user_stats_ref = db.collection("chats").document(str_chat_id).collection("user_stats").document(str(winner_data['user_id']))
        
        # Get current stats to calculate new rank (need a transaction ideally, but read-write is fine for low load)
        doc = await user_stats_ref.get()
        current_season = get_current_season_id()
        
        current_points = 0
        current_wins = 0
        
        # Lazy Reset: Check if season changed
        if doc.exists:
            data = doc.to_dict()
            if data.get('season_id') == current_season:
                current_points = data.get("total_points", 0)
                current_wins = data.get("snitch_count", 0)
            # If season_id differs or missing, we start fresh (0 points/wins for this season)
            
        new_points = current_points + winner_data.get('points', 0)
        new_wins = current_wins + 1
        new_rank = calculate_rank(new_points)

        await user_stats_ref.set({
            "username": winner_data['username'],
            "season_id": current_season,
            "snitch_count": new_wins,
            "total_points": new_points,
            "current_rank": new_rank,
            "last_title": winner_data['title'],
            "last_win_date": winner_data['date_key']
        }, merge=True)

def calculate_rank(points):
    """
    Calculates the Snitch Rank based on total points.
    Theme: Prison Caste (Reverse/Ironic)
    """
    if points >= 200:
        return "Масть Проткнутая 👑"
    elif points >= 120:
        return "Обиженный 🚽"
    elif points >= 60:
        return "Козёл 🐐"
    elif points >= 20:
        return "Шнырь 🧹"
    else:
        return "Порядочный 😐"

async def get_user_stats(chat_id: int, user_id: int):
    """
    Fetches stats for a specific user.
    """
    chat_id = str(chat_id)
    user_id = str(user_id)
    doc_ref = db.collection("chats").document(chat_id).collection("user_stats").document(user_id)
    doc = await doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    return None

async def mark_message_reported(chat_id: int, msg_id: int, reporter_id: int, reason: str):
    """
    Flags a message as reported by a user.
    """
    chat_id = str(chat_id)
    msg_id = str(msg_id)
    doc_ref = db.collection("chats").document(chat_id).collection("messages").document(msg_id)
    
    await doc_ref.set({
        "is_reported": True,
        "reported_by": reporter_id,
        "report_reason": reason,
        "report_timestamp": firestore.SERVER_TIMESTAMP
    }, merge=True)

async def log_reaction(chat_id: int, user_id: int, username: str, message_id: int, emoji: str, timestamp: datetime):
    """
    Logs a reaction event. Fetches the original message to provide context.
    """
    chat_id = str(chat_id)
    message_id = str(message_id)
    
    # Fetch original message
    msg_ref = db.collection("chats").document(chat_id).collection("messages").document(message_id)
    msg_doc = await msg_ref.get()
    
    original_text = "Unknown Message"
    target_user = "Unknown"
    
    if msg_doc.exists:
        data = msg_doc.to_dict()
        original_text = data.get("text", "")
        target_user = data.get("username", "Unknown")
        
    # Create log entry
    # We use a composite key to avoid duplicates if needed, but timestamp is good enough
    reaction_id = f"reaction_{message_id}_{user_id}_{int(timestamp.timestamp())}"
    
    date_key = timestamp.strftime("%Y-%m-%d")
    
    log_text = f"[REACTION] {username} reacted {emoji} to {target_user}'s message: \"{original_text}\""
    
    doc_ref = db.collection("chats").document(chat_id).collection("messages").document(reaction_id)
    
    data = {
        "user_id": int(user_id),
        "username": username,
        "full_name": username, # Fallback
        "text": log_text,
        "timestamp": timestamp,
        "date_key": date_key,
        "type": "reaction",
        "target_msg_id": message_id
    }
    
    await doc_ref.set(data)
