import json
import math
import os
from copy import deepcopy

CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "defaults.json")

def load_default_config():
    try:
        with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Failed to load defaults.json: {e}")
        return {}

DEFAULT_CONFIG_VALUES = load_default_config()

class GameConfig:
    def __init__(self):
        self.reset_to_defaults()

    def reset_to_defaults(self):
        """Resets all configuration values to their factory defaults."""
        for key, val in deepcopy(DEFAULT_CONFIG_VALUES).items():
            if key.startswith("RANK_"):
                second = float("inf") if val[1] is None else val[1]
                setattr(self, key, (val[0], second))
            else:
                setattr(self, key, val)

    def to_dict(self) -> dict:
        """Serializes current configuration to a JSON-safe dictionary."""
        result = {}
        for key, default_val in DEFAULT_CONFIG_VALUES.items():
            current_val = getattr(self, key, default_val)
            if key.startswith("RANK_") and isinstance(current_val, (tuple, list)):
                second = None if (math.isinf(current_val[1]) or current_val[1] is None) else int(current_val[1])
                result[key] = [int(current_val[0]), second]
            else:
                result[key] = current_val
        return result

    def update_from_dict(self, data: dict):
        """Updates configuration in-memory from dictionary with type coercion."""
        for key, val in data.items():
            if key not in DEFAULT_CONFIG_VALUES or val is None:
                continue

            default_val = DEFAULT_CONFIG_VALUES[key]

            if key == "REACTION_ALLOWED_EMOJIS":
                if isinstance(val, str):
                    emojis = [x.strip() for x in val.replace(",", " ").split() if x.strip()]
                    setattr(self, key, emojis if emojis else DEFAULT_CONFIG_VALUES["REACTION_ALLOWED_EMOJIS"])
                elif isinstance(val, list):
                    setattr(self, key, [str(x).strip() for x in val if str(x).strip()])
            elif key.startswith("RANK_") and isinstance(val, (list, tuple)) and len(val) >= 2:
                second = float("inf") if (val[1] is None or val[1] == "" or val[1] == "inf") else int(val[1])
                setattr(self, key, (int(val[0]), second))
            elif isinstance(default_val, bool):
                setattr(self, key, bool(val))
            elif isinstance(default_val, int):
                setattr(self, key, int(val))
            elif isinstance(default_val, float):
                setattr(self, key, float(val))
            elif isinstance(default_val, str):
                setattr(self, key, str(val).strip())
            else:
                setattr(self, key, val)

config = GameConfig()
