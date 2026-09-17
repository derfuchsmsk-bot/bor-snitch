import os
import io
import time
import wave
import random
import asyncio
import logging
import tempfile
from typing import Optional

from vertexai.generative_models import GenerativeModel, Part, HarmCategory, HarmBlockThreshold
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

VOICE_SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

class VoiceChatService:
    _client = None
    _pytgcalls = None
    _is_running = False
    _active_calls = {}          # chat_id -> asyncio.Task (watchdog)
    _listener_tasks = {}        # chat_id -> asyncio.Task (audio listener)
    _last_activity = {}         # chat_id -> float (timestamp)
    _last_bot_reply_time = {}   # chat_id -> float (timestamp of last bot speech)
    _is_speaking = {}           # chat_id -> bool (lock preventing bot from interrupting itself or hearing itself)
    _lock = asyncio.Lock()

    @classmethod
    def is_in_call(cls, chat_id: int) -> bool:
        """Returns True if the bot is currently connected to a voice chat."""
        return int(chat_id) in cls._active_calls

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
    def pcm_to_wav(cls, pcm_bytes: bytes, channels: int = 2, sampwidth: int = 2, framerate: int = 48000) -> bytes:
        """Converts raw PCM audio bytes to WAV container in-memory."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sampwidth)
            wav_file.setframerate(framerate)
            wav_file.writeframes(pcm_bytes)
        return buf.getvalue()

    @classmethod
    async def play_phrase_in_call(cls, chat_id: int, phrase: str):
        """
        Synthesizes text via ElevenLabs/TTS and smoothly streams it into the call,
        locking playback to prevent speech stuttering and echo feedback.
        """
        from pytgcalls.types import MediaStream

        cid = int(chat_id)
        cls._is_speaking[cid] = True
        pytgcalls = await cls.ensure_started()

        try:
            audio_bytes, audio_fmt = await TTSService.synthesize_speech(phrase)

            suffix = f".{audio_fmt}"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                tmp_file.write(audio_bytes)
                tmp_path = tmp_file.name

            cls.record_activity(cid)
            await pytgcalls.play(cid, MediaStream(tmp_path))
            logger.info(f"Streaming phrase into call {cid}: '{phrase[:40]}...'")

            # Calculate natural duration: MP3 ~16KB/s, give audio time to play fully
            duration = max(3.0, len(audio_bytes) / 16000.0 + 1.2)
            await asyncio.sleep(duration)
        except Exception as e:
            logger.error(f"Error playing phrase in call {cid}: {e}")
        finally:
            cls._last_bot_reply_time[cid] = time.time()
            cls._is_speaking[cid] = False
            if 'tmp_path' in locals():
                asyncio.create_task(cls._delayed_file_cleanup(tmp_path, delay=15))

    @classmethod
    async def _delayed_file_cleanup(cls, file_path: str, delay: int = 15):
        await asyncio.sleep(delay)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass

    @classmethod
    async def speak_text_response_in_call(cls, chat_id: int, username: str, user_text: str):
        """
        When someone writes in the chat while the bot is in a voice call,
        Gemini generates a Kizaru reply and speaks it directly into the voice call.
        """
        cid = int(chat_id)
        if not cls.is_in_call(cid) or cls._is_speaking.get(cid, False):
            return

        cls.record_activity(cid)

        prompt = f"""
Ты — Снитч-Бот в голосовом чате Telegram в образе рэпера Кизару (Олег Нечипоренко).
Пользователь {username} только что написал в чат: "{user_text}".
ИНСТРУКЦИЯ:
Ответь ему в голосовой чат прямо сейчас дерзко, на чилле и по фактам на сленге Кизару (1 короткое хлесткое предложение).
Отвечай СТРОГО на русском языке, без смайликов и списков (для чтения вслух в микрофон).
"""
        try:
            model = GenerativeModel(config.AI_MODEL_ANALYSIS)
            resp = await model.generate_content_async(
                contents=[prompt],
                safety_settings=VOICE_SAFETY_SETTINGS,
                generation_config={"temperature": 0.85, "max_output_tokens": 120}
            )
            reply = resp.text.strip() if resp and resp.text else ""
            if reply:
                reply_cleaned = TTSService.clean_text_for_speech(reply)
                logger.info(f"Speaking chat reply into voice call {cid}: {reply_cleaned}")
                await cls.play_phrase_in_call(cid, reply_cleaned)
        except Exception as e:
            logger.error(f"Error speaking text response in call: {e}")

    @classmethod
    async def join_voice_chat(cls, chat_id: int) -> str:
        """
        Connects the bot to the group voice chat, drops the Kizaru greeting,
        and launches the listener and inactivity watchdog.
        """
        if not getattr(config, "VOICE_CHAT_ENABLED", True) or config.BOT_DISABLED:
            raise RuntimeError("Voice chat feature is currently disabled")

        cid = int(chat_id)
        phrase = random.choice(KIZARU_GREETINGS)
        cls.record_activity(cid)

        # Cancel any previous tasks if running
        if cid in cls._active_calls:
            cls._active_calls[cid].cancel()
        if cid in cls._listener_tasks:
            cls._listener_tasks[cid].cancel()

        # Connect and play greeting
        await cls.play_phrase_in_call(cid, phrase)

        # Start watchdog loop and audio listener loop
        cls._active_calls[cid] = asyncio.create_task(cls._inactivity_watchdog(cid))
        cls._listener_tasks[cid] = asyncio.create_task(cls._voice_listener_loop(cid))

        logger.info(f"Bot joined voice chat {cid} with Kizaru greeting and live listener.")
        return phrase

    @classmethod
    async def _voice_listener_loop(cls, chat_id: int):
        """
        Captures incoming live voice audio from participants in the call,
        cleans noise and echo, and triggers smart Kizaru speech replies.
        """
        cid = int(chat_id)
        record_file = os.path.join(tempfile.gettempdir(), f"voice_incoming_{cid}.raw")
        from pytgcalls.types import RecordStream

        # Wait 3 seconds after greeting before opening listener
        await asyncio.sleep(3)

        try:
            pytgcalls = await cls.ensure_started()
            try:
                await pytgcalls.record(cid, RecordStream(audio=record_file))
                logger.info(f"Live microphone recording started for chat {cid}")
            except Exception as e:
                logger.warning(f"Could not initialize PyTgCalls recording: {e}")
                return

            while cid in cls._active_calls:
                await asyncio.sleep(4)

                # If bot is currently speaking, discard buffer and don't listen to yourself
                if cls._is_speaking.get(cid, False):
                    if os.path.exists(record_file):
                        try:
                            open(record_file, "wb").close()
                        except Exception:
                            pass
                    continue

                if not os.path.exists(record_file):
                    continue

                size = os.path.getsize(record_file)
                # Need at least ~250KB of 48kHz 16bit audio (~1.3s of real vocal speech, not clicks/breaths)
                if size < 250_000:
                    continue

                # Enforce minimum cooldown between voice replies (12 seconds)
                if (time.time() - cls._last_bot_reply_time.get(cid, 0)) < 12.0:
                    continue

                try:
                    with open(record_file, "rb") as f:
                        raw_pcm = f.read()

                    # Flush buffer
                    open(record_file, "wb").close()

                    wav_bytes = cls.pcm_to_wav(raw_pcm)
                    cls.record_activity(cid)

                    # Send audio chunk to Gemini for comprehension
                    audio_part = Part.from_data(wav_bytes, mime_type="audio/wav")
                    prompt = """
