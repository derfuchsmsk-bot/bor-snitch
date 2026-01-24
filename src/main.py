from fastapi import FastAPI, Request, Header, HTTPException
from aiogram import Bot, Dispatcher, types
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.utils.config import settings
from src.bot.handlers import router
from src.services.db import get_logs_for_date, save_daily_results, apply_weekly_decay, db
from src.services.ai import analyze_daily_logs
from datetime import datetime, timezone
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

app = FastAPI()
scheduler = AsyncIOScheduler()

# Initialize Bot and Dispatcher
# Bot is initialized globally here
bot = Bot(token=settings.TELEGRAM_TOKEN)

async def scheduled_weekly_decay():
    """
    Runs weekly decay for all active chats.
    """
    logging.info("Starting scheduled weekly decay...")
    try:
        # Assuming all docs in 'chats' are active chats
        chats_ref = db.collection("chats")
        async for chat_doc in chats_ref.stream():
            chat_data = chat_doc.to_dict()
            if not chat_data.get("active"):
                continue
                
            chat_id = chat_doc.id
            logging.info(f"Applying decay for chat {chat_id}")
            await apply_weekly_decay(chat_id)
            
            # Announce
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text="🧹 *Еженедельная Амнистия!*\n\nОчки всех моргунчиков поделены на двое. У вас есть шанс исправиться (или замаститься снова).",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logging.error(f"Failed to send decay announcement to {chat_id}: {e}")
                
    except Exception as e:
        logging.error(f"Error in scheduled decay: {e}")

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
    
    # Start Scheduler (Every Sunday at 23:59 UTC)
    scheduler.add_job(scheduled_weekly_decay, 'cron', day_of_week='sun', hour=23, minute=59)
    scheduler.start()

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
        await save_daily_results(chat_id, result)
        
        # Announce in chat
        offenders = result.get('offenders', [])
        
        if not offenders:
            text = "✨ *ИТОГИ ДНЯ* ✨\n\nСегодня в чате царила гармония. Ни одного нарушения! 🕊️"
        else:
            text = "🚨 *ИТОГИ ДНЯ* 🚨\n\n"
            i = 1
            for off in offenders:
                quote = off.get('quote')
                username = off.get('username', 'Аноним')
                user_id = off.get('user_id')
                if user_id:
                    text += f"{i}. 👤 [{username}](tg://user?id={user_id}) (+{off.get('points', 0)} pts)\n"
                else:
                    text += f"{i}. 👤 *{username}* (+{off.get('points', 0)} pts)\n"
                text += f"   🏆 *Титул:* {off.get('title', '-')}\n"
                text += f"   📝 *Вердикт:* {off.get('reason', '-')}\n"
                if quote:
                    text += f"   💬 _{quote}_\n"
                text += "\n"
                i += 1
               
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
        
    return {"status": "analyzed", "result": result}

@app.post("/weekly_decay")
async def weekly_decay(request: Request, x_secret_token: str = Header(None, alias="X-Secret-Token")):
    """
    Halve points for all users.
    Triggered by Cloud Scheduler weekly.
    """
    if x_secret_token != settings.SECRET_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")
        
    data = await request.json()
    chat_id = data.get("chat_id")
    
    if not chat_id:
        raise HTTPException(status_code=400, detail="Missing chat_id")
        
    await apply_weekly_decay(chat_id)
    
    await bot.send_message(
        chat_id=chat_id,
        text="🧹 *Еженедельная Амнистия!*\n\nОчки всех мастюганов поделены на двое. У вас есть шанс исправиться (или замаститься снова).",
        parse_mode="Markdown"
    )
    
    return {"status": "decayed"}
    
@app.get("/")
async def health_check():
    return {"status": "ok", "service": "BorSnitchBot"}
