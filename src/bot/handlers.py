from aiogram import Router, types, F
from aiogram.filters import Command
from ..services.db import log_message, db
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
    Show current snitch stats.
    """
    # Fetch stats from Firestore
    chat_id = str(message.chat.id)
    stats_ref = db.collection("chats").document(chat_id).collection("user_stats")
    
    # Sort by total_points
    docs = stats_ref.order_by("total_points", direction="DESCENDING").limit(10).stream()
    
    text = "🏆 **Топ Снитчей (Иерархия):**\n\n"
    i = 1
    async for doc in docs:
        data = doc.to_dict()
        rank = data.get('current_rank', 'Порядочный 😐')
        points = data.get('total_points', 0)
        wins = data.get('snitch_count', 0)
        
        text += f"{i}. {data.get('username', 'Unknown')} — {points} очков\n"
        text += f"   Масть: {rank}\n"
        text += f"   Побед: {wins} | Последний титул: {data.get('last_title', '-')}\n\n"
        i += 1
        
    await message.answer(text, parse_mode="Markdown")

@router.message(F.text)
async def handle_messages(message: types.Message):
    """
    Catch all text messages and log them.
    """
    # Log to Firestore
    try:
        await log_message(message)
    except Exception as e:
        logging.error(f"Failed to log message: {e}")
