import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from src.services.db import db, apply_weekly_amnesty

logging.basicConfig(level=logging.INFO)

async def main():
    logging.info("Starting Weekly Amnesty (Halving points accumulated in the last 7 days)...")
    
    # Get all chats
    chats_ref = db.collection("chats")
    
    # Stream all chats
    try:
        async for doc in chats_ref.stream():
            chat_id = doc.id
            logging.info(f"Processing chat {chat_id}...")
            try:
                await apply_weekly_amnesty(chat_id)
                logging.info(f"Chat {chat_id} processed.")
            except Exception as e:
                logging.error(f"Error processing chat {chat_id}: {e}")
    except Exception as e:
        logging.error(f"Error streaming chats: {e}")
            
    logging.info("Weekly Amnesty Completed.")

if __name__ == "__main__":
    asyncio.run(main())
