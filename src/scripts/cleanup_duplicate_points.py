import asyncio
import os
import sys
import argparse

# Add src to path
sys.path.append(os.getcwd())

from src.services.db import db, calculate_rank

async def cleanup_points(chat_id, date_key, user_id, points_to_subtract, username=None):
    chat_id = str(chat_id)
    
    if not user_id and username:
        print(f"Searching for user {username} in chat {chat_id}...")
        stats_ref = db.collection("chats").document(chat_id).collection("user_stats")
        async for doc in stats_ref.stream():
            data = doc.to_dict()
            if data.get("username") == username or data.get("username") == username.lstrip('@'):
                user_id = doc.id
                break
    
    if not user_id:
        print(f"Error: Could not find user_id for {username or 'unknown user'}")
        return

    print(f"Cleaning up {points_to_subtract} points for user {user_id} in chat {chat_id} for date {date_key}...")
    
    user_id = str(user_id)
    user_stats_ref = db.collection("chats").document(chat_id).collection("user_stats").document(user_id)
    doc = await user_stats_ref.get()
    
    if not doc.exists:
        print(f"Error: User {user_id} stats not found in chat {chat_id}.")
        return

    data = doc.to_dict()
    current_points = data.get("total_points", 0)
    new_points = max(0, current_points - points_to_subtract)
    new_rank = calculate_rank(new_points)
    
    # Also decrement snitch_count if we are removing a whole day's violation
    current_wins = data.get("snitch_count", 0)
    new_wins = max(0, current_wins - 1)

    await user_stats_ref.update({
        "total_points": new_points,
        "snitch_count": new_wins,
        "current_rank": new_rank
    })
    
    print(f"Successfully updated user {user_id}. Points: {current_points} -> {new_points}. Wins: {current_wins} -> {new_wins}.")

async def main():
    parser = argparse.ArgumentParser(description="Cleanup duplicate points for a user.")
    parser.add_argument("--chat_id", required=True, help="Telegram Chat ID")
    parser.add_argument("--date", default="2026-01-30", help="Date of the duplicate analysis")
    parser.add_argument("--user_id", help="Telegram User ID (optional if username provided)")
    parser.add_argument("--username", help="Telegram Username (optional if user_id provided)")
    parser.add_argument("--points", type=int, required=True, help="Number of points to subtract")
    
    args = parser.parse_args()
    
    if not args.user_id and not args.username:
        print("Error: Either --user_id or --username must be provided.")
        return

    await cleanup_points(args.chat_id, args.date, args.user_id, args.points, username=args.username)

if __name__ == "__main__":
    asyncio.run(main())
