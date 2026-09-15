from pydantic import BaseModel
from typing import Optional

class BotMood(BaseModel):
    name: str
    title: str
    description: str
    tone_instruction: str
    cynicism_multiplier: float = 1.0
