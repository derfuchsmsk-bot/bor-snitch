from aiogram import Router, types, F
from aiogram.types import MessageReactionUpdated
from aiogram.filters import Command
from ..services.db import log_message, db, get_user_stats, mark_message_reported, log_reaction, get_current_season_id
from ..services.ai import validate_report
from ..utils.text import escape
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
    stats_list.sort(key=lambda x: x.get('total_points', 0), reverse=True)
    
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
        last_title = escape(data.get('last_title', '-'))
        
        text += f"{i}. {username} — {points} очков\n"
        text += f"   Масть: {rank}\n"
        text += f"   Снитч Дня: {wins} | Последняя малява: {last_title}\n\n"
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
        "🔹 <b>Нытье</b> — 10 pts\n"
        "🔹 <b>Духота/Игнор</b> — 15 pts\n"
        "🔹 <b>Кринж</b> — 20 pts\n"
        "🔹 <b>Токсичность</b> — 25 pts\n"
        "🔹 <b>Снитчевание</b> — 50 pts\n\n"
        "⚠️ <b>Особые правила:</b>\n"
        "🤡 Реакция клоуна = Токсичность\n"
        "👻 Игнор тега = Духота или Токсичность\n"
        "🧹 <b>Еженедельная Амнистия:</b> Каждое воскресенье очки делятся на 2.\n\n"
        "👑 <b>Масти:</b>\n"
        "▫️ 0-49: Порядочный 😐\n"
        "▫️ 50-249: Шнырь 🧹\n"
        "▫️ 250-749: Козёл 🐐\n"
        "▫️ 750-1499: Обиженный 🚽\n"
        "▫️ 1500+: Масть Проткнутая 👑"
    )
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
    if stats and stats.get('season_id') != current_season:
        stats = None # Treat as clean for this season

    if not stats:
        await message.answer(f"👤 <b>{escape(target_user.full_name)}</b> без косяков. (0 очков)", parse_mode="HTML")
        return

    rank = escape(stats.get('current_rank', 'Порядочный 😐'))
    points = stats.get('total_points', 0)
    wins = stats.get('snitch_count', 0)
    last_title = escape(stats.get('last_title', 'Нет'))
    
    text = (
        f"👤 <b>Личное Дело:</b> {escape(target_user.full_name)}\n\n"
        f"🏷️ <b>Масть:</b> {rank}\n"
        f"⚖️ <b>Очки:</b> {points}\n"
        f"🏆 <b>Снитч Дня:</b> {wins}\n"
        f"🔖 <b>Последняя малява:</b> {last_title}"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(Command("report"))
async def cmd_report(message: types.Message):
    """
    Report a message for being 'bad'.
    """
    if not message.reply_to_message or not message.reply_to_message.text:
        await message.answer("❌ <b>Ошибка:</b> Используйте команду ответом на сообщение снитча.", parse_mode="HTML")
        return

    reported_msg = message.reply_to_message
    
    # Don't let users report themselves (optional, but logical)
    if reported_msg.from_user.id == message.from_user.id:
        await message.answer("❌ Самодонос? Это конечно похвально, но нет.")
        return

    status_msg = await message.answer("🕵️‍♂️ <b>Анализ доноса...</b>", parse_mode="HTML")
    
    # Validate with AI
    result = await validate_report(reported_msg.text)
    
    if result and result.get("valid"):
        category = escape(result.get("category", "Unspecified"))
        reason = escape(result.get("reason", "Violation detected"))
        
        # Mark in DB
        await mark_message_reported(
            message.chat.id,
            reported_msg.message_id,
            message.from_user.id,
            f"{category}: {reason}"
        )
        
        await status_msg.edit_text(
            f"✅ <b>Донос принят!</b>\n\n"
            f"📂 <b>Категория:</b> {category}\n"
            f"📝 <b>Вердикт:</b> {reason}\n"
            f"👮‍♂️ <i>Ну ты конечно козёл.</i>",
            parse_mode="HTML"
        )
    else:
        deny_reason = escape(result.get("reason", "Not a violation") if result else "AI Error")
        await status_msg.edit_text(
            f"❌ <b>Отклонено.</b>\n\n"
            f"Это не масть. Хватит спамить, ты уже ходишь под вопросом, клоун.\n"
            f"<i>(Причина: {deny_reason})</i>",
            parse_mode="HTML"
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
