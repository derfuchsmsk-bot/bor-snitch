import jwt
import time
import logging
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Request, Header, HTTPException, Depends
from aiogram import Bot, Dispatcher, types
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from src.utils.config import settings
from src.bot.handlers import router
from src.services.db import apply_weekly_amnesty, db
from src.services.analysis_service import AnalysisService
from src.services.lore_service import LoreService
from src.utils import messages

# Configure logging
logging.basicConfig(level=logging.INFO)

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

scheduler = AsyncIOScheduler()

# Initialize Bot, Dispatcher and Services
bot = Bot(token=settings.TELEGRAM_TOKEN)
analysis_service = AnalysisService(bot)

from src.utils.game_config import config

async def scheduled_agreement_check():
    if config.BOT_DISABLED:
        logging.info("Skipping scheduled agreement check because bot is disabled.")
        return
    logging.info("Starting scheduled agreement check...")
    try:
        chats_ref = db.collection("chats")
        async for chat_doc in chats_ref.stream():
            chat_data = chat_doc.to_dict()
            if not chat_data.get("active"):
                continue
            await analysis_service.perform_agreement_check(chat_doc.id)
    except Exception as e:
        logging.error(f"Error in scheduled agreement check: {e}")

async def scheduled_daily_analysis():
    if config.BOT_DISABLED:
        logging.info("Skipping scheduled daily analysis because bot is disabled.")
        return
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
                await analysis_service.perform_chat_analysis(chat_id)
            except Exception as e:
                logging.error(f"Failed to analyze chat {chat_id}: {e}")
                
    except Exception as e:
        logging.error(f"Error in scheduled analysis: {e}")

async def scheduled_weekly_decay():
    if config.BOT_DISABLED:
        logging.info("Skipping scheduled weekly amnesty because bot is disabled.")
        return
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

async def scheduled_lore_evolution():
    if config.BOT_DISABLED:
        logging.info("Skipping scheduled lore evolution because bot is disabled.")
        return
    logging.info("Starting scheduled lore evolution...")
    try:
        chats_ref = db.collection("chats")
        async for chat_doc in chats_ref.stream():
            chat_data = chat_doc.to_dict()
            if not chat_data.get("active"):
                continue
            
            chat_id = chat_doc.id
            logging.info(f"Evolving lore for chat {chat_id}")
            try:
                await LoreService.evolve_lore(int(chat_id))
            except Exception as e:
                logging.error(f"Failed to evolve lore for chat {chat_id}: {e}")
    except Exception as e:
        logging.error(f"Error in scheduled lore evolution: {e}")

@app.on_event("startup")
async def on_startup():
    from src.utils.game_config import config
    
    # Base commands that should always be visible (or admin commands)
    # We remove the regular commands so they don't show up in the menu when disabled
    # However, setting commands dynamically based on state might require a different approach
    # For now, let's keep the basic commands but maybe hide them if disabled, 
    # but the simplest is just to leave them or let them return "bot is disabled"
    # Actually, the user wants them GONE from the menu.
    
    if config.BOT_DISABLED:
        # If disabled at startup, only show admin commands
        commands = [
            types.BotCommand(command="bot_enable", description="Включить бота (Admin)"),
        ]
    else:
        commands = [
            types.BotCommand(command="status", description="Мое личное дело"),
            types.BotCommand(command="stats", description="Топ Снитчей"),
            types.BotCommand(command="rules", description="Кодекс Снитча"),
            types.BotCommand(command="report", description="Донос (Reply)"),
            types.BotCommand(command="casino", description="Испытать удачу"),
            types.BotCommand(command="all", description="Позвать всех"),
            types.BotCommand(command="remember", description="Запомнить факт (Lore)"),
            types.BotCommand(command="bot_disable", description="Отключить бота (Admin)"),
        ]
        if config.ENABLE_AGREEMENTS:
            commands.append(types.BotCommand(command="agreements", description="Список договоренностей"))
            commands.append(types.BotCommand(command="dispute", description="Оспорить слово пацана"))
            
    await bot.set_my_commands(commands)
    scheduler.add_job(scheduled_weekly_decay, 'cron', day_of_week='sun', hour=23, minute=59)
    scheduler.add_job(scheduled_lore_evolution, 'cron', day_of_week='mon', hour=0, minute=30)
    
    if config.ENABLE_AGREEMENTS:
        scheduler.add_job(scheduled_agreement_check, 'interval', minutes=30)
        
    scheduler.start()

dp = Dispatcher()
dp.include_router(router)

def verify_jwt(x_secret_token: str = Header(None, alias="X-Secret-Token")):
    if not x_secret_token:
        raise HTTPException(status_code=403, detail="Missing token")
    try:
        if x_secret_token == settings.SECRET_TOKEN:
            return True
            
        payload = jwt.decode(x_secret_token, settings.JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=403, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=403, detail="Invalid token")

@app.post("/webhook")
@limiter.limit("60/minute")
async def telegram_webhook(request: Request):
    if config.BOT_DISABLED:
        return {"status": "skipped", "message": "Bot is disabled"}
    try:
        update_data = await request.json()
        update = types.Update(**update_data)
        await dp.feed_update(bot, update)
        return {"status": "ok"}
    except Exception as e:
        logging.error(f"Webhook error: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/analyze_daily")
async def analyze_daily(request: Request, auth=Depends(verify_jwt)):
    data = await request.json()
    chat_id = data.get("chat_id")
    if not chat_id:
        raise HTTPException(status_code=400, detail="Missing chat_id")
    return await analysis_service.perform_chat_analysis(chat_id)

@app.post("/weekly_decay")
async def weekly_decay(request: Request, auth=Depends(verify_jwt)):
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

@app.post("/evolve_lore")
async def evolve_lore_endpoint(request: Request, auth=Depends(verify_jwt)):
    """
    Эндпоинт для триггера эволюции лора из Google Cloud Scheduler.
    """
    data = await request.json()
    chat_id = data.get("chat_id")
    
    if not chat_id:
        raise HTTPException(status_code=400, detail="Missing chat_id")
        
    logging.info(f"Manual lore evolution triggered for chat {chat_id}")
    
    try:
        # Запускаем эволюцию (это может занять время, лучше делать в фоне,
        # но для Cloud Scheduler синхронный ответ тоже допустим, если уложимся в таймаут)
        await LoreService.evolve_lore(int(chat_id))
        return {"status": "evolution_completed", "chat_id": chat_id}
    except Exception as e:
        logging.error(f"Lore evolution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/token")
@limiter.limit("5/minute")
async def get_token(request: Request, x_secret_token: str = Header(None, alias="X-Secret-Token")):
    if x_secret_token != settings.SECRET_TOKEN:
         raise HTTPException(status_code=403, detail="Invalid secret")
    
    payload = {
        "sub": "admin",
        "exp": time.time() + 3600
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    return {"token": token}

@app.get("/")
async def health_check():
    return {
        "status": "ok", 
        "service": "BorSnitchBot",
        "bot_disabled": config.BOT_DISABLED
    }
