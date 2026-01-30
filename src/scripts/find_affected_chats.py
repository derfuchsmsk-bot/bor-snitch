import asyncio
import os
import sys

# Add src to path
sys.path.append(os.getcwd())

from src.services.db import db

async def find_chat():
    print("Searching for chats with daily results for 2026-01-30...")
    chats_ref = db.collection('chats')
    async for chat_doc in chats_ref.stream():
        daily_ref = chat_doc.reference.collection('daily_results').document('2026-01-30')
        doc = await daily_ref.get()
        if doc.exists:
            data = doc.to_dict()
            offenders = data.get('offenders', [])
            usernames = [o.get('username') for o in offenders]
            print(f"Found chat: {chat_doc.id}")
            print(f"Offenders: {usernames}")
            
            # Look at user stats to see if points are indeed higher than expected
            for offender in offenders:
                uid = str(offender.get('user_id'))
                if not uid: continue
                stats_ref = chat_doc.reference.collection('user_stats').document(uid)
                stats_doc = await stats_ref.get()
                if stats_doc.exists:
                    stats = stats_doc.to_dict()
                    print(f"  User {offender.get('username')} ({uid}): Total Points: {stats.get('total_points')}, Points in this record: {offender.get('points')}")

if __name__ == "__main__":
    asyncio.run(find_chat())
