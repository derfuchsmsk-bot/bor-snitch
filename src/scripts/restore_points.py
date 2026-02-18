import asyncio
import json
import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Load env vars first
load_dotenv()

# Set Google Cloud credentials if not set
if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS") and os.path.exists("service-account.json"):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath("service-account.json")

from src.services.db import db

async def restore_points(backup_file_path):
    print(f"Starting points restoration from {backup_file_path}...")
    
    if not os.path.exists(backup_file_path):
        print(f"Error: Backup file {backup_file_path} not found.")
        return
        
    with open(backup_file_path, 'r', encoding='utf-8') as f:
        backup_data = json.load(f)
        
    for chat_id, users_stats in backup_data.items():
        print(f"Restoring stats for chat {chat_id}...")
        
        chat_ref = db.collection("chats").document(str(chat_id))
        stats_ref = chat_ref.collection("user_stats")
        
        # Batch updates for efficiency
        batch = db.batch()
        count = 0
        
        for user_data in users_stats:
            user_id = str(user_data.get('user_id'))
            if not user_id:
                print(f"Skipping user without ID: {user_data}")
                continue
                
            doc_ref = stats_ref.document(user_id)
            
            # Remove the ID from the data payload as it's the document key
            data_to_save = {k: v for k, v in user_data.items() if k != 'user_id'}
            
            batch.set(doc_ref, data_to_save, merge=True)
            count += 1
            
            if count >= 400: # Firestore batch limit is 500
                await batch.commit()
                batch = db.batch()
                count = 0
                print("Committed batch...")
                
        if count > 0:
            await batch.commit()
            
        print(f"Restored {len(users_stats)} users for chat {chat_id}.")
            
    print("Restoration completed successfully.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python src/scripts/restore_points.py <path_to_backup_json>")
    else:
        asyncio.run(restore_points(sys.argv[1]))
