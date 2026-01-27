from google.cloud import firestore
from datetime import datetime, timezone, timedelta
import logging
from ..utils.game_config import config

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

    # Detect forwarded messages to prevent false positive attribution
    is_forward = False
    # Check forward_origin (Bot API 7.0+) or legacy fields
    if getattr(message, 'forward_origin', None) or \
       getattr(message, 'forward_date', None) or \
       getattr(message, 'forward_from', None) or \
       getattr(message, 'forward_from_chat', None):
        is_forward = True

    if is_forward and text_content:
        text_content = f"[FORWARD] {text_content}"

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
    
    logging.debug(f"Writing message {msg_id} to Firestore (Chat: {chat_id})...")
    await doc_ref.set(data)
    logging.debug(f"Message {msg_id} written successfully.")

    # Update user's last active date
    try:
        user_stats_ref = db.collection("chats").document(chat_id).collection("user_stats").document(user_id)
        await user_stats_ref.set({
            "username": message.from_user.username or message.from_user.first_name,
            "last_active_date": message.date,
            "full_name": message.from_user.full_name # Ensure name is up to date
        }, merge=True)
    except Exception as e:
        logging.error(f"Failed to update last_active_date for user {user_id}: {e}")

async def save_agreement(chat_id: int, agreement: dict):
    """
    Saves a new agreement found by AI.
    agreement: { "text": "...", "users": [...], "created_at": ... }
    """
    chat_id = str(chat_id)
    coll_ref = db.collection("chats").document(chat_id).collection("agreements")
    
    data = agreement.copy()
    data['status'] = 'active'
    # Ensure timestamp is set to SERVER_TIMESTAMP to avoid AI hallucinated dates
    # or invalid string formats. We trust the agreement is being created "now" (during analysis).
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

async def check_afk_users(chat_id: int):
    """
    Checks for users who haven't written for 2+ days.
    Returns list of offenders.
    """
    chat_id = str(chat_id)
    stats_ref = db.collection("chats").document(chat_id).collection("user_stats")
    
    now = datetime.now(timezone.utc)
    offenders = []
    
    current_season = get_current_season_id()
    
    async for doc in stats_ref.stream():
        data = doc.to_dict()
        last_active = data.get('last_active_date')
        
        if not last_active:
            # Skip if no record (e.g. legacy data without date, or just created)
            # We assume they are active to avoid false positives during migration
            continue
            
        # Ensure last_active is datetime
        if not hasattr(last_active, 'timestamp'):
            continue
            
        # Check difference
        # Normalize to avoid TZ issues (comparing UTC to UTC)
        if last_active.tzinfo is None:
             last_active = last_active.replace(tzinfo=timezone.utc)
             
        diff = now - last_active
        days_inactive = diff.days
        
        if days_inactive >= config.IGNORE_DAYS_BEFORE_PENALTY:
            # Penalty Logic
            # Base: 50. Progressive: +50 for each extra day.
            
            extra_days = days_inactive - config.IGNORE_DAYS_BEFORE_PENALTY
            points = config.POINTS_AFK_BASE + (extra_days * config.POINTS_AFK_DAILY)
            
            username = data.get('username', 'Ghost')
            
            offenders.append({
                "user_id": doc.id,
                "username": username,
                "category": "Snitching", # AFK is a form of betrayal
                "reason": f"AFK в чате: {days_inactive} дн. молчания",
                "points": points,
                "quote": None
            })
            
    return offenders

