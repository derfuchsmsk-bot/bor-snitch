from aiogram import Router, types, F
from aiogram.types import MessageReactionUpdated
from aiogram.filters import Command
from ..services.db import log_message, db, get_user_stats, mark_message_reported, log_reaction, get_current_season_id, get_active_agreements, get_recent_messages, get_subsequent_messages, get_message, record_gamble_result, increment_false_report_count, add_points, update_edited_message, get_chat_users, dispute_agreement
from ..services.ai import validate_report, transcribe_media, generate_cynical_comment, validate_fact
from ..services.fact_service import FactService
from ..utils.text import escape
from ..utils.game_config import config
from ..utils import messages
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
    await db.collection("chats").document(str(message.chat.id)).set({"active": True}, merge=True)

@router.message(Command("stats"))
async def cmd_stats(message: types.Message):
    chat_id = str(message.chat.id)
    stats_ref = db.collection("chats").document(chat_id).collection("user_stats")
    current_season = get_current_season_id()
    
    docs = stats_ref.stream()
    stats_list = []
    
    async for doc in docs:
        data = doc.to_dict()
        if data.get('season_id') == current_season:
            stats_list.append(data)
            
    stats_list.sort(key=lambda x: int(x.get('total_points', 0)), reverse=True)
    top_stats = stats_list[:10]
    
    text = f"🏆 <b>Топ Снитчей (Сезон {current_season}):</b>\n\n"
    if not top_stats:
        text += "Пока пусто. Сезон только начался! 🍂"
    
    for i, data in enumerate(top_stats, 1):
        rank = escape(data.get('current_rank', 'Порядочный 😐'))
        points = data.get('total_points', 0)
        username = escape(data.get('username', 'Unknown'))
        if not username.startswith("@"):
             username = f"@{username}"
        
        text += f"{i}. {username} — {points} очков\n"
        text += f"   🃏Масть: {rank}\n"
        
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
        
    await message.answer(text, parse_mode="HTML")

@router.message(Command("rules"))
async def cmd_rules(message: types.Message):
    await message.answer(messages.RULES_TEXT, parse_mode="HTML")

@router.message(Command("agreements"))
async def cmd_agreements(message: types.Message):
    if not config.ENABLE_AGREEMENTS:
        return
    agreements = await get_active_agreements(message.chat.id)
    if not agreements:
        await message.answer("🤝 <b>Договоренности:</b>\n\nНет действующих договоренностей. Живите спокойно... пока что.", parse_mode="HTML")
        return

    text = "🤝 <b>Слово Пацана (Действующие):</b>\n\n"
    for i, ag in enumerate(agreements, 1):
        agreement_text = escape(ag.get('text', '???'))
        ag_type = ag.get('type', 'vow')
        
        icon = "🕯" # vow
        if ag_type == "pact": icon = "🤝"
        elif ag_type == "public": icon = "📢"
        
        status_icon = "⏳"
        
        expires_at = ag.get('expires_at')
        time_str = ""
        if expires_at:
            if hasattr(expires_at, 'strftime'):
                time_str = f" (до {expires_at.strftime('%d.%m %H:%M')})"
        
        users = ag.get('users', [])
        users_str = ", ".join([f"<b>{escape(u if u.startswith('@') else '@'+u)}</b>" for u in users])
        text += f"{i}. {status_icon} {icon} {users_str}: <b>{agreement_text}</b>{time_str} (Оспорить: /disput {i})\n"

    await message.answer(text, parse_mode="HTML")

