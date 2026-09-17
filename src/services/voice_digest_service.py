import logging
from datetime import datetime, timezone, timedelta
from vertexai.generative_models import GenerativeModel, HarmCategory, HarmBlockThreshold
from aiogram.types import BufferedInputFile

from src.utils.game_config import config
from src.utils.prompts import get_voice_digest_prompt
from src.utils.text import escape
from src.services.lore_service import LoreService
from src.services.tts_service import TTSService
from src.repositories.message_repository import message_repository
from src.repositories.agreement_repository import agreement_repository
from src.repositories.user_repository import user_repository

logger = logging.getLogger(__name__)

# Permissive safety settings so creative/satirical crime chronicle scripts are never cut off by Google filters
SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

class VoiceDigestService:
    @classmethod
    async def generate_digest_script(cls, chat_id: int, edition_type: str = "Дневной выпуск (14:00)") -> str:
        """
        Gathers recent chat context, lore and agreements, then uses Gemini to draft
        a radio crime news / cynical investigator script.
        """
        now_utc = datetime.now(timezone.utc)
        # Scan messages from the last 10 hours for day edition, or 8 hours for evening
        lookback_hours = 10 if "дневн" in edition_type.lower() or "14:00" in edition_type else 8
        start_time = now_utc - timedelta(hours=lookback_hours)

        logs = await message_repository.get_logs_for_time_range(chat_id, start_time, now_utc)
        lore_json = await LoreService.get_lore_as_json(chat_id)
        agreements = await agreement_repository.get_active_agreements(chat_id)

        agreements_str = "Нет активных договоренностей."
        if agreements:
            lines = []
            for ag in agreements:
                users = ", ".join(ag.get("users", []))
                lines.append(f"- {users}: {ag.get('text')}")
            agreements_str = "\n".join(lines)

        # Summarize logs
        logs_summary = ""
        if logs:
            sample_logs = logs[-350:] if len(logs) > 350 else logs
            log_lines = []
            for m in sample_logs:
                u = m.get("username") or m.get("full_name") or "Кто-то"
                txt = m.get("text", "")
                ts = m.get("timestamp")
                time_str = ts.strftime("%H:%M") if hasattr(ts, "strftime") else ""
                time_prefix = f"[{time_str}] " if time_str else ""
                if txt:
                    log_lines.append(f"{time_prefix}{u}: {txt}")
            logs_summary = "\n".join(log_lines)
        else:
            logs_summary = "В чате за последнее время было подозрительно тихо, никто не писал."

        # Fetch recent offenders from ledger
        recent_ledger = await user_repository.get_points_ledger(chat_id, limit=10)
        offenders_summary = "Новых штрафов не зафиксировано."
        if recent_ledger:
            off_lines = []
            for ev in recent_ledger:
                off_lines.append(f"- User {ev.get('user_id')}: {ev.get('points_delta')} очков за {ev.get('reason')}")
            offenders_summary = "\n".join(off_lines)

        prompt = get_voice_digest_prompt(
            edition_type=edition_type,
            lore_json=lore_json,
            active_agreements=agreements_str,
            offenders_summary=offenders_summary,
            current_context=logs_summary
        )
        prompt += "\n\nВАЖНОЕ ТРЕБОВАНИЕ: Твой ответ ОБЯЗАН быть СТРОГО НА РУССКОМ ЯЗЫКЕ! Напиши подробный монолог на 220-320 слов (хронометраж 1.5 - 2 минуты речи). Подробно пройдись по всем событиям дня!"

        model = GenerativeModel(config.AI_MODEL_ANALYSIS)
        try:
            response = await model.generate_content_async(
                contents=[prompt],
                generation_config={
                    "temperature": 0.8,
                    "max_output_tokens": 3500
                },
                safety_settings=SAFETY_SETTINGS
            )
            raw_text = ""
            if response.candidates:
                candidate = response.candidates[0]
                logger.info(f"Gemini voice candidate finish reason: {candidate.finish_reason}")
                if candidate.content and candidate.content.parts:
                    raw_text = "".join([part.text for part in candidate.content.parts if hasattr(part, "text")]).strip()
            if not raw_text and response.text:
                raw_text = response.text.strip()

            # Filter out any internal thought/checklist prefixes if generated
            lines = raw_text.split('\n')
            filtered_lines = []
            for l in lines:
                l_strip = l.strip()
                if any(x in l_strip for x in ["Pronunciation check", "check for TTS", "brackets (", "NONE -", "links: NONE", "NONE:"]):
                    continue
                if l_strip.startswith("«") and "NONE" in l_strip:
                    continue
                filtered_lines.append(l)
            raw_text = "\n".join(filtered_lines).strip()

            cleaned_script = TTSService.clean_text_for_speech(raw_text)
            logger.info(f"Generated voice digest script ({len(cleaned_script)} chars) for chat {chat_id}")
            return cleaned_script
        except Exception as e:
            logger.error(f"Failed to generate voice digest script: {e}")
            raise

    @classmethod
    async def create_and_send_voice_digest(
        cls,
        chat_id: int,
        edition_type: str = "Дневной выпуск (14:00)",
        bot = None,
        send_to_telegram: bool = True
    ) -> dict:
        """
        Orchestrates full voice digest creation:
        1. Drafts script via Gemini
        2. Synthesizes OGG_OPUS voice via Google Cloud Text-to-Speech
        3. Sends Telegram voice message with caption
        """
        if config.BOT_DISABLED:
            logger.info("Bot is disabled, skipping voice digest.")
            return {"status": "skipped", "reason": "bot_disabled"}

        if not getattr(config, "VOICE_DIGEST_ENABLED", True):
            logger.info("Voice digests are disabled in config, skipping.")
            return {"status": "skipped", "reason": "voice_digest_disabled"}

        script = await cls.generate_digest_script(chat_id, edition_type)
        audio_bytes, audio_format = await TTSService.synthesize_speech(script)

        if send_to_telegram and bot:
            if "дневн" in edition_type.lower() or "14:00" in edition_type:
                title = "🎙️ ОБЕДЕННАЯ ХРОНИКА САЙОНАРЫ (14:00)"
            elif "вечерн" in edition_type.lower() or "22:00" in edition_type:
                title = "📻 ВЕЧЕРНИЙ ПРИГОВОР САЙОНАРЫ (22:00)"
            else:
                title = f"🎙️ {edition_type.upper()}"

            caption = f"<b>{title}</b>"

            voice_file = BufferedInputFile(audio_bytes, filename=f"snitch_digest_{chat_id}.{audio_format}")
            try:
                await bot.send_voice(
                    chat_id=chat_id,
                    voice=voice_file,
                    caption=caption,
                    parse_mode="HTML"
                )
                logger.info(f"Voice digest sent to Telegram chat {chat_id}")
            except Exception as e:
                logger.error(f"Failed to send voice message to chat {chat_id}: {e}")
                raise

        return {
            "status": "success",
            "chat_id": chat_id,
            "edition": edition_type,
            "script": script,
            "audio_bytes_length": len(audio_bytes)
        }
