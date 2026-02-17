import vertexai
from vertexai.generative_models import GenerativeModel, SafetySetting, Part
import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
from src.utils.config import settings
from src.utils.game_config import config
from src.utils.prompts import (
    get_system_prompt,
    get_report_validation_prompt,
    get_cynical_comment_prompt,
    MEMORY_SUMMARIZATION_PROMPT,
    FACT_VALIDATION_PROMPT
)
from src.services.lore_service import LoreService
from src.services.fact_service import FactService
from src.models.ai import (
    DailyAnalysisResult,
    ReportValidationResult,
    FactValidationResult,
    MemorySummaryResult
)
import json
import logging
import re
from datetime import timedelta, timezone, datetime

# Initialize Vertex AI
init_params = {
    "project": settings.GCP_PROJECT_ID,
    "location": settings.GCP_LOCATION
}

if settings.GCP_LOCATION != "global":
    init_params["api_transport"] = "grpc"

vertexai.init(**init_params)

# Cache for cynical comments: (chat_id, current_text) -> comment
# TTL: 1 hour, Max size: 1000 entries
try:
    from cachetools import TTLCache
    comment_cache = TTLCache(maxsize=1000, ttl=3600)
except ImportError:
    comment_cache = {}

async def validate_report(target_text, context_msgs=None, chat_id=None) -> ReportValidationResult:
    """
    Checks if a reported message is actually a violation, considering context.
    Returns ReportValidationResult object.
    """
    if not target_text:
        return ReportValidationResult(
            valid=False, 
            reason="Empty message", 
            points=0,
            thought_process="No text to analyze."
        )

    model = GenerativeModel(config.AI_MODEL_ANALYSIS)
    
    context_str = ""
    if context_msgs:
        context_str = "КОНТЕКСТ (Предыдущие сообщения):\n"
        now = datetime.now(timezone.utc)
        
        for msg in context_msgs:
            name = msg.get('username', 'Unknown')
            if msg.get('is_bot') or name == "YOU (Snitch Bot)":
                 name = "YOU (Snitch Bot)"

            txt = msg.get('text', '')
            
            ts = msg.get('timestamp')
            time_str = ""
            if ts:
                if isinstance(ts, datetime):
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    diff = now - ts
                    minutes = int(diff.total_seconds() / 60)
                    time_str = f"({minutes} мин назад)"
            
            context_str += f"- {name} {time_str}: {txt}\n"
        context_str += "\n"

    prompt = f"""
    {context_str}
    СООБЩЕНИЕ НА ПРОВЕРКУ (REPORTED MESSAGE):
    "{target_text}"
    """
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    async def _generate_with_retry():
        return await model.generate_content_async(
            contents=[get_report_validation_prompt(), prompt],
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": ReportValidationResult
            }
        )

    try:
        response = await _generate_with_retry()
        # With response_schema, json.loads is usually sufficient if the SDK handles it, 
        # but currently the Python SDK returns text that is JSON.
        result_dict = json.loads(response.text)
        return ReportValidationResult(**result_dict)
    except Exception as e:
        logging.error(f"Error during report validation: {e}")
        return ReportValidationResult(
            valid=False, 
            reason=f"AI Error: {str(e)}", 
            thought_process=f"Exception: {e}"
        )

