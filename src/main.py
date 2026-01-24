from fastapi import FastAPI, Request, Header, HTTPException
from aiogram import Bot, Dispatcher, types
from src.utils.config import settings
from src.bot.handlers import router
from src.services.db import get_logs_for_date, save_daily_winner
from src.services.ai import analyze_daily_logs
from datetime import datetime, timezone
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

app = FastAPI()

# Initialize Bot and Dispatcher
# Bot is initialized globally here
bot = Bot(token=settings.TELEGRAM_TOKEN)

@app.on_event("startup")
async def on_startup():
    """
    Set bot commands on startup.
    """
    commands = [
        types.BotCommand(command="status", description="Мое личное дело"),
        types.BotCommand(command="stats", description="Топ Снитчей"),
        types.BotCommand(command="rules", description="Кодекс Снитча"),
        types.BotCommand(command="report", description="Донести на ближнего (Reply)"),
    ]
    await bot.set_my_commands(commands)
dp = Dispatcher()
dp.include_router(router)

@app.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Handle incoming Telegram updates.
    """
    try:
        update_data = await request.json()
        update = types.Update(**update_data)
        await dp.feed_update(bot, update)
        return {"status": "ok"}
    except Exception as e:
        logging.error(f"Webhook error: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/analyze_daily")
async def analyze_daily(request: Request, x_secret_token: str = Header(None, alias="X-Secret-Token")):
    """
    Trigger daily analysis.
    Called by Cloud Scheduler.
    Payload: {"chat_id": 123456}
    """
    # Verify secret token
    if x_secret_token != settings.SECRET_TOKEN:
        # Allow checking query param or generic auth if header not set by scheduler easily
        # For now strict check
        raise HTTPException(status_code=403, detail="Invalid token")
        
    data = await request.json()
    chat_id = data.get("chat_id")
    
    if not chat_id:
        raise HTTPException(status_code=400, detail="Missing chat_id")
        
    # Get logs for current UTC day
    # Note: If users are in UTC+3, and scheduler runs at 21:00 UTC (00:00 MSK), 
    # we should check which 'date_key' we are targeting.
    # For MVP: We assume scheduler runs at 23:50 UTC and we analyze current UTC date.
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    logging.info(f"Starting analysis for chat {chat_id} date {today_str}")
    
    logs = await get_logs_for_date(chat_id, today_str)
    
    if not logs:
        logging.info("No logs found.")
        await bot.send_message(chat_id=chat_id, text="Сегодня слишком тихо... Снитч не найден. (Нет логов)")
        return {"status": "no logs"}
        
    result = await analyze_daily_logs(logs)
    
    if result:
        # Add date info
        result['date_key'] = today_str
        
        # Save to DB
        await save_daily_winner(chat_id, result)
        
        # Announce in chat
        text = f"🚨 **ИТОГИ ДНЯ** 🚨\n\n" \
               f"🏆 **Снитч дня:** {result.get('username', 'Аноним')}\n" \
               f"👑 **Титул:** {result.get('title', 'Неизвестный')}\n" \
               f"📝 **Вердикт:** {result.get('reason', 'Нет описания')}"
               
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
        
    return {"status": "analyzed", "result": result}
    
@app.get("/")
async def health_check():
    return {"status": "ok", "service": "BorSnitchBot"}
