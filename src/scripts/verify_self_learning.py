import asyncio
import os
import sys
from dotenv import load_dotenv

# Load env vars first
load_dotenv()

# Add src to path
sys.path.append(os.getcwd())

from src.services.ai import analyze_daily_logs
from src.services.lore_service import LoreService

async def verify_injection():
    chat_id = -954103380
    print(f"Verifying lore injection for chat {chat_id}...")
    
    # 1. Check if we can get lore
    lore = await LoreService.get_lore(chat_id)
    print(f"Lore version in DB: {lore.get('universe', {}).get('name', 'Unknown')}")
    
    # 2. Mock logs
    logs = [
        {"username": "test_user", "text": "Hello bot", "timestamp": "2026-02-11T12:00:00Z", "user_id": 123}
    ]
    
    # 3. Call analysis (this will trigger prompt generation)
    # We don't necessarily need to wait for the whole AI response if we just want to verify the logic doesn't crash
    # But since we're here, let's see if it works.
    print("Calling analyze_daily_logs...")
    result = await analyze_daily_logs(logs, chat_id=chat_id, date_str="2026-02-11")
    
    if result:
        print("Success! AI responded using dynamic lore.")
        if "ai_thought_process" in result:
             print(f"Thought process snippet: {result['ai_thought_process'][:100]}...")
    else:
        print("Failed to get AI response.")

if __name__ == "__main__":
    asyncio.run(verify_injection())
