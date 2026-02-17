import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Load env vars first
load_dotenv()

from src.services.db import (
    db, get_logs_for_time_range, save_daily_results, 
    get_active_agreements, save_agreement, check_afk_users, 
    update_agreement_status, update_agreement_text,
    get_agreement_by_id
)
from src.services.ai import analyze_daily_logs, summarize_day
from src.utils.config import settings
from src.utils.game_config import config
from src.utils import messages
from src.utils.text import escape
from aiogram import Bot

async def run_manual_summary():
    chat_id = settings.MAIN_CHAT_ID
    
    # 1. Define Time Window (2026-02-16 12:00 MSK to 23:50 MSK)
    # MSK is UTC+3
    target_date_str = "2026-02-16"
    
    start_dt_utc = datetime(2026, 2, 16, 9, 0, 0, tzinfo=timezone.utc) # 12:00 MSK
    end_dt_utc = datetime(2026, 2, 16, 20, 50, 0, tzinfo=timezone.utc) # 23:50 MSK
    
    print(f"Running manual summary for {target_date_str}")
    print(f"Time Window (UTC): {start_dt_utc} to {end_dt_utc}")
    
    # 2. Fetch Logs
    logs = await get_logs_for_time_range(chat_id, start_dt_utc, end_dt_utc)
    print(f"Fetched {len(logs)} messages.")
    
    if not logs:
        print("No logs found. Aborting.")
        return

    # 3. Context for AI
    future_end_dt_utc = end_dt_utc + timedelta(hours=4)
    future_logs = await get_logs_for_time_range(chat_id, end_dt_utc, future_end_dt_utc)
    
    active_agreements = []
    if config.ENABLE_AGREEMENTS:
        active_agreements = await get_active_agreements(chat_id)
        
    # 4. Run Analysis
    print("Running AI analysis...")
    ai_result = await analyze_daily_logs(
        logs, 
        active_agreements=active_agreements, 
        date_str=target_date_str, 
        future_logs=future_logs, 
        chat_id=chat_id
    )
    
    if not ai_result:
        print("AI Analysis failed.")
        return

    # 5. Process Results
    afk_offenders = [] # Skipping AFK check for this specific manual run as requested "only messages from..."
    
    final_result = {
        "offenders": [],
        "new_agreements": [],
        "resolved_agreements": [],
        "updated_agreements": []
    }
    
    # ai_result is a Pydantic model
    final_result["offenders"].extend([off.model_dump() for off in ai_result.offenders])
    final_result["new_agreements"].extend([ag.model_dump() for ag in ai_result.new_agreements])
    final_result["resolved_agreements"].extend([res.model_dump() for res in ai_result.resolved_agreements])
    final_result["updated_agreements"].extend([upd.model_dump() for upd in ai_result.updated_agreements])
    if ai_result.thought_process:
        final_result["ai_thought_process"] = ai_result.thought_process
        
    final_result["offenders"].extend(afk_offenders)
    final_result['date_key'] = target_date_str
    
    print("Saving results to database...")
    await save_daily_results(chat_id, final_result)
    
    # Agreements Handling
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

    # 6. Generate Report Text
    print("Generating report text...")
    text_to_send = await generate_report_text_async(final_result, chat_id)
    print("\n=== REPORT TEXT ===\n")
    print(text_to_send)
    print("\n===================\n")
    
    # 7. Send to Telegram
    confirm = input("Send this report to Telegram? (y/n): ")
    if confirm.lower() == 'y':
        bot = Bot(token=settings.TELEGRAM_TOKEN)
        try:
            await bot.send_message(chat_id=chat_id, text=text_to_send, parse_mode="HTML")
            print("Sent successfully.")
        finally:
            await bot.session.close()

    # 8. Summarize Memory
    print("Summarizing day for memory...")
    await summarize_day(chat_id, target_date_str, logs)
    print("Memory saved.")

async def generate_report_text_async(final_result, chat_id):
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
            
    return text

# Sync wrapper for initial print (incomplete, replaced by async one)
def generate_report_text(final_result, chat_id):
    # This was a placeholder, actual generation happens in async function
    return "Report text will be generated in async step..."

if __name__ == "__main__":
    asyncio.run(run_manual_summary())
