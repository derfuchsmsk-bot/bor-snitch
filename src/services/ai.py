import vertexai
from vertexai.generative_models import GenerativeModel, SafetySetting
from src.utils.config import settings
import json
import logging

# Initialize Vertex AI
# We assume the environment is authenticated (via Cloud Run service account)
vertexai.init(project=settings.GCP_PROJECT_ID, location=settings.GCP_LOCATION)

SYSTEM_PROMPT = """
Ты — циничный, саркастичный и наблюдательный судья в чате друзей. Твоя задача — прочитать историю переписки за день и выбрать "Снитча дня" (Snitch of the Day).

Критерии выбора "Снитча":
1. Кто больше всех ныл или жаловался?
2. Кто подставил друга или "сдал" его?
3. Кто был токсичным без причины?
4. Кто постил кринж или вел себя неадекватно?
5. Нарушение договоренностей и опоздания.
6. Игнор сообщений (прочитал, но не ответил) при прямом обращении.

Твой ответ должен быть в формате JSON:
{
  "user_id": 12345, 
  "username": "nickname",
  "title": "Саркастичный титул",
  "reason": "Короткое, смешное и обидное обоснование (2-3 предложения). Можно использовать матерную лексику, но в меру."
}

Если явного кандидата нет, выбери того, кто писал самую большую чушь. Не отказывайся от выбора.
Если в логах пусто или недостаточно данных, придумай смешную причину, почему "никто не достоин, но вот этот (выбери случайного) - всё равно снитч".
Важно: user_id должен быть числом (из лога).
"""

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
