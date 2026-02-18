import asyncio
import argparse
import sys
import os
import math
import re
from datetime import datetime, timedelta, timezone
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
from src.utils.game_config import config

# Constants
TARGET_CATEGORIES = ["Snitching"] # Currently Whining/Stiffness fall under Snitching often, but let's check text
TARGET_KEYWORDS = ["нытье", "духота", "whining", "stiffness"]
AMNESTY_DAY_OF_WEEK = 6 # Sunday (0=Monday, 6=Sunday)
AMNESTY_HOUR = 23
AMNESTY_MINUTE = 59

def calculate_decayed_points(points, event_date_str):
    """
    Calculates how many points remain from the original amount after weekly amnesties.
    Amnesty happens every Sunday at 23:59.
    """
    try:
        event_date = datetime.fromisoformat(event_date_str)
    except ValueError:
        # Fallback for simple date strings
        event_date = datetime.strptime(event_date_str, "%Y-%m-%d")

    # Ensure timezone awareness (assume UTC if none, though project uses MSK mostly)
    if event_date.tzinfo is None:
        event_date = event_date.replace(tzinfo=timezone.utc)
        
    now = datetime.now(timezone.utc)
    
    current_points = points
    
    # Iterate through days from event to now to find Sundays
    current_check = event_date
    amnesties_passed = 0
    
    loop_limit = 1000
    loop_count = 0
    
    while current_check < now:
        loop_count += 1
        if loop_count > loop_limit:
            print(f"WARNING: Loop limit reached for date {event_date_str}")
            break
            
        # Calculate next amnesty (Next Sunday 23:59) strictly AFTER current_check
        days_until_sunday = (AMNESTY_DAY_OF_WEEK - current_check.weekday() + 7) % 7
        candidate_amnesty = current_check + timedelta(days=days_until_sunday)
        candidate_amnesty = candidate_amnesty.replace(hour=AMNESTY_HOUR, minute=AMNESTY_MINUTE, second=0, microsecond=0)
        
        # If the candidate is not in the future relative to current_check, add a week
        if candidate_amnesty <= current_check:
            candidate_amnesty += timedelta(days=7)

        # If this next amnesty has already happened relative to 'now', apply it
        if candidate_amnesty < now:
            amnesties_passed += 1
            current_points = current_points // 2
            current_check = candidate_amnesty # Move up to this amnesty point
        else:
            # The next amnesty hasn't happened yet
            break
            
    return current_points, amnesties_passed

