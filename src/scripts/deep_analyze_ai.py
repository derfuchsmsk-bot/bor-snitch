import asyncio
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

# Load environment variables from .env
load_dotenv()

from src.services.db import db, get_logs_for_time_range
from src.utils.game_config import config

async def deep_analyze_ai_decisions():
    today = datetime.now()
    # Analyzing today and yesterday to be sure we catch the 12:00 (MSK) run
    dates_to_check = [
        today.strftime("%Y-%m-%d"),
        (today - timedelta(days=1)).strftime("%Y-%m-%d")
    ]
    
    moscow_tz = timezone(timedelta(hours=config.TIMEZONE_OFFSET))
    
    chats_ref = db.collection("chats")
    chats = await chats_ref.get()
    
    for chat in chats:
        chat_id = chat.id
        for date_str in dates_to_check:
            daily_doc = await chats_ref.document(chat_id).collection("daily_results").document(date_str).get()
            
            if not daily_doc.exists:
                continue

            data = daily_doc.to_dict()
            print(f"\n{'='*60}")
            print(f"CHAT: {chat_id} | DATE: {date_str}")
            print(f"{'='*60}")
            
            # 1. Show the Offenders and their Reasons
            offenders = data.get("offenders", [])
            if offenders:
                print("\nVERDICTS (The 'What'):")
                for off in offenders:
                    print(f"  - @{off.get('username')}: {off.get('points')} pts")
                    print(f"    Reason: {off.get('reason')}")
            
            # 2. Show Thought Process if it exists
            thoughts = data.get("ai_thought_process")
            if thoughts:
                print("\nAI THOUGHT PROCESS (The 'Why' - Internal):")
                print(thoughts)
            else:
                print("\nAI THOUGHT PROCESS: [Not found in daily_results document]")

            # 3. Pull the actual logs for that window to "see what the bot saw"
            # In main.py, the window is roughly 24h ending at 23:50 MSK of the analysis_date
            # But the user mentioned "12:00 today". 
            # If the bot ran at 12:00, it probably analyzed the last 24h.
            
            analysis_dt = datetime.strptime(date_str, "%Y-%m-%d")
            # This is a rough approximation of the window
            end_dt_msk = datetime.combine(analysis_dt.date(), datetime.min.time(), tzinfo=moscow_tz).replace(hour=23, minute=50)
            start_dt_msk = end_dt_msk - timedelta(days=1)
            
            start_dt_utc = start_dt_msk.astimezone(timezone.utc)
            end_dt_utc = end_dt_msk.astimezone(timezone.utc)
            
            print(f"\nCONTEXT LOGS (The 'Evidence' for window {start_dt_msk.strftime('%H:%M')} to {end_dt_msk.strftime('%H:%M')} MSK):")
            logs = await get_logs_for_time_range(chat_id, start_dt_utc, end_dt_utc)
            
            # Focus logs on mentioned offenders to keep it readable
            offender_ids = [str(off.get('user_id')) for off in offenders if off.get('user_id')]
            
            if not logs:
                print("  [No logs found for this period]")
            else:
                for log in logs:
                    uid = str(log.get('user_id'))
                    is_offender = uid in offender_ids
                    prefix = ">>> " if is_offender else "    "
                    ts = log['timestamp']
                    if ts.tzinfo is None: ts = ts.replace(tzinfo=timezone.utc)
                    ts_msk = ts.astimezone(moscow_tz).strftime("%H:%M")
                    
                    print(f"{prefix}[{ts_msk}] {log.get('username')}: {log.get('text')}")

if __name__ == "__main__":
    asyncio.run(deep_analyze_ai_decisions())
