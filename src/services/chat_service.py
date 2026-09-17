import random
from datetime import datetime, timezone
from ..utils.game_config import config
from ..services import db
from ..services import ai
from ..services.mood_service import MoodService
from ..services.dossier_service import DossierService
import logging

class ChatService:
    # Cooldown states: chat_id -> datetime, (chat_id, user_id) -> datetime
    _last_comment_time = {}
    _last_user_comment_time = {}
    _last_reaction_time = {}

    @classmethod
    async def cleanup_old_cooldowns(cls):
        """Periodically clean up old cooldown entries to prevent memory leaks."""
        now = datetime.now()
        for chat_id, last_time in list(cls._last_comment_time.items()):
            if (now - last_time).total_seconds() > config.CYNICAL_COMMENT_COOLDOWN_SECONDS * 3:
                del cls._last_comment_time[chat_id]
        for key, last_time in list(cls._last_user_comment_time.items()):
            if (now - last_time).total_seconds() > config.CYNICAL_COMMENT_COOLDOWN_SECONDS * 3:
                del cls._last_user_comment_time[key]
        for chat_id, last_time in list(cls._last_reaction_time.items()):
            if (now - last_time).total_seconds() > getattr(config, "REACTION_COOLDOWN_SECONDS", 120) * 3:
                del cls._last_reaction_time[chat_id]

    @classmethod
    def should_react(cls, chat_id: int, text: str, stats: dict) -> tuple[bool, str]:
        """
        Determines whether the bot should put an emoji reaction on a message and chooses which emoji.
        """
        if not getattr(config, "REACTIONS_ENABLED", True):
            return False, ""

        if not text or text.startswith('/'):
            return False, ""

        now = datetime.now()
        last_time = cls._last_reaction_time.get(chat_id)
        cooldown = getattr(config, "REACTION_COOLDOWN_SECONDS", 120)
        if last_time and (now - last_time).total_seconds() < cooldown:
            return False, ""

        allowed_emojis = getattr(config, "REACTION_ALLOWED_EMOJIS", ["🤡", "🗿", "🚽", "👑", "🍿", "👀", "🔥", "👌"])
        if not allowed_emojis:
            return False, ""

        base_chance = getattr(config, "REACTION_CHANCE", 0.02)
        chance = base_chance
        text_lower = text.lower()
        preferred_emoji = None

        # Triggers:
        # 1. Whining, cringe, complaining -> 🤡
        if any(w in text_lower for w in ["устал", "все плохо", "всё плохо", "тяжело", "кринж", "душно", "зануда", "бред", "ппц", "жесть", "нытье", "обиделся"]):
            chance += 0.08
            preferred_emoji = "🤡"

        # 2. Sinner roast target (high points / rank Обиженный / Козёл) -> 🚽 or 🤡
        pts = stats.get('total_points', 0) if stats else 0
        if pts >= 250:
            chance += 0.06
            preferred_emoji = "🚽" if "🚽" in allowed_emojis else "🤡"

        # 3. Drama, gossip, accusations, snitching -> 🍿 or 👀
        if any(w in text_lower for w in ["донос", "крыса", "снитч", "предатель", "врешь", "врёшь", "спорим", "забьемся", "докажи", "слился", "позор"]):
            chance += 0.08
            preferred_emoji = "🍿" if "🍿" in allowed_emojis else "👀"

        # 4. Sigma / pact / agreement / respect -> 🗿 or 👑
        if any(w in text_lower for w in ["по рукам", "договорились", "базар", "пацан", "красава", "база", "согласен", "победа", "слово"]):
            chance += 0.08
            preferred_emoji = "🗿" if "🗿" in allowed_emojis else "👑"

        # 5. Stickers / memes -> 🔥 or 🤡
        if "[sticker]" in text_lower or "[image/meme]" in text_lower:
            chance += 0.05
            preferred_emoji = "🔥" if "🔥" in allowed_emojis else "🤡"

        # 6. Questions
        if "?" in text:
            chance += 0.04
            preferred_emoji = "👀"

        if random.random() < chance:
            if preferred_emoji and preferred_emoji in allowed_emojis:
                chosen = preferred_emoji
            else:
                chosen = random.choice(allowed_emojis)
            return True, chosen

        return False, ""

    @classmethod
    async def process_reaction(cls, message, comment_text: str):
        """
        Attempts to apply a cynical emoji reaction to the user's message.
        """
        try:
            if config.BOT_DISABLED or not getattr(config, "REACTIONS_ENABLED", True):
                return False

            if getattr(message.from_user, 'is_bot', False):
                return False

            chat_id = message.chat.id
            user_id = message.from_user.id
            user_stats = await db.get_user_stats(chat_id, user_id)

            should, emoji = cls.should_react(chat_id, comment_text, user_stats)
            if should and emoji:
                from aiogram.types import ReactionTypeEmoji
                cls._last_reaction_time[chat_id] = datetime.now()
                try:
                    await message.react(reaction=[ReactionTypeEmoji(emoji=emoji)])
                    logging.info(f"Bot reacted with {emoji} to message {message.message_id} in chat {chat_id}")
                    return True
                except Exception as e:
                    logging.debug(f"Could not apply reaction {emoji}: {e}")
                    return False
        except Exception as e:
            logging.debug(f"Error in process_reaction: {e}")
        return False

    @classmethod
    def should_comment(cls, text: str, stats: dict, is_mentioned: bool = False) -> bool:
        """
        Fast Heuristic Filter for 'Smart' Cynical Comments.
        """
        if not text or text.startswith('/'):
            return False
            
        # If directly mentioned or replied to, always reply!
        if is_mentioned:
            return True

        mood = MoodService.get_current_mood()
        chance = config.CYNICAL_COMMENT_CHANCE * mood.cynicism_multiplier
        text_lower = text.lower()
        
        # Keyword triggers (strongest trigger)
        if any(kw in text_lower for kw in ["бот", "bot", "снитч", "snitch", "ии", "ai", "судья", "масть", "очки"]):
            chance += 0.20
        
        # Meme / Image trigger (bot loves reacting to visual humor)
        if "[image/meme]" in text_lower:
            chance += 0.12

        # Voice note trigger
        if "[voice]" in text_lower or "[video note]" in text_lower:
            chance += 0.05
        
        # Question trigger
        if "?" in text:
            chance += 0.06
        
        # Emotional debate / scream trigger
        if "!" in text or (len(text) > 20 and text.isupper()):
            chance += 0.05
            
        # Rant trigger
        if len(text) > 150:
            chance += 0.05
            
        # Sinner roast target (roast users with high points)
        if stats and stats.get('total_points', 0) > 150:
            chance += 0.05
            
        return random.random() < chance

    @classmethod
    async def process_cynical_comment(cls, message, comment_text: str):
        """
        Processes a potential cynical comment with Fast & Slow attention logic.
        Returns the generated comment if one should be sent, else None.
        """
        if not comment_text or comment_text.startswith('/'):
            return None

        try:
            chat_id = message.chat.id
            user_id = message.from_user.id
            now = datetime.now()
            
            # Robust Mention Detection: @bot or reply to bot
            bot_user = await message.bot.get_me()
            is_mentioned = False
            is_reply_to_bot = False
            
            if message.text:
                is_mentioned = f"@{bot_user.username}" in message.text
            
            if message.reply_to_message and message.reply_to_message.from_user.id == bot_user.id:
                is_mentioned = True
                is_reply_to_bot = True
            
            # Special Check: Correction loop when replying to bot
            if is_reply_to_bot:
                correction_keywords = ["неправда", "врешь", "врёшь", "забудь", "ошибка", "wrong", "lie", "бред", "галлюцинация", "hallucination"]
                if any(kw in comment_text.lower() for kw in correction_keywords):
                    # User is correcting the bot
                    cls._last_comment_time[chat_id] = now
                    cls._last_user_comment_time[(chat_id, user_id)] = now
                    return "🤐 Понял, завязываю галлюцинировать. Зафиксировал ошибку в протоколе, больше не повторится."

            # Cooldown check:
            last_chat_time = cls._last_comment_time.get(chat_id)
            last_user_time = cls._last_user_comment_time.get((chat_id, user_id))
            
            # Mentions bypass cooldown. Spontaneous remarks respect cooldowns.
            if not is_mentioned:
                if last_chat_time and (now - last_chat_time).total_seconds() < config.CYNICAL_COMMENT_COOLDOWN_SECONDS:
                    return None
                if last_user_time and (now - last_user_time).total_seconds() < (config.CYNICAL_COMMENT_COOLDOWN_SECONDS * 1.5):
                    return None

            user_stats = await db.get_user_stats(chat_id, user_id)
            
            if cls.should_comment(comment_text, user_stats, is_mentioned):
                context_msgs = await db.get_recent_messages(chat_id, message.date, limit=12)
                username = message.from_user.username or message.from_user.first_name
                
                comment = await ai.generate_cynical_comment(
                    context_msgs, 
                    comment_text, 
                    username, 
                    chat_id=chat_id
                )
                
                if comment:
                    cls._last_comment_time[chat_id] = now
                    cls._last_user_comment_time[(chat_id, user_id)] = now
                    return comment
        except Exception as e:
            logging.error(f"Error in process_cynical_comment: {e}")
            
        return None

