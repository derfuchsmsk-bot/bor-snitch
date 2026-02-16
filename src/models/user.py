from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class UserStats(BaseModel):
    user_id: str
    username: Optional[str] = None
    full_name: Optional[str] = None
    total_points: int = 0
    current_rank: str = "Порядочный 😐"
    snitch_count: int = 0
    false_report_count: int = 0
    last_active_date: Optional[datetime] = None
    last_gamble_date: Optional[str] = None
    last_win_date: Optional[str] = None
    season_id: Optional[str] = None
