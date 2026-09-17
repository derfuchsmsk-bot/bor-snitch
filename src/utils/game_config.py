from copy import deepcopy
import math

DEFAULT_CONFIG_VALUES = {
    # Global Bot State
    "BOT_DISABLED": False,
    "ACCOUNTING_EPOCH_DATE": "2026-09-15",

    # Points
    "POINTS_WHINING": 0,
    "POINTS_STIFFNESS": 0,
    "POINTS_TOXICITY": 25,
    "POINTS_SNITCHING": 50,
    "POINTS_AFK_BASE": 50,
    "POINTS_AFK_DAILY": 50,

    # Gambling
    "GAMBLE_WIN_CHANCE": 0.50,
    "GAMBLE_WIN_POINTS": 50,
    "GAMBLE_LOSS_POINTS": 60,

    # False Reports
    "FALSE_REPORT_LIMIT": 3,
    "FALSE_REPORT_PENALTY": 15,

    # Rules
    "IGNORE_DAYS_BEFORE_PENALTY": 2,

    # Random Cynical Comments
    "CYNICAL_COMMENT_CHANCE": 0.002,
    "CYNICAL_COMMENT_COOLDOWN_SECONDS": 180,

    # Automatic Emoji Reactions
    "REACTIONS_ENABLED": True,
    "REACTION_CHANCE": 0.02,
    "REACTION_COOLDOWN_SECONDS": 120,
    "REACTION_ALLOWED_EMOJIS": ["🤡", "🗿", "🚽", "👑", "🍿", "👀", "🔥", "👌"],

    # Voice Digest (Daily audio reports via ElevenLabs or Google TTS)
    "VOICE_DIGEST_ENABLED": True,
    "VOICE_DIGEST_TIME_1": "14:00",
    "VOICE_DIGEST_TIME_2": "22:00",
    "TTS_PROVIDER": "elevenlabs",
    "ELEVENLABS_VOICE_ID": "6A9D8WSMm4rFsg2DWFeE", # Egor Gadzhiyev (fallback to Adam if free plan)
    "ELEVENLABS_MODEL_ID": "eleven_multilingual_v2",
    "ELEVENLABS_STABILITY": 0.45,
    "ELEVENLABS_SIMILARITY_BOOST": 0.85,
    "VOICE_DIGEST_VOICE": "ru-RU-Wavenet-D",
    "VOICE_DIGEST_PITCH": -1.5,
    "VOICE_DIGEST_SPEED": 1.05,

    # Live Voice Chat (Kizaru persona in group calls)
    "VOICE_CHAT_ENABLED": True,
    "VOICE_CHAT_INACTIVITY_TIMEOUT_SECONDS": 60,

    # Ranks (serialized as lists, second value None = inf)
    "RANK_NORMAL": [0, 49],
    "RANK_SHNYR": [50, 249],
    "RANK_GOAT": [250, 499],
    "RANK_OFFENDED": [500, 999],
    "RANK_PIERCED": [1000, None],

    # Context & Limits
    "REPORT_CONTEXT_LIMIT": 25,
    "REPORT_NEXT_CONTEXT_LIMIT": 5,
    "MENTION_CHUNK_SIZE": 50,

    # Agreements
    "ENABLE_AGREEMENTS": False,
    "AGREEMENT_DISPUTE_WINDOW_MINUTES": 15,
    "AGREEMENT_DEFAULT_LIFESPAN_HOURS": 24,

    # Time & Analysis
    "TIMEZONE_OFFSET": 3,
    "ANALYSIS_CUTOFF_HOUR": 4,

    # AI Models
    "AI_MODEL_ANALYSIS": "gemini-3.8-flash",
    "AI_MODEL_MULTIMODAL": "gemini-3.8-flash",
}


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