Ты — Снитч-Бот в голосовом чате Telegram в образе рэпера Кизару (Олег Нечипоренко).
Послушай аудиозапись того, что только что сказали пацаны в войс-чате.
КРИТИЧЕСКИ ВАЖНО:
1. Если в аудио тишина, фоновый шум, дыхание, шорохи или обычный разговор парней без прямого обращения к тебе — ответь СТРОГО ОДНИМ СЛОВОМ: IGNORE.
2. Отвечай ТОЛЬКО если они обращаются к тебе (Снитч, Кизару, Бот, Олег), задают вопрос или кто-то откровенно ноет/спорит.
3. Твой ответ: 1 короткая хлесткая фраза на сленге Кизару (Барселона, курите бамбук, не нагоняй воздух).
4. Пиши СТРОГО НА РУССКОМ для чтения вслух.
"""
                    model = GenerativeModel(config.AI_MODEL_ANALYSIS)
                    resp = await model.generate_content_async(
                        contents=[prompt, audio_part],
                        safety_settings=VOICE_SAFETY_SETTINGS,
                        generation_config={"temperature": 0.75, "max_output_tokens": 100}
                    )
                    reply = resp.text.strip() if resp and resp.text else ""

                    if reply and not reply.upper().startswith("IGNORE"):
                        reply_cleaned = TTSService.clean_text_for_speech(reply)
                        logger.info(f"Kizaru responding to voice in call {cid}: '{reply_cleaned}'")
                        await cls.play_phrase_in_call(cid, reply_cleaned)
                        # Re-attach recording after playback
                        try:
                            await pytgcalls.record(cid, RecordStream(audio=record_file))
                        except Exception:
                            pass
                except Exception as e:
                    logger.debug(f"Audio chunk evaluation skipped: {e}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in voice listener loop: {e}")
        finally:
            if os.path.exists(record_file):
                try:
                    os.remove(record_file)
                except Exception:
                    pass

    @classmethod
    async def _inactivity_watchdog(cls, chat_id: int):
        """Background loop that automatically disconnects the bot after 60s of silence."""
        cid = int(chat_id)
        timeout = getattr(config, "VOICE_CHAT_INACTIVITY_TIMEOUT_SECONDS", 60)

        try:
            while True:
                await asyncio.sleep(5)
                # If bot is currently speaking, don't count it as inactivity
                if cls._is_speaking.get(cid, False):
                    cls.record_activity(cid)
                    continue

                last_act = cls._last_activity.get(cid, time.time())
                elapsed = time.time() - last_act

                if elapsed >= timeout:
                    logger.info(f"Inactivity timeout ({elapsed:.0f}s >= {timeout}s) triggered for voice chat {cid}.")
                    exit_phrase = random.choice(KIZARU_INACTIVITY_EXITS)
                    try:
                        await cls.play_phrase_in_call(cid, exit_phrase)
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

        # Cancel listener task
        if cid in cls._listener_tasks:
            cls._listener_tasks[cid].cancel()
            del cls._listener_tasks[cid]

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
            except Exception as e:
                logger.warning(f"Could not play manual leave phrase: {e}")

        if cls._pytgcalls is not None:
            try:
                await cls._pytgcalls.leave_call(cid)
                logger.info(f"Bot left voice chat {cid} (reason: {reason}).")
            except Exception as e:
                logger.warning(f"Error leaving call: {e}")

        return exit_phrase
