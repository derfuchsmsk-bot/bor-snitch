from fastapi import FastAPI, Request, Header, HTTPException
from aiogram import Bot, Dispatcher, types
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.utils.config import settings
from src.bot.handlers import router
from src.services.db import get_logs_for_time_range, save_daily_results, apply_weekly_amnesty, db, get_active_agreements, save_agreement, check_afk_users
from src.services.ai import analyze_daily_logs
from src.utils.text import escape
from src.utils.game_config import config
from src.utils import messages
from datetime import datetime, timezone, timedelta, time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

app = FastAPI()
scheduler = AsyncIOScheduler()

# Initialize Bot and Dispatcher
bot = Bot(token=settings.TELEGRAM_TOKEN)

async def perform_chat_analysis(chat_id: str):
    """
    Core logic for daily analysis.
    """
    moscow_tz = timezone(timedelta(hours=config.TIMEZONE_OFFSET))
    now_msk = datetime.now(moscow_tz)
    
    # Determine the date we are analyzing.
    analysis_date = now_msk.date()
    if now_msk.hour < config.ANALYSIS_CUTOFF_HOUR:
         analysis_date -= timedelta(days=1)
         
    # End of window is always 23:50 of the analysis_date
    end_dt_msk = datetime.combine(analysis_date, time(23, 50), tzinfo=moscow_tz)
    start_dt_msk = end_dt_msk - timedelta(days=1)
    
    # Convert to UTC for DB query
    end_dt_utc = end_dt_msk.astimezone(timezone.utc)
    start_dt_utc = start_dt_msk.astimezone(timezone.utc)
    
    today_str = end_dt_msk.strftime("%Y-%m-%d")
    active_agreements = await get_active_agreements(chat_id)
    
    logging.info(f"Starting analysis for chat {chat_id}. Window (MSK): {start_dt_msk} to {end_dt_msk}")
    logs = await get_logs_for_time_range(chat_id, start_dt_utc, end_dt_utc)
    
    ai_result = None
    if logs:
        ai_result = await analyze_daily_logs(logs, active_agreements=active_agreements, date_str=today_str)
    
    afk_offenders = await check_afk_users(chat_id)
    
    if not logs and not afk_offenders:
        logging.info("No logs and no AFK violations.")
        await bot.send_message(chat_id=chat_id, text="Сегодня слишком тихо... Снитч не найден. (Нет логов и нарушений)")
        return {"status": "no logs"}

    final_result = {
        "offenders": [],
        "new_agreements": []
    }
    
    if ai_result:
        final_result["offenders"].extend(ai_result.get("offenders", []))
        final_result["new_agreements"].extend(ai_result.get("new_agreements", []))
        
    final_result["offenders"].extend(afk_offenders)
    
    if final_result:
        final_result['date_key'] = today_str
        await save_daily_results(chat_id, final_result)
        
        new_agreements = final_result.get('new_agreements', [])
        for ag in new_agreements:
            await save_agreement(chat_id, ag)
        
        offenders = final_result.get('offenders', [])
        
        if not offenders:
            text = messages.DAILY_SUMMARY_TITLE + messages.DAILY_NO_OFFENDERS
        else:
            text = messages.DAILY_OFFENDERS_TITLE
            for i, off in enumerate(offenders, 1):
                quote = off.get('quote')
                username = escape(off.get('username', 'Аноним'))
                if not username.startswith("@"):
                     username = f"@{username}"

                user_id = off.get('user_id')
                reason = escape(off.get('reason', '-'))
                
                if user_id:
                    text += f"{i}. 👤 <a href='tg://user?id={user_id}'>{username}</a> (+{off.get('points', 0)} pts)\n"
                else:
                    text += f"{i}. 👤 <b>{username}</b> (+{off.get('points', 0)} pts)\n"
                text += f"   📝 <b>Вердикт:</b> {reason}\n"
                if quote:
                    text += f"   💬 <i>{escape(quote)}</i>\n"
                text += "\n"
        
        if new_agreements:
            text += messages.NEW_AGREEMENTS_TITLE
            for ag in new_agreements:
                 text += f"📌 {escape(ag.get('text'))}\n"
                 
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
        
    return {"status": "analyzed", "result": final_result}

async def scheduled_daily_analysis():
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
    logging.info("Starting scheduled weekly amnesty...")
    try:
        chats_ref = db.collection("chats")
        async for chat_doc in chats_ref.stream():
            chat_data = chat_doc.to_dict()
            if not chat_data.get("active"):
                continue
                
            chat_id = chat_doc.id
            logging.info(f"Applying amnesty for chat {chat_id}")
            await apply_weekly_amnesty(chat_id)
            
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=messages.AMNESTY_MESSAGE,
                    parse_mode="HTML"
                )
            except Exception as e:
                logging.error(f"Failed to send amnesty announcement to {chat_id}: {e}")
                
    except Exception as e:
        logging.error(f"Error in scheduled amnesty: {e}")

@app.on_event("startup")
async def on_startup():
    commands = [
        types.BotCommand(command="status", description="Мое личное дело"),
        types.BotCommand(command="stats", description="Топ Снитчей"),
        types.BotCommand(command="rules", description="Кодекс Снитча"),
        types.BotCommand(command="report", description="Донос (Reply)"),
        types.BotCommand(command="casino", description="Испытать удачу"),
        types.BotCommand(command="agreements", description="Список договоренностей"),
        types.BotCommand(command="all", description="Позвать всех"),
    ]
    await bot.set_my_commands(commands)
    scheduler.add_job(scheduled_weekly_decay, 'cron', day_of_week='sun', hour=23, minute=59)
    scheduler.start()

dp = Dispatcher()
dp.include_router(router)

@app.post("/webhook")
async def telegram_webhook(request: Request):
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
    if x_secret_token != settings.SECRET_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")
    data = await request.json()
    chat_id = data.get("chat_id")
    if not chat_id:
        raise HTTPException(status_code=400, detail="Missing chat_id")
    return await perform_chat_analysis(chat_id)

@app.post("/weekly_decay")
async def weekly_decay(request: Request, x_secret_token: str = Header(None, alias="X-Secret-Token")):
    if x_secret_token != settings.SECRET_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")
    data = await request.json()
    chat_id = data.get("chat_id")
    if not chat_id:
        raise HTTPException(status_code=400, detail="Missing chat_id")
    await apply_weekly_amnesty(chat_id)
    await bot.send_message(
        chat_id=chat_id,
        text=messages.AMNESTY_MESSAGE,
        parse_mode="HTML"
    )
    return {"status": "amnesty_applied"}
    
@app.get("/")
async def health_check():
    return {"status": "ok", "service": "BorSnitchBot"}