@router.message(Command("dispute", "disput"))
async def cmd_dispute(message: types.Message):
    if not config.ENABLE_AGREEMENTS:
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Укажи ID договоренности или порядковый номер из последнего отчета.\nПример: /dispute 1")
        return

    # In a real scenario we might map number to ID from session state,
    # but here we'll assume they pass the ID or we'd need to fetch the last analysis result.
    # For now, let's look for the agreement by ID if it's long, or by "recent index" if it's small.
    # To keep it simple, we'll fetch active agreements and use the index.
    
    try:
        idx = int(args[1]) - 1
        active = await get_active_agreements(message.chat.id)
        if 0 <= idx < len(active):
            target_id = active[idx]['id']
            success, error_code = await dispute_agreement(message.chat.id, target_id)
            if success:
                await message.answer(messages.AGREEMENT_DISPUTE_SUCCESS, parse_mode="HTML")
            else:
                if error_code == "too_late":
                    await message.answer(messages.AGREEMENT_DISPUTE_TOO_LATE, parse_mode="HTML")
                else:
                    await message.answer(messages.AGREEMENT_DISPUTE_NOT_FOUND, parse_mode="HTML")
        else:
            await message.answer(messages.AGREEMENT_DISPUTE_NOT_FOUND, parse_mode="HTML")
    except ValueError:
        # Try as direct ID
        target_id = args[1]
        success, error_code = await dispute_agreement(message.chat.id, target_id)
        if success:
            await message.answer(messages.AGREEMENT_DISPUTE_SUCCESS, parse_mode="HTML")
        else:
             await message.answer(messages.AGREEMENT_DISPUTE_NOT_FOUND, parse_mode="HTML")

@router.message(Command("all"))
async def cmd_all(message: types.Message):
    users = await get_chat_users(message.chat.id)
    if not users:
        await message.answer(messages.NO_USERS_TO_TAG)
        return

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

    chunk_size = config.MENTION_CHUNK_SIZE
    for i in range(0, len(mentions), chunk_size):
        chunk = mentions[i:i + chunk_size]
        text = messages.ALL_COMMAND_TITLE + " ".join(chunk)
        await message.answer(text, parse_mode="HTML")

@router.message(Command("status", "me"))
async def cmd_status(message: types.Message):
    target_user = message.from_user
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user

    stats = await get_user_stats(message.chat.id, target_user.id)
    current_season = get_current_season_id()
    
    achievements = []
    if stats:
        achievements = stats.get('achievements', [])
        if stats.get('season_id') != current_season:
            stats['total_points'] = 0
            stats['snitch_count'] = 0
            stats['current_rank'] = 'Порядочный 😐'

    if not stats:
        await message.answer(f"👤 <b>{escape(target_user.full_name)}</b> без косяков. (0 очков)", parse_mode="HTML")
        return

    rank = escape(stats.get('current_rank', 'Порядочный 😐'))
    points = stats.get('total_points', 0)
    
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
    if not message.reply_to_message:
        await message.answer("❌ <b>Ошибка:</b> Используйте команду ответом на сообщение снитча.", parse_mode="HTML")
        return

    reported_msg = message.reply_to_message
    target_text = reported_msg.text
    
    if not target_text and (reported_msg.voice or reported_msg.video_note):
        stored_msg = await get_message(message.chat.id, reported_msg.message_id)
        if stored_msg:
             target_text = stored_msg.get('text')
    
    if not target_text and reported_msg.sticker:
        target_text = f"[STICKER] {reported_msg.sticker.emoji or 'Unknown'} (ID: {reported_msg.sticker.file_unique_id})"
    
    if not target_text:
        await message.answer("❌ <b>Ошибка:</b> Сообщение не содержит текста, стикера или еще не обработано.", parse_mode="HTML")
        return
    
    if reported_msg.from_user.id == message.from_user.id:
        await message.answer("❌ Самодонос? Это конечно похвально, но нет.")
        return

    status_msg = await message.answer(messages.REPORT_ANALYSIS_START, parse_mode="HTML")
    
    prev_msgs = await get_recent_messages(message.chat.id, reported_msg.date, limit=config.REPORT_CONTEXT_LIMIT)
    next_msgs = await get_subsequent_messages(message.chat.id, reported_msg.date, limit=config.REPORT_NEXT_CONTEXT_LIMIT)
    
    context_msgs = prev_msgs + next_msgs
    result = await validate_report(target_text, context_msgs, chat_id=message.chat.id)
    
    if result and result.get("valid"):
        category = escape(result.get("category", "Unspecified"))
        reason = escape(result.get("reason", "Violation detected"))
        points = result.get("points", 0)
        ai_thoughts = result.get("ai_thought_process")
        
        await mark_message_reported(
            message.chat.id,
            reported_msg.message_id,
            message.from_user.id,
            f"{category}: {reason}",
            points_awarded=points,
            ai_thought_process=ai_thoughts
        )
        await add_points(message.chat.id, reported_msg.from_user.id, points)
        
        await status_msg.edit_text(
            messages.REPORT_ACCEPTED.format(category=category, points=points, reason=reason),
            parse_mode="HTML"
        )
    else:
        new_count = await increment_false_report_count(message.chat.id, message.from_user.id)
        deny_reason = escape(result.get("reason", "Not a violation") if result else "AI Error")
        response_text = messages.REPORT_REJECTED.format(reason=deny_reason)
        
        if new_count % config.FALSE_REPORT_LIMIT == 0:
            await add_points(message.chat.id, message.from_user.id, config.FALSE_REPORT_PENALTY)
            response_text += messages.REPORT_PENALTY.format(penalty=config.FALSE_REPORT_PENALTY, count=new_count)
            
        await status_msg.edit_text(response_text, parse_mode="HTML")

