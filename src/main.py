import jwt
import time
import logging
from google.cloud import firestore

from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Request, Header, HTTPException, Depends
from aiogram import Bot, Dispatcher, types
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from src.utils.limiter import limiter

from src.utils.config import settings
from src.bot.handlers import router
from src.services.db import apply_weekly_amnesty, db
from src.services.analysis_service import AnalysisService
from src.services.lore_service import LoreService
from src.services.config_service import ConfigService
from src.services.prompt_service import PromptService
from src.admin.router import router as admin_router
from src.utils import messages

# Configure logging
logging.basicConfig(level=logging.INFO)

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
            if not chat_data.get("active") or not chat_doc.id.startswith("-"):
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
            if not chat_data.get("active") or not chat_doc.id.startswith("-"):
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
            if not chat_data.get("active") or not chat_doc.id.startswith("-"):
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
            if not chat_data.get("active") or not chat_doc.id.startswith("-"):
                continue
            
            chat_id = chat_doc.id
            logging.info(f"Evolving lore for chat {chat_id}")
            try:
                await LoreService.evolve_lore(int(chat_id))
            except Exception as e:
                logging.error(f"Failed to evolve lore for chat {chat_id}: {e}")
    except Exception as e:
        logging.error(f"Error in scheduled lore evolution: {e}")

async def scheduled_voice_digest(edition_type: str):
    if config.BOT_DISABLED or not getattr(config, "VOICE_DIGEST_ENABLED", True):
        logging.info("Skipping voice digest because bot or feature is disabled.")
        return
    logging.info(f"Starting scheduled voice digest ({edition_type})...")
    from src.services.voice_digest_service import VoiceDigestService
    try:
        chats_ref = db.collection("chats")
        async for chat_doc in chats_ref.stream():
            chat_data = chat_doc.to_dict()
            if not chat_data.get("active") or not chat_doc.id.startswith("-"):
                continue
            chat_id = chat_doc.id
            try:
                await VoiceDigestService.create_and_send_voice_digest(
                    chat_id=int(chat_id),
                    edition_type=edition_type,
                    bot=bot,
                    send_to_telegram=True
                )
            except Exception as e:
                logging.error(f"Failed voice digest for chat {chat_id}: {e}")
    except Exception as e:
        logging.error(f"Error in scheduled voice digest: {e}")

async def scheduled_thought():
    from src.utils.game_config import config
    from src.utils.config import settings
    if config.BOT_DISABLED or not getattr(config, "THOUGHTS_ENABLED", True):
        logging.info("Skipping scheduled thought because bot or feature is disabled.")
        return

    logging.info("Starting scheduled thought generation...")
    from src.services.thought_service import ThoughtService
    try:
        source_chat_id = settings.MAIN_CHAT_ID
        target_chat_id = getattr(settings, "CHANNEL_ID", None) or source_chat_id
        await ThoughtService.create_and_send_thought(
            source_chat_id=source_chat_id,
            target_chat_id=target_chat_id,
            bot=bot
        )
    except Exception as e:
        logging.error(f"Error in scheduled thought generation: {e}")

def sync_thoughts_jobs():
    """Dynamically schedules or removes daily textual thoughts based on GameConfig."""
    try:
        job_ids = ["thought_1", "thought_2", "thought_3", "thought_4", "thought_5"]
        if not getattr(config, "THOUGHTS_ENABLED", True) or config.BOT_DISABLED:
            for job_id in job_ids:
                if scheduler.get_job(job_id):
                    scheduler.remove_job(job_id)
            logging.info("Thoughts jobs unscheduled.")
            return

        times = [
            getattr(config, f"THOUGHTS_TIME_{i}", None) for i in range(1, 6)
        ]
        
        for i, t_str in enumerate(times, 1):
            job_id = f"thought_{i}"
            if not t_str:
                if scheduler.get_job(job_id):
                    scheduler.remove_job(job_id)
                continue

            h, m = [int(x) for x in t_str.split(":")[:2]]
            utc_h = (h - getattr(config, "TIMEZONE_OFFSET", 3)) % 24

            scheduler.add_job(
                scheduled_thought,
                'cron',
                hour=utc_h,
                minute=m,
                id=job_id,
                replace_existing=True
            )
            logging.info(f"Scheduled thought_{i}: {t_str} MSK (UTC {utc_h:02d}:{m:02d})")
            
    except Exception as e:
        logging.error(f"Failed to sync thoughts jobs: {e}")

def sync_voice_digest_jobs():
    """Dynamically schedules or removes daily voice digest cron jobs based on GameConfig."""
    try:
        if not getattr(config, "VOICE_DIGEST_ENABLED", True) or config.BOT_DISABLED:
            for job_id in ["voice_digest_1", "voice_digest_2"]:
                if scheduler.get_job(job_id):
                    scheduler.remove_job(job_id)
            logging.info("Voice digest jobs unscheduled.")
            return

        # Parse Time 1 (default 14:00)
        t1 = getattr(config, "VOICE_DIGEST_TIME_1", "14:00")
        h1, m1 = [int(x) for x in t1.split(":")[:2]]
        utc_h1 = (h1 - config.TIMEZONE_OFFSET) % 24

        # Parse Time 2 (default 22:00)
        t2 = getattr(config, "VOICE_DIGEST_TIME_2", "22:00")
        h2, m2 = [int(x) for x in t2.split(":")[:2]]
        utc_h2 = (h2 - config.TIMEZONE_OFFSET) % 24

        scheduler.add_job(
            scheduled_voice_digest,
            'cron',
            hour=utc_h1,
            minute=m1,
            args=["Дневной выпуск (14:00)"],
            id="voice_digest_1",
            replace_existing=True
        )
        scheduler.add_job(
            scheduled_voice_digest,
            'cron',
            hour=utc_h2,
            minute=m2,
            args=["Вечерний выпуск (22:00)"],
            id="voice_digest_2",
            replace_existing=True
        )
        logging.info(f"Scheduled voice digests: {t1} MSK (UTC {utc_h1:02d}:{m1:02d}) & {t2} MSK (UTC {utc_h2:02d}:{m2:02d})")
    except Exception as e:
        logging.error(f"Failed to sync voice digest jobs: {e}")