async def cleanup_whining_stiffness(dry_run=True):
    print(f"Starting Cleanup Script (Dry Run: {dry_run})...")
    
    chats_ref = db.collection("chats")
    
    total_deductions = {} # user_id -> points_to_remove
    user_names = {}
    
    chat_docs = await chats_ref.get()
    print(f"Found {len(chat_docs)} chats.")
    
    for chat_doc in chat_docs:
        chat_id = chat_doc.id
        print(f"Processing Chat: {chat_id}")
        
        # 1. Iterate through daily results
        daily_ref = chat_doc.reference.collection("daily_results")
        daily_docs = await daily_ref.get()
        print(f"  Found {len(daily_docs)} daily results.")
        
        for daily_doc in daily_docs:
            data = daily_doc.to_dict()
            date_key = daily_doc.id
            offenders = data.get('offenders', [])
            
            for offender in offenders:
                reason = offender.get('reason', '').lower()
                category = offender.get('category', '')
                points = offender.get('points', 0)
                user_id = str(offender.get('user_id'))
                username = offender.get('username', 'Unknown')
                
                # Check if this entry matches Whining or Stiffness
                is_direct_category = category in ["Stiffness", "Whining", "Духота", "Нытье"]
                
                is_keyword_match = False
                if not is_direct_category:
                    for kw in TARGET_KEYWORDS:
                        if kw in reason:
                            is_keyword_match = True
                            break
                
                points_to_remove = 0
                
                if is_direct_category and points > 0:
                    # Case A: Explicit Category -> Remove all points
                    points_to_remove = points
                    print(f"  [CATEGORY MATCH] {date_key}: {username} - Category: {category} ({points} pts)")
                    
                elif is_keyword_match and points > 0:
                    # Case B: Keyword Match -> Safety Logic
                    
                    # 1. Try to extract specific points from text (e.g. "whining (10)")
                    extracted_points = 0
                    # Matches: "нытье ... (10", "stiffness - 15"
                    matches = re.findall(r"(?:нытье|духота|whining|stiffness).*?[-—\s\(]+(\d+)", reason)
                    if matches:
                        # Filter out unlikely large numbers (years)
                        valid_matches = [int(m) for m in matches if int(m) < 100]
                        extracted_points = sum(valid_matches)
                        
                    if extracted_points > 0:
                        points_to_remove = extracted_points
                        # Cap at total points just in case
                        points_to_remove = min(points_to_remove, points)
                    elif points <= 20:
                        # 2. If no specific points found, but total is small, assume it's all whining/stiffness
                        points_to_remove = points
                    else:
                        # 3. High points (likely Snitching) and no specific breakdown found -> SKIP
                        print(f"  [SKIP] {date_key}: {username} - High points ({points}) with ambiguous reason.")
                        continue
                
                if points_to_remove > 0:

                    # Calculate how much of these points are still "alive"
                    remaining_points, amnesties = calculate_decayed_points(points_to_remove, date_key)
                    
                    if remaining_points > 0:
                        if user_id not in total_deductions:
                            total_deductions[user_id] = 0
                            user_names[user_id] = username
                            
                        total_deductions[user_id] += remaining_points
                        
                        print(f"  [MATCH] {date_key}: {username} - {reason} ({points} pts)")
                        if points_to_remove != points:
                             print(f"      -> Identified {points_to_remove} pts for removal (mixed penalty).")
                        print(f"      -> {amnesties} amnesties passed. Remaining effect: {remaining_points} pts")

    print("\n--- SUMMARY OF DEDUCTIONS ---")
    if not total_deductions:
        print("No points to remove found.")
        return

    for user_id, deduction in total_deductions.items():
        name = user_names.get(user_id)
        print(f"User: {name} (ID: {user_id}) -> Remove {deduction} points")
        
        if not dry_run:
            # Apply update
            # Need to fetch current stats first to be safe
             stats = await user_repository.get_user_stats(chat_id, int(user_id))
             if stats:
                 current_total = stats.get('total_points', 0)
                 new_total = max(0, current_total - deduction)
                 new_rank = user_repository.calculate_rank(new_total)
                 
                 await db.collection("chats").document(chat_id).collection("user_stats").document(user_id).update({
                     "total_points": new_total,
                     "current_rank": new_rank
                 })
                 print(f"      [UPDATED] {current_total} -> {new_total}")
             else:
                 print(f"      [ERROR] User stats not found for {user_id}")

    if not dry_run:
        print("\nChanges applied successfully.")
        
        # Generate Report Text for Telegram
        report_text = "🧹 <b>Амнистия: Очистка от Нытья и Духоты</b>\n\n"
        report_text += "Согласно указу, все баллы, начисленные за категории «Нытье» и «Духота», были аннулированы (с учетом прошедших еженедельных списаний).\n\n"
        
        for user_id, deduction in total_deductions.items():
             name = user_names.get(user_id)
             if name.startswith("@"):
                 report_text += f"👤 {name}: -{deduction} очков\n"
             else:
                 report_text += f"👤 <b>{name}</b>: -{deduction} очков\n"
                 
        print("\n--- REPORT TEXT FOR TELEGRAM ---")
        print(report_text)
        print("--------------------------------")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Cleanup Whining and Stiffness points.')
    parser.add_argument('--run', action='store_true', help='Execute changes (disable dry-run)')
    args = parser.parse_args()
    
    asyncio.run(cleanup_whining_stiffness(dry_run=not args.run))
