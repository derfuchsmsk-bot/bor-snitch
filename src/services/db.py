import asyncio
import warnings
from google.cloud import firestore
from ..utils.config import settings
from datetime import datetime, timezone, timedelta
import logging
from ..utils.game_config import config
from ..database import db
from ..repositories.user_repository import user_repository
from ..repositories.message_repository import message_repository
from ..repositories.agreement_repository import agreement_repository

def get_current_season_id():
    """Returns the current season ID (Global)."""
    return "global" # Single season forever, only weekly decay

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
        "is_bot": getattr(message.from_user, 'is_bot', False),
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
        await user_repository.update_user_last_active(
            chat_id,
            user_id,
            message.date,
            message.from_user.username or message.from_user.first_name,
            message.from_user.full_name
        )
    except Exception as e:
        logging.error(f"Failed to update last_active_date for user {user_id}: {e}")

async def save_agreement(chat_id: int, agreement: dict):
    """
    [DEPRECATED] Use agreement_repository.save_agreement directly.
    Saves a new agreement found by AI.
    agreement: { "text": "...", "users": [...], "type": "...", "expires_at": "..." }
    """
    warnings.warn("save_agreement is deprecated, use agreement_repository.save_agreement instead", DeprecationWarning, stacklevel=2)
    data = agreement.copy()
    data['status'] = 'active'
    # Ensure timestamp is set to SERVER_TIMESTAMP to avoid AI hallucinated dates
    data['created_at'] = firestore.SERVER_TIMESTAMP
    
    # 15 minutes window for dispute
    dispute_delta = timedelta(minutes=config.AGREEMENT_DISPUTE_WINDOW_MINUTES)
    data['can_be_disputed_until'] = datetime.now(timezone.utc) + dispute_delta
    
    # Handle expiry if provided by AI, else default 24h
    if not data.get('expires_at'):
        data['expires_at'] = datetime.now(timezone.utc) + timedelta(hours=config.AGREEMENT_DEFAULT_LIFESPAN_HOURS)
    elif isinstance(data['expires_at'], str):
        try:
            data['expires_at'] = datetime.fromisoformat(data['expires_at'].replace('Z', '+00:00'))
        except Exception:
            data['expires_at'] = datetime.now(timezone.utc) + timedelta(hours=config.AGREEMENT_DEFAULT_LIFESPAN_HOURS)
        
    await agreement_repository.save_agreement(chat_id, data)

async def get_agreement_by_id(chat_id: int, agreement_id: str):
    """[DEPRECATED] Fetches a specific agreement."""
    warnings.warn("get_agreement_by_id is deprecated, use agreement_repository.get_agreement instead", DeprecationWarning, stacklevel=2)
    return await agreement_repository.get_agreement(chat_id, agreement_id)

async def dispute_agreement(chat_id: int, agreement_id: str):
    """
    [DEPRECATED] Marks an agreement as disputed if within the time window.
    Returns (success, message).
    """
    warnings.warn("dispute_agreement is deprecated, use agreement_repository.dispute_agreement instead", DeprecationWarning, stacklevel=2)
    return await agreement_repository.dispute_agreement(chat_id, agreement_id)

async def update_agreement_status(chat_id: int, agreement_id: str, status: str, reason: str = None):
    """[DEPRECATED] Updates agreement status (fulfilled/broken)."""
    warnings.warn("update_agreement_status is deprecated, use agreement_repository.update_agreement instead", DeprecationWarning, stacklevel=2)
    update_data = {"status": status}
    if reason:
        update_data["resolution_reason"] = reason
    
    await agreement_repository.update_agreement(chat_id, agreement_id, update_data)

async def update_agreement_text(chat_id: int, agreement_id: str, new_text: str, reason: str = None):
    """[DEPRECATED] Updates agreement text and optionally adds an update reason."""
    warnings.warn("update_agreement_text is deprecated, use agreement_repository.update_agreement instead", DeprecationWarning, stacklevel=2)
    update_data = {"text": new_text}
    if reason:
        update_data["update_reason"] = reason
    update_data["updated_at"] = firestore.SERVER_TIMESTAMP
    
    await agreement_repository.update_agreement(chat_id, agreement_id, update_data)

