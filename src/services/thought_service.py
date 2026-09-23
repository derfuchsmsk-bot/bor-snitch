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
    async def generate_thought_text(cls, source_chat_id: int | str = None) -> str:
        c_id = None
        if source_chat_id:
            try:
                c_id = int(source_chat_id)
            except (ValueError, TypeError):
                c_id = source_chat_id

        try:
            lore_json = await LoreService.get_lore_as_json(c_id) if c_id else "{}"
        except Exception as e:
            logger.warning(f"Could not load lore for chat {c_id}: {e}")
            lore_json = "{}"

        prompt = get_scheduled_thought_prompt(
            lore_json=lore_json
        )

        model = GenerativeModel(config.AI_MODEL_ANALYSIS)
        response = await model.generate_content_async(
            contents=[prompt],
            generation_config={
                "temperature": 0.85,
                "max_output_tokens": 4096
            },
            safety_settings=SAFETY_SETTINGS
        )

        raw_text = ""
        if response.candidates:
            candidate = response.candidates[0]
            logger.info(f"Gemini thought candidate finish reason: {candidate.finish_reason}")
            if candidate.content and candidate.content.parts:
                raw_text = "".join([
                    part.text for part in candidate.content.parts
                    if hasattr(part, "text") and not getattr(part, "thought", False)
                ]).strip()
        if not raw_text and response.text:
            raw_text = response.text.strip()

        raw_text = raw_text.strip().strip('"').strip('«').strip('»')

        # Prevent mid-sentence cutoffs: ensure text ends with terminal punctuation
        if raw_text and raw_text[-1] not in ('.', '!', '?', '…', '"', '»'):
            last_punct = max(
                raw_text.rfind('.'),
                raw_text.rfind('!'),
                raw_text.rfind('?'),
                raw_text.rfind('…')
            )
            # If there's an earlier finished sentence, cut off the trailing incomplete fragment
            if last_punct > 0:
                raw_text = raw_text[:last_punct + 1].strip()
            else:
                raw_text = raw_text + "."

        if raw_text:
            year = datetime.now().year
            raw_text = f"{raw_text}\n\n— Снитч-бот, {year}г."

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
