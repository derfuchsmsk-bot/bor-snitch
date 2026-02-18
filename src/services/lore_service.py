import json
import logging
from datetime import datetime, timezone
from google.cloud import firestore
from vertexai.generative_models import GenerativeModel

from .db import db
from ..utils.game_config import config
from .fact_service import FactService

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        return super().default(obj)

class LoreService:
    @staticmethod
    async def get_lore(chat_id: int):
        """
        Fetches lore for a specific chat.
        Falls back to empty default if not found in DB.
        """
        chat_id_str = str(chat_id)
        doc_ref = db.collection("chats").document(chat_id_str).collection("lore").document("current")
        
        default_lore = {
            "core": {
                "universe": "Cynical Snitch Bot Ecosystem",
                "characters": [],
                "concepts": [],
                "dictionary": {}
            },
            "current_context": "Initial state.",
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            doc = await doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                return data.get("data") or data # Handle both nested and flat structures
            else:
                logging.info(f"Lore not found for chat {chat_id}, using minimal default.")
                return default_lore
        except Exception as e:
            logging.error(f"Error fetching lore from DB: {e}")
            return default_lore

    @staticmethod
    async def get_lore_as_json(chat_id: int):
        """Returns lore as a formatted JSON string for prompts."""
        lore_data = await LoreService.get_lore(chat_id)
        return json.dumps(lore_data, ensure_ascii=False, indent=2)

    @staticmethod
    async def update_lore(chat_id: int, new_lore_data: dict, generated_by: str = "system"):
        """Updates the lore in Firestore."""
        chat_id_str = str(chat_id)
        doc_ref = db.collection("chats").document(chat_id_str).collection("lore").document("current")
        
        # Get current version to increment
        doc = await doc_ref.get()
        version = 1
        if doc.exists:
            version = doc.to_dict().get("version", 0) + 1

        payload = {
            "data": new_lore_data,
            "version": version,
            "updated_at": datetime.now(timezone.utc),
            "generated_by": generated_by
        }
        
        await doc_ref.set(payload)
        logging.info(f"Lore updated to version {version} for chat {chat_id}")
        return version

    @staticmethod
    async def evolve_lore(chat_id: int):
        """
        Analyzes recent memories and verified facts to evolve the chat's lore.
        Updates current_context and adds new verified facts.
        """
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
            logging.info(f"No memories found for chat {chat_id}. Skipping evolution.")
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
            logging.info(f"Analyzing memories for chat {chat_id}...")
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
            logging.info(f"Lore evolution: Current context updated for chat {chat_id}.")
            
            # 6. Promote high-confidence candidates to Verified Facts
            for candidate in analysis.get('new_candidates', []):
                if candidate.get('confidence', 0) >= 0.8:
                    await FactService.add_fact(
                        chat_id, 
                        candidate['text'], 
                        source="evolution_engine", 
                        confidence=candidate['confidence']
                    )
                    logging.info(f"Lore evolution: Promoted to Fact for chat {chat_id}: {candidate['text']}")
                
            logging.info(f"Lore evolution completed successfully for chat {chat_id}!")
                
        except Exception as e:
            logging.error(f"Lore evolution failed for chat {chat_id}: {e}")
