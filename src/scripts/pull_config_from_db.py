import json
import os
import sys
import asyncio
from dotenv import load_dotenv

# Load env before importing db
load_dotenv()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.database import db

async def pull_config():
    print("Fetching system_config/game_config from Firestore...")
    config_doc = await db.collection("system_config").document("game_config").get()
    if config_doc.exists:
        config_data = config_doc.to_dict()
        with open('src/config/defaults.json', 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
        print("✅ Saved to src/config/defaults.json")
    else:
        print("❌ No game_config found in Firestore.")

    print("Fetching system_config/prompts from Firestore...")
    prompts_doc = await db.collection("system_config").document("prompts").get()
    if prompts_doc.exists:
        prompts_data = prompts_doc.to_dict()
        
        # Load existing prompts.json to preserve metadata
        with open('src/config/prompts.json', 'r', encoding='utf-8') as f:
            local_prompts = json.load(f)
            
        for key, template in prompts_data.items():
            if key in local_prompts:
                local_prompts[key]["default"] = template
                
        with open('src/config/prompts.json', 'w', encoding='utf-8') as f:
            json.dump(local_prompts, f, indent=4, ensure_ascii=False)
        print("✅ Saved to src/config/prompts.json")
    else:
        print("❌ No prompts found in Firestore.")

if __name__ == "__main__":
    asyncio.run(pull_config())