@router.message(Command("casino"))
async def cmd_casino(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    tz_moscow = timezone(timedelta(hours=config.TIMEZONE_OFFSET))
    now = datetime.now(tz_moscow)
    today_str = now.strftime("%Y-%m-%d")
    
    stats = await get_user_stats(chat_id, user_id)
    if stats and stats.get('last_gamble_date') == today_str:
        await message.reply(messages.CASINO_ALREADY_PLAYED)
        return

    is_win = random.random() < config.GAMBLE_WIN_CHANCE
    current_points = stats.get('total_points', 0) if stats else 0
    
    if is_win:
        deduction = config.GAMBLE_WIN_POINTS
        new_points = max(0, current_points - deduction)
        text = messages.CASINO_WIN.format(deduction=deduction, new_points=new_points)
    else:
        penalty = config.GAMBLE_LOSS_POINTS
        new_points = current_points + penalty
        text = messages.CASINO_LOSS.format(penalty=penalty, new_points=new_points)
        
    await record_gamble_result(chat_id, user_id, new_points, today_str)
    await message.reply(text, parse_mode="HTML")

@router.message(Command("remember"))
async def cmd_remember(message: types.Message):
    """
    Manually add a fact to verified_facts.
    Example: /remember Vanya has a new car
    Or reply to a message with /remember
    """
    fact_text = ""
    if message.reply_to_message:
        fact_text = message.reply_to_message.text or message.reply_to_message.caption
    else:
        fact_text = message.text.replace("/remember", "").strip()

    if not fact_text:
        await message.answer("❌ Что запомнить? Напиши после команды или ответь на сообщение.")
        return

    status_msg = await message.answer("🤔 Проверяю твой «факт» на вшивость...")
    
    validation = await validate_fact(fact_text)
    
    if not validation.get("is_fact"):
        reason = validation.get("reason", "Это не похоже на полезный факт.")
        await status_msg.edit_text(f"❌ <b>Отказ:</b> {escape(reason)}", parse_mode="HTML")
        return

    final_fact = validation.get("cleaned_fact") or fact_text
    
    success = await FactService.add_fact(message.chat.id, final_fact, source=f"user_{message.from_user.id}")
    if success:
        if final_fact.strip() != fact_text.strip():
            await status_msg.edit_text(f"✅ <b>Запомнил в нормальном виде:</b>\n<i>{escape(final_fact)}</i>", parse_mode="HTML")
        else:
            await status_msg.edit_text("✅ <b>Запомнил.</b> Теперь это истина.", parse_mode="HTML")
    else:
        await status_msg.edit_text("❌ Не удалось запомнить. Видимо, я перегружен.")

@router.message_reaction()
async def handle_reactions(reaction: MessageReactionUpdated):
    old_emojis = {r.emoji for r in reaction.old_reaction if hasattr(r, 'emoji')}
    new_emojis = {r.emoji for r in reaction.new_reaction if hasattr(r, 'emoji')}
    added = new_emojis - old_emojis
    
    if not added:
        return
        
    for emoji in added:
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
    await update_edited_message(message)

def should_comment(text: str, stats: dict) -> bool:
    """
    Logic for 'Smart' Cynical Comments.
    """
    if not text or text.startswith('/'):
        return False
        
    chance = config.CYNICAL_COMMENT_CHANCE
    text_lower = text.lower()
    
    # Keyword triggers (strongest trigger)
    if any(kw in text_lower for kw in ["бот", "bot", "снитч", "snitch", "ии", "ai"]):
        chance += 0.15
    
    # Question trigger (native dialogue integration)
    if "?" in text:
        chance += 0.05
    
    # Emotional trigger
    if "!" in text:
        chance += 0.02
        
    # Rant trigger
    if len(text) > 150:
        chance += 0.05
        
    # High points target trigger (roast the sinners)
    if stats and stats.get('total_points', 0) > 100:
        chance += 0.02
        
    return random.random() < chance

@router.message(F.text | F.sticker | F.voice | F.video_note)
async def handle_messages(message: types.Message):
    override_text = None
    if message.voice or message.video_note:
        try:
            file_id = message.voice.file_id if message.voice else message.video_note.file_id
            file_info = await message.bot.get_file(file_id)
            file_io = BytesIO()
            await message.bot.download_file(file_info.file_path, file_io)
            file_bytes = file_io.getvalue()
            mime_type = "audio/ogg" if message.voice else "video/mp4"
            transcription = await transcribe_media(file_bytes, mime_type)
            prefix = "[VOICE]" if message.voice else "[VIDEO NOTE]"
            override_text = f"{prefix} {transcription}"
        except Exception as e:
            logging.error(f"Failed to transcribe media: {e}")
            override_text = f"[{'VOICE' if message.voice else 'VIDEO NOTE'}] (Transcription Failed)"
    
    if message.sticker:
         override_text = f"[STICKER] {message.sticker.emoji or 'Unknown'} (File ID: {message.sticker.file_unique_id})"

    try:
        await log_message(message, override_text=override_text)
    except Exception as e:
        logging.error(f"Failed to log message: {e}")

    # Cynical Comment Logic
    comment_text = message.text or override_text
    if comment_text and not comment_text.startswith('/'):
        try:
            chat_id = message.chat.id
            now = datetime.now()
            last_time = last_comment_time.get(chat_id)
            
            # Robust Mention Detection: @bot or reply to bot
            bot_user = await message.bot.get_me()
            is_mentioned = False
            
            if message.text:
                is_mentioned = f"@{bot_user.username}" in message.text
            
            if not is_mentioned and message.reply_to_message:
                is_mentioned = message.reply_to_message.from_user.id == bot_user.id
            
            # If mentioned, ignore cooldown. Otherwise check cooldown.
            if is_mentioned or (not last_time or (now - last_time).total_seconds() > config.CYNICAL_COMMENT_COOLDOWN_SECONDS):
                user_stats = await get_user_stats(chat_id, message.from_user.id)
                
                # If mentioned, force reply. Otherwise roll dice.
                if is_mentioned or should_comment(comment_text, user_stats):
                    context_msgs = await get_recent_messages(chat_id, message.date, limit=5)
                    username = message.from_user.username or message.from_user.first_name
                    comment = await generate_cynical_comment(context_msgs, comment_text, username, chat_id=chat_id)
                    
                    if comment:
                        # Detection of corrections in the comment text if we want to be fancy,
                        # but for now let's check the USER'S input for "wrong/неправда"
                        
                        await message.reply(comment)
                        last_comment_time[chat_id] = now

                # Correction Loop: If user says "Это неправда" or "Ты врешь" etc.
                correction_keywords = ["неправда", "врешь", "забудь", "ошибка", "wrong", "lie", "hallucination"]
                if is_mentioned and any(kw in comment_text.lower() for kw in correction_keywords):
                    # Try to find what exactly was wrong.
                    # For simplicity, we remove the last mentioned fact if it's a direct reply to bot
                    if message.reply_to_message and message.reply_to_message.from_user.id == bot_user.id:
                        # We don't know exactly WHICH fact was wrong, but we can log it or
                        # just acknowledge that the bot might have hallucinated.
                        # Real implementation would use AI to extract the "wrong" fact.
                        await message.reply("🤐 Понял, завязываю галлюцинировать. Если я сказал что-то не то — сорян.")
        except Exception as e:
            logging.error(f"Error in cynical comment logic: {e}")
