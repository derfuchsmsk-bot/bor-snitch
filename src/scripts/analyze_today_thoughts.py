import asyncio
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

from src.services.db import db
from datetime import datetime, timedelta
import json

async def analyze_today_points():
    today = datetime.now()
    dates_to_check = [
        today.strftime("%Y-%m-%d"),
        (today - timedelta(days=1)).strftime("%Y-%m-%d")
    ]
    print(f"Searching for analysis results for dates: {', '.join(dates_to_check)}")
    
    chats_ref = db.collection("chats")
    chats = await chats_ref.get()
    
    found_any = False
    for chat in chats:
        chat_id = chat.id
        for date_str in dates_to_check:
            daily_doc = await chats_ref.document(chat_id).collection("daily_results").document(date_str).get()
            
            if not daily_doc.exists:
                continue

            found_any = True
            data = daily_doc.to_dict()
            print(f"\n=== Chat ID: {chat_id} ===")
            
            thought_process = data.get("ai_thought_process")
            if thought_process:
                print("AI Thought Process:")
                print(thought_process)
            else:
                print("No AI thought process found for this entry.")
                
            offenders = data.get("offenders", [])
            if offenders:
                print("\nOffenders:")
                for off in offenders:
                    print(f"- {off.get('username')} ({off.get('user_id')}): {off.get('points')} pts")
                    print(f"  Reason: {off.get('reason')}")
            else:
                print("\nNo offenders found.")
                
    if not found_any:
        print(f"No daily results found for {', '.join(dates_to_check)} in any chat.")

if __name__ == "__main__":
    asyncio.run(analyze_today_points())
