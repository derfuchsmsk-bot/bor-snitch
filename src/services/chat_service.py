import random
from datetime import datetime
from ..utils.game_config import config
from ..services import db
from ..services import ai
import logging

class ChatService:
    # Global state for cynical comment cooldowns (chat_id -> datetime)
    _last_comment_time = {}

    @classmethod
    async def cleanup_old_cooldowns(cls):
        """Periodically clean up old cooldown entries to prevent memory leaks."""
        now = datetime.now()
        for chat_id, last_time in list(cls._last_comment_time.items()):
            if (now - last_time).total_seconds() > config.CYNICAL_COMMENT_COOLDOWN_SECONDS * 2:
                del cls._last_comment_time[chat_id]

    @classmethod
    def should_comment(cls, text: str, stats: dict, is_mentioned: bool = False) -> bool:
        """
        Logic for 'Smart' Cynical Comments.
        """
        if not text or text.startswith('/'):
            return False
            
        # If mentioned, we almost always want to reply (unless it's a command handled elsewhere)
        if is_mentioned:
            return True

        chance = config.CYNICAL_COMMENT_CHANCE
        text_lower = text.lower()
        
        # Keyword triggers (strongest trigger)
        if any(kw in text_lower for kw in ["бот", "bot", "снитч", "snitch", "ии", "ai"]):
            chance += 0.15
        
        # Question trigger (native dialogue integration)
        if "?" in text:
            chance += 0.05
        
        # Emotional trigger
        if "!" in text:
            chance += 0.02
            
        # Rant trigger
        if len(text) > 150:
            chance += 0.05
            
        # High points target trigger (roast the sinners)
        if stats and stats.get('total_points', 0) > 100:
            chance += 0.02
            
        return random.random() < chance

    @classmethod
    async def process_cynical_comment(cls, message, comment_text: str):
        """
        Processes a potential cynical comment.
        Returns the generated comment if one should be sent, else None.
        """
        if not comment_text or comment_text.startswith('/'):
            return None

        try:
            chat_id = message.chat.id
            now = datetime.now()
            last_time = cls._last_comment_time.get(chat_id)
            
            # Robust Mention Detection: @bot or reply to bot
            bot_user = await message.bot.get_me()
            is_mentioned = False
            
            if message.text:
                is_mentioned = f"@{bot_user.username}" in message.text
            
            if not is_mentioned and message.reply_to_message:
                is_mentioned = message.reply_to_message.from_user.id == bot_user.id
            
            # If mentioned, ignore cooldown. Otherwise check cooldown.
            if is_mentioned or (not last_time or (now - last_time).total_seconds() > config.CYNICAL_COMMENT_COOLDOWN_SECONDS):
                user_stats = await db.get_user_stats(chat_id, message.from_user.id)
                
                # If mentioned, force reply. Otherwise roll dice.
                if cls.should_comment(comment_text, user_stats, is_mentioned):
                    # Increased context limit to 10 for better conversation history awareness
                    context_msgs = await db.get_recent_messages(chat_id, message.date, limit=10)
                    username = message.from_user.username or message.from_user.first_name
                    
                    comment = await ai.generate_cynical_comment(
                        context_msgs, 
                        comment_text, 
                        username, 
                        chat_id=chat_id
                    )
                    
                    if comment:
                        cls._last_comment_time[chat_id] = now
                        return comment
        except Exception as e:
            logging.error(f"Error in process_cynical_comment: {e}")
            
        return None
