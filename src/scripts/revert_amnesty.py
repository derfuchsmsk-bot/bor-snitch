import asyncio
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
from src.repositories.user_repository import user_repository

async def revert_amnesty():
    chat_id = -1003893798466
    
    # Reductions that were applied:
    to_restore = {
        "974975544": 2,   # MosesKmS
        "213555791": 20,  # ustaliyputnik
        "383998331": 70,  # Arsinov
        "460322254": 8,   # shaloputnik
        "991728230": 11,  # ioann_thegreat
        "200666412": 8,   # derfuchz
        "615090692": 14   # prodolzhayem
    }
    
    print(f"Reverting changes for chat {chat_id}...")
    
    for user_id_str, points in to_restore.items():
        user_id = int(user_id_str)
        stats = await user_repository.get_user_stats(chat_id, user_id)
        if stats:
            current_total = stats.get('total_points', 0)
            new_total = current_total + points
            new_rank = user_repository.calculate_rank(new_total)
            
            await db.collection("chats").document(str(chat_id)).collection("user_stats").document(user_id_str).update({
                "total_points": new_total,
                "current_rank": new_rank
            })
            print(f"Restored {user_id_str}: {current_total} -> {new_total} (+{points})")
        else:
            print(f"Could not find stats for user {user_id_str}")

    print("Revert completed.")

if __name__ == "__main__":
    asyncio.run(revert_amnesty())
