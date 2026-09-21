import logging
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from vertexai.generative_models import GenerativeModel, HarmCategory, HarmBlockThreshold
from .db import get_logs_for_time_range
from ..utils.game_config import config
from ..utils.prompts import get_feedback_analysis_prompt
from ..models.ai import FeedbackAnalysisResult
from ..repositories.lesson_repository import lesson_repository

logger = logging.getLogger(__name__)

FEEDBACK_SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

class LearningService:
    @staticmethod
    async def analyze_feedback(chat_id: int | str, date_key: Optional[str] = None) -> Optional[FeedbackAnalysisResult]:
        """
        Analyzes user feedback (replies to bot or messages mentioning the bot) to extract lessons.
        If date_key is None, uses today's date in bot's timezone.
        """
        chat_id_int = int(chat_id)
        moscow_tz = timezone(timedelta(hours=config.TIMEZONE_OFFSET))

        if not date_key:
            now_msk = datetime.now(moscow_tz)
            date_key = now_msk.strftime("%Y-%m-%d")

        try:
            dt_obj = datetime.strptime(date_key, "%Y-%m-%d")
        except ValueError:
            logger.error(f"Invalid date_key format for analyze_feedback: {date_key}")
            return None

        start_dt = dt_obj.replace(tzinfo=moscow_tz).astimezone(timezone.utc)
        end_dt = start_dt + timedelta(days=1)

        logs = await get_logs_for_time_range(chat_id_int, start_dt, end_dt)
        if not logs:
            logger.info(f"No logs found for chat {chat_id} on {date_key}")
            return None

        # Filter messages that look like feedback (replies or mentions)
        feedback_logs = []
        for log in logs:
            text = (log.get("text") or "").lower()
            if log.get("reply_to") or any(kw in text for kw in ["бот", "снитч", "snitch"]):
                feedback_logs.append(log)

        if not feedback_logs:
            logger.info(f"No feedback messages found for chat {chat_id} on {date_key}")
            return None

        # Format feedback for AI
        feedback_str = ""
        for f in feedback_logs:
            username = f.get("username") or "Anon"
            text = f.get("text") or ""
            feedback_str += f"- {username}: {text}\n"

        model = GenerativeModel(config.AI_MODEL_ANALYSIS)
        prompt = f"""
        ДАТА: {date_key}
        ЛОГИ ОБРАТНОЙ СВЯЗИ (Сообщения пользователей о боте или ответы боту):
        {feedback_str}

        Проанализируй эти сообщения согласно FEEDBACK_ANALYSIS_PROMPT.
        """

        try:
            feedback_schema = {
                "type": "OBJECT",
                "properties": {
                    "verdict": {"type": "STRING", "description": "fair | mistake | unclear"},
                    "reasoning": {"type": "STRING", "description": "Verdict reason"},
                    "learned_rule": {"type": "STRING", "description": "New rule if needed"}
                },
                "required": ["verdict", "reasoning"]
            }

            response = await model.generate_content_async(
                contents=[get_feedback_analysis_prompt(), prompt],
                generation_config={
                    "response_mime_type": "application/json",
                    "response_schema": feedback_schema
                },
                safety_settings=FEEDBACK_SAFETY_SETTINGS
            )

            result_dict = json.loads(response.text)
            result = FeedbackAnalysisResult(**result_dict)

            if result and result.learned_rule and result.learned_rule.strip():
                rule_text = result.learned_rule.strip()
                await lesson_repository.create_lesson(chat_id_int, {
                    "created_at": datetime.now(timezone.utc),
                    "date_key": date_key,
                    "trigger_context": feedback_str[:1000],
                    "learned_rule": rule_text,
                    "verdict": result.verdict,
                    "reasoning": result.reasoning,
                    "status": "active"
                })
                logger.info(f"New lesson learned for chat {chat_id}: {rule_text}")

            return result

        except Exception as e:
            logger.error(f"Error during feedback analysis for chat {chat_id}: {e}", exc_info=True)
            return None

    @staticmethod
    async def get_active_lessons(chat_id: int | str, limit: int = 5) -> List[str]:
        """
        Fetches active lessons (rule strings), newest first, to inject into the prompt.
        """
        return await lesson_repository.get_active_rules(chat_id, limit=limit)

    @staticmethod
    async def create_lesson_from_annulment(
        chat_id: int | str,
        event_data: dict,
        annul_reason: str,
        custom_rule: Optional[str] = None
    ) -> Optional[dict]:
        """
        Synthesizes a behavioral rule and records a new active lesson when an admin annuls a verdict.
        If custom_rule is provided, uses it directly; otherwise invokes Gemini to extract a rule.
        """
        chat_id_int = int(chat_id)
        rule_text = (custom_rule or "").strip()
        reasoning = f"Аннулирование вердикта администратором: {annul_reason}"

        if not rule_text:
            prompt = f"""
Ты — система самообучения Снитч-Бота. Администратор только что отменил (аннулировал) ошибочное решение/начисление очков бота в чате.

ДАННЫЕ ОШИБОЧНОГО ВЕРДИКТА:
- Тип события: {event_data.get('event_type')}
- За что были начислены/сняты очки: "{event_data.get('reason')}"
- Дельта очков: {event_data.get('points_delta')}
- Участник: {event_data.get('username') or event_data.get('user_id')}

ОБОСНОВАНИЕ ОТМЕНЫ АДМИНИСТРАТОРОМ (В чём ошибся бот):
"{annul_reason}"

ИНСТРУКЦИЯ:
Сформулируй ОДНО краткое, ёмкое и чёткое правило поведения для бота (1-2 предложения), чтобы бот больше НИКОГДА не совершал подобной ошибки.
Примеры хороших правил:
- "Не считать токсичностью дружеские подколы про игры и стримы между кентами."
- "Не штрафовать за отмену встречи, если участник предупредил заранее или была уважительная причина."
- "Не считать мастью отказ от участия в пакте, если человек изначально не давал явного согласия."
- "Учитывать контекст сарказма и цитирования мемов при оценке токсичности."
"""
            try:
                model = GenerativeModel(config.AI_MODEL_ANALYSIS)
                schema = {
                    "type": "OBJECT",
                    "properties": {
                        "learned_rule": {"type": "STRING", "description": "Сформулированное правило поведения на русском языке"},
                        "reasoning": {"type": "STRING", "description": "Краткое пояснение ошибки"}
                    },
                    "required": ["learned_rule"]
                }
                response = await model.generate_content_async(
                    contents=[prompt],
                    generation_config={
                        "response_mime_type": "application/json",
                        "response_schema": schema
                    },
                    safety_settings=FEEDBACK_SAFETY_SETTINGS
                )
                res_data = json.loads(response.text)
                rule_text = (res_data.get("learned_rule") or "").strip()
                if res_data.get("reasoning"):
                    reasoning = res_data["reasoning"].strip()
            except Exception as e:
                logger.warning(f"Could not synthesize annulment rule via Gemini: {e}")
                rule_text = f"Не штрафовать за подобные действия: {annul_reason}"

        if not rule_text:
            rule_text = f"Не штрафовать за подобные действия: {annul_reason}"

        moscow_tz = timezone(timedelta(hours=config.TIMEZONE_OFFSET))
        date_key = datetime.now(moscow_tz).strftime("%Y-%m-%d")

        lesson = await lesson_repository.create_lesson(chat_id_int, {
            "created_at": datetime.now(timezone.utc),
            "date_key": date_key,
            "trigger_context": f"Отмена вердикта {event_data.get('id', event_data.get('event_id'))}. Исходная причина: {event_data.get('reason')}. Причина отмены: {annul_reason}",
            "learned_rule": rule_text,
            "verdict": "mistake",
            "reasoning": reasoning,
            "status": "active"
        })
        logger.info(f"Recorded new lesson from annulment for chat {chat_id}: {rule_text}")
        return lesson