async def analyze_daily_logs(logs, active_agreements=None, date_str=None, future_logs=None, chat_id=None) -> DailyAnalysisResult:
    """
    Sends chat logs to Gemini and returns the winner analysis.
    Returns DailyAnalysisResult.
    """
    if not logs:
        return None

    model = GenerativeModel(config.AI_MODEL_ANALYSIS)
    
    # Map for reply resolution
    all_logs = logs + (future_logs or [])
    id_map = {log.get('message_id'): log.get('username') for log in all_logs if log.get('message_id')}

    moscow_tz = timezone(timedelta(hours=config.TIMEZONE_OFFSET))

    def format_log_entry(log):
        ts = log['timestamp']
        if hasattr(ts, 'astimezone'):
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            ts = ts.astimezone(moscow_tz)
            
        time_str = ts.strftime("%H:%M") if hasattr(ts, 'strftime') else str(ts)
        
        reply_context = ""
        reply_id = log.get('reply_to')
        if reply_id:
            target_user = id_map.get(str(reply_id))
            if target_user:
                reply_context = f" [Reply to {target_user}, MsgID: {reply_id}]"
            else:
                reply_context = f" [Reply to MsgID: {reply_id}]"
        
        report_tag = ""
        if log.get('is_reported'):
            reason = log.get('report_reason', 'No reason')
            points_awarded = log.get('points_awarded', 0)
            report_tag = f" [REPORTED BY USER: {reason}]"
            if points_awarded > 0:
                report_tag += f" [POINTS ALREADY AWARDED ({points_awarded}) - DO NOT SCORE]"
        
        username = log['username']
        if log.get('is_bot') or username == "YOU (Snitch Bot)":
            username = "YOU (Snitch Bot)"

        return f"[{time_str}] {username} (ID: {log['user_id']}){reply_context}: {log['text']}{report_tag}"

    chat_history = "LOG START (MESSAGES TO JUDGE)\n"
    for log in logs:
        chat_history += format_log_entry(log) + "\n"
    chat_history += "LOG END"

    future_context_str = ""
    if future_logs:
        future_context_str = "\nFUTURE CONTEXT (DO NOT JUDGE, ONLY FOR REFERENCE):\n"
        for log in future_logs:
            future_context_str += format_log_entry(log) + "\n"
        future_context_str += "END FUTURE CONTEXT\n"

    agreements_text = "Нет действующих договоренностей."
    if config.ENABLE_AGREEMENTS and active_agreements:
        agreements_text = ""
        for ag in active_agreements:
             ts = ag.get('created_at')
             date_str_agr = ts.strftime("%Y-%m-%d") if hasattr(ts, 'strftime') else "Unknown"
             ag_type = ag.get('type', 'vow')
             ag_users = ", ".join(ag.get('users', []))
             agreements_text += f"- [ID: {ag['id']}] {ag_users}: {ag['text']} (Тип: {ag_type}, от {date_str_agr})\n"

    # Add Day of Week for better context
    try:
        dt_obj = datetime.fromisoformat(date_str) if date_str else datetime.now()
        days_ru = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        day_of_week = days_ru[dt_obj.weekday()]
        full_date_str = f"{date_str} ({day_of_week})"
    except Exception:
        full_date_str = date_str or 'Unknown'

    agreements_section = ""
    if config.ENABLE_AGREEMENTS:
        agreements_section = f"""
    ACTIVE AGREEMENTS (Проверь на нарушения):
    {agreements_text}
    """

    prompt = f"""
    СЕГОДНЯШНЯЯ ДАТА: {full_date_str}
    {agreements_section}
    Вот лог чата за сегодня:
    {chat_history}
    {future_context_str}
    
    Определи Снитча Дня согласно твоей системной инструкции.
    {"ВАЖНО: Все описания договоренностей в поле 'text' должны быть на РУССКОМ ЯЗЫКЕ." if config.ENABLE_AGREEMENTS else ""}
    """
    
    try:
        lore_full = await LoreService.get_lore(chat_id) if chat_id else {}
        lore_core = lore_full.get('core', lore_full)
        lore_json = json.dumps(lore_core, ensure_ascii=False, indent=2)
        
        facts_str = await FactService.get_facts_as_str(chat_id) if chat_id else ""
        context_str = lore_full.get('current_context', "")
        
        from src.services.learning import LearningService
        lessons = await LearningService.get_active_lessons(chat_id) if chat_id else []
        
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type(Exception),
            reraise=True
        )
        async def _generate_with_retry():
            # Define schema properties
            schema_properties = {
                "thought_process": {"type": "STRING", "description": "Подробный разбор полетов и анализ ситуации перед вынесением вердикта"},
                "offenders": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "user_id": {"type": "INTEGER", "description": "Telegram User ID"},
                            "username": {"type": "STRING", "description": "Username"},
                            "category": {"type": "STRING", "description": "Toxicity | Snitching"},
                            "points": {"type": "INTEGER", "description": "Points"},
                            "reason": {"type": "STRING", "description": "Reason"},
                            "quote": {"type": "STRING", "description": "Quote"}
                        },
                        "required": ["username", "category", "points", "reason"]
                    }
                }
            }
            
            required_fields = ["thought_process", "offenders"]

            if config.ENABLE_AGREEMENTS:
                schema_properties["new_agreements"] = {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "text": {"type": "STRING", "description": "Описание договоренности СТРОГО НА РУССКОМ"},
                            "users": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Список участников"},
                            "type": {"type": "STRING", "description": "vow | pact | public"},
                            "expires_at": {"type": "STRING", "description": "YYYY-MM-DDTHH:MM:SS"},
                            "reasoning": {"type": "STRING", "description": "Reasoning"}
                        },
                        "required": ["text", "users", "type", "reasoning"]
                    }
                }
                schema_properties["resolved_agreements"] = {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "id": {"type": "STRING", "description": "ID"},
                            "status": {"type": "STRING", "description": "fulfilled | broken"},
                            "reason": {"type": "STRING", "description": "Reason"}
                        },
                        "required": ["id", "status", "reason"]
                    }
                }
                schema_properties["updated_agreements"] = {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "id": {"type": "STRING", "description": "ID"},
                            "text": {"type": "STRING", "description": "New text"},
                            "reason": {"type": "STRING", "description": "Reason"}
                        },
                        "required": ["id", "text", "reason"]
                    }
                }
                required_fields.extend(["new_agreements", "resolved_agreements", "updated_agreements"])

            daily_analysis_schema = {
                "type": "OBJECT",
                "properties": schema_properties,
                "required": required_fields
            }

            return await model.generate_content_async(
                contents=[get_system_prompt(lore_json, facts_str, context_str, lessons), prompt],
                generation_config={
                    "response_mime_type": "application/json",
                    "response_schema": daily_analysis_schema
                }
            )

        response = await _generate_with_retry()
        
        logging.info(f"AI Response with thoughts: {response.text[:500]}...")
        result_dict = json.loads(response.text)
        return DailyAnalysisResult(**result_dict)
    except Exception as e:
        logging.error(f"Error during AI analysis: {e}")
        return None

