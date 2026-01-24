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
    # Fetch stats from Firestore (simplified for now)
    # Ideally, we query the 'user_stats' subcollection
    chat_id = str(message.chat.id)
    stats_ref = db.collection("chats").document(chat_id).collection("user_stats")
    docs = stats_ref.order_by("snitch_count", direction="DESCENDING").limit(5).stream()
    
    text = "🏆 **Топ Снитчей:**\n\n"
    i = 1
    async for doc in docs:
        data = doc.to_dict()
        text += f"{i}. {data.get('username', 'Unknown')} — {data.get('snitch_count', 0)} раз(а)\n"
        text += f"   Last title: {data.get('last_title', 'N/A')}\n"
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
