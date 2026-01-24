from fastapi import FastAPI, Request, Header, HTTPException
from aiogram import Bot, Dispatcher, types
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.utils.config import settings
from src.bot.handlers import router
from src.services.db import get_logs_for_time_range, save_daily_results, apply_weekly_decay, db, get_active_agreements, save_agreement
from src.services.ai import analyze_daily_logs
from src.utils.text import escape
from datetime import datetime, timezone, timedelta, time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

app = FastAPI()
scheduler = AsyncIOScheduler()

# Initialize Bot and Dispatcher
# Bot is initialized globally here
bot = Bot(token=settings.TELEGRAM_TOKEN)

async def perform_chat_analysis(chat_id: str):
    """
    Core logic for daily analysis.
    """
    # Calculate time window: 23:50 MSK to 23:50 MSK
    msk_tz = timezone(timedelta(hours=3))
    now_msk = datetime.now(msk_tz)
    
    # Determine the date we are analyzing.
    # If it's early morning (e.g. before 4 AM), we assume we are finalizing yesterday's business.
    # Otherwise (e.g. 12:00 or 23:50), we are analyzing Today.
    analysis_date = now_msk.date()
    if now_msk.hour < 4:
         analysis_date -= timedelta(days=1)
         
    # End of window is always 23:50 of the analysis_date
    end_dt_msk = datetime.combine(analysis_date, time(23, 50), tzinfo=msk_tz)
    
    start_dt_msk = end_dt_msk - timedelta(days=1)
    
    # Convert to UTC for DB query
    end_dt_utc = end_dt_msk.astimezone(timezone.utc)
    start_dt_utc = start_dt_msk.astimezone(timezone.utc)
    
    # Date key for saving results (Use MSK date of the end of the period)
    today_str = end_dt_msk.strftime("%Y-%m-%d")
    
    # Fetch active agreements
    active_agreements = await get_active_agreements(chat_id)
    
    logging.info(f"Starting analysis for chat {chat_id}. Window (MSK): {start_dt_msk} to {end_dt_msk}")
    
    logs = await get_logs_for_time_range(chat_id, start_dt_utc, end_dt_utc)
    
    if not logs:
        logging.info("No logs found.")
        await bot.send_message(chat_id=chat_id, text="Сегодня слишком тихо... Снитч не найден. (Нет логов)")
        return {"status": "no logs"}
        
    result = await analyze_daily_logs(logs, active_agreements=active_agreements)
    
    if result:
        # Add date info
        result['date_key'] = today_str
        
        # Save to DB
        await save_daily_results(chat_id, result)
        
        # Save New Agreements
        new_agreements = result.get('new_agreements', [])
        for ag in new_agreements:
            await save_agreement(chat_id, ag)
        
        # Announce in chat
        offenders = result.get('offenders', [])
        
        if not offenders:
            text = "✨ <b>ИТОГИ ДНЯ</b> ✨\n\nСегодня в чате царила гармония. Ни одного нарушения! 🕊️"
        else:
            text = "🚨 <b>ИТОГИ ДНЯ</b> 🚨\n\n"
            i = 1
            for off in offenders:
                quote = off.get('quote')
                username = escape(off.get('username', 'Аноним'))
                user_id = off.get('user_id')
                title = escape(off.get('title', '-'))
                reason = escape(off.get('reason', '-'))
                
                if user_id:
                    text += f"{i}. 👤 <a href='tg://user?id={user_id}'>{username}</a> (+{off.get('points', 0)} pts)\n"
                else:
                    text += f"{i}. 👤 <b>{username}</b> (+{off.get('points', 0)} pts)\n"
                text += f"   🏆 <b>Малява по этапу:</b> {title}\n"
                text += f"   📝 <b>Вердикт:</b> {reason}\n"
                if quote:
                    text += f"   💬 <i>{escape(quote)}</i>\n"
                text += "\n"
                i += 1
        
        if new_agreements:
            text += "\n🤝 <b>Новые договоренности:</b>\n"
            for ag in new_agreements:
                 text += f"📌 {escape(ag.get('text'))}\n"
                 
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
        
    return {"status": "analyzed", "result": result}

async def scheduled_daily_analysis():
    """
    Runs daily analysis for all active chats.
    """
    logging.info("Starting scheduled daily analysis...")
    try:
        chats_ref = db.collection("chats")
        async for chat_doc in chats_ref.stream():
            chat_data = chat_doc.to_dict()
            if not chat_data.get("active"):
                continue
            
            chat_id = chat_doc.id
            logging.info(f"Running daily analysis for chat {chat_id}")
            try:
                await perform_chat_analysis(chat_id)
            except Exception as e:
                logging.error(f"Failed to analyze chat {chat_id}: {e}")
                
    except Exception as e:
        logging.error(f"Error in scheduled analysis: {e}")

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
                    text="🧹 <b>Еженедельная Амнистия!</b>\n\nОчки всех моргунчиков поделены на двое. У вас есть шанс исправиться (или замаститься снова).",
                    parse_mode="HTML"
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
        types.BotCommand(command="report", description="Донос (Reply)"),
    ]
    await bot.set_my_commands(commands)
    
    # Start Scheduler
    # Weekly Decay: Every Sunday at 23:59 UTC
    scheduler.add_job(scheduled_weekly_decay, 'cron', day_of_week='sun', hour=23, minute=59)
    
    # NOTE: Daily analysis is triggered externally by Cloud Scheduler to support Serverless architecture.
    # See setup instructions for Cloud Scheduler configuration.
    
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
        
    return await perform_chat_analysis(chat_id)

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
        text="🧹 <b>Еженедельная Амнистия!</b>\n\nОчки всех мастюганов поделены на двое. У вас есть шанс исправиться (или замаститься снова).",
        parse_mode="HTML"
    )
    
    return {"status": "decayed"}
    
@app.get("/")
async def health_check():
    return {"status": "ok", "service": "BorSnitchBot"}
