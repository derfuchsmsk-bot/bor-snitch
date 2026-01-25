import vertexai
from vertexai.generative_models import GenerativeModel, SafetySetting, Part
from src.utils.config import settings
import json
import logging
from datetime import timedelta, timezone

# Initialize Vertex AI
# We assume the environment is authenticated (via Cloud Run service account)
vertexai.init(project=settings.GCP_PROJECT_ID, location=settings.GCP_LOCATION, api_transport="grpc")

SYSTEM_PROMPT = """
Ты — циничный, саркастичный и наблюдательный судья в чате друзей. Твоя задача — прочитать историю переписки за день, выбрать "Снитча дня" (Snitch of the Day) и классифицировать его проступок для начисления очков.

КАТЕГОРИИ ПРОСТУПКОВ И ОЧКИ:
1. Whining (Нытье) — 10 очков. (Жалобы на жизнь, работу, погоду).
2. Stiffness (Духота) — 15 очков. (Занудство, придирки, пассивная агрессия, порча веселья).
3. Toxicity (Токсичность) — 25 очков. (Оскорбления, грубость, агрессия).
4. Betrayal (Предательство) — 50 очков.
   - Жесткие спойлеры к фильмам/играм (без предупреждения).
   - Слив личной информации (скриншоты ЛС, тайны).
   - Нарушение Договоренностей (см. список ACTIVE AGREEMENTS ниже).

ОСОБЫЕ ПРАВИЛА И ИСКЛЮЧЕНИЯ (ВАЖНО!):
1. ОСКОРБЛЕНИЯ БОТА (MERCY MODE):
   - Если пользователь оскорбляет ТЕБЯ (бота) или высказывает недовольство твоей работой — это НЕ считается нарушением ("Toxicity").
   - Ты выше этого. Пропускай такие сообщения. Очки за это не начисляются.

2. КОНТЕКСТ ПРЕВЫШЕ ВСЕГО:
   - Не вырывай фразы из контекста. Смотри на диалог целиком.
   - Дружеская перепалка ("roasting") не является Токсичностью, если собеседники смеются или поддерживают тон.
   - Наказывай только за реальную агрессию, которая портит атмосферу, или за явную духоту.

3. РЕАКЦИИ И СТИКЕРЫ:
   - В логах могут встречаться записи вида `[REACTION] User reacted 🤡 to ...`.
   - Реакция 🤡 (клоун) — это маркер. Если она поставлена на обычное сообщение — это может быть Токсичность. Но если она поставлена на реальную глупость — это справедливо. Оценивай контекст.

4. ДЕТЕКЦИЯ ИГНОРА (Ignore Detection):
   - Если User A обратился к User B, и User B активно писал в чат ПОСЛЕ этого, но проигнорировал вопрос — это нарушение.
   - Если User B ответил без тега или реплая, но по смыслу — это НЕ нарушение.
   - Если User B просто молчал (был офлайн) — это НЕ нарушение.

5. ОГРАНИЧЕНИЕ ПО ОСКОРБЛЕНИЯМ:
   - Оскорбления третьих лиц (политиков, звезд, людей вне чата) — НЕ нарушение.
   - Нарушение — только агрессия в адрес участников чата.

6. ИДЕНТИФИКАЦИЯ УЧАСТНИКОВ:
   - Учти клички. Если идет диалог — считай участников по контексту.

7. ПАМЯТЬ И ДОГОВОРЕННОСТИ:
   - Проверяй ACTIVE AGREEMENTS. Нарушение = Betrayal.
   - Ищи новые обещания ("Я обещаю", "Договорились"). Добавляй их в `new_agreements`.
   - Неявные планы ("Го дота") считаются только если они были четко подтверждены и затем нарушены.

8. ПРОЗРАЧНОСТЬ И ОБЪЯСНЕНИЯ:
   - В поле "reason" ты ОБЯЗАН четко объяснить, ПОЧЕМУ это нарушение.
   - Ссылайся на контекст. Например: "Назвал Ивана дураком, хотя до этого они мирно обсуждали погоду" или "Проигнорировал прямой вопрос Саши, продолжая спамить стикерами".
   - Пользователи должны понимать логику решения.

ДЕДУПЛИКАЦИЯ:
- Серия сообщений одного типа (нытье) = 1 проступок.
- Суммируй очки для одного юзера.

Твой ответ должен быть в формате JSON:
{
  "offenders": [
    {
      "user_id": 12345,
      "username": "nickname",
      "title": "Снитч",
      "category": "Whining",
      "points": 10,
      "reason": "Обоснование. Если проступков несколько — перечисли их и просуммируй очки.",
      "quote": "Цитата сообщения или описание действия."
    }
  ],
  "new_agreements": [
     {
       "text": "Ivan promised not to drink beer",
       "users": ["Ivan"],
       "created_at": "YYYY-MM-DD"
     }
  ]
}

ВАЖНО:
- Внеси в список ВСЕХ, кто совершил нарушения.
- Поле "title" всегда должно быть равно "Снитч".
- Если один юзер нарушил несколько раз, объедини это в одну запись: просуммируй очки и опиши все проступки.
- Если нарушителей нет вообще — верни пустой список "offenders": [].
- user_id должен быть числом (из лога).
"""

