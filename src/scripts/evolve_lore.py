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
from src.services.fact_service import FactService
from src.utils.game_config import config

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        return super().default(obj)

async def evolve_lore(chat_id: int):
    chat_id_str = str(chat_id)
    
    # 1. Get current lore (Full structure)
    current_lore_full = await LoreService.get_lore(chat_id)
    core = current_lore_full.get('core', current_lore_full)
    
    # 2. Get verified facts
    verified_facts = await FactService.get_facts(chat_id)
    verified_facts_str = json.dumps(verified_facts, ensure_ascii=False, indent=2, cls=DateTimeEncoder)
    
    # 3. Get recent memories
    memories_ref = db.collection("chats").document(chat_id_str).collection("memories")
    memories = []
    async for doc in memories_ref.order_by("date", direction=firestore.Query.DESCENDING).limit(14).stream():
        memories.append(doc.to_dict())
        
    if not memories:
        print(f"No memories found for chat {chat_id}. Skipping evolution.")
        return

    # 4. Prepare AI Prompt for "Truth Extraction"
    memories_text = json.dumps(memories, ensure_ascii=False, indent=2, cls=DateTimeEncoder)
    
    prompt = f"""
    You are the 'Truth Extractor' for the Snitch Bot.
    
    CORE LORE:
    {json.dumps(core, ensure_ascii=False, indent=2)}
    
    VERIFIED FACTS (Absolute Truth):
    {verified_facts_str}
    
    RECENT MEMORIES (Raw observations):
    {memories_text}
    
    TASK:
    1. Update the 'current_context' string. This should be a concise summary of what's happening lately (last 7 days).
    2. Identify NEW candidates for 'verified_facts'. A candidate is a fact mentioned multiple times or with high certainty in memories.
    3. Output ONLY valid JSON.

    JSON FORMAT:
    {{
      "current_context": "Text summary of recent events (Russian)",
      "new_candidates": [
        {{
          "text": "Fact text (Russian)",
          "confidence": 0.0-1.0,
          "reasoning": "Why this is a fact?"
        }}
      ]
    }}
    """
    
    model = GenerativeModel(config.AI_MODEL_ANALYSIS)
    
    try:
        print(f"Analyzing memories for chat {chat_id}...")
        response = await model.generate_content_async(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        analysis = json.loads(response.text)
        
        # 5. Update Context in Lore
        new_lore_data = current_lore_full.copy()
        new_lore_data['current_context'] = analysis.get('current_context', "")
        new_lore_data['updated_at'] = datetime.now(timezone.utc).isoformat()
        
        await LoreService.update_lore(chat_id, new_lore_data, generated_by="evolution_engine_v2")
        print("Current context updated.")
        
        # 6. Promote high-confidence candidates to Verified Facts
        for candidate in analysis.get('new_candidates', []):
            if candidate.get('confidence', 0) >= 0.8:
                await FactService.add_fact(
                    chat_id, 
                    candidate['text'], 
                    source="evolution_engine", 
                    confidence=candidate['confidence']
                )
                print(f"Promoted to Fact: {candidate['text']}")
            
        print("Lore evolution completed successfully!")
            
    except Exception as e:
        print(f"Evolution failed: {e}")

if __name__ == "__main__":
    chat_id = -954103380 # Default chat
    asyncio.run(evolve_lore(chat_id))
