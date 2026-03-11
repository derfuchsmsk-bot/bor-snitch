import asyncio
import os
import sys
import logging
from aiogram import Bot, types
from aiogram.types import BotCommand

# Add src to path to allow imports
sys.path.append(os.getcwd())

from src.utils.config import settings
from src.bot.handlers import get_chat_users
from src.utils.messages import ALL_COMMAND_TITLE
from src.utils.text import escape
from src.utils.game_config import config

from dotenv import load_dotenv

# Load env vars from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

async def test_all_command(chat_id: int):
    """
    Manually triggers the logic of the /all command for a specific chat.
    This simulates the command execution without needing a message update.
    """
    bot = Bot(token=settings.TELEGRAM_TOKEN)
    
    print(f"Testing /all logic for chat_id: {chat_id}...")
    
    try:
        # Re-using the same logic from handlers.py
        users, _ = await get_chat_users(chat_id)
        print(f"Found {len(users) if users else 0} users in DB.")
        
        if not users:
            print("No users found to tag.")
            return

        mentions = []
        for u in users:
            user_id = u['user_id']
            username = u['username']
            full_name = u['full_name'] or "Аноним"
            if username:
                mentions.append(f"@{escape(username)}")
            else:
                mentions.append(f"<a href='tg://user?id={user_id}'>{escape(full_name)}</a>")
        
        if not mentions:
            print("No mentions generated.")
            return

        chunk_size = config.MENTION_CHUNK_SIZE
        for i in range(0, len(mentions), chunk_size):
            chunk = mentions[i:i + chunk_size]
            text = ALL_COMMAND_TITLE + " ".join(chunk)
            
            print(f"Sending chunk {i//chunk_size + 1}...")
            await bot.send_message(chat_id, text, parse_mode="HTML")
            print("Message sent successfully.")
            
    except Exception as e:
        print(f"Error during test: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    # Use the main chat ID from config
    target_chat = settings.MAIN_CHAT_ID
    if len(sys.argv) > 1:
        try:
            target_chat = int(sys.argv[1])
        except ValueError:
            print(f"Invalid chat ID: {sys.argv[1]}")
            sys.exit(1)
            
    if not target_chat:
        print("No chat ID provided. Set MAIN_CHAT_ID in .env or pass as argument.")
        sys.exit(1)
        
    asyncio.run(test_all_command(target_chat))
