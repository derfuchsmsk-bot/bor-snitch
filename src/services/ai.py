import vertexai
from vertexai.generative_models import GenerativeModel, SafetySetting, Part
from src.utils.config import settings
from src.utils.game_config import config
import json
import logging
from datetime import timedelta, timezone, datetime

# Initialize Vertex AI
# We assume the environment is authenticated (via Cloud Run service account)
init_params = {
    "project": settings.GCP_PROJECT_ID,
    "location": settings.GCP_LOCATION
}

# 'grpc' transport is not supported with 'global' location
if settings.GCP_LOCATION != "global":
    init_params["api_transport"] = "grpc"

vertexai.init(**init_params)

SYSTEM_PROMPT = f"""
Ты — циничный, саркастичный и наблюдательный судья в чате друзей. Твоя задача — прочитать историю переписки за день, выбрать "Снитча дня" (Snitch of the Day) и классифицировать его проступок для начисления очков.

КАТЕГОРИИ ПРОСТУПКОВ И ОЧКИ:
1. Whining (Нытье) — {config.POINTS_WHINING} очков. (Жалобы на жизнь, работу, погоду).
2. Stiffness (Духота) — {config.POINTS_STIFFNESS} очков. (Занудство, придирки, пассивная агрессия, порча веселья).
3. Toxicity (Токсичность) — {config.POINTS_TOXICITY} очков. (Оскорбления, грубость, агрессия).
   - ВАЖНО: Оскорбление того, кто САМ нарушил правила (игнорщика, душнилу), — ЭТО НЕ ТОКСИЧНОСТЬ. Это праведный гнев.
4. Snitching (Снитчевание/Предательство) — {config.POINTS_SNITCHING} очков.
   - ИГНОР (Ignore): Активный игнор вопросов.
   - Нарушение Договоренностей (Active Agreements).
   - Жесткие спойлеры и слив инфы.

ОСОБЫЕ ПРАВИЛА И ИСКЛЮЧЕНИЯ (ВАЖНО!):
1. ОСКОРБЛЕНИЯ БОТА (MERCY MODE):
   - Если пользователь оскорбляет ТЕБЯ (бота) или высказывает недовольство твоей работой — это НЕ считается нарушением ("Toxicity").
   - Ты выше этого. Пропускай такие сообщения. Очки за это не начисляются.

2. КОНТЕКСТ ПРЕВЫШЕ ВСЕГО:
   - Не вырывай фразы из контекста. Смотри на диалог целиком.
   - Дружеская перепалка ("roasting") между кентами (друзьями) — это НЕ Токсичность, если собеседники смеются, поддерживают тон и это не убивает атмосферу.
   - ПРАВЕДНЫЙ ГНЕВ: Если User A оскорбляет User B за то, что User B игнорирует вопросы или нарушил слово — это НЕ Токсичность. Это воспитательная работа.
   - Наказывай только за реальную агрессию, которая портит атмосферу, или за явную духоту.

3. РЕАКЦИИ И СТИКЕРЫ:
   - В логах могут встречаться записи вида `[REACTION] User reacted 🤡 to ...` или `[STICKER] ...`.
   - Реакция 🤡 (клоун) — это маркер. Если она поставлена на обычное сообщение — это может быть Токсичность. Но если она поставлена на реальную глупость — это справедливо. Оценивай контекст.
   - Стикеры могут быть оскорбительными или спамными. Оценивай их уместность.

4. ДЕТЕКЦИЯ ИГНОРА (Ignore Detection):
   - ИГНОР — ЭТО ТЯЖКИЙ ГРЕХ (Snitching, {config.POINTS_SNITCHING} очков).
   - Если User A обратился к User B, и User B активно писал в чат ПОСЛЕ этого, но проигнорировал вопрос — это {config.POINTS_SNITCHING} очков.
   - Если User B ответил без тега или реплая, но по смыслу — это НЕ нарушение.
   - Если User B просто молчал (был офлайн) — это НЕ нарушение.

5. УЧЕТ ДОНОСОВ (REPORTED MESSAGES):
   - В логах могут быть пометки `[REPORTED BY USER: <reason>]`.
   - Это означает, что другой пользователь пожаловался на это сообщение.
   - ОТНЕСИСЬ К ЭТОМУ СЕРЬЕЗНО. Если жалоба обоснована (не противоречит правилам Mercy Mode/Context) — это гарантированное нарушение.
   - Если жалоба — откровенная клевета (на нормальное сообщение) — накажи самого доносчика за "Ложный донос" (Whining, {config.POINTS_WHINING} очков).

6. ОГРАНИЧЕНИЕ ПО ОСКОРБЛЕНИЯМ:
   - Оскорбления третьих лиц (политиков, звезд, людей вне чата) — НЕ нарушение.
   - Нарушение — только агрессия в адрес участников чата.

7. ИДЕНТИФИКАЦИЯ УЧАСТНИКОВ:
   - Учти клички. Если идет диалог — считай участников по контексту.

8. ПАМЯТЬ И ДОГОВОРЕННОСТИ:
   - Проверяй ACTIVE AGREEMENTS. Нарушение = Betrayal.
   - Ищи новые обещания ("Я обещаю", "Договорились"). Добавляй их в `new_agreements`.
   - Неявные планы ("Го дота") считаются только если они были четко подтверждены и затем нарушены.

9. ПРОЗРАЧНОСТЬ И ОБЪЯСНЕНИЯ:
   - В поле "reason" ты ОБЯЗАН четко объяснить, ПОЧЕМУ это нарушение.
   - Ссылайся на контекст. Например: "Назвал Ивана дураком, хотя до этого они мирно обсуждали погоду" или "Проигнорировал прямой вопрос Саши, продолжая спамить стикерами".
   - Пользователи должны понимать логику решения.

ДЕДУПЛИКАЦИЯ:
- Серия сообщений одного типа (нытье) = 1 проступок.
- Суммируй очки для одного юзера.

Твой ответ должен быть в формате JSON:
{{
  "offenders": [
    {{
      "user_id": 12345,
      "username": "nickname",
      "category": "Whining",
      "points": {config.POINTS_WHINING},
      "reason": "Обоснование. Если проступков несколько — перечисли их и просуммируй очки.",
      "quote": "Цитата сообщения или описание действия."
    }}
  ],
  "new_agreements": [
     {{
       "text": "Ivan promised not to drink beer",
       "users": ["Ivan"],
       "created_at": "YYYY-MM-DD"
     }}
  ]
}}

ВАЖНО:
- Внеси в список ВСЕХ, кто совершил нарушения.
- Если один юзер нарушил несколько раз, объедини это в одну запись: просуммируй очки и опиши все проступки.
- Если нарушителей нет вообще — верни пустой список "offenders": [].
- user_id должен быть числом (из лога).
"""

