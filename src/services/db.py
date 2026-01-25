from google.cloud import firestore
from datetime import datetime, timezone
import logging

def get_current_season_id():
    """Returns the current season ID (Global)."""
    return "global" # Single season forever, only weekly decay

# Initialize Firestore Async Client
# Note: Requires GOOGLE_APPLICATION_CREDENTIALS env var or running in GCP
db = firestore.AsyncClient()

async def log_message(message, override_text=None):
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
    
    text_content = override_text or message.text or message.caption
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

async def save_agreement(chat_id: int, agreement: dict):
    """
    Saves a new agreement found by AI.
    agreement: { "text": "...", "users": [...], "created_at": ... }
    """
    chat_id = str(chat_id)
    coll_ref = db.collection("chats").document(chat_id).collection("agreements")
    
    data = agreement.copy()
    data['status'] = 'active'
    # Ensure timestamp is set
    if 'created_at' not in data:
        data['created_at'] = firestore.SERVER_TIMESTAMP
        
    await coll_ref.add(data)

async def get_active_agreements(chat_id: int):
    """
    Fetches active agreements for the chat.
    """
    chat_id = str(chat_id)
    coll_ref = db.collection("chats").document(chat_id).collection("agreements")
    query = coll_ref.where(filter=firestore.FieldFilter("status", "==", "active"))
    
    agreements = []
    async for doc in query.stream():
        data = doc.to_dict()
        data['id'] = doc.id
        agreements.append(data)
    return agreements

async def apply_weekly_decay(chat_id: int):
    """
    Halves the points for all users in the current season.
    """
    chat_id = str(chat_id)
    stats_ref = db.collection("chats").document(chat_id).collection("user_stats")
    
    current_season = get_current_season_id()
    
    # Process all users
    async for doc in stats_ref.stream():
        data = doc.to_dict()
        
        # Only affect current season
        if data.get('season_id') != current_season:
            continue
            
        current_points = data.get('total_points', 0)
        
        if current_points == 0:
            continue
            
        new_points = current_points // 2
        new_rank = calculate_rank(new_points)
        
        await stats_ref.document(doc.id).update({
            "total_points": new_points,
            "current_rank": new_rank
        })
        
    return True
    # logging.info(f"Logged message {msg_id} for chat {chat_id}")

async def get_logs_for_time_range(chat_id: int, start_dt: datetime, end_dt: datetime):
    """
    Fetches messages within a specific time range [start_dt, end_dt).
    """
    chat_ref = db.collection("chats").document(str(chat_id))
    messages_ref = chat_ref.collection("messages")
    
    # Query: timestamp >= start_dt AND timestamp < end_dt
    query = messages_ref.where(filter=firestore.FieldFilter("timestamp", ">=", start_dt))\
                        .where(filter=firestore.FieldFilter("timestamp", "<", end_dt))
    
    logs = []
    async for doc in query.stream():
        data = doc.to_dict()
        data['message_id'] = doc.id
        logs.append(data)
        
    # Sort by timestamp
    logs.sort(key=lambda x: x['timestamp'])
    return logs

async def save_daily_results(chat_id: int, analysis_result: dict):
    """
    Saves the result of the daily analysis (list of offenders).
    analysis_result: { "offenders": [...], "date_key": ... }
    """
    str_chat_id = str(chat_id)
    date_key = analysis_result['date_key']
    
    daily_ref = db.collection("chats").document(str_chat_id).collection("daily_results").document(date_key)
    current_season = get_current_season_id()
    
    # 1. Check for existing results for this date (Idempotency / Re-run logic)
    # If we run analysis multiple times a day, we must not double-count points.
    # We revert the previous points for this day before adding new ones.
    existing_doc = await daily_ref.get()
    
    if existing_doc.exists:
        logging.info(f"Re-analyzing date {date_key} for chat {chat_id}. Reverting previous points.")
        old_data = existing_doc.to_dict()
        old_offenders = old_data.get('offenders', [])
        
        # Revert old points
        for offender in old_offenders:
            user_id = offender.get('user_id')
            if not user_id: continue
            
            user_stats_ref = db.collection("chats").document(str_chat_id).collection("user_stats").document(str(user_id))
            doc = await user_stats_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                if data.get('season_id') == current_season:
                    # Subtract points
                    reverted_points = max(0, data.get("total_points", 0) - offender.get('points', 0))
                    # Decrement snitch count (assuming 1 win/violation per daily record)
                    reverted_wins = max(0, data.get("snitch_count", 0) - 1)
                    reverted_rank = calculate_rank(reverted_points)
                    
                    await user_stats_ref.update({
                        "total_points": reverted_points,
                        "snitch_count": reverted_wins,
                        "current_rank": reverted_rank
                    })

    # 2. Save the NEW daily result record
    await daily_ref.set(analysis_result)
    
    # 3. Update user stats for EACH offender (New points)
    offenders = analysis_result.get('offenders', [])
    
    for offender in offenders:
        user_id = offender.get('user_id')
        if not user_id:
            continue
            
        user_stats_ref = db.collection("chats").document(str_chat_id).collection("user_stats").document(str(user_id))
        
        # Get current stats
        doc = await user_stats_ref.get()
        
        current_points = 0
        current_wins = 0 # Count as "Days with violations"
        
        if doc.exists:
            data = doc.to_dict()
            if data.get('season_id') == current_season:
                current_points = data.get("total_points", 0)
                current_wins = data.get("snitch_count", 0)
        
        new_points = current_points + offender.get('points', 0)
        new_wins = current_wins + 1
        new_rank = calculate_rank(new_points)

        await user_stats_ref.set({
            "username": offender['username'],
            "season_id": current_season,
            "snitch_count": new_wins,
            "total_points": new_points,
            "current_rank": new_rank,
            "last_title": offender.get('title', '-'),
            "last_win_date": date_key
        }, merge=True)

def calculate_rank(points):
    """
    Calculates the Snitch Rank based on total points.
    Theme: Prison Caste (Reverse/Ironic)
    """
    if points >= 1500:
        return "Масть Проткнутая 👑"
    elif points >= 750:
        return "Обиженный 🚽"
    elif points >= 250:
        return "Козёл 🐐"
    elif points >= 50:
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
