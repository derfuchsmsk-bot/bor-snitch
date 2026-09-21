import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.utils.game_config import DEFAULT_CONFIG_VALUES
from src.services.prompt_service import PromptService

os.makedirs('src/config', exist_ok=True)

with open('src/config/defaults.json', 'w', encoding='utf-8') as f:
    json.dump(DEFAULT_CONFIG_VALUES, f, indent=4, ensure_ascii=False)

prompts = {}
cls_prompts = PromptService._default_prompts
for p_id, p_data in cls_prompts.items():
    prompts[p_id] = {
        "name": p_data["name"],
        "description": p_data["description"],
        "placeholders": p_data["placeholders"],
        "default": p_data["default"]
    }

with open('src/config/prompts.json', 'w', encoding='utf-8') as f:
    json.dump(prompts, f, indent=4, ensure_ascii=False)

print("Created JSON files in src/config/")