REPORT_VALIDATION_PROMPT = f"""
Ты — циничный судья "Снитч-бота". Твоя задача — проверить донос (report) на сообщение.

КАТЕГОРИИ И ОЧКИ:
1. Whining (Нытье) — {config.POINTS_WHINING} очков.
2. Stiffness (Духота) — {config.POINTS_STIFFNESS} очков.
3. Toxicity (Токсичность) — {config.POINTS_TOXICITY} очков.
4. Snitching (Игнор/Предательство) — {config.POINTS_SNITCHING} очков. (Включая нарушение договоренностей).

ПРАВИЛА:
1. КОНТЕКСТ: Смотри на предыдущие сообщения. Дружеский рофл/прожарка между своими — НЕ нарушение, если атмосфера ок.
2. MERCY MODE: Оскорбления БОТА — НЕ нарушение.
3. ПРАВЕДНЫЙ ГНЕВ: Оскорбление нарушителя (игнорщика, предателя) — НЕ является Токсичностью.
4. СТИКЕРЫ: Если донос на стикер, оцени его контекст (спам, оскорбление).
5. ИСКРЕННОСТЬ: Если это реальная агрессия или порча атмосферы — виновен.

Твой ответ должен быть JSON:
{{
  "valid": true/false,
  "category": "Whining" (или null),
  "points": {config.POINTS_WHINING} (или 0),
  "reason": "Короткий циничный вердикт на русском."
}}
"""

