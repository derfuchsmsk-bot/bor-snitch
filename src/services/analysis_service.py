import logging
from datetime import datetime, timezone, timedelta, time
from google.cloud import firestore
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError

from src.utils.config import settings
from src.utils.game_config import config
from src.utils import messages
from src.utils.text import escape
from src.services.db import (
    db, get_logs_for_time_range, save_daily_results, 
    get_active_agreements, save_agreement, check_afk_users, 
    update_agreement_status, get_agreement_by_id, update_agreement_text, 
    get_last_agreement_check, set_last_agreement_check
)
from src.services.ai import analyze_daily_logs, summarize_day
from src.services.learning import LearningService

class AnalysisService:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def perform_chat_analysis(self, chat_id: str):
        """
        Core logic for daily analysis.
        """
        moscow_tz = timezone(timedelta(hours=config.TIMEZONE_OFFSET))
        now_utc = datetime.now(timezone.utc)
        
        # 0. Distributed Lock
        lock_ref = db.collection("chats").document(chat_id).collection("locks").document("daily_analysis")
        
        try:
            lock_doc = await lock_ref.get()
            if lock_doc.exists:
                lock_data = lock_doc.to_dict()
                lock_time = lock_data.get("timestamp")
                if lock_time:
                    if lock_time.tzinfo is None:
                        lock_time = lock_time.replace(tzinfo=timezone.utc)
                    
                    if now_utc - lock_time < timedelta(minutes=5):
                        logging.warning(f"Analysis for chat {chat_id} is already in progress. Skipping.")
                        return {"status": "locked"}
            
            await lock_ref.set({"timestamp": firestore.SERVER_TIMESTAMP})
        except Exception as e:
            logging.error(f"Locking error for chat {chat_id}: {e}")
        
        now_msk = datetime.now(moscow_tz)
        
        analysis_date = now_msk.date()
        if now_msk.hour < config.ANALYSIS_CUTOFF_HOUR:
             analysis_date -= timedelta(days=1)
             
        end_dt_msk = datetime.combine(analysis_date, time(23, 50), tzinfo=moscow_tz)
        start_dt_msk = end_dt_msk - timedelta(days=1)
        
        end_dt_utc = end_dt_msk.astimezone(timezone.utc)
        start_dt_utc = start_dt_msk.astimezone(timezone.utc)
        
        today_str = end_dt_msk.strftime("%Y-%m-%d")
        active_agreements = []
        if config.ENABLE_AGREEMENTS:
            active_agreements = await get_active_agreements(chat_id)
        
        logging.info(f"Starting analysis for chat {chat_id}. Window (MSK): {start_dt_msk} to {end_dt_msk}")
        logs = await get_logs_for_time_range(chat_id, start_dt_utc, end_dt_utc)

        future_end_dt_utc = end_dt_utc + timedelta(hours=4)
        future_logs = await get_logs_for_time_range(chat_id, end_dt_utc, future_end_dt_utc)
        
        ai_result = None
        if logs:
            ai_result = await analyze_daily_logs(logs, active_agreements=active_agreements, date_str=today_str, future_logs=future_logs, chat_id=chat_id)
        
        afk_offenders = await check_afk_users(chat_id)
        
        if not logs and not afk_offenders:
            logging.info("No logs and no AFK violations.")
            try:
                await self.bot.send_message(chat_id=chat_id, text="Сегодня слишком тихо... Снитч не найден. (Нет логов и нарушений)")
            except TelegramForbiddenError:
                logging.error(f"DIAGNOSIS_CHECK: Bot kicked from chat {chat_id}. Cannot send message.")
                raise
            return {"status": "no logs"}

        final_result = {
            "offenders": [],
            "new_agreements": [],
            "resolved_agreements": [],
            "updated_agreements": []
        }
        
        if ai_result:
            # ai_result is a Pydantic model (DailyAnalysisResult)
            final_result["offenders"].extend([off.model_dump() for off in ai_result.offenders])
            final_result["new_agreements"].extend([ag.model_dump() for ag in ai_result.new_agreements])
            final_result["resolved_agreements"].extend([res.model_dump() for res in ai_result.resolved_agreements])
            final_result["updated_agreements"].extend([upd.model_dump() for upd in ai_result.updated_agreements])
            if ai_result.thought_process:
                final_result["ai_thought_process"] = ai_result.thought_process
            
        final_result["offenders"].extend(afk_offenders)
        
        if final_result:
            final_result['date_key'] = today_str
            await save_daily_results(chat_id, final_result)
            
            for ag in final_result.get('new_agreements', []):
                await save_agreement(chat_id, ag)
                
            for res in final_result.get('resolved_agreements', []):
                res_id = res.get('id')
                status = res.get('status')
                reason = res.get('reason')
                if res_id and status in ['fulfilled', 'broken']:
                    await update_agreement_status(chat_id, res_id, status, reason)
            
            for upd in final_result.get('updated_agreements', []):
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
            
            new_agreements = final_result.get('new_agreements', [])
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

            resolved_agreements = final_result.get('resolved_agreements', [])
            if resolved_agreements:
                text += "\n\n⚖️ <b>Итоги по старым базарам:</b>\n"
                for res in resolved_agreements:
                    res_id = res.get('id')
                    status = res.get('status')
                    orig_ag = await get_agreement_by_id(chat_id, res_id)
                    orig_text = orig_ag.get('text', '???') if orig_ag else '???'
                    orig_users = ", ".join([f"<b>{escape(u)}</b>" for u in orig_ag.get('users', [])]) if orig_ag else '???'
                    
                    if status == 'fulfilled':
                        text += f"✅ <b>Сдержал слово:</b> {orig_users} — «{escape(orig_text)}»\n"
                    elif status == 'broken':
                        text += f"❌ <b>ФУФЛОМЕТ:</b> {orig_users} — «{escape(orig_text)}»\n"
                     
            updated_agreements = final_result.get('updated_agreements', [])
            if updated_agreements:
                text += "\n\n🔄 <b>Обновления по базарам:</b>\n"
                for upd in updated_agreements:
                    upd_id = upd.get('id')
                    new_text = upd.get('text')
                    orig_ag = await get_agreement_by_id(chat_id, upd_id)
                    orig_users = ", ".join(orig_ag.get('users', [])) if orig_ag else '???'
                    text += f"📝 {orig_users}: {escape(new_text)}\n"
                     
            try:
                await self.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
            except TelegramForbiddenError:
                 logging.error(f"DIAGNOSIS_CHECK: Bot kicked from chat {chat_id}. Cannot send daily report.")
                 raise

        try:
            await LearningService.analyze_feedback(chat_id, today_str)
        except Exception as e:
            logging.error(f"Failed to analyze feedback for chat {chat_id}: {e}")

        try:
            await summarize_day(chat_id, today_str, logs)
        except Exception as e:
            logging.error(f"Failed to summarize day for chat {chat_id}: {e}")

        try:
            await lock_ref.delete()
        except Exception as e:
            logging.error(f"Failed to release lock for chat {chat_id}: {e}")

        return {"status": "analyzed", "result": final_result}

    async def perform_agreement_check(self, chat_id: str):
        """
        Checks for new agreements.
        """
        if not config.ENABLE_AGREEMENTS:
            return
            
        now_utc = datetime.now(timezone.utc)
        last_check = await get_last_agreement_check(chat_id)
        
        if not last_check:
            last_check = now_utc - timedelta(minutes=30)
        
        if last_check.tzinfo is None:
            last_check = last_check.replace(tzinfo=timezone.utc)
            
        logs = await get_logs_for_time_range(chat_id, last_check, now_utc)
        if not logs:
            await set_last_agreement_check(chat_id, now_utc)
            return
        
        active_agreements = await get_active_agreements(chat_id)
        ai_result = await analyze_daily_logs(logs, active_agreements=active_agreements, chat_id=chat_id)
        
        if not ai_result:
            await set_last_agreement_check(chat_id, now_utc)
            return

        new_agreements = [ag.model_dump() for ag in ai_result.new_agreements]
        updated_agreements = [upd.model_dump() for upd in ai_result.updated_agreements]
        
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
            await self.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
        
        await set_last_agreement_check(chat_id, now_utc)
