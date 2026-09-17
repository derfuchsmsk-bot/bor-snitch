from pydantic import BaseModel, Field
from typing import Optional, Any

class LessonModel(BaseModel):
    id: Optional[str] = None
    learned_rule: str = Field(..., description="Сформулированное правило поведения бота")
    verdict: Optional[str] = Field("fair", description="fair | mistake | unclear")
    reasoning: Optional[str] = Field(None, description="Обоснование вердикта и правила")
    trigger_context: Optional[str] = Field(None, description="Контекст сообщений, вызвавший урок")
    status: str = Field("active", description="active | archived")
    date_key: Optional[str] = Field(None, description="Дата в формате YYYY-MM-DD")
    created_at: Any = Field(None, description="Дата/время создания")
