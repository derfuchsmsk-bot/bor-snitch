import logging
from datetime import datetime, timezone, timedelta
from vertexai.generative_models import GenerativeModel, HarmCategory, HarmBlockThreshold
from src.utils.game_config import config
from src.utils.config import settings
from src.utils.prompts import get_scheduled_thought_prompt
from src.services.lore_service import LoreService
from src.repositories.message_repository import message_repository

logger = logging.getLogger(__name__)

SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

class ThoughtService:
    @classmethod
    async def generate_thought_text(cls, source_chat_id: int | str) -> str:
        try:
            c_id = int(source_chat_id)
        except (ValueError, TypeError):
            c_id = source_chat_id

        now_utc = datetime.now(timezone.utc)
        start_time = now_utc - timedelta(hours=12)
        try:
            logs = await message_repository.get_logs_for_time_range(c_id, start_time, now_utc)
        except Exception as e:
            logger.warning(f"Could not load logs for chat {c_id}: {e}")
            logs = []

        try:
            lore_json = await LoreService.get_lore_as_json(c_id)
        except Exception as e:
            logger.warning(f"Could not load lore for chat {c_id}: {e}")
            lore_json = "{}"

        if logs:
            sample_logs = logs[-150:] if len(logs) > 150 else logs
            log_lines = []
            for m in sample_logs:
                u = m.get("username") or m.get("full_name") or "Участник"
                txt = m.get("text", "")
                ts = m.get("timestamp")
                time_str = ts.strftime("%H:%M") if hasattr(ts, "strftime") else ""
                time_prefix = f"[{time_str}] " if time_str else ""
                if txt:
                    log_lines.append(f"{time_prefix}{u}: {txt}")
            logs_summary = "\n".join(log_lines)
        else:
            logs_summary = "В чате пока тихо, пацаны молчат."

        prompt = get_scheduled_thought_prompt(
            lore_json=lore_json,
            current_context=logs_summary
        )

        moscow_tz = timezone(timedelta(hours=getattr(config, "TIMEZONE_OFFSET", 3)))
        current_time_str = datetime.now(moscow_tz).strftime("%Y-%m-%d %H:%M:%S (МСК)")
        prompt = f"ТЕКУЩЕЕ МОСКОВСКОЕ ВРЕМЯ: {current_time_str}\n\n" + prompt

        model = GenerativeModel(config.AI_MODEL_ANALYSIS)
        response = await model.generate_content_async(
            contents=[prompt],
            generation_config={
                "temperature": 0.85,
                "max_output_tokens": 512
            },
            safety_settings=SAFETY_SETTINGS
        )

        raw_text = ""
        if response.candidates:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                raw_text = "".join([
                    part.text for part in candidate.content.parts
                    if hasattr(part, "text") and not getattr(part, "thought", False)
                ]).strip()
        if not raw_text and response.text:
            raw_text = response.text.strip()

        raw_text = raw_text.strip().strip('"').strip('«').strip('»')
        return raw_text

    @classmethod
    async def create_and_send_thought(cls, source_chat_id=None, target_chat_id=None, bot=None):
        if config.BOT_DISABLED or not getattr(config, "THOUGHTS_ENABLED", True):
            logger.info("Thoughts are disabled in config, skipping.")
            return {"status": "skipped", "reason": "disabled"}

        src_id = source_chat_id or settings.MAIN_CHAT_ID
        tgt_id = target_chat_id or getattr(settings, "CHANNEL_ID", None) or src_id

        logger.info(f"Generating thought based on chat {src_id}, sending to {tgt_id}")
        thought_text = await cls.generate_thought_text(src_id)

        if not thought_text:
            logger.warning(f"AI generated empty thought for chat {src_id}")
            return {"status": "empty"}

        if bot:
            await bot.send_message(chat_id=tgt_id, text=thought_text)
            logger.info(f"Successfully sent thought to {tgt_id}: {thought_text}")

        return {"status": "success", "target_chat_id": str(tgt_id), "text": thought_text}
