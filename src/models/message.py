from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Any

class MessageModel(BaseModel):
    message_id: str
    user_id: int
    username: Optional[str] = None
    full_name: Optional[str] = None
    is_bot: bool = False
    text: Optional[str] = None
    timestamp: datetime
    date_key: str
    reply_to: Optional[int] = None
    
    # Report fields
    is_reported: bool = False
    reported_by: Optional[int] = None
    report_reason: Optional[str] = None
    report_timestamp: Optional[Any] = None # Can be ServerTimestamp
    points_awarded: int = 0
    ai_thought_process: Optional[str] = None

    # Edit fields
    is_edited: bool = False
    last_edit_date: Optional[datetime] = None

    # Reaction fields (if stored as a message)
    type: Optional[str] = None # 'reaction' or None
    target_msg_id: Optional[str] = None
