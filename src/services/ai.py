import vertexai
from vertexai.generative_models import GenerativeModel, SafetySetting, Part
from src.utils.config import settings
from src.utils.game_config import config
from src.utils.prompts import SYSTEM_PROMPT, REPORT_VALIDATION_PROMPT, CYNICAL_COMMENT_PROMPT
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
    """
    try:
        # Try finding the last '{' to '}' block
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            json_str = match.group(0)
            return json.loads(json_str)
        return json.loads(text)
    except Exception as e:
        logging.error(f"Failed to extract JSON from AI response: {e}. Text: {text[:200]}...")
        return None

async def validate_report(target_text, context_msgs=None):
    """
    Checks if a reported message is actually a violation, considering context.
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
            contents=[REPORT_VALIDATION_PROMPT, prompt],
            generation_config={"response_mime_type": "text/plain"} # Using plain text to handle mixed output
        )
        result = extract_json(response.text)
        if result:
            return result
        return {"valid": False, "reason": "AI Error (JSON Extraction)"}
    except Exception as e:
        logging.error(f"Error during report validation: {e}")
        return {"valid": False, "reason": f"AI Error: {str(e)}"}

async def analyze_daily_logs(logs, active_agreements=None, date_str=None):
    """
    Sends chat logs to Gemini and returns the winner analysis.
    """
    if not logs:
        return None

    model = GenerativeModel(config.AI_MODEL_ANALYSIS)
    
    id_map = {log.get('message_id'): log.get('username') for log in logs if log.get('message_id')}

    chat_history = "LOG START\n"
    moscow_tz = timezone(timedelta(hours=config.TIMEZONE_OFFSET))
    
    for log in logs:
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

        chat_history += f"[{time_str}] {log['username']} (ID: {log['user_id']}){reply_context}: {log['text']}{report_tag}\n"
    chat_history += "LOG END"

    agreements_text = "Нет действующих договоренностей."
    if active_agreements:
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

    prompt = f"""
    СЕГОДНЯШНЯЯ ДАТА: {full_date_str}
    
    ACTIVE AGREEMENTS (Проверь на нарушения):
    {agreements_text}
    
    Вот лог чата за сегодня:
    {chat_history}
    
    Определи Снитча Дня согласно твоей системной инструкции. Верни THOUGHT PROCESS и FINAL JSON.
    ВАЖНО: Все описания договоренностей в поле "text" должны быть на РУССКОМ ЯЗЫКЕ.
    """
    
    try:
        response = await model.generate_content_async(
            contents=[SYSTEM_PROMPT, prompt],
            generation_config={"response_mime_type": "text/plain"}
        )
        
        logging.info(f"AI Response with thoughts: {response.text[:500]}...")
        result = extract_json(response.text)
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

async def generate_cynical_comment(context_msgs, current_text, current_username="Unknown"):
    """
    Generates a short, cynical comment based on context.
    """
    model = GenerativeModel(config.AI_MODEL_ANALYSIS)
    
    context_str = ""
    for msg in context_msgs:
        name = msg.get('username', 'Unknown')
        txt = msg.get('text', '')
        context_str += f"- {name}: {txt}\n"
        
    prompt = f"""
    КОНТЕКСТ:
    {context_str}
    
    ПОСЛЕДНЕЕ СООБЩЕНИЕ (от пользователя {current_username}):
    "{current_text}"
    
    Напиши комментарий согласно инструкции.
    """
    
    try:
        response = await model.generate_content_async(
            contents=[CYNICAL_COMMENT_PROMPT, prompt]
        )
        return response.text.strip()
    except Exception as e:
        logging.error(f"Error generating comment: {e}")
        return None
