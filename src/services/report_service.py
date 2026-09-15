from ..services import db
from ..services import ai
from ..utils.game_config import config
from ..utils import messages
from ..utils.text import escape
from ..models.points import PointEvent

class ReportService:

    @staticmethod
    async def process_report(message, reported_msg, target_text: str):
        """
        Processes a report command.
        Returns the result text to reply with and the result status (valid/invalid).
        """
        chat_id = message.chat.id
        reporter_id = message.from_user.id
        target_user_id = reported_msg.from_user.id
        msg_id = reported_msg.message_id

        # 1. Deduplication / Already Processed Check
        existing_msg = await db.message_repository.get_message(chat_id, msg_id)
        if existing_msg and (existing_msg.get("is_reported") or existing_msg.get("points_awarded", 0) > 0):
            return messages.REPORT_ALREADY_PROCESSED, False

        # 2. Context gathering
        prev_msgs = await db.get_recent_messages(chat_id, reported_msg.date, limit=config.REPORT_CONTEXT_LIMIT)
        next_msgs = await db.get_subsequent_messages(chat_id, reported_msg.date, limit=config.REPORT_NEXT_CONTEXT_LIMIT)
        context_msgs = prev_msgs + next_msgs

        # 3. AI Validation
        result = await ai.validate_report(target_text, context_msgs, chat_id=chat_id)

        # 4. Handle Technical / Infrastructure Error (DO NOT penalize user!)
        if not result or result.status == "technical_error":
            return messages.REPORT_TECH_ERROR, False

        # 5. Handle Valid Report
        if result.valid and result.status == "accepted":
            category = escape(result.category or "Unspecified")
            reason = escape(result.reason or "Violation detected")
            points = result.points or (config.POINTS_SNITCHING if "snitch" in category.lower() else config.POINTS_TOXICITY)
            ai_thoughts = result.thought_process

            # Transactional points ledger addition
            event = PointEvent(
                event_id=f"report:{chat_id}:{msg_id}:{reporter_id}",
                chat_id=str(chat_id),
                user_id=str(target_user_id),
                points_delta=points,
                event_type="report",
                reason=f"{category}: {reason}",
                season_id="global"
            )
            await db.user_repository.apply_point_event_transactional(chat_id, event)

            await db.mark_message_reported(
                chat_id,
                msg_id,
                reporter_id,
                f"{category}: {reason}",
                points_awarded=points,
                ai_thought_process=ai_thoughts
            )

            return messages.REPORT_ACCEPTED.format(category=category, points=points, reason=reason), True

        # 6. Handle Genuinely Unfounded Report (Rejected)
        else:
            new_count = await db.increment_false_report_count(chat_id, reporter_id)
            deny_reason = escape(result.reason if result else "Недостаточно оснований")
            response_text = messages.REPORT_REJECTED.format(reason=deny_reason)

            if new_count % config.FALSE_REPORT_LIMIT == 0:
                penalty_event = PointEvent(
                    event_id=f"false_report:{chat_id}:{reporter_id}:{new_count}",
                    chat_id=str(chat_id),
                    user_id=str(reporter_id),
                    points_delta=config.FALSE_REPORT_PENALTY,
                    event_type="false_report",
                    reason=f"Серия ложных доносов ({new_count})",
                    season_id="global"
                )
                await db.user_repository.apply_point_event_transactional(chat_id, penalty_event)
                response_text += messages.REPORT_PENALTY.format(penalty=config.FALSE_REPORT_PENALTY, count=new_count)

            return response_text, False
