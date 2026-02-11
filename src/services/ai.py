import vertexai
from vertexai.generative_models import GenerativeModel, SafetySetting, Part
from src.utils.config import settings
from src.utils.game_config import config
from src.utils.prompts import (
    get_system_prompt,
    get_report_validation_prompt,
    get_cynical_comment_prompt,
    MEMORY_SUMMARIZATION_PROMPT,
    FEEDBACK_ANALYSIS_PROMPT,
    FACT_VALIDATION_PROMPT
)
from src.services.lore_service import LoreService
from src.services.fact_service import FactService
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

def extract_json(text: str) -> dict:
    """
    Extracts JSON from text that might contain 'THOUGHT PROCESS' or other markers.
    Looks for the first '{' and the last '}'.
    Also injects 'ai_thought_process' into the result.
    """
    try:
        # Try finding the last '{' to '}' block
        match = re.search(r'\{.*\}', text, re.DOTALL)
        thought_process = ""
        result = None

        if match:
            json_str = match.group(0)
            # Everything before the match is thought process
            thought_process = text[:match.start()].strip()
            result = json.loads(json_str)
        else:
            result = json.loads(text)
        
        if isinstance(result, dict):
            # Clean up headers like "THOUGHT PROCESS:"
            thought_process = re.sub(r'^(THOUGHT PROCESS|THOUGHTS|REASONING)[:\-\s]*', '', thought_process, flags=re.IGNORECASE|re.MULTILINE).strip()
            # Also remove "FINAL JSON:" if it ended up in thought process or at end
            thought_process = re.sub(r'(FINAL JSON|JSON OUTPUT)[:\-\s]*$', '', thought_process, flags=re.IGNORECASE|re.MULTILINE).strip()
            
            result['ai_thought_process'] = thought_process

        return result
    except Exception as e:
        logging.error(f"Failed to extract JSON from AI response: {e}. Text: {text[:200]}...")
        return None

def parse_ai_response(text: str) -> dict:
    """
    Parses AI response to separate JSON and thought process.
    Returns the JSON dictionary with 'ai_thought_process' injected.
    """
    try:
        json_data = extract_json(text)
        if not json_data:
            return None
            
        # If extraction worked, try to isolate thoughts
        # We reconstruct what extract_json did to find the JSON string location
        match = re.search(r'\{.*\}', text, re.DOTALL)
        thoughts = ""
        if match:
            # Everything before the JSON is thoughts (roughly)
            # or we just remove the JSON string from the original text
            json_str = match.group(0)
            thoughts = text.replace(json_str, "").strip()
            
            # Optional cleanup of markers
            for marker in ["THOUGHT PROCESS", "FINAL JSON", "```json", "```"]:
                thoughts = thoughts.replace(marker, "")
            thoughts = thoughts.strip()
            
        if isinstance(json_data, dict):
            json_data['ai_thought_process'] = thoughts
            
        return json_data
    except Exception as e:
        logging.error(f"Error parsing AI response with thoughts: {e}")
        return None

async def validate_report(target_text, context_msgs=None, chat_id=None):
    """
    Checks if a reported message is actually a violation, considering context.
    Returns JSON dict with 'ai_thought_process' included.
    """
    if not target_text:
        return {"valid": False, "reason": "Empty message", "points": 0}

    model = GenerativeModel(config.AI_MODEL_ANALYSIS)
    
    context_str = ""
    if context_msgs:
        context_str = "КОНТЕКСТ (Предыдущие сообщения):\n"
        # We use UTC for calculation but display is generic here
        now = datetime.now(timezone.utc)
        
        for msg in context_msgs:
            name = msg.get('username', 'Unknown')
            # Check for bot marker
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
    
    Верни THOUGHT PROCESS и FINAL JSON.
    """
    
    try:
        response = await model.generate_content_async(
            contents=[get_report_validation_prompt(), prompt],
            generation_config={"response_mime_type": "text/plain"} # Using plain text to handle mixed output
        )
        result = parse_ai_response(response.text)
        if result:
            return result
        return {"valid": False, "reason": "AI Error (JSON Extraction)"}
    except Exception as e:
        logging.error(f"Error during report validation: {e}")
        return {"valid": False, "reason": f"AI Error: {str(e)}"}

async def analyze_daily_logs(logs, active_agreements=None, date_str=None, future_logs=None, chat_id=None):
    """
    Sends chat logs to Gemini and returns the winner analysis.
    future_logs: Messages from the start of the NEXT day (for context only, to prevent false positives on ignores).
    """
    if not logs:
        return None

    model = GenerativeModel(config.AI_MODEL_ANALYSIS)
    
    # Map for reply resolution (includes future logs for context)
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
    
    Определи Снитча Дня согласно твоей системной инструкции. Верни THOUGHT PROCESS и FINAL JSON.
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
        
        response = await model.generate_content_async(
            contents=[get_system_prompt(lore_json, facts_str, context_str, lessons), prompt],
            generation_config={"response_mime_type": "text/plain"}
        )
        
        logging.info(f"AI Response with thoughts: {response.text[:500]}...")
        result = parse_ai_response(response.text)
        return result
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

async def summarize_day(chat_id: int, date_key: str, logs: list):
    """
    Summarizes day's events and stores in memories collection.
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
        response = await model.generate_content_async(
            contents=[MEMORY_SUMMARIZATION_PROMPT, prompt],
            generation_config={"response_mime_type": "text/plain"}
        )
        result = parse_ai_response(response.text)
        if result:
            from .db import db # Avoid circular import if needed
            chat_id_str = str(chat_id)
            doc_ref = db.collection("chats").document(chat_id_str).collection("memories").document(date_key)
            
            result['date'] = date_key
            result['created_at'] = datetime.now(timezone.utc)
            
            await doc_ref.set(result)
            logging.info(f"Memory saved for chat {chat_id} on {date_key}")
            return result
    except Exception as e:
        logging.error(f"Error during summarization: {e}")
    return None

async def generate_cynical_comment(context_msgs, current_text, current_username="Unknown", chat_id=None):
    """
    Generates a short, cynical comment based on context.
    """
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
        
        response = await model.generate_content_async(
            contents=[get_cynical_comment_prompt(lore_json, facts_str, context_str), prompt]
        )
        return response.text.strip()
    except Exception as e:
        logging.error(f"Error generating comment: {e}")
        return None

async def validate_fact(text: str) -> dict:
    """
    Validates if the text is a fact and cleans it up using AI.
    Returns: { "is_fact": bool, "cleaned_fact": str, "reason": str }
    """
    if not text or len(text.strip()) < 3:
        return {
            "is_fact": False,
            "cleaned_fact": None,
            "reason": "Слишком короткий текст."
        }

    model = GenerativeModel(config.AI_MODEL_ANALYSIS)
    
    prompt = f"ТЕКСТ ДЛЯ ПРОВЕРКИ:\n\"{text}\"\n\nВерни ТОЛЬКО JSON."

    try:
        response = await model.generate_content_async(
            contents=[FACT_VALIDATION_PROMPT, prompt],
            generation_config={"response_mime_type": "application/json"}
        )
        
        # We expect strictly JSON since we specified the mime type
        result = json.loads(response.text)
        return result
    except Exception as e:
        logging.error(f"Error during fact validation: {e}")
        # Fallback to accepting as is if AI fails, or we can be strict.
        # Given the requirements, it's better to be strict if we want validation.
        return {
            "is_fact": False,
            "cleaned_fact": None,
            "reason": f"Ошибка AI при валидации: {str(e)}"
        }
