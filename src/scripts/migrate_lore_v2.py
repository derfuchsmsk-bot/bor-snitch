import asyncio
import os
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load env vars first
load_dotenv()

# Add src to path
sys.path.append(os.getcwd())

from src.services.lore_service import LoreService
from src.services.db import db
from src.utils.lore import LORE_DATA

async def migrate_v2():
    chat_id = -954103380 # Main chat ID
    chat_id_str = str(chat_id)
    
    print(f"Migrating lore to V2 (Tiered Truth) for chat {chat_id}...")
    
    # 1. Prepare new structure
    # We split LORE_DATA into core and initial facts
    core = {
        "universe": LORE_DATA.get("universe"),
        "characters": LORE_DATA.get("characters"),
        "concepts": LORE_DATA.get("concepts"),
        "dictionary": LORE_DATA.get("dictionary")
    }
    
    # Initial verified facts from legendary events
    verified_facts = []
    for event in LORE_DATA.get("legendary_events", []):
        verified_facts.append({
            "text": event.get("desc") or event.get("title"),
            "date": event.get("date") or event.get("year"),
            "confidence": 1.0,
            "source": "historical_legend"
        })

    # 2. Update the main lore document
    new_lore_data = {
        "core": core,
        "current_context": "Бот запущен в режиме Tiered Truth. Пока новостей нет.",
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        # Update lore
        await LoreService.update_lore(chat_id, new_lore_data, generated_by="migration_v2")
        
        # 3. Create verified_facts collection
        facts_ref = db.collection("chats").document(chat_id_str).collection("verified_facts")
        
        # Clear existing facts if any (for idempotency)
        async for doc in facts_ref.stream():
            await doc.reference.delete()
            
        # Add initial facts
        for i, fact in enumerate(verified_facts):
            fact_id = f"initial_fact_{i}"
            await facts_ref.document(fact_id).set(fact)
            
        print(f"Migration successful! Lore V2 initialized with {len(verified_facts)} verified facts.")
        
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    asyncio.run(migrate_v2())
