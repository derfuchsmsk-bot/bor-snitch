import logging
from datetime import datetime, timezone, timedelta
from vertexai.generative_models import GenerativeModel
from .db import db, get_logs_for_time_range
from ..utils.game_config import config
from ..utils.prompts import FEEDBACK_ANALYSIS_PROMPT
from ..models.ai import FeedbackAnalysisResult
import json

class LearningService:
    @staticmethod
    async def analyze_feedback(chat_id: int, date_key: str):
        """
        Analyzes user feedback (replies to bot) to extract lessons.
        """
        chat_id_str = str(chat_id)
        
        # 1. Fetch bot's messages from today
        # We need messages sent BY THE BOT.
        # Currently, we don't log bot messages in the 'messages' collection 
        # (check db.log_message - it takes a Message object, usually from handlers).
        # However, daily_results stores the offenders.
        
        # Let's assume we want to look at messages that are replies to the bot.
        # To do this effectively, we need to know the bot's user_id.
        # For now, let's look at all messages from today and filter those that are replies.
        
        moscow_tz = timezone(timedelta(hours=config.TIMEZONE_OFFSET))
        dt_obj = datetime.strptime(date_key, "%Y-%m-%d")
        start_dt = dt_obj.replace(tzinfo=moscow_tz).astimezone(timezone.utc)
        end_dt = start_dt + timedelta(days=1)
        
        logs = await get_logs_for_time_range(chat_id, start_dt, end_dt)
        if not logs:
            return None

        # Filter messages that look like feedback (replies or mentions)
        # In a real scenario, we'd check if reply_to points to a bot message ID.
        # For simplicity, let's look for messages containing "бот" or "снитч" or replies.
        feedback_logs = []
        for log in logs:
            text = log.get('text', '').lower()
            if log.get('reply_to') or any(kw in text for kw in ["бот", "снитч", "snitch"]):
                feedback_logs.append(log)
        
        if not feedback_logs:
            logging.info(f"No feedback found for chat {chat_id} on {date_key}")
            return None

        # 2. Format feedback for AI
        feedback_str = ""
        for f in feedback_logs:
            feedback_str += f"- {f.get('username')}: {f.get('text')}\n"

        # 3. Call AI
        model = GenerativeModel(config.AI_MODEL_ANALYSIS)
        prompt = f"""
        ДАТА: {date_key}
        ЛОГИ ОБРАТНОЙ СВЯЗИ (Сообщения пользователей о боте или ответы боту):
        {feedback_str}
        
        Проанализируй эти сообщения согласно FEEDBACK_ANALYSIS_PROMPT.
        """
        
        try:
            response = await model.generate_content_async(
                contents=[FEEDBACK_ANALYSIS_PROMPT, prompt],
                generation_config={
                    "response_mime_type": "application/json",
                    "response_schema": FeedbackAnalysisResult
                }
            )
            
            result_dict = json.loads(response.text)
            result = FeedbackAnalysisResult(**result_dict)
            
            if result and result.learned_rule:
                # 4. Save lesson to DB
                lesson_coll = db.collection("chats").document(chat_id_str).collection("lessons")
                await lesson_coll.add({
                    "created_at": datetime.now(timezone.utc),
                    "date_key": date_key,
                    "trigger_context": feedback_str[:1000], # Save a snippet
                    "learned_rule": result.learned_rule,
                    "verdict": result.verdict,
                    "reasoning": result.reasoning,
                    "status": "active"
                })
                logging.info(f"New lesson learned for chat {chat_id}: {result.learned_rule}")
                return result
                
        except Exception as e:
            logging.error(f"Error during feedback analysis: {e}")
            
        return None

    @staticmethod
    async def get_active_lessons(chat_id: int, limit: int = 5):
        """
        Fetches active lessons to inject into the prompt.
        """
        from google.cloud import firestore
        chat_id_str = str(chat_id)
        lessons_ref = db.collection("chats").document(chat_id_str).collection("lessons")
        query = lessons_ref.where(filter=firestore.FieldFilter("status", "==", "active")).limit(limit)
        
        lessons = []
        async for doc in query.stream():
            lessons.append(doc.to_dict().get("learned_rule"))
        
        # Sort in memory to avoid needing composite index
        lessons.reverse() # If we want "latest" first and they are streamed in order?
        # Actually stream order is not guaranteed.
        # But for just a few lessons, we don't need sorting.
        
        return lessons
