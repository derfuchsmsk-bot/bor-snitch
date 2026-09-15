from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class UserDossier(BaseModel):
    user_id: str
    username: Optional[str] = None
    full_name: Optional[str] = None
    communication_style: str = Field(default="Обычный участник", description="Стиль общения (ироничный тролль, душнила, философ и т.д.)")
    friends_roasting: List[str] = Field(default_factory=list, description="Список username тех, с кем взаимный дружеский стеб (roasting)")
    weaknesses: List[str] = Field(default_factory=list, description="Слабости или темы для подколов")
    favorite_topics: List[str] = Field(default_factory=list, description="Любимые темы в чате")
    summary: str = Field(default="", description="Краткая характеристика персонажа")
    updated_at: Optional[datetime] = None
