from fastapi import FastAPI, Request, Header, HTTPException
from aiogram import Bot, Dispatcher, types
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.utils.config import settings
from src.bot.handlers import router
from src.services.db import get_logs_for_time_range, save_daily_results, apply_weekly_amnesty, db, get_active_agreements, save_agreement, check_afk_users, update_agreement_status, get_agreement_by_id, update_agreement_text, get_last_agreement_check, set_last_agreement_check
from google.cloud import firestore
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
    now_utc = datetime.now(timezone.utc)
    
    # 0. Distributed Lock to prevent concurrent analysis for the same chat
    # We use a lock document with a TTL (5 minutes)
    lock_ref = db.collection("chats").document(chat_id).collection("locks").document("daily_analysis")
    
    try:
        lock_doc = await lock_ref.get()
        if lock_doc.exists:
            lock_data = lock_doc.to_dict()
            lock_time = lock_data.get("timestamp")
            if lock_time:
                # Ensure TZ awareness for comparison
                if lock_time.tzinfo is None:
                    lock_time = lock_time.replace(tzinfo=timezone.utc)
                
                if now_utc - lock_time < timedelta(minutes=5):
                    logging.warning(f"Analysis for chat {chat_id} is already in progress (Locked {now_utc - lock_time} ago). Skipping.")
                    return {"status": "locked"}
        
        # Acquire lock
        await lock_ref.set({"timestamp": firestore.SERVER_TIMESTAMP})
    except Exception as e:
        logging.error(f"Locking error for chat {chat_id}: {e}")
        # Proceed anyway if lock check fails, to avoid deadlocks
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
        "new_agreements": [],
        "resolved_agreements": [],
        "updated_agreements": []
    }
    
    if ai_result:
        final_result["offenders"].extend(ai_result.get("offenders", []))
        final_result["new_agreements"].extend(ai_result.get("new_agreements", []))
        final_result["resolved_agreements"].extend(ai_result.get("resolved_agreements", []))
        final_result["updated_agreements"].extend(ai_result.get("updated_agreements", []))
        
    final_result["offenders"].extend(afk_offenders)
    
    if final_result:
        final_result['date_key'] = today_str
        await save_daily_results(chat_id, final_result)
        
        # 4. Process new agreements
        new_agreements = final_result.get('new_agreements', [])
        for ag in new_agreements:
            await save_agreement(chat_id, ag)
            
        # 5. Process resolved agreements
        resolved_agreements = final_result.get('resolved_agreements', [])
        for res in resolved_agreements:
            res_id = res.get('id')
            status = res.get('status')
            reason = res.get('reason')
            if res_id and status in ['fulfilled', 'broken']:
                await update_agreement_status(chat_id, res_id, status, reason)
        
        # 5b. Process updated agreements
        updated_agreements = final_result.get('updated_agreements', [])
        for upd in updated_agreements:
            upd_id = upd.get('id')
            new_text = upd.get('text')
            reason = upd.get('reason')
            if upd_id and new_text:
                await update_agreement_text(chat_id, upd_id, new_text, reason)

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
            all_active = await get_active_agreements(chat_id)
            for ag in new_agreements:
                 ag_type = ag.get('type', 'vow')
                 icon = "🕯"
                 if ag_type == "pact": icon = "🤝"
                 elif ag_type == "public": icon = "📢"
                 
                 users = ag.get('users', [])
                 users_str = ", ".join([f"<b>{escape(u if u.startswith('@') else '@'+u)}</b>" for u in users])
                 
                 # Find index in all_active
                 ag_text = ag.get('text')
                 idx = -1
                 for i, active_ag in enumerate(all_active, 1):
                     if active_ag.get('text') == ag_text:
                         idx = i
                         break
                 
                 text += f"{icon} {users_str}: {escape(ag_text)}"
                 if idx != -1:
                     text += f" (Оспорить: /disput {idx})"
                 text += "\n"
            text += messages.AGREEMENT_CREATED_FOOTER.format(minutes=config.AGREEMENT_DISPUTE_WINDOW_MINUTES)

        # 6. Add resolved agreements to summary
        if resolved_agreements:
            text += "\n\n⚖️ <b>Итоги по старым базарам:</b>\n"
            for res in resolved_agreements:
                res_id = res.get('id')
                status = res.get('status')
                # Try to find original agreement text
                orig_ag = await get_agreement_by_id(chat_id, res_id)
                orig_text = orig_ag.get('text', '???') if orig_ag else '???'
                orig_users = ", ".join([f"<b>{escape(u)}</b>" for u in orig_ag.get('users', [])]) if orig_ag else '???'
                
                if status == 'fulfilled':
                    text += f"✅ <b>Сдержал слово:</b> {orig_users} — «{escape(orig_text)}»\n"
                elif status == 'broken':
                    text += f"❌ <b>ФУФЛОМЕТ:</b> {orig_users} — «{escape(orig_text)}»\n"
                 
        # 7. Add updated agreements to summary
        if updated_agreements:
            text += "\n\n🔄 <b>Обновления по базарам:</b>\n"
            for upd in updated_agreements:
                upd_id = upd.get('id')
                new_text = upd.get('text')
                # Fetch original to show "before -> after"
                orig_ag = await get_agreement_by_id(chat_id, upd_id)
                orig_users = ", ".join(orig_ag.get('users', [])) if orig_ag else '???'
                text += f"📝 {orig_users}: {escape(new_text)}\n"
                 
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")

    # Release lock
    try:
        await lock_ref.delete()
    except Exception as e:
        logging.error(f"Failed to release lock for chat {chat_id}: {e}")

    return {"status": "analyzed", "result": final_result}