async def sync_bot_commands():
    """Dynamically synchronizes Telegram bot menu commands based on current GameConfig."""
    try:
        if config.BOT_DISABLED:
            commands = []
        else:
            commands = [
                types.BotCommand(command="status", description="Мое личное дело"),
                types.BotCommand(command="stats", description="Топ Снитчей"),
                types.BotCommand(command="rules", description="Кодекс Снитча"),
                types.BotCommand(command="report", description="Донос (Reply)"),
                types.BotCommand(command="casino", description="Испытать удачу"),
                types.BotCommand(command="all", description="Позвать всех"),
                types.BotCommand(command="digest", description="Голосовая хроника (Voice)"),
                types.BotCommand(command="remember", description="Запомнить факт (Lore)"),
                types.BotCommand(command="forget", description="Сбросить лор (Очистка)"),
                types.BotCommand(command="bot_disable", description="Отключить бота (Admin)"),
            ]
            if getattr(config, "ENABLE_DEBTS", True):
                commands.insert(6, types.BotCommand(command="debts", description="Кто кому торчит (Долги)"))
                
            if config.ENABLE_AGREEMENTS:
                commands.append(types.BotCommand(command="agreements", description="Список договоренностей"))
                commands.append(types.BotCommand(command="dispute", description="Оспорить слово пацана"))

        await bot.set_my_commands(commands)
        logging.info(f"Synchronized {len(commands)} bot commands with Telegram.")
    except Exception as e:
        logging.warning(f"Failed to synchronize bot commands: {e}")

@app.on_event("startup")
async def on_startup():
    # Load dynamic configurations and prompts from Firestore
    await ConfigService.load_config()
    await PromptService.load_prompts()

    # Synchronize bot commands
    await sync_bot_commands()

    # Synchronize voice digest jobs
    sync_voice_digest_jobs()
    
    # Synchronize thoughts jobs
    sync_thoughts_jobs()
    
    scheduler.add_job(scheduled_weekly_decay, 'cron', day_of_week='sun', hour=23, minute=59)
    scheduler.add_job(scheduled_lore_evolution, 'cron', day_of_week='mon', hour=0, minute=30)
    
    if config.ENABLE_AGREEMENTS:
        scheduler.add_job(scheduled_agreement_check, 'interval', minutes=30)
        
    try:
        scheduler.start()
    except Exception as e:
        logging.warning(f"Scheduler start issue: {e}")

# Include routers
app.include_router(admin_router)
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
    # Verify Telegram Bot API secret token if configured
    secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if settings.SECRET_TOKEN and secret_token:
        if secret_token != settings.SECRET_TOKEN:
            logging.warning("Rejected webhook request with invalid secret token.")
            raise HTTPException(status_code=403, detail="Invalid secret token")

    try:
        update_data = await request.json()
        update_id = update_data.get("update_id")

        # Idempotent deduplication for Telegram updates
        if update_id is not None:
            update_ref = db.collection("processed_updates").document(str(update_id))
            try:
                await update_ref.create({
                    "update_id": update_id,
                    "processed_at": firestore.SERVER_TIMESTAMP
                })
            except Exception as e:
                err_msg = str(e).lower()
                if "alreadyexists" in type(e).__name__.lower() or "already exists" in err_msg:
                    logging.info(f"Duplicate update_id {update_id} received, returning 200 without reprocessing.")
                    return {"status": "ok", "message": "duplicate"}
                logging.warning(f"Could not record update_id {update_id} in processed_updates: {e}")

        update = types.Update(**update_data)
        await dp.feed_update(bot, update)
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Webhook processing error: {e}")
        raise HTTPException(status_code=500, detail="Internal processing error")

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
    
@app.post("/voice_digest")
async def voice_digest_endpoint(request: Request, auth=Depends(verify_jwt)):
    """
    Эндпоинт для запуска генерации голосовой сводки из Google Cloud Scheduler или вручную.
    """
    data = await request.json()
    chat_id = data.get("chat_id")
    edition = data.get("edition") or "Дневной выпуск (14:00)"
    if not chat_id:
        raise HTTPException(status_code=400, detail="Missing chat_id")

    from src.services.voice_digest_service import VoiceDigestService
    try:
        result = await VoiceDigestService.create_and_send_voice_digest(
            chat_id=int(chat_id),
            edition_type=edition,
            bot=bot,
            send_to_telegram=True
        )
        return result
    except Exception as e:
        logging.error(f"Voice digest error: {e}")
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
