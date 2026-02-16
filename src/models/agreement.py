from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional, Any

class AgreementModel(BaseModel):
    id: Optional[str] = None
    text: str
    users: List[str]
    type: str # 'vow', 'pact', 'public'
    status: str = 'active' # 'active', 'fulfilled', 'broken', 'disputed'
    created_at: Any = None # ServerTimestamp
    expires_at: datetime
    can_be_disputed_until: datetime
    
    # Optional fields
    resolution_reason: Optional[str] = None
    update_reason: Optional[str] = None
    updated_at: Optional[Any] = None