async def perform_agreement_check(chat_id: str):
    """
    Checks for new agreements every 30 minutes.
    """
    now_utc = datetime.now(timezone.utc)
    last_check = await get_last_agreement_check(chat_id)
    
    if not last_check:
        # If first time, check last 30 minutes
        last_check = now_utc - timedelta(minutes=30)
    
    # Ensure last_check is TZ aware
    if last_check.tzinfo is None:
        last_check = last_check.replace(tzinfo=timezone.utc)
        
    logs = await get_logs_for_time_range(chat_id, last_check, now_utc)
    if not logs:
        await set_last_agreement_check(chat_id, now_utc)
        return
    
    active_agreements = await get_active_agreements(chat_id)
    ai_result = await analyze_daily_logs(logs, active_agreements=active_agreements)
    
    if not ai_result:
        await set_last_agreement_check(chat_id, now_utc)
        return

    new_agreements = ai_result.get("new_agreements", [])
    updated_agreements = ai_result.get("updated_agreements", [])
    
    text = ""
    if new_agreements:
        text += messages.NEW_AGREEMENTS_TITLE
        for ag in new_agreements:
            await save_agreement(chat_id, ag)
        
        all_active = await get_active_agreements(chat_id)
        for ag in new_agreements:
            ag_type = ag.get('type', 'vow')
            icon = "🕯"
            if ag_type == "pact": icon = "🤝"
            elif ag_type == "public": icon = "📢"
            users = ag.get('users', [])
            users_str = ", ".join([f"<b>{escape(u if u.startswith('@') else '@'+u)}</b>" for u in users])
            
            # Find index in all_active
            ag_text = ag.get('text')
            idx = -1
            for i, active_ag in enumerate(all_active, 1):
                if active_ag.get('text') == ag_text:
                    idx = i
                    break
            
            text += f"{icon} {users_str}: {escape(ag_text)}"
            if idx != -1:
                text += f" (Оспорить: /disput {idx})"
            text += "\n"
        text += messages.AGREEMENT_CREATED_FOOTER.format(minutes=config.AGREEMENT_DISPUTE_WINDOW_MINUTES)

    if updated_agreements:
        text += "\n\n🔄 <b>Обновления по базарам:</b>\n"
        for upd in updated_agreements:
            upd_id = upd.get('id')
            new_text = upd.get('text')
            reason = upd.get('reason')
            if upd_id and new_text:
                await update_agreement_text(chat_id, upd_id, new_text, reason)
                orig_ag = await get_agreement_by_id(chat_id, upd_id)
                orig_users = ", ".join(orig_ag.get('users', [])) if orig_ag else '???'
                text += f"📝 {orig_users}: {escape(new_text)}\n"

    if text:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
    
    await set_last_agreement_check(chat_id, now_utc)

async def scheduled_agreement_check():
    logging.info("Starting scheduled agreement check...")
    try:
        chats_ref = db.collection("chats")
        async for chat_doc in chats_ref.stream():
            chat_data = chat_doc.to_dict()
            if not chat_data.get("active"):
                continue
            await perform_agreement_check(chat_doc.id)
    except Exception as e:
        logging.error(f"Error in scheduled agreement check: {e}")

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
        types.BotCommand(command="dispute", description="Оспорить слово пацана"),
        types.BotCommand(command="all", description="Позвать всех"),
    ]
    await bot.set_my_commands(commands)
    scheduler.add_job(scheduled_weekly_decay, 'cron', day_of_week='sun', hour=23, minute=59)
    scheduler.add_job(scheduled_agreement_check, 'interval', minutes=30)
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
