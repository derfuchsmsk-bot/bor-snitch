from google.cloud import firestore
from datetime import datetime, timezone
import logging

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
    
    text_content = message.text or message.caption or ""
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
        logs.append(doc.to_dict())
        
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
    
    # 2. Update user stats (increment counter)
    if winner_data.get('user_id'):
        user_stats_ref = db.collection("chats").document(str_chat_id).collection("user_stats").document(str(winner_data['user_id']))
        
        # Transactional update would be better, but simple merge is okay for MVP
        # Using increment transform
        await user_stats_ref.set({
            "username": winner_data['username'],
            "snitch_count": firestore.Increment(1),
            "last_title": winner_data['title'],
            "last_win_date": winner_data['date_key']
        }, merge=True)
