from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Any

class FactModel(BaseModel):
    id: Optional[str] = None
    text: str
    created_at: Any = None # ServerTimestamp
    source: str = "system"
    confidence: float = 1.0
    date: Optional[str] = None # Optional string date if extracted
