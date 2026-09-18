from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class PointEvent(BaseModel):
    event_id: str = Field(description="Unique idempotency ID for the point transaction")
    chat_id: str
    user_id: str
    points_delta: int
    event_type: str = Field(description="report | gamble | daily_analysis | afk | weekly_amnesty | appeal | admin_adjust | spontaneous_verdict")
    reason: Optional[str] = None
    season_id: str = "global"
    week_key: Optional[str] = Field(default_factory=lambda: PointEvent.current_week_key())
    created_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def current_week_key(cls, dt: Optional[datetime] = None) -> str:
        d = dt or datetime.now(timezone.utc)
        year, week, _ = d.isocalendar()
        return f"{year}-W{week:02d}"
