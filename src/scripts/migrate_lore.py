import asyncio
import os
import sys
from dotenv import load_dotenv

# Load env vars first
load_dotenv()

# Add src to path
sys.path.append(os.getcwd())

from src.services.lore_service import LoreService
from src.utils.lore import LORE_DATA
from src.utils.config import settings

async def migrate():
    # Primary chat ID from generate_monthly_lore.py or config
    chat_id = settings.MAIN_CHAT_ID
    
    print(f"Migrating default lore to Firestore for chat {chat_id}...")
    
    try:
        version = await LoreService.update_lore(chat_id, LORE_DATA, generated_by="initial_migration")
        print(f"Migration successful! Lore version {version} created.")
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    asyncio.run(migrate())
