import asyncio
import json
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Load env vars first
load_dotenv()

# Set Google Cloud credentials if not set
if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS") and os.path.exists("service-account.json"):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath("service-account.json")

from src.services.db import db

async def backup_points():
    print("Starting points backup...")
    
    backup_data = {}
    
    # Get all chats
    chats_ref = db.collection("chats")
    async for chat_doc in chats_ref.stream():
        chat_id = chat_doc.id
        print(f"Processing chat {chat_id}...")
        
        backup_data[chat_id] = []
        
        stats_ref = chat_doc.reference.collection("user_stats")
        async for stat_doc in stats_ref.stream():
            data = stat_doc.to_dict()
            data['user_id'] = stat_doc.id # Ensure ID is preserved
            backup_data[chat_id].append(data)
            
    # Save to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(os.getcwd(), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    
    filename = os.path.join(backup_dir, f"points_backup_{timestamp}.json")
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
    print(f"Backup completed successfully. Saved to: {filename}")
    return filename

if __name__ == "__main__":
    asyncio.run(backup_points())
