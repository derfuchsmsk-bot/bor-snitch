import random
from datetime import datetime, timezone
from typing import Optional, Tuple
from ..utils.game_config import config
from ..services import db
from ..services import ai
from ..services.mood_service import MoodService
from ..services.dossier_service import DossierService
from ..services.lore_service import LoreService
from ..models.points import PointEvent
from ..models.ai import CynicalCommentResult
from src.repositories.debt_repository import debt_repository
from ..utils.text import escape
import logging

class ChatService:
    # Cooldown states: chat_id -> datetime, (chat_id, user_id) -> datetime
    _last_comment_time = {}
    _last_user_comment_time = {}
    _last_reaction_time = {}
    _last_spontaneous_judgment_time = {}

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
        for chat_id, last_time in list(cls._last_spontaneous_judgment_time.items()):
            if (now - last_time).total_seconds() > getattr(config, "SPONTANEOUS_JUDGMENT_COOLDOWN_SECONDS", 180) * 3:
                del cls._last_spontaneous_judgment_time[chat_id]

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
    def _get_name_variants(cls, name: str) -> list:
        clean = name.strip().lstrip('@').lower()
        variants = {clean}
        # Common Russian declension endings (Сене -> сен, Паштету -> паштет, Любецкого -> любецк)
        for ending in ('ого', 'его', 'ому', 'ему', 'ом', 'ем', 'ой', 'ей', 'а', 'я', 'у', 'ю', 'е', 'ы', 'и'):
            if clean.endswith(ending) and len(clean) - len(ending) >= 3:
                variants.add(clean[:-len(ending)])
        return list(variants)

    @classmethod
    async def resolve_user(cls, chat_id: int, target_name: str, context_msgs: list) -> Tuple[Optional[int], str]:
        """
        Attempts to resolve target_name (username, first name, or lore alias, with Russian inflections) to (user_id, display_name).
        """
        if not target_name:
            return None, ""

        variants = cls._get_name_variants(target_name)

        # 1. Check in context messages
        for msg in reversed(context_msgs or []):
            u_name = str(msg.get('username') or '').lstrip('@').lower()
            f_name = str(msg.get('first_name') or '').lower()
            u_id = msg.get('user_id')
            if u_id:
                for v in variants:
                    if v == u_name or v in f_name or f_name.startswith(v):
                        return int(u_id), msg.get('username') or msg.get('first_name') or str(u_id)

        # 2. Check in chat user stats
        try:
            users, _ = await db.user_repository.get_chat_users(chat_id, limit=200)
            for u in users:
                u_name = str(u.get('username') or '').lstrip('@').lower()
                f_name = str(u.get('full_name') or '').lower()
                u_id = u.get('user_id')
                if u_id:
                    for v in variants:
                        if v == u_name or v in f_name or f_name.startswith(v):
                            return int(u_id), u.get('username') or u.get('full_name') or str(u_id)

            # 3. Check in Lore characters
            lore_data = await LoreService.get_lore(chat_id)
            core = lore_data.get('core', lore_data)
            characters = core.get('characters', [])
            for char in characters:
                handle = str(char.get('handle') or '').lstrip('@').lower()
                char_names = [str(n).lower() for n in char.get('names', [])]
                
                # Check if target_name matches handle or any lore name variant
                matched_char = False
                for v in variants:
                    if v == handle or any(v in n or n.startswith(v) for n in char_names):
                        matched_char = True
                        break

                if matched_char:
                    target_id = char.get('id')
                    for u in users:
                        u_name = str(u.get('username') or '').lstrip('@').lower()
                        u_fullname = str(u.get('full_name') or '').lower()
                        if (
                            (handle and u_name == handle) or
                            (target_id and str(u.get('user_id')) == str(target_id)) or
                            any(n and (n in u_fullname or u_fullname.startswith(n) or n in u_name) for n in char_names)
                        ):
                            return int(u.get('user_id')), u.get('username') or char.get('names', [''])[0] or str(u.get('user_id'))
        except Exception as e:
            logging.warning(f"Error resolving user: {e}")

        return None, target_name

    @classmethod
    async def process_cynical_comment(cls, message, comment_text: str):
        """
        Processes a potential cynical comment with Fast & Slow attention logic and spontaneous judgment.
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
                
                result = await ai.generate_cynical_comment(
                    context_msgs, 
                    comment_text, 
                    username, 
                    chat_id=chat_id
                )
                
                if not result:
                    return None

                comment_body = result.comment if isinstance(result, CynicalCommentResult) else str(result)
                award_points = result.award_points if isinstance(result, CynicalCommentResult) else False
                target_user_str = result.target_username if isinstance(result, CynicalCommentResult) else None
                points_delta = result.points_delta if isinstance(result, CynicalCommentResult) else 0
                verdict_reason = result.reason if isinstance(result, CynicalCommentResult) else None
                
                # Debt tracking via spontaneous AI parsing
                if getattr(config, "ENABLE_DEBTS", True) and isinstance(result, CynicalCommentResult) and result.debt_transactions:
                    dt_dicts = [dt.model_dump() for dt in result.debt_transactions]
                    for dt in dt_dicts:
                        _, r_debtor = await cls.resolve_user(chat_id, dt.get('debtor', ''), context_msgs)
                        if r_debtor:
                            dt['debtor'] = r_debtor.lstrip('@')
                        _, r_creditor = await cls.resolve_user(chat_id, dt.get('creditor', ''), context_msgs)
                        if r_creditor:
                            dt['creditor'] = r_creditor.lstrip('@')

                    await debt_repository.update_debts(chat_id, dt_dicts)
                    
                    debt_text = "\n\n💸 <b>Кстати, я зафиксировал долги:</b>\n"
                    for dt in dt_dicts:
                        debtor = dt.get('debtor', 'Кто-то')
                        creditor = dt.get('creditor', 'Кому-то')
                        amount = dt.get('amount', 0)
                        is_settled = dt.get('is_settled', False)
                        reason = dt.get('reason', '')
                        reason_str = f" ({escape(reason)})" if reason else ""
                        if is_settled:
                            debt_text += f"✅ {escape(debtor.capitalize())} вернул {amount} {escape(creditor.capitalize())}{reason_str}\n"
                        else:
                            debt_text += f"📉 {escape(debtor.capitalize())} торчит {amount} {escape(creditor.capitalize())}{reason_str}\n"
                    
                    comment_body += debt_text

                cls._last_comment_time[chat_id] = now
                cls._last_user_comment_time[(chat_id, user_id)] = now

                # Spontaneous Judgment execution:
                if (
                    award_points and
                    getattr(config, "SPONTANEOUS_JUDGMENT_ENABLED", True) and
                    target_user_str and
                    points_delta != 0
                ):
                    last_judgment = cls._last_spontaneous_judgment_time.get(chat_id)
                    cooldown = getattr(config, "SPONTANEOUS_JUDGMENT_COOLDOWN_SECONDS", 180)

                    # Direct mentions and replies to the bot bypass cooldown
                    if is_mentioned or not last_judgment or (now - last_judgment).total_seconds() >= cooldown:
                        target_id, resolved_name = await cls.resolve_user(chat_id, target_user_str, context_msgs)
                        if target_id and target_id != bot_user.id:
                            # Locate the offending/target message in context
                            target_msg = None
                            for m in reversed(context_msgs or []):
                                if str(m.get('user_id')) == str(target_id):
                                    target_msg = m
                                    break

                            target_msg_id = (target_msg.get('message_id') if target_msg else None) or getattr(message, 'message_id', None)

                            # Deduplication check: only applies to penalties (points_delta > 0) to avoid double-scoring an infraction
                            already_scored = False
                            if points_delta > 0 and target_msg_id:
                                existing = await db.message_repository.get_message(chat_id, target_msg_id)
                                if existing and (existing.get("points_awarded", 0) > 0 or existing.get("is_reported")):
                                    already_scored = True

                            if not already_scored:
                                event_id = f"spontaneous:{chat_id}:{target_id}:{target_msg_id if points_delta > 0 else message.message_id}"
                                event = PointEvent(
                                    event_id=event_id,
                                    chat_id=str(chat_id),
                                    user_id=str(target_id),
                                    points_delta=points_delta,
                                    event_type="spontaneous_verdict",
                                    reason=verdict_reason or ("Масть" if points_delta > 0 else "Людское"),
                                    season_id="global"
                                )
                                apply_res = await db.user_repository.apply_point_event_transactional(chat_id, event)
                                if apply_res.get("applied") and not apply_res.get("already_processed"):
                                    cls._last_spontaneous_judgment_time[chat_id] = now

                                    # Flag the message in DB only for infractions so /report and daily analysis will NOT double-charge!
                                    if points_delta > 0 and target_msg_id:
                                        await db.message_repository.mark_message_reported(
                                            chat_id=chat_id,
                                            msg_id=target_msg_id,
                                            reporter_id=bot_user.id,
                                            reason=verdict_reason or "Масть",
                                            points_awarded=points_delta,
                                            ai_thought_process=f"Spontaneous verdict in chat: {comment_body}"
                                        )

                                    tag_display = f"@{resolved_name}" if not str(resolved_name).startswith('@') else resolved_name
                                    clean_reason = escape(verdict_reason or ("Масть" if points_delta > 0 else "Людское"))

                                    if points_delta > 0:
                                        banner = f"\n\n⚖️ <b>Вердикт Смотрящего: +{points_delta} pts {tag_display}</b>\n📝 <i>Причина: {clean_reason}</i>"
                                    else:
                                        banner = f"\n\n👑 <b>Людской поступок: {points_delta} pts {tag_display}</b>\n📝 <i>Причина: {clean_reason}</i>"

                                    return escape(comment_body) + banner

                return comment_body
        except Exception as e:
            logging.error(f"Error in process_cynical_comment: {e}")
            
        return None

