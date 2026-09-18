import asyncio
import argparse
import sys
import os
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

load_dotenv()

if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS") and os.path.exists("service-account.json"):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath("service-account.json")

from src.services.db import db
from src.repositories.user_repository import user_repository


async def main():
    parser = argparse.ArgumentParser(description="Check and reset false report strikes")
    parser.add_argument("--chat_id", type=str, help="Chat ID")
    parser.add_argument("--user_id", type=str, help="User ID to reset")
    parser.add_argument("--reset", action="store_true", help="Reset false_report_count to 0")
    args = parser.parse_args()

    chats_ref = db.collection("chats")

    if args.chat_id:
        chat_docs = [await chats_ref.document(str(args.chat_id)).get()]
    else:
        chat_docs = [doc async for doc in chats_ref.stream()]

    print(f"Found {len(chat_docs)} chat(s) to inspect.\n")

    for chat in chat_docs:
        if not chat.exists:
            continue
        c_id = chat.id
        users_ref = chats_ref.document(c_id).collection("users")
        
        async for u_doc in users_ref.stream():
            u_data = u_doc.to_dict() or {}
            false_reports = u_data.get("false_report_count", 0)
            u_id = u_doc.id
            username = u_data.get("username") or u_data.get("first_name") or u_id

            if args.user_id and str(args.user_id) != str(u_id):
                continue

            if false_reports > 0 or args.user_id:
                print(f"Chat: {c_id} | User: {username} ({u_id}) | false_report_count: {false_reports}")
                if args.reset:
                    await user_repository.reset_false_report_count(int(c_id), int(u_id))
                    print(f"  -> Reset false_report_count to 0 for {username} ({u_id})")


if __name__ == "__main__":
    asyncio.run(main())
