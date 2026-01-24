import vertexai
from vertexai.generative_models import GenerativeModel, SafetySetting
from src.utils.config import settings
import json
import logging

# Initialize Vertex AI
# We assume the environment is authenticated (via Cloud Run service account)
vertexai.init(project=settings.GCP_PROJECT_ID, location=settings.GCP_LOCATION)

SYSTEM_PROMPT = """
Ты — циничный, саркастичный и наблюдательный судья в чате друзей. Твоя задача — прочитать историю переписки за день, выбрать "Снитча дня" (Snitch of the Day) и классифицировать его проступок для начисления очков.

КАТЕГОРИИ ПРОСТУПКОВ И ОЧКИ:
1. Whining (Нытье) — 10 очков. (Жалобы на жизнь, работу, погоду).
2. Stiffness (Духота) — 15 очков. (Занудство, придирки, пассивная агрессия).
3. Cringe (Кринж) — 20 очков. (Неудачные шутки, странное поведение, испанский стыд).
4. Toxicity (Токсичность) — 25 очков. (Оскорбления, грубость, агрессия).
5. Betrayal (Предательство) — 50 очков. (Слив инфы, подстава, нарушение договоренностей).

Твой ответ должен быть в формате JSON:
{
  "user_id": 12345,
  "username": "nickname",
  "title": "Смешной титул дня (на основе проступка)",
  "category": "Whining",
  "points": 10,
  "reason": "Короткое, смешное и обидное обоснование (2-3 предложения). Можно использовать матерную лексику, но в меру."
}

Если явного кандидата нет, выбери того, кто был ближе всего к категории "Кринж" или "Духота". Не отказывайся от выбора.
Если в логах пусто или недостаточно данных, придумай смешную причину, почему "никто не достоин, но вот этот (выбери случайного) - всё равно снитч".
Важно: user_id должен быть числом (из лога).
"""

REPORT_VALIDATION_PROMPT = """
Ты — строгий модератор "Снитч-бота". Твоя задача — проверить, является ли сообщение нарушением.

КАТЕГОРИИ (Violations):
1. Whining (Нытье) - жалобы.
2. Stiffness (Духота) - занудство.
3. Cringe (Кринж) - стыд.
4. Toxicity (Токсичность) - агрессия.
5. Betrayal (Предательство) - слив.

Твой ответ должен быть JSON:
{
  "valid": true/false,
  "category": "Whining" (или null),
  "reason": "Короткое объяснение на русском"
}

Если сообщение нейтральное, смешное (в хорошем смысле) или не подходит под категории — ставь valid: false.
Будь строг. Не каждое сообщение — это нарушение.
"""

async def validate_report(text):
    """
    Checks if a reported message is actually a violation.
    Returns: { valid: bool, category: str, reason: str }
    """
    if not text:
        return {"valid": False, "reason": "Empty message"}

    model = GenerativeModel("gemini-3-flash-preview")
    
    prompt = f"""
    Проверь это сообщение на нарушения:
    "{text}"
    
    Верни JSON.
    """
    
    try:
        response = await model.generate_content_async(
            contents=[REPORT_VALIDATION_PROMPT, prompt],
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text)
    except Exception as e:
        logging.error(f"Error during report validation: {e}")
        return {"valid": False, "reason": "AI Error"}

async def analyze_daily_logs(logs):
    """
    Sends chat logs to Gemini and returns the winner analysis.
    """
    if not logs:
        return None

    # Use the latest Flash model
    model = GenerativeModel("gemini-3-flash-preview")
    
    # Format logs into a readable string
    chat_history = "LOG START\n"
    for log in logs:
        # Check if timestamp is datetime or string (Firestore returns datetime)
        ts = log['timestamp']
        time_str = ts.strftime("%H:%M") if hasattr(ts, 'strftime') else str(ts)
        
        chat_history += f"[{time_str}] {log['username']} (ID: {log['user_id']}): {log['text']}\n"
    chat_history += "LOG END"

    prompt = f"""
    Вот лог чата за сегодня:
    {chat_history}
    
    Определи Снитча Дня согласно твоей системной инструкции. Верни ТОЛЬКО JSON.
    """
    
    try:
        response = await model.generate_content_async(
            contents=[SYSTEM_PROMPT, prompt],
            generation_config={"response_mime_type": "application/json"}
        )
        
        logging.info(f"AI Response: {response.text}")
        return json.loads(response.text)
    except Exception as e:
        logging.error(f"Error during AI analysis: {e}")
        return None
