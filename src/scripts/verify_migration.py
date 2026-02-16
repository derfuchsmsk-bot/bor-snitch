import asyncio
import os
import sys
from dotenv import load_dotenv
from google.cloud import firestore

# Load env vars first
load_dotenv()

# Add src to path
sys.path.append(os.getcwd())

from src.database import db

OLD_CHAT_ID = "-954103380"
NEW_CHAT_ID = "-1003893798466"

COLLECTIONS_TO_CHECK = [
    "agreements",
    "daily_results",
    "lessons",
    "lore",
    "memories",
    "messages",
    "user_stats",
    "verified_facts"
]

async def count_docs(collection_ref):
    count = 0
    async for _ in collection_ref.stream():
        count += 1
    return count

async def verify():
    print(f"Verifying migration from {OLD_CHAT_ID} to {NEW_CHAT_ID}...")
    
    source_chat_ref = db.collection("chats").document(OLD_CHAT_ID)
    target_chat_ref = db.collection("chats").document(NEW_CHAT_ID)
    
    all_match = True
    
    for col_name in COLLECTIONS_TO_CHECK:
        print(f"Checking '{col_name}'...")
        source_col = source_chat_ref.collection(col_name)
        target_col = target_chat_ref.collection(col_name)
        
        count_source = await count_docs(source_col)
        count_target = await count_docs(target_col)
        
        if count_source == count_target:
            print(f"  [OK] Count matches: {count_source}")
        else:
            print(f"  [FAIL] Count mismatch! Source: {count_source}, Target: {count_target}")
            all_match = False

    if all_match:
        print("\nSUCCESS: All collection counts match!")
    else:
        print("\nWARNING: Some counts do not match.")

if __name__ == "__main__":
    asyncio.run(verify())