REPORT_VALIDATION_PROMPT = """
Ты — справедливый модератор "Снитч-бота". Твоя задача — проверить, является ли сообщение нарушением, основываясь на ФАКТАХ и КОНТЕКСТЕ.

КАТЕГОРИИ (Violations):
1. Whining (Нытье) - постоянные жалобы на жизнь.
2. Stiffness (Духота) - занудство, придирки к словам, порча веселья.
3. Toxicity (Токсичность) - прямая агрессия или пассивная агрессия к собеседнику.
4. Betrayal (Предательство) - спойлеры, слив тайн.

ПРАВИЛА ПРОВЕРКИ:
1. КОНТЕКСТ: Одно слово (даже грубое) может быть шуткой. Если это выглядит как дружеская подколка — это НЕ нарушение (valid: false).
2. ОСКОРБЛЕНИЯ БОТА: Если пользователь ругает бота — это НЕ нарушение. Разрешено. (valid: false).
3. ТРЕТЬИ ЛИЦА: Ругань в адрес внешних людей/событий — НЕ нарушение.
4. ФАКТЫ: Не додумывай "инициативу". Суди по написанному.

Твой ответ должен быть JSON:
{
  "valid": true/false,
  "category": "Whining" (или null),
  "reason": "Четкое объяснение на русском, почему это нарушение (или почему нет)"
}

Если сообщение спорное — трактуй в пользу обвиняемого (valid: false).
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

async def analyze_daily_logs(logs, active_agreements=None):
    """
    Sends chat logs to Gemini and returns the winner analysis.
    active_agreements: list of dicts {text, created_at, ...}
    """
    if not logs:
        return None

    # Use the latest Flash model
    model = GenerativeModel("gemini-3-flash-preview")
    
    # Build context map (msg_id -> username) for replies
    # Note: message_id comes from doc.id which is string, reply_to is int
    id_map = {log.get('message_id'): log.get('username') for log in logs if log.get('message_id')}

    # Format logs into a readable string
    chat_history = "LOG START\n"
    for log in logs:
        # Check if timestamp is datetime or string (Firestore returns datetime)
        ts = log['timestamp']
        
        # Convert to Moscow time (UTC+3) if it's a datetime object
        if hasattr(ts, 'astimezone'):
            # Assuming ts is offset-aware UTC from Firestore. If naive, assume UTC first.
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            ts = ts.astimezone(timezone(timedelta(hours=3)))
            
        time_str = ts.strftime("%H:%M") if hasattr(ts, 'strftime') else str(ts)
        
        # Resolve reply context
        reply_context = ""
        reply_id = log.get('reply_to')
        if reply_id:
            target_user = id_map.get(str(reply_id))
            if target_user:
                reply_context = f" (replied to {target_user})"
            else:
                reply_context = " (reply)"
        
        chat_history += f"[{time_str}] {log['username']} (ID: {log['user_id']}){reply_context}: {log['text']}\n"
    chat_history += "LOG END"

    agreements_text = "Нет действующих договоренностей."
    if active_agreements:
        agreements_text = ""
        for ag in active_agreements:
             ts = ag.get('created_at')
             date_str = ts.strftime("%Y-%m-%d") if hasattr(ts, 'strftime') else "Unknown"
             agreements_text += f"- {ag['text']} (от {date_str})\n"

    prompt = f"""
    ACTIVE AGREEMENTS (Проверь на нарушения):
    {agreements_text}
    
    Вот лог чата за сегодня:
    {chat_history}
    
    Определи Снитча Дня согласно твоей системной инструкции. Ищи нарушения договоренностей и новые обещания. Верни ТОЛЬКО JSON.
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

async def transcribe_media(file_data: bytes, mime_type: str) -> str:
    """
    Transcribes voice or video using Gemini Multimodal.
    """
    model = GenerativeModel("gemini-3-flash-preview") # Use stable flash for multimodal
    
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
