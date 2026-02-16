from ..services import db
from ..services import ai
from ..utils.game_config import config
from ..utils import messages
from ..utils.text import escape

class ReportService:

    @staticmethod
    async def process_report(message, reported_msg, target_text: str):
        """
        Processes a report command.
        Returns the result text to reply with and the result status (valid/invalid).
        """
        # Context gathering
        prev_msgs = await db.get_recent_messages(message.chat.id, reported_msg.date, limit=config.REPORT_CONTEXT_LIMIT)
        next_msgs = await db.get_subsequent_messages(message.chat.id, reported_msg.date, limit=config.REPORT_NEXT_CONTEXT_LIMIT)
        
        context_msgs = prev_msgs + next_msgs
        result = await ai.validate_report(target_text, context_msgs, chat_id=message.chat.id)
        
        # result is now a ReportValidationResult Pydantic object
        if result and result.valid:
            category = escape(result.category or "Unspecified")
            reason = escape(result.reason or "Violation detected")
            points = result.points
            ai_thoughts = result.thought_process
            
            await db.mark_message_reported(
                message.chat.id,
                reported_msg.message_id,
                message.from_user.id,
                f"{category}: {reason}",
                points_awarded=points,
                ai_thought_process=ai_thoughts
            )
            await db.add_points(message.chat.id, reported_msg.from_user.id, points)
            
            return messages.REPORT_ACCEPTED.format(category=category, points=points, reason=reason), True
        else:
            new_count = await db.increment_false_report_count(message.chat.id, message.from_user.id)
            deny_reason = escape(result.reason if result else "AI Error")
            response_text = messages.REPORT_REJECTED.format(reason=deny_reason)
            
            if new_count % config.FALSE_REPORT_LIMIT == 0:
                await db.add_points(message.chat.id, message.from_user.id, config.FALSE_REPORT_PENALTY)
                response_text += messages.REPORT_PENALTY.format(penalty=config.FALSE_REPORT_PENALTY, count=new_count)
                
            return response_text, False
