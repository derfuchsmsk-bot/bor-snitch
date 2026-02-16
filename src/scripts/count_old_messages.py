import asyncio
import os
import sys
from dotenv import load_dotenv
from google.cloud import firestore

load_dotenv()
sys.path.append(os.getcwd())
from src.database import db

OLD_CHAT_ID = "-954103380"

async def count_messages():
    print(f"Counting messages in {OLD_CHAT_ID}...")
    coll = db.collection("chats").document(OLD_CHAT_ID).collection("messages")
    count = 0
    async for _ in coll.stream():
        count += 1
        if count % 1000 == 0:
            print(f"Counted {count}...")
    print(f"Total messages to migrate: {count}")

if __name__ == "__main__":
    asyncio.run(count_messages())
