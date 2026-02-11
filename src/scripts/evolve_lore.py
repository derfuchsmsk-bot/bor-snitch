import asyncio
import os
import sys
import json
import logging
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from vertexai.generative_models import GenerativeModel

# Load env vars first
load_dotenv()

# Add src to path
sys.path.append(os.getcwd())

from google.cloud import firestore
from src.services.db import db
from src.services.lore_service import LoreService

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        return super().default(obj)
from src.services.learning import LearningService
from src.utils.game_config import config

async def evolve_lore(chat_id: int):
    chat_id_str = str(chat_id)
    
    # 1. Get current lore
    current_lore = await LoreService.get_lore(chat_id)
    
    # 2. Get recent memories (last 30 days)
    memories_ref = db.collection("chats").document(chat_id_str).collection("memories")
    # Fetch all memories (we assume there are not thousands)
    # In a real scenario, we'd filter by date
    memories = []
    async for doc in memories_ref.order_by("date", direction=firestore.Query.DESCENDING).limit(30).stream():
        memories.append(doc.to_dict())
        
    if not memories:
        print(f"No memories found for chat {chat_id}. Skipping evolution.")
        return

    # 3. Get active lessons
    lessons_ref = db.collection("chats").document(chat_id_str).collection("lessons")
    lessons = []
    async for doc in lessons_ref.where(filter=firestore.FieldFilter("status", "==", "active")).stream():
        lessons.append(doc.to_dict().get("learned_rule"))

    # 4. Prepare AI Prompt
    memories_text = json.dumps(memories, ensure_ascii=False, indent=2, cls=DateTimeEncoder)
    lessons_text = "\n".join([f"- {l}" for l in lessons])
    
    prompt = f"""
    You are the 'Evolution Engine' of the Snitch Bot.
    
    CURRENT LORE:
    {json.dumps(current_lore, ensure_ascii=False, indent=2)}
    
    RECENT MEMORIES (Last 30 days):
    {memories_text}
    
    LEARNED LESSONS (Behavioral adjustments):
    {lessons_text}
    
    TASK:
    Generate an UPDATED LORE JSON that incorporates new facts, character developments, and events from the memories.
    Also, if lessons suggest permanent character traits (e.g., "Bot should stop joking about X"), update the character description of the Bot (if present) or general 'concepts'.
    
    INSTRUCTIONS:
    1. Output ONLY valid JSON.
    2. Maintain the cynical, street-smart tone.
    3. Be selective: only add legendary events or significant character changes.
    4. Language: Russian.
    """
    
    model = GenerativeModel(config.AI_MODEL_ANALYSIS)
    
    try:
        print(f"Evolving lore for chat {chat_id}...")
        response = await model.generate_content_async(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        new_lore = json.loads(response.text)
        
        # 5. Save new lore
        version = await LoreService.update_lore(chat_id, new_lore, generated_by="evolution_engine")
        print(f"Lore evolved successfully to version {version}!")
        
        # 6. Archive lessons that were incorporated
        # For simplicity, we just mark all current active lessons as 'archived'
        # In a real system, we might want to be more granular.
        async for doc in lessons_ref.where(filter=firestore.FieldFilter("status", "==", "active")).stream():
            await doc.reference.update({"status": "archived", "archived_at": datetime.now(timezone.utc)})
            
    except Exception as e:
        print(f"Evolution failed: {e}")

if __name__ == "__main__":
    chat_id = -954103380 # Default chat
    asyncio.run(evolve_lore(chat_id))
