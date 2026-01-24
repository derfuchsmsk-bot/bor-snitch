from aiogram import Router, types, F
from aiogram.types import MessageReactionUpdated
from aiogram.filters import Command
from ..services.db import log_message, db, get_user_stats, mark_message_reported, log_reaction
from ..services.ai import validate_report
from datetime import datetime, timezone
import logging

router = Router()

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
    current_season = datetime.now(timezone.utc).strftime("%Y-%m")
    
    # Fetch all and filter in python to handle "lazy reset" view
    # (Users with old season_id shouldn't appear in current leaderboard)
    docs = stats_ref.stream()
    stats_list = []
    
    async for doc in docs:
        data = doc.to_dict()
        if data.get('season_id') == current_season:
            stats_list.append(data)
            
    # Sort by total_points DESC
    stats_list.sort(key=lambda x: x.get('total_points', 0), reverse=True)
    
    # Take top 10
    top_stats = stats_list[:10]
    
    text = f"🏆 *Топ Снитчей (Сезон {current_season}):*\n\n"
    
    if not top_stats:
        text += "Пока пусто. Сезон только начался! 🍂"
    
    i = 1
    for data in top_stats:
        rank = data.get('current_rank', 'Порядочный 😐')
        points = data.get('total_points', 0)
        wins = data.get('snitch_count', 0)
        
        text += f"{i}. {data.get('username', 'Unknown')} — {points} очков\n"
        text += f"   Масть: {rank}\n"
        text += f"   Побед: {wins} | Последний титул: {data.get('last_title', '-')}\n\n"
        i += 1
        
    await message.answer(text, parse_mode="Markdown")

@router.message(Command("rules"))
async def cmd_rules(message: types.Message):
    """
    Show the rules and point system.
    """
    text = (
        "📜 *Кодекс Снитча*\n\n"
        "За что начисляются очки (суммируются за день):\n"
        "🔹 *Нытье (Whining)* — 10 pts\n"
        "🔹 *Духота/Игнор (Stiffness)* — 15 pts\n"
        "🔹 *Кринж (Cringe)* — 20 pts\n"
        "🔹 *Токсичность (Toxicity)* — 25 pts\n"
        "🔹 *Предательство (Betrayal)* — 50 pts\n\n"
        "⚠️ *Особые правила:*\n"
        "🤡 Реакция клоуна = Токсичность\n"
        "👻 Игнор тега = Духота или Токсичность\n"
        "🧹 *Еженедельная Амнистия:* Каждое воскресенье очки делятся на 2.\n\n"
        "👑 *Иерархия:*\n"
        "▫️ 0-49: Порядочный 😐\n"
        "▫️ 50-249: Шнырь 🧹\n"
        "▫️ 250-749: Козёл 🐐\n"
        "▫️ 750-1499: Обиженный 🚽\n"
        "▫️ 1500+: Масть Проткнутая 👑"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(Command("status", "me"))
async def cmd_status(message: types.Message):
    """
    Show personal stats or stats of the replied user.
    """
    target_user = message.from_user
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user

    stats = await get_user_stats(message.chat.id, target_user.id)
    
    current_season = datetime.now(timezone.utc).strftime("%Y-%m")
    
    # Check if stats are from current season
    if stats and stats.get('season_id') != current_season:
        stats = None # Treat as clean for this season

    if not stats:
        await message.answer(f"👤 *{target_user.full_name}* пока чист перед законом в этом сезоне. (0 очков)")
        return

    rank = stats.get('current_rank', 'Порядочный 😐')
    points = stats.get('total_points', 0)
    wins = stats.get('snitch_count', 0)
    last_title = stats.get('last_title', 'Нет')
    
    text = (
        f"👤 *Личное Дело:* {target_user.full_name}\n\n"
        f"🏷️ *Звание:* {rank}\n"
        f"⚖️ *Очки:* {points}\n"
        f"🏆 *Побед (Снитч Дня):* {wins}\n"
        f"🔖 *Последний титул:* {last_title}"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(Command("report"))
async def cmd_report(message: types.Message):
    """
    Report a message for being 'bad'.
    """
    if not message.reply_to_message or not message.reply_to_message.text:
        await message.answer("❌ *Ошибка:* Используйте команду ответом на сообщение нарушителя.")
        return

    reported_msg = message.reply_to_message
    
    # Don't let users report themselves (optional, but logical)
    if reported_msg.from_user.id == message.from_user.id:
        await message.answer("❌ Самодонос? Это конечно похвально, но нет.")
        return

    status_msg = await message.answer("🕵️‍♂️ *Анализ доноса...*")
    
    # Validate with AI
    result = await validate_report(reported_msg.text)
    
    if result and result.get("valid"):
        category = result.get("category", "Unspecified")
        reason = result.get("reason", "Violation detected")
        
        # Mark in DB
        await mark_message_reported(
            message.chat.id,
            reported_msg.message_id,
            message.from_user.id,
            f"{category}: {reason}"
        )
        
        await status_msg.edit_text(
            f"✅ *Донос принят!*\n\n"
            f"📂 *Категория:* {category}\n"
            f"📝 *Вердикт:* {reason}\n"
            f"👮‍♂️ _Администрация благодарит вас за бдительность._",
            parse_mode="Markdown"
        )
    else:
        deny_reason = result.get("reason", "Not a violation") if result else "AI Error"
        await status_msg.edit_text(
            f"❌ *Отклонено.*\n\n"
            f"Это не нарушение. Хватит спамить, или сам поедешь в карцер.\n"
            f"_(Причина: {deny_reason})_",
            parse_mode="Markdown"
        )

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
        await log_reaction(
            chat_id=reaction.chat.id,
            user_id=reaction.user.id,
            username=reaction.user.username or reaction.user.first_name,
            message_id=reaction.message_id,
            emoji=emoji,
            timestamp=reaction.date
        )

@router.message(F.text | F.sticker)
async def handle_messages(message: types.Message):
    """
    Catch all text messages and stickers and log them.
    """
    # Log to Firestore
    try:
        await log_message(message)
    except Exception as e:
        logging.error(f"Failed to log message: {e}")
