from aiogram import Router, types, F
from aiogram.types import MessageReactionUpdated
from aiogram.filters import Command
from ..services.db import log_message, db, get_user_stats, mark_message_reported, log_reaction, get_current_season_id, get_active_agreements, get_recent_messages, get_subsequent_messages, get_message, record_gamble_result, increment_false_report_count, add_points, update_edited_message, get_chat_users
from ..services.ai import validate_report, transcribe_media, generate_cynical_comment
from ..utils.text import escape
from ..utils.game_config import config
from datetime import datetime, timezone, timedelta
import logging
from io import BytesIO
import random

router = Router()

# Global state for cynical comment cooldowns (chat_id -> datetime)
last_comment_time = {}

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Я Снитч-бот. Я слежу за вами. 👁️")
    # Save chat to active chats
    await db.collection("chats").document(str(message.chat.id)).set({"active": True}, merge=True)

@router.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """
    Show current season snitch stats.
    """
    # Fetch stats from Firestore
    chat_id = str(message.chat.id)
    stats_ref = db.collection("chats").document(chat_id).collection("user_stats")
    
    # Get current season
    current_season = get_current_season_id()
    
    # Fetch all and filter in python to handle "lazy reset" view
    # (Users with old season_id shouldn't appear in current leaderboard)
    docs = stats_ref.stream()
    stats_list = []
    
    async for doc in docs:
        data = doc.to_dict()
        if data.get('season_id') == current_season:
            stats_list.append(data)
            
    # Sort by total_points DESC
    stats_list.sort(key=lambda x: int(x.get('total_points', 0)), reverse=True)
    
    # Take top 10
    top_stats = stats_list[:10]
    
    text = f"🏆 <b>Топ Снитчей (Сезон {current_season}):</b>\n\n"
    
    if not top_stats:
        text += "Пока пусто. Сезон только начался! 🍂"
    
    i = 1
    for data in top_stats:
        rank = escape(data.get('current_rank', 'Порядочный 😐'))
        points = data.get('total_points', 0)
        wins = data.get('snitch_count', 0)
        username = escape(data.get('username', 'Unknown'))
        if not username.startswith("@"):
             username = f"@{username}"
        
        text += f"{i}. {username} — {points} очков\n"
        text += f"   🃏Масть: {rank}\n"
        
        # Achievements in body
        achievements = data.get('achievements', [])
        if achievements:
            ach_list = []
            for ach in achievements:
                if isinstance(ach, dict):
                    icon = ach.get('icon', '')
                    title = ach.get('title', '')
                    if title:
                        ach_list.append(f"{title}{icon}")
                elif isinstance(ach, str):
                    ach_list.append(ach)
            
            if ach_list:
                text += f"   🏅Ачивки: {', '.join(ach_list)}\n"

        text += "\n"
        i += 1
        
    await message.answer(text, parse_mode="HTML")