async def transcribe_media(file_data: bytes, mime_type: str) -> str:
    """
    Transcribes voice or video using Gemini Multimodal.
    """
    model = GenerativeModel(config.AI_MODEL_MULTIMODAL)
    
    prompt = "Transcribe this audio/video verbatim. Return only the text in Russian (or original language if not Russian)."
    
    try:
        response = await model.generate_content_async(
            contents=[
                Part.from_data(data=file_data, mime_type=mime_type),
                prompt
            ]
        )
        return response.text.strip()
    except Exception as e:
        logging.error(f"Transcription error: {e}")
        return f"[Transcription Failed: {e}]"

async def summarize_day(chat_id: int, date_key: str, logs: list) -> MemorySummaryResult:
    """
    Summarizes day's events and stores in memories collection.
    Returns MemorySummaryResult.
    """
    if not logs:
        return None

    model = GenerativeModel(config.AI_MODEL_ANALYSIS)
    
    # Format logs for summarization
    formatted_logs = ""
    for log in logs:
        username = log.get('username')
        if log.get('is_bot') or username == "YOU (Snitch Bot)":
            username = "YOU (Snitch Bot)"
        formatted_logs += f"- {username}: {log.get('text')}\n"

    prompt = f"""
    ДАТА: {date_key}
    ЛОГИ ЧАТА:
    {formatted_logs}
    """
    
    try:
        memory_schema = {
            "type": "OBJECT",
            "properties": {
                "summary": {"type": "STRING", "description": "Short summary"},
                "key_facts": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Key facts"},
                "emotional_vibe": {"type": "STRING", "description": "Vibe"},
                "major_events": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "title": {"type": "STRING"},
                            "participants": {"type": "ARRAY", "items": {"type": "STRING"}},
                            "outcome": {"type": "STRING"}
                        },
                        "required": ["title", "participants", "outcome"]
                    }
                }
            },
            "required": ["summary", "key_facts", "emotional_vibe", "major_events"]
        }

        response = await model.generate_content_async(
            contents=[MEMORY_SUMMARIZATION_PROMPT, prompt],
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": memory_schema
            }
        )
        result_dict = json.loads(response.text)
        result = MemorySummaryResult(**result_dict)

        if result:
            from .db import db # Avoid circular import if needed
            chat_id_str = str(chat_id)
            doc_ref = db.collection("chats").document(chat_id_str).collection("memories").document(date_key)
            
            # Convert to dict for Firestore
            data = result.model_dump()
            data['date'] = date_key
            data['created_at'] = datetime.now(timezone.utc)
            
            await doc_ref.set(data)
            logging.info(f"Memory saved for chat {chat_id} on {date_key}")
            return result
    except Exception as e:
        logging.error(f"Error during summarization: {e}")
    return None

