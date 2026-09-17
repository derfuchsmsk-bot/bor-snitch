import os
import time
import random
import asyncio
import logging
import tempfile
from typing import Optional

from src.utils.config import settings
from src.utils.game_config import config
from src.services.tts_service import TTSService

logger = logging.getLogger(__name__)

KIZARU_GREETINGS = [
    "Вассап, хоуми. Снитч-Бот на связи прямо с Барселоны. Чё вы тут за базар развели? Давайте, поясняйте за свои движения.",
    "Йо. Я залетел послушать, кто тут рил, а кто просто нагоняет воздух. Говорите, я на микрофоне.",
    "Вассап. Вы тут на суете, а я на чилле. Ну и кто сегодня главный клоун в конфе?"
]

KIZARU_INACTIVITY_EXITS = [
    "Йо, вы чё, уснули там? Сидите на немом трэпе. Мне скучно, я погнал делать дела. Покеда, хоуми, курите бамбук.",
    "Вы замолчали, как будто копы в дверь постучали. Раз базарить не о чем, я ливаю. Не позорьтесь.",
    "Сплошное молчание, бро. Ноль движа, ноль энергетики. Я отключаюсь, архив всё помнит."
]

KIZARU_LEAVE_EXITS = [
    "Сливаете меня? Окей, хоуми, я пошел курить бамбук у бассейна, а вы тут дальше варитесь.",
    "Без базара, я на выходе. Но помните: Снитч-Бот всё слышал. Вечером очки посчитаем."
]

class VoiceChatService:
    _client = None
    _pytgcalls = None
    _is_running = False
    _active_calls = {}      # chat_id -> asyncio.Task
    _last_activity = {}     # chat_id -> float (timestamp)
    _lock = asyncio.Lock()

    @classmethod
    async def ensure_started(cls):
        """Initializes and connects Telethon client and PyTgCalls instance."""
        async with cls._lock:
            if cls._is_running and cls._pytgcalls is not None:
                return cls._pytgcalls

            if not settings.TELEGRAM_API_ID or not settings.TELEGRAM_API_HASH:
                raise ValueError("TELEGRAM_API_ID and TELEGRAM_API_HASH must be configured in settings")

            from telethon import TelegramClient
            from telethon.sessions import StringSession
            from pytgcalls import PyTgCalls

            if settings.TELEGRAM_STRING_SESSION:
                session = StringSession(settings.TELEGRAM_STRING_SESSION)
            else:
                session = os.path.join(tempfile.gettempdir(), "snitch_bot_telethon")

            cls._client = TelegramClient(
                session,
                api_id=int(settings.TELEGRAM_API_ID),
                api_hash=str(settings.TELEGRAM_API_HASH)
            )

            if settings.TELEGRAM_STRING_SESSION:
                await cls._client.connect()
                if not await cls._client.is_user_authorized():
                    raise RuntimeError("StringSession provided but user account is not authorized")
            else:
                await cls._client.start(bot_token=settings.TELEGRAM_TOKEN)

            cls._pytgcalls = PyTgCalls(cls._client)
            await cls._pytgcalls.start()
            cls._is_running = True
            logger.info("VoiceChatService: PyTgCalls & Telethon client successfully started.")
            return cls._pytgcalls

    @classmethod
    def record_activity(cls, chat_id: int):
        """Resets the inactivity timer for the active call."""
        cls._last_activity[int(chat_id)] = time.time()

    @classmethod
    async def play_phrase_in_call(cls, chat_id: int, phrase: str):
        """Synthesizes text via ElevenLabs/TTS and streams it into the Telegram voice call."""
        from pytgcalls.types import MediaStream

        pytgcalls = await cls.ensure_started()
        audio_bytes, audio_fmt = await TTSService.synthesize_speech(phrase)

        # Write to temporary file for PyTgCalls MediaStream
        suffix = f".{audio_fmt}"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(audio_bytes)
            tmp_path = tmp_file.name

        try:
            cls.record_activity(chat_id)
            await pytgcalls.play(int(chat_id), MediaStream(tmp_path))
            logger.info(f"Streaming phrase into call {chat_id}: '{phrase[:40]}...'")
        finally:
            # Schedule file deletion after audio has been streamed
            asyncio.create_task(cls._delayed_file_cleanup(tmp_path, delay=20))

    @classmethod
    async def _delayed_file_cleanup(cls, file_path: str, delay: int = 20):
        await asyncio.sleep(delay)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass

    @classmethod
    async def join_voice_chat(cls, chat_id: int) -> str:
        """
        Connects the bot to the group voice chat, drops the Kizaru greeting,
        and launches the 60-second inactivity watchdog.
        """
        if not getattr(config, "VOICE_CHAT_ENABLED", True) or config.BOT_DISABLED:
            raise RuntimeError("Voice chat feature is currently disabled")

        cid = int(chat_id)
        phrase = random.choice(KIZARU_GREETINGS)
        cls.record_activity(cid)

        # Connect and play greeting
        await cls.play_phrase_in_call(cid, phrase)

        # Cancel any previous watchdog if running
        if cid in cls._active_calls:
            cls._active_calls[cid].cancel()

        # Start watchdog loop
        cls._active_calls[cid] = asyncio.create_task(cls._inactivity_watchdog(cid))
        logger.info(f"Bot joined voice chat {cid} with Kizaru greeting.")
        return phrase

    @classmethod
    async def _inactivity_watchdog(cls, chat_id: int):
        """Background loop that automatically disconnects the bot after 60s of silence."""
        cid = int(chat_id)
        timeout = getattr(config, "VOICE_CHAT_INACTIVITY_TIMEOUT_SECONDS", 60)

        try:
            while True:
                await asyncio.sleep(5)
                last_act = cls._last_activity.get(cid, time.time())
                elapsed = time.time() - last_act

                if elapsed >= timeout:
                    logger.info(f"Inactivity timeout ({elapsed:.0f}s >= {timeout}s) triggered for voice chat {cid}.")
                    exit_phrase = random.choice(KIZARU_INACTIVITY_EXITS)
                    try:
                        await cls.play_phrase_in_call(cid, exit_phrase)
                        # Give audio time to stream before hanging up
                        await asyncio.sleep(5)
                    except Exception as e:
                        logger.warning(f"Could not play exit phrase: {e}")

                    await cls.leave_voice_chat(cid, reason="timeout")
                    break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in voice chat watchdog: {e}")

    @classmethod
    async def leave_voice_chat(cls, chat_id: int, reason: str = "manual") -> Optional[str]:
        """Disconnects the bot from the group voice chat with optional Kizaru exit line."""
        cid = int(chat_id)

        # Cancel watchdog
        if cid in cls._active_calls:
            cls._active_calls[cid].cancel()
            del cls._active_calls[cid]

        cls._last_activity.pop(cid, None)

        exit_phrase = None
        if reason == "manual":
            exit_phrase = random.choice(KIZARU_LEAVE_EXITS)
            try:
                await cls.play_phrase_in_call(cid, exit_phrase)
                await asyncio.sleep(4)
            except Exception as e:
                logger.warning(f"Could not play manual leave phrase: {e}")

        if cls._pytgcalls is not None:
            try:
                await cls._pytgcalls.leave_call(cid)
                logger.info(f"Bot left voice chat {cid} (reason: {reason}).")
            except Exception as e:
                logger.warning(f"Error leaving call: {e}")

        return exit_phrase