@router.message(Command("rules"))
async def cmd_rules(message: types.Message):
    """
    Show the rules and point system.
    """
    text = (
        "📜 <b>Кодекс Снитча</b>\n\n"
        "За что начисляются очки (суммируются за день):\n"
        f"🔹 <b>Нытье</b> — {config.POINTS_WHINING} pts\n"
        f"🔹 <b>Духота</b> — {config.POINTS_STIFFNESS} pts\n"
        f"🔹 <b>Токсичность</b> — {config.POINTS_TOXICITY} pts\n"
        f"🔹 <b>Снитчевание (Игнор/Предательство)</b> — {config.POINTS_SNITCHING} pts\n"
        f"🔹 <b>AFK (Молчанка)</b> — {config.POINTS_AFK_BASE}+ pts (2 дня тишины = 50, далее +50 за день)\n"
        f"🔹 <b>Ложные доносы</b> — +{config.FALSE_REPORT_PENALTY} pts (за каждые {config.FALSE_REPORT_LIMIT} отклоненных репорта)\n\n"
        "🎰 <b>Казино (/casino):</b>\n"
        f"Раз в сутки можно испытать удачу.\n"
        f"Победа: -{config.GAMBLE_WIN_POINTS} pts | Проигрыш: +{config.GAMBLE_LOSS_POINTS} pts\n\n"
        "⚠️ <b>Особые правила:</b>\n"
        "🤡 Реакция клоуна = Токсичность\n"
        "👻 Игнор тега = Духота или Токсичность\n"
        "🧹 <b>Еженедельная Амнистия:</b> Каждое воскресенье очки за неделю делятся на 2.\n\n"
        "👑 <b>Масти:</b>\n"
        f"▫️ {config.RANK_NORMAL[0]}-{config.RANK_NORMAL[1]}: Порядочный 😐\n"
        f"▫️ {config.RANK_SHNYR[0]}-{config.RANK_SHNYR[1]}: Шнырь 🧹\n"
        f"▫️ {config.RANK_GOAT[0]}-{config.RANK_GOAT[1]}: Козёл 🐐\n"
        f"▫️ {config.RANK_OFFENDED[0]}-{config.RANK_OFFENDED[1]}: Обиженный 🚽\n"
        f"▫️ {config.RANK_PIERCED[0]}+: Масть Проткнутая 👑"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(Command("agreements"))
async def cmd_agreements(message: types.Message):
    """
    Show active agreements.
    """
    agreements = await get_active_agreements(message.chat.id)
    
    if not agreements:
        await message.answer("🤝 <b>Договоренности:</b>\n\nНет действующих договоренностей. Живите спокойно... пока что.", parse_mode="HTML")
        return

    text = "🤝 <b>Действующие договоренности:</b>\n\n"
    
    for i, ag in enumerate(agreements, 1):
        agreement_text = escape(ag.get('text', '???'))
        
        # Format date
        created_at = ag.get('created_at')
        date_str = "?"
        if created_at:
             # Assuming created_at is a datetime object or similar (Firestore Timestamp)
             try:
                 # Check if it has method strftime
                 if hasattr(created_at, 'strftime'):
                     date_str = created_at.strftime("%d.%m.%Y")
                 else:
                     # It might be a datetime string or something else, just cast to str
                     date_str = str(created_at).split(' ')[0]
             except Exception:
                 date_str = "Unknown"

        text += f"{i}. {agreement_text} <i>(от {date_str})</i>\n"

    await message.answer(text, parse_mode="HTML")

@router.message(Command("all"))
async def cmd_all(message: types.Message):
    """
    Tag all users in the chat.
    """
    users = await get_chat_users(message.chat.id)
    
    if not users:
        await message.answer("В этом чате еще никто не отметился... кроме тебя, возможно.")
        return

    # Filter out the bot itself if it somehow got into user_stats (though unlikely based on log_message)
    # Also we might want to avoid tagging the person who called the command, but usually /all tags everyone.
    
    mentions = []
    for u in users:
        user_id = u['user_id']
        username = u['username']
        full_name = u['full_name'] or "Аноним"
        
        if username:
            mentions.append(f"@{username}")
        else:
            mentions.append(f"<a href='tg://user?id={user_id}'>{escape(full_name)}</a>")
    
    if not mentions:
        await message.answer("Некого тегать.")
        return

    # Split into chunks of 50 to avoid Telegram limits
    chunk_size = 50
    for i in range(0, len(mentions), chunk_size):
        chunk = mentions[i:i + chunk_size]
        text = "📣 <b>ВНИМАНИЕ ВСЕМ!</b>\n\n" + " ".join(chunk)
        await message.answer(text, parse_mode="HTML")

@router.message(Command("status", "me"))
async def cmd_status(message: types.Message):
    """
    Show personal stats or stats of the replied user.
    """
    target_user = message.from_user
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user

    stats = await get_user_stats(message.chat.id, target_user.id)
    
    current_season = get_current_season_id()
    
    # Check if stats are from current season
    achievements = []
    if stats:
        achievements = stats.get('achievements', [])
        if stats.get('season_id') != current_season:
            # Reset seasonal stats for display, but keep achievements
            # We modify a copy or just set keys on the dict since it's transient
            stats['total_points'] = 0
            stats['snitch_count'] = 0
            stats['current_rank'] = 'Порядочный 😐'

    if not stats:
        await message.answer(f"👤 <b>{escape(target_user.full_name)}</b> без косяков. (0 очков)", parse_mode="HTML")
        return

    rank = escape(stats.get('current_rank', 'Порядочный 😐'))
    points = stats.get('total_points', 0)
    wins = stats.get('snitch_count', 0)
    
    display_name = escape(target_user.full_name)
    if target_user.username:
        display_name = f"@{target_user.username}"

    text = (
        f"👤 <b>Личное Дело:</b> {display_name}\n\n"
        f"🃏 <b>Масть:</b> {rank}\n"
        f"⚖️ <b>Очки:</b> {points}"
    )

    if achievements:
        text += "\n\n🏅 <b>Ачивки:</b>\n"
        for ach in achievements:
            if isinstance(ach, str):
                text += f"• {escape(ach)}\n"
            elif isinstance(ach, dict):
                icon = ach.get('icon', '🎖')
                title = escape(ach.get('title', 'Unknown'))
                description = escape(ach.get('description', ''))
                text += f"{icon} <b>{title}</b>"
                if description:
                    text += f" — <i>{description}</i>"
                text += "\n"

    await message.answer(text, parse_mode="HTML")

@router.message(Command("report"))
async def cmd_report(message: types.Message):
    """
    Report a message for being 'bad'.
    """
    if not message.reply_to_message:
        await message.answer("❌ <b>Ошибка:</b> Используйте команду ответом на сообщение снитча.", parse_mode="HTML")
        return

    reported_msg = message.reply_to_message
    target_text = reported_msg.text
    
    # If no text, check if it's media that might have been transcribed
    if not target_text and (reported_msg.voice or reported_msg.video_note):
        # Fetch from DB to see if we have transcription
        stored_msg = await get_message(message.chat.id, reported_msg.message_id)
        if stored_msg:
             target_text = stored_msg.get('text')
    
    # Check for sticker
    if not target_text and reported_msg.sticker:
        target_text = f"[STICKER] {reported_msg.sticker.emoji or 'Unknown'} (ID: {reported_msg.sticker.file_unique_id})"
    
    if not target_text:
        await message.answer("❌ <b>Ошибка:</b> Сообщение не содержит текста, стикера или еще не обработано.", parse_mode="HTML")
        return
    
    # Don't let users report themselves (optional, but logical)
    if reported_msg.from_user.id == message.from_user.id:
        await message.answer("❌ Самодонос? Это конечно похвально, но нет.")
        return

    status_msg = await message.answer("🕵️‍♂️ <b>Анализ доноса...</b>", parse_mode="HTML")
    
    # Fetch context (Use limit from config)
    # We fetch PREVIOUS messages (context limit) AND SUBSEQUENT messages (fixed small limit, e.g. 5)
    prev_msgs = await get_recent_messages(message.chat.id, reported_msg.date, limit=config.REPORT_CONTEXT_LIMIT)
    next_msgs = await get_subsequent_messages(message.chat.id, reported_msg.date, limit=5)
    
    context_msgs = prev_msgs + next_msgs
    
    # Validate with AI
    result = await validate_report(target_text, context_msgs)
    
    if result and result.get("valid"):
        category = escape(result.get("category", "Unspecified"))
        reason = escape(result.get("reason", "Violation detected"))
        points = result.get("points", 0)
        
        # Mark in DB
        await mark_message_reported(
            message.chat.id,
            reported_msg.message_id,
            message.from_user.id,
            f"{category}: {reason}",
            points_awarded=points
        )
        
        # Award points immediately
        await add_points(message.chat.id, reported_msg.from_user.id, points)
        
        await status_msg.edit_text(
            f"✅ <b>Донос принят!</b>\n\n"
            f"📂 <b>Категория:</b> {category} (+{points} pts)\n"
            f"📝 <b>Вердикт:</b> {reason}\n"
            f"⚖️ <i>Очки начислены моментально.</i>",
            parse_mode="HTML"
        )
    else:
        # Increment false report count
        new_count = await increment_false_report_count(message.chat.id, message.from_user.id)
        
        deny_reason = escape(result.get("reason", "Not a violation") if result else "AI Error")
        response_text = (
            f"❌ <b>Отклонено.</b>\n\n"
            f"Это не масть. Хватит спамить, ты уже ходишь под вопросом, клоун 🤡🤡🤡\n"
            f"<i>(Причина: {deny_reason})</i>"
        )
        
        # Check for penalty
        if new_count % config.FALSE_REPORT_LIMIT == 0:
            await add_points(message.chat.id, message.from_user.id, config.FALSE_REPORT_PENALTY)
            response_text += (
                f"\n\n🚨 <b>Ты конкретный снитч: +{config.FALSE_REPORT_PENALTY} очков.</b>\n"
                f"<i>(Ложных доносов подряд: {new_count})</i>"
            )
            
        await status_msg.edit_text(response_text, parse_mode="HTML")

@router.message(Command("casino"))
async def cmd_casino(message: types.Message):
    """
    Daily gambling mechanic (Roulette).
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Check cooldown (Moscow Time)
    tz_moscow = timezone(timedelta(hours=3))
    now = datetime.now(tz_moscow)
    today_str = now.strftime("%Y-%m-%d")
    
    stats = await get_user_stats(chat_id, user_id)
    if stats and stats.get('last_gamble_date') == today_str:
        await message.reply("Ты уже лудил сегодня, додеп только завтра.")
        return

    # Roll
    is_win = random.random() < config.GAMBLE_WIN_CHANCE
    logging.info(f"Casino roll for user {user_id} in chat {chat_id}: {'WIN' if is_win else 'LOSS'} (Chance: {config.GAMBLE_WIN_CHANCE})")
    
    current_points = stats.get('total_points', 0) if stats else 0
    
    if is_win:
        # Win: Remove points (Good)
        deduction = config.GAMBLE_WIN_POINTS
        new_points = max(0, current_points - deduction)
        text = (
            f"🎰 <b>ЗАНОС!</b>\n\n"
            f"Тебе фартануло. Сняли {deduction} очков.\n"
            f"Текущий счет: {new_points}"
        )
    else:
        # Lose: Add points (Bad)
        penalty = config.GAMBLE_LOSS_POINTS
        new_points = current_points + penalty
        text = (
            f"🎰 <b>АХХАХАХАХАХ ОСЁЛ ЕБАНЫЙ, А ДОДЕПНУТЬ НЕ ПОЛУЧИТСЯ АХАХАХАХХА!</b>\n\n"
            f"Ты проиграл. +{penalty} очков.\n"
            f"Текущий счет: {new_points}"
        )
        
    await record_gamble_result(chat_id, user_id, new_points, today_str)
    await message.reply(text, parse_mode="HTML")

@router.message_reaction()
async def handle_reactions(reaction: MessageReactionUpdated):
    """
    Log reactions to messages.
    """
    # We only care about added reactions
    
    # Check what was added
    old_emojis = {r.emoji for r in reaction.old_reaction if hasattr(r, 'emoji')}
    new_emojis = {r.emoji for r in reaction.new_reaction if hasattr(r, 'emoji')}
    
    added = new_emojis - old_emojis
    
    if not added:
        return
        
    # Log each added emoji
    for emoji in added:
        logging.debug(f"Processing reaction: {emoji} for message {reaction.message_id}")
        await log_reaction(
            chat_id=reaction.chat.id,
            user_id=reaction.user.id,
            username=reaction.user.username or reaction.user.first_name,
            message_id=reaction.message_id,
            emoji=emoji,
            timestamp=reaction.date
        )

@router.edited_message()
async def handle_edited_messages(message: types.Message):
    """
    Handle edited messages and update them in Firestore.
    """
    logging.debug(f"Processing edited message {message.message_id} in chat {message.chat.id}")
    await update_edited_message(message)

@router.message(F.text | F.sticker | F.voice | F.video_note)
async def handle_messages(message: types.Message):
    """
    Catch all text messages, stickers, voices, and video notes; log them.
    Also handles random cynical comments.
    """
    override_text = None

    # Handle Voice & Video Notes
    if message.voice or message.video_note:
        try:
            file_id = message.voice.file_id if message.voice else message.video_note.file_id
            logging.debug(f"Starting processing for media file_id: {file_id}")
            
            file_info = await message.bot.get_file(file_id)
            
            # Download to memory
            file_io = BytesIO()
            await message.bot.download_file(file_info.file_path, file_io)
            file_bytes = file_io.getvalue()
            logging.debug(f"Downloaded media file. Size: {len(file_bytes)} bytes")
            
            mime_type = "audio/ogg" if message.voice else "video/mp4"
            
            # Transcribe
            logging.debug(f"Transcribing media ({mime_type})...")
            transcription = await transcribe_media(file_bytes, mime_type)
            logging.debug(f"Transcription result: {transcription[:100]}...")
            
            prefix = "[VOICE]" if message.voice else "[VIDEO NOTE]"
            override_text = f"{prefix} {transcription}"
            
        except Exception as e:
            logging.error(f"Failed to transcribe media: {e}", exc_info=True)
            override_text = f"[{'VOICE' if message.voice else 'VIDEO NOTE'}] (Transcription Failed)"
    
    # Handle Stickers
    if message.sticker:
         override_text = f"[STICKER] {message.sticker.emoji or 'Unknown'} (File ID: {message.sticker.file_unique_id})"

    # Log to Firestore
    try:
        logging.debug(f"Logging message {message.message_id} to DB (override_text={bool(override_text)})...")
        await log_message(message, override_text=override_text)
        logging.debug(f"Message {message.message_id} logged successfully.")
    except Exception as e:
        logging.error(f"Failed to log message: {e}", exc_info=True)

    # Random Cynical Comment Logic
    # Only for text messages, not commands, and not if we just handled media/stickers (unless we want to comment on them too? Let's stick to text for now)
    if message.text and not message.text.startswith('/'):
        try:
            if random.random() < config.CYNICAL_COMMENT_CHANCE:
                chat_id = message.chat.id
                now = datetime.now()
                last_time = last_comment_time.get(chat_id)
                
                # Check cooldown
                if not last_time or (now - last_time).total_seconds() > config.CYNICAL_COMMENT_COOLDOWN_SECONDS:
                    # Generate comment
                    # Get small context for immediate reply
                    context_msgs = await get_recent_messages(chat_id, message.date, limit=5)
                    username = message.from_user.username or message.from_user.first_name
                    comment = await generate_cynical_comment(context_msgs, message.text, username)
                    
                    if comment:
                        await message.reply(comment)
                        last_comment_time[chat_id] = now
                        logging.info(f"Sent cynical comment to chat {chat_id}")
        except Exception as e:
            logging.error(f"Error in cynical comment logic: {e}")
