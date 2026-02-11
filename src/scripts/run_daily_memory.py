import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Load env vars first
load_dotenv()

# Add src to path
sys.path.append(os.getcwd())

from src.services.db import db, get_logs_for_time_range
from src.services.ai import summarize_day
from src.utils.game_config import config

async def run_history_summarization():
    chat_id = -954103380
    
    # Analyze last 7 days
    end_date = datetime.now(timezone.utc)
    
    for i in range(7):
        date_obj = end_date - timedelta(days=i)
        date_key = date_obj.strftime("%Y-%m-%d")
        
        moscow_tz = timezone(timedelta(hours=config.TIMEZONE_OFFSET))
        start_dt = date_obj.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
        end_dt = start_dt + timedelta(days=1)

        print(f"Summarizing {date_key}...")
        logs = await get_logs_for_time_range(chat_id, start_dt, end_dt)
        
        if logs:
            result = await summarize_day(chat_id, date_key, logs)
            if result:
                print(f"Success: {result.get('summary')[:50]}...")
        else:
            print("No logs found.")

if __name__ == "__main__":
    asyncio.run(run_history_summarization())