async def apply_weekly_amnesty(chat_id: int):
    """
    Applies weekly amnesty: Points accumulated in the LAST 7 DAYS are halved.
    Total points are reduced by (WeeklyPoints / 2).
    """
    chat_id = str(chat_id)
    daily_ref = db.collection("chats").document(chat_id).collection("daily_results")
    stats_ref = db.collection("chats").document(chat_id).collection("user_stats")
    
    # 1. Calculate the date range (Last 7 days excluding today? Or just last 7 entries?)
    # Let's say last 7 days.
    today = datetime.now()
    dates_to_check = []
    for i in range(7):
        d = today - timedelta(days=i)
        dates_to_check.append(d.strftime("%Y-%m-%d"))
        
    # 2. Aggregate weekly points per user
    weekly_points = {} # user_id -> points
    
    for date_key in dates_to_check:
        doc = await daily_ref.document(date_key).get()
        if doc.exists:
            data = doc.to_dict()
            offenders = data.get('offenders', [])
            for off in offenders:
                uid = str(off.get('user_id'))
                pts = off.get('points', 0)
                weekly_points[uid] = weekly_points.get(uid, 0) + pts
                
    if not weekly_points:
        logging.info(f"No points found for amnesty in last 7 days for chat {chat_id}.")
        return False
        
    # 3. Apply reduction
    current_season = get_current_season_id()
    
    for user_id, w_points in weekly_points.items():
        if w_points <= 0:
            continue
            
        reduction = w_points // 2
        if reduction <= 0:
            continue
            
        # Fetch user stats
        user_doc_ref = stats_ref.document(user_id)
        user_doc = await user_doc_ref.get()
        
        if user_doc.exists:
            data = user_doc.to_dict()
            if data.get('season_id') == current_season:
                current_total = data.get('total_points', 0)
                new_total = max(0, current_total - reduction)
                new_rank = calculate_rank(new_total)
                
                await user_doc_ref.update({
                    "total_points": new_total,
                    "current_rank": new_rank
                })
                logging.info(f"Amnesty applied for user {user_id}: -{reduction} points (Weekly: {w_points}).")
                
    return True

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

async def get_recent_messages(chat_id: int, before_timestamp: datetime, limit: int = 5):
    """
    Fetches the last N messages before a specific timestamp for context.
    """
    chat_ref = db.collection("chats").document(str(chat_id))
    messages_ref = chat_ref.collection("messages")
    
    # Query: timestamp < before_timestamp, ORDER BY timestamp DESC, LIMIT limit
    query = messages_ref.where(filter=firestore.FieldFilter("timestamp", "<", before_timestamp))\
                        .order_by("timestamp", direction=firestore.Query.DESCENDING)\
                        .limit(limit)
    
    logs = []
    async for doc in query.stream():
        data = doc.to_dict()
        data['message_id'] = doc.id
        logs.append(data)
        
    # Reverse to return in chronological order
    logs.reverse()
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
            "last_win_date": date_key
        }, merge=True)

def calculate_rank(points):
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

async def get_message(chat_id: int, message_id: int):
    """
    Fetches a specific message by ID.
    """
    chat_id = str(chat_id)
    message_id = str(message_id)
    doc_ref = db.collection("chats").document(chat_id).collection("messages").document(message_id)
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
    
    logging.debug(f"Writing reaction {reaction_id} to Firestore...")
    await doc_ref.set(data)
    logging.debug(f"Reaction {reaction_id} written successfully.")

async def record_gamble_result(chat_id: int, user_id: int, new_points: int, date_key: str):
    """
    Updates user stats after a gamble.
    """
    chat_id = str(chat_id)
    user_id = str(user_id)
    user_stats_ref = db.collection("chats").document(chat_id).collection("user_stats").document(user_id)
    
    new_rank = calculate_rank(new_points)
    
    await user_stats_ref.set({
        "total_points": new_points,
        "current_rank": new_rank,
        "last_gamble_date": date_key
    }, merge=True)

async def increment_false_report_count(chat_id: int, user_id: int):
    """
    Increments the false report counter and returns the new value.
    """
    chat_id = str(chat_id)
    user_id = str(user_id)
    user_stats_ref = db.collection("chats").document(chat_id).collection("user_stats").document(user_id)
    
    doc = await user_stats_ref.get()
    
    current_count = 0
    if doc.exists:
        data = doc.to_dict()
        current_count = data.get("false_report_count", 0)
        
    new_count = current_count + 1
    
    await user_stats_ref.set({
        "false_report_count": new_count
    }, merge=True)
    
    return new_count

async def apply_penalty(chat_id: int, user_id: int, points: int):
    """
    Applies immediate penalty points.
    """
    chat_id = str(chat_id)
    user_id = str(user_id)
    user_stats_ref = db.collection("chats").document(chat_id).collection("user_stats").document(user_id)
    
    doc = await user_stats_ref.get()
    current_points = 0
    
    if doc.exists:
        data = doc.to_dict()
        current_points = data.get("total_points", 0)
        
    new_points = current_points + points
    new_rank = calculate_rank(new_points)
    
    await user_stats_ref.set({
        "total_points": new_points,
        "current_rank": new_rank
    }, merge=True)
