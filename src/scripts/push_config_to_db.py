import json
import os
import sys
import asyncio
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.database import db

async def push_config():
    print("Reading src/config/defaults.json...")
    with open('src/config/defaults.json', 'r', encoding='utf-8') as f:
        config_data = json.load(f)
        
    print("Pushing system_config/game_config to Firestore...")
    await db.collection("system_config").document("game_config").set(config_data)
    print("✅ Pushed game_config.")

    print("Reading src/config/prompts.json...")
    with open('src/config/prompts.json', 'r', encoding='utf-8') as f:
        local_prompts = json.load(f)
        
    prompts_data = {k: v["default"] for k, v in local_prompts.items()}
        
    print("Pushing system_config/prompts to Firestore...")
    await db.collection("system_config").document("prompts").set(prompts_data)
    print("✅ Pushed prompts.")

if __name__ == "__main__":
    asyncio.run(push_config())