async def get_last_agreement_check(chat_id: str) -> datetime:
    """[DEPRECATED] Gets the timestamp of the last agreement check."""
    warnings.warn("get_last_agreement_check is deprecated, use agreement_repository.get_last_agreement_check instead", DeprecationWarning, stacklevel=2)
    return await agreement_repository.get_last_agreement_check(chat_id)

async def set_last_agreement_check(chat_id: str, ts: datetime):
    """[DEPRECATED] Sets the timestamp of the last agreement check."""
    warnings.warn("set_last_agreement_check is deprecated, use agreement_repository.set_last_agreement_check instead", DeprecationWarning, stacklevel=2)
    await agreement_repository.set_last_agreement_check(chat_id, ts)

async def get_active_agreements(chat_id: int):
    """
    [DEPRECATED] Fetches active agreements for the chat.
    """
    warnings.warn("get_active_agreements is deprecated, use agreement_repository.get_active_agreements instead", DeprecationWarning, stacklevel=2)
    return await agreement_repository.get_active_agreements(chat_id)

async def check_afk_users(chat_id: int):
    """
    Checks for users who haven't written for 2+ days.
    Returns list of offenders.
    """
    chat_id = str(chat_id)
    stats_ref = db.collection("chats").document(chat_id).collection("user_stats")
    
    # Use Moscow timezone for consistency with analysis logic
    moscow_tz = timezone(timedelta(hours=config.TIMEZONE_OFFSET))
    now_msk = datetime.now(moscow_tz)
    offenders = []
    
    current_season = get_current_season_id()
    
    async for doc in stats_ref.stream():
        data = doc.to_dict()
        last_active = data.get('last_active_date')
        
        if not last_active:
            # Skip if no record (e.g. legacy data without date, or just created)
            # We assume they are active to avoid false positives during migration
            continue
            
        # Ensure last_active is datetime and in Moscow timezone
        if not hasattr(last_active, 'timestamp'):
            continue
            
        # Convert to Moscow timezone for consistent comparison
        if last_active.tzinfo is None:
            last_active = last_active.replace(tzinfo=timezone.utc).astimezone(moscow_tz)
        else:
            last_active = last_active.astimezone(moscow_tz)
            
        # Calculate days inactive in Moscow timezone
        diff = now_msk - last_active
        days_inactive = diff.days
        
        if days_inactive >= config.IGNORE_DAYS_BEFORE_PENALTY:
            # Penalty Logic
            # Base: 50. Flat daily penalty (no progressive multiplier).
            
            points = config.POINTS_AFK_BASE
            
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
    Applies weekly amnesty: Halves the total points of every user in the chat.
    """
    chat_id = str(chat_id)
    stats_ref = db.collection("chats").document(chat_id).collection("user_stats")
    
    current_season = get_current_season_id()
    
    # 1. Fetch all user stats
    async for doc in stats_ref.stream():
        data = doc.to_dict()
        if data.get('season_id') == current_season:
            current_total = data.get('total_points', 0)
            new_total = max(0, current_total // 2)
            new_rank = calculate_rank(new_total)
            
            await doc.reference.update({
                "total_points": new_total,
                "current_rank": new_rank
            })
            logging.info(f"Amnesty applied for user {doc.id}: -{current_total - new_total} points (Total: {current_total}).")
    
    return True

async def get_logs_for_time_range(chat_id: int, start_dt: datetime, end_dt: datetime):
    """
    [DEPRECATED] Fetches messages within a specific time range [start_dt, end_dt).
    """
    warnings.warn("get_logs_for_time_range is deprecated, use message_repository.get_logs_for_time_range instead", DeprecationWarning, stacklevel=2)
    return await message_repository.get_logs_for_time_range(chat_id, start_dt, end_dt)

async def get_recent_messages(chat_id: int, before_timestamp: datetime, limit: int = 5):
    """
    [DEPRECATED] Fetches the last N messages before a specific timestamp for context.
    """
    warnings.warn("get_recent_messages is deprecated, use message_repository.get_recent_messages instead", DeprecationWarning, stacklevel=2)
    return await message_repository.get_recent_messages(chat_id, before_timestamp, limit)

async def get_subsequent_messages(chat_id: int, after_timestamp: datetime, limit: int = 5):
    """
    [DEPRECATED] Fetches the next N messages after a specific timestamp.
    """
    warnings.warn("get_subsequent_messages is deprecated, use message_repository.get_subsequent_messages instead", DeprecationWarning, stacklevel=2)
    return await message_repository.get_subsequent_messages(chat_id, after_timestamp, limit)

async def save_daily_results(chat_id: int, analysis_result: dict):
    """
    Saves the result of the daily analysis (list of offenders) atomically.
    Uses Firestore Transaction to prevent race conditions.
    analysis_result: { "offenders": [...], "date_key": ... }
    """
    str_chat_id = str(chat_id)
    date_key = analysis_result['date_key']
    current_season = get_current_season_id()
    
    daily_ref = db.collection("chats").document(str_chat_id).collection("daily_results").document(date_key)

    @firestore.async_transactional
    async def _save_in_transaction(transaction, daily_ref, analysis_result, str_chat_id, date_key, current_season):
        # 1. Read existing daily record
        existing_doc = await daily_ref.get(transaction=transaction)
        old_offenders_map = {}
        if existing_doc.exists:
            old_data = existing_doc.to_dict()
            for off in old_data.get('offenders', []):
                uid = str(off.get('user_id'))
                if uid:
                    old_offenders_map[uid] = off

        # 2. Identify all users to update
        new_offenders = analysis_result.get('offenders', [])
        new_offenders_map = {str(off.get('user_id')): off for off in new_offenders if off.get('user_id')}
        
        all_user_ids = set(old_offenders_map.keys()) | set(new_offenders_map.keys())
        
        # 3. Read all user stats
        user_stats_refs = {uid: db.collection("chats").document(str_chat_id).collection("user_stats").document(uid) for uid in all_user_ids}
        # In Firestore Transactions, we must perform all reads before any writes.
        # Use asyncio.gather for parallel reads to optimize performance.
        uids = list(user_stats_refs.keys())
        tasks = [user_stats_refs[uid].get(transaction=transaction) for uid in uids]
        results = await asyncio.gather(*tasks)
        user_stats_docs = dict(zip(uids, results))

        # 4. Calculate updates
        for uid in all_user_ids:
            stats_doc = user_stats_docs[uid]
            ref = user_stats_refs[uid]
            
            current_points = 0
            current_wins = 0
            username = "Unknown"
            
            if stats_doc.exists:
                data = stats_doc.to_dict()
                if data.get('season_id') == current_season:
                    current_points = data.get("total_points", 0)
                    current_wins = data.get("snitch_count", 0)
                    username = data.get("username", username)

            # Revert old points if user was in previous analysis
            if uid in old_offenders_map:
                old_offender = old_offenders_map[uid]
                current_points = max(0, current_points - old_offender.get('points', 0))
                current_wins = max(0, current_wins - 1)

            # Add new points if user is in current analysis
            if uid in new_offenders_map:
                new_offender = new_offenders_map[uid]
                current_points += new_offender.get('points', 0)
                current_wins += 1
                username = new_offender.get('username', username)

            new_rank = calculate_rank(current_points)
            
            # Prepare update
            transaction.set(ref, {
                "username": username,
                "season_id": current_season,
                "snitch_count": current_wins,
                "total_points": current_points,
                "current_rank": new_rank,
                "last_win_date": date_key
            }, merge=True)

        # 5. Save the daily result record
        transaction.set(daily_ref, analysis_result)
        
    # Execute the transaction
    transaction = db.transaction()
    await _save_in_transaction(transaction, daily_ref, analysis_result, str_chat_id, date_key, current_season)

def calculate_rank(points):
    """
    [DEPRECATED] Calculates the Snitch Rank based on total points.
    Theme: Prison Caste (Reverse/Ironic)
    """
    warnings.warn("calculate_rank is deprecated, use user_repository.calculate_rank instead", DeprecationWarning, stacklevel=2)
    return user_repository.calculate_rank(points)

async def get_user_stats(chat_id: int, user_id: int):
    """
    [DEPRECATED] Fetches stats for a specific user.
    """
    warnings.warn("get_user_stats is deprecated, use user_repository.get_user_stats instead", DeprecationWarning, stacklevel=2)
    return await user_repository.get_user_stats(chat_id, user_id)

async def get_message(chat_id: int, message_id: int):
    """
    [DEPRECATED] Fetches a specific message by ID.
    """
    warnings.warn("get_message is deprecated, use message_repository.get_message instead", DeprecationWarning, stacklevel=2)
    return await message_repository.get_message(chat_id, message_id)

async def mark_message_reported(chat_id: int, msg_id: int, reporter_id: int, reason: str, points_awarded: int = 0, ai_thought_process: str = None):
    """
    [DEPRECATED] Flags a message as reported by a user.
    """
    warnings.warn("mark_message_reported is deprecated, use message_repository.mark_message_reported instead", DeprecationWarning, stacklevel=2)
    await message_repository.mark_message_reported(chat_id, msg_id, reporter_id, reason, points_awarded, ai_thought_process)

async def log_reaction(chat_id: int, user_id: int, username: str, message_id: int, emoji: str, timestamp: datetime):
    """
    Logs a reaction event. Fetches the original message to provide context.
    """
    chat_id = str(chat_id)
    message_id = str(message_id)
    
    # Fetch original message
    msg_data = await message_repository.get_message(chat_id, message_id)
    
    original_text = "Unknown Message"
    target_user = "Unknown"
    
    if msg_data:
        original_text = msg_data.get("text", "")
        target_user = msg_data.get("username", "Unknown")
        
    # Create log entry
    # We use a composite key to avoid duplicates if needed, but timestamp is good enough
    reaction_id = f"reaction_{message_id}_{user_id}_{int(timestamp.timestamp())}"
    
    date_key = timestamp.strftime("%Y-%m-%d")
    
    log_text = f"[REACTION] {username} reacted {emoji} to {target_user}'s message: \"{original_text}\""
    
    data = {
        "message_id": reaction_id,
        "user_id": int(user_id),
        "username": username,
        "full_name": username, # Fallback
        "text": log_text,
        "timestamp": timestamp,
        "date_key": date_key,
        "type": "reaction",
        "target_msg_id": message_id
    }
    
    await message_repository.log_message(chat_id, data)

async def record_gamble_result(chat_id: int, user_id: int, new_points: int, date_key: str):
    """
    [DEPRECATED] Updates user stats after a gamble.
    """
    warnings.warn("record_gamble_result is deprecated, use user_repository.record_gamble_result instead", DeprecationWarning, stacklevel=2)
    await user_repository.record_gamble_result(chat_id, user_id, new_points, date_key)

async def increment_false_report_count(chat_id: int, user_id: int):
    """
    [DEPRECATED] Increments the false report counter and returns the new value.
    """
    warnings.warn("increment_false_report_count is deprecated, use user_repository.increment_false_report_count instead", DeprecationWarning, stacklevel=2)
    return await user_repository.increment_false_report_count(chat_id, user_id)

async def add_points(chat_id: int, user_id: int, points: int):
    """
    [DEPRECATED] Applies immediate points (penalty or reward).
    """
    warnings.warn("add_points is deprecated, use user_repository.add_points instead", DeprecationWarning, stacklevel=2)
    await user_repository.add_points(chat_id, user_id, points)

async def update_edited_message(message):
    """
    Updates an existing message in Firestore when it is edited.
    """
    chat_id = str(message.chat.id)
    msg_id = str(message.message_id)
    
    text_content = message.text or message.caption
    if not text_content and message.sticker:
        text_content = f"[STICKER] {message.sticker.emoji or 'Unknown'}"
        
    if not text_content:
        return

    update_data = {
        "text": text_content,
        "is_edited": True,
        "last_edit_date": message.edit_date
    }
    
    await message_repository.update_message(chat_id, msg_id, update_data)

async def get_chat_users(chat_id: int, limit: int = 100, cursor=None):
    """
    [DEPRECATED] Fetches users who have stats in the chat with pagination.
    Used for the /all command and management.
    """
    warnings.warn("get_chat_users is deprecated, use user_repository.get_chat_users instead", DeprecationWarning, stacklevel=2)
    return await user_repository.get_chat_users(chat_id, limit, cursor)

async def get_all_chats(limit: int = 20, cursor=None):
    """
    Fetches chats with pagination.
    """
    chats_ref = db.collection("chats")
    query = chats_ref.order_by("__name__").limit(limit)
    if cursor:
        query = query.start_after(cursor)
    
    chats = []
    last_doc = None
    async for doc in query.stream():
        data = doc.to_dict()
        data['id'] = doc.id
        chats.append(data)
        last_doc = doc
    return chats, last_doc