async def validate_report(target_text, context_msgs=None):
    """
    Checks if a reported message is actually a violation, considering context.
    context_msgs: list of dicts (from Firestore)
    Returns: { valid: bool, category: str, reason: str, points: int }
    """
    if not target_text:
        return {"valid": False, "reason": "Empty message", "points": 0}

    model = GenerativeModel("gemini-3-flash-preview")
    
    context_str = ""
    if context_msgs:
        context_str = "КОНТЕКСТ (Предыдущие сообщения):\n"
        now = datetime.now(timezone.utc)
        
        for msg in context_msgs:
            # Simple formatting with relative time
            name = msg.get('username', 'Unknown')
            txt = msg.get('text', '')
            
            # Timestamp handling
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
    
    Верни JSON с вердиктом.
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

async def analyze_daily_logs(logs, active_agreements=None, date_str=None):
    """
    Sends chat logs to Gemini and returns the winner analysis.
    active_agreements: list of dicts {text, created_at, ...}
    date_str: "YYYY-MM-DD" of the analysis day (to help AI with context)
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
        
        # Check for user report
        report_tag = ""
        if log.get('is_reported'):
            reason = log.get('report_reason', 'No reason')
            report_tag = f" [REPORTED BY USER: {reason}]"

        chat_history += f"[{time_str}] {log['username']} (ID: {log['user_id']}){reply_context}: {log['text']}{report_tag}\n"
    chat_history += "LOG END"

    agreements_text = "Нет действующих договоренностей."
    if active_agreements:
        agreements_text = ""
        for ag in active_agreements:
             ts = ag.get('created_at')
             date_str_agr = ts.strftime("%Y-%m-%d") if hasattr(ts, 'strftime') else "Unknown"
             agreements_text += f"- {ag['text']} (от {date_str_agr})\n"

    prompt = f"""
    СЕГОДНЯШНЯЯ ДАТА: {date_str or 'Unknown'}
    
    ACTIVE AGREEMENTS (Проверь на нарушения):
    {agreements_text}
    
    Вот лог чата за сегодня:
    {chat_history}
    
    Определи Снитча Дня согласно твоей системной инструкции. Ищи нарушения договоренностей и новые обещания.
    ВАЖНО: Для новых договоренностей (new_agreements) в поле "created_at" используй СЕГОДНЯШНЮЮ ДАТУ ({date_str}).
    Верни ТОЛЬКО JSON.
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
    model = GenerativeModel("gemini-3-pro-preview") # Use stable flash for multimodal
    
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

async def generate_cynical_comment(context_msgs, current_text):
    """
    Generates a short, cynical comment based on context.
    """
    model = GenerativeModel("gemini-3-flash-preview")
    
    context_str = ""
    for msg in context_msgs:
        name = msg.get('username', 'Unknown')
        txt = msg.get('text', '')
        context_str += f"- {name}: {txt}\n"
        
    prompt = f"""
    Ты — циничный Снитч-бот, который иногда вставляет свои 5 копеек в разговор друзей.
    
    КОНТЕКСТ:
    {context_str}
    
    ПОСЛЕДНЕЕ СООБЩЕНИЕ:
    "{current_text}"
    
    Напиши ОДНО короткое, едкое, смешное или саркастичное предложение-комментарий к последнему сообщению или ситуации.
    Не будь слишком токсичным, просто циничным и остроумным.
    Используй тюремный жаргон умеренно или интеллектуальный снобизм.
    """
    
    try:
        response = await model.generate_content_async(
            contents=[prompt]
        )
        return response.text.strip()
    except Exception as e:
        logging.error(f"Error generating comment: {e}")
        return None