async def generate_cynical_comment(context_msgs, current_text, current_username="Unknown", chat_id=None):
    """
    Generates a short, cynical comment based on context.
    """
    # Improved cache key: include chat_id, current_text, and a hash of context_msgs
    context_hash = hash(frozenset(msg.get('message_id', msg.get('text', '')) for msg in context_msgs))
    cache_key = (chat_id, current_text, context_hash)
    
    if cache_key in comment_cache:
        logging.info(f"Using cached cynical comment for chat {chat_id}")
        return comment_cache[cache_key]

    model = GenerativeModel(config.AI_MODEL_ANALYSIS)
    
    context_str = ""
    for msg in context_msgs:
        name = msg.get('username', 'Unknown')
        if msg.get('is_bot') or name == "YOU (Snitch Bot)":
            name = "YOU (Snitch Bot)"

        txt = msg.get('text', '')
        if txt == current_text:
            continue
        context_str += f"- {name}: {txt}\n"
        
    prompt = f"""
КОНТЕКСТ ПРЕДЫДУЩИХ СООБЩЕНИЙ:
{context_str}

АКТУАЛЬНОЕ СООБЩЕНИЕ, НА КОТОРОЕ НУЖНО ОТВЕТИТЬ (от пользователя {current_username}):
"{current_text}"

ИНСТРУКЦИЯ: Напиши ОДНО короткое, едкое и живое предложение, которое будет НАТИВНЫМ продолжением этого диалога.
Избегай упоминаний лора (штора, плитка, пуэр, вахта), если только они не упомянуты в самом сообщении.
Не используй клише про "обучение", "волю" или "репорты". Отвечай как человек человеку.
"""
    
    try:
        lore_full = await LoreService.get_lore(chat_id) if chat_id else {}
        lore_core = lore_full.get('core', lore_full)
        lore_json = json.dumps(lore_core, ensure_ascii=False, indent=2)
        
        facts_str = await FactService.get_facts_as_str(chat_id) if chat_id else ""
        context_str = lore_full.get('current_context', "")
        
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=6),
            retry=retry_if_exception_type(Exception),
            reraise=True
        )
        async def _generate_with_retry():
            return await model.generate_content_async(
                contents=[get_cynical_comment_prompt(lore_json, facts_str, context_str), prompt]
            )

        response = await _generate_with_retry()
        comment = response.text.strip()
        comment_cache[cache_key] = comment
        return comment
    except Exception as e:
        logging.error(f"Error generating comment: {e}")
        return None

async def validate_fact(text: str) -> FactValidationResult:
    """
    Validates if the text is a fact and cleans it up using AI.
    Returns FactValidationResult object.
    """
    if not text or len(text.strip()) < 3:
        return FactValidationResult(
            is_fact=False,
            cleaned_fact=None,
            reason="Слишком короткий текст."
        )

    model = GenerativeModel(config.AI_MODEL_ANALYSIS)
    
    prompt = f"ТЕКСТ ДЛЯ ПРОВЕРКИ:\n\"{text}\""

    try:
        response = await model.generate_content_async(
            contents=[FACT_VALIDATION_PROMPT, prompt],
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": FactValidationResult
            }
        )
        
        result_dict = json.loads(response.text)
        return FactValidationResult(**result_dict)
    except Exception as e:
        logging.error(f"Error during fact validation: {e}")
        return FactValidationResult(
            is_fact=False,
            cleaned_fact=None,
            reason=f"Ошибка AI при валидации: {str(e)}"
        )
