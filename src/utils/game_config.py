from dataclasses import dataclass

@dataclass
class GameConfig:
    # Points
    POINTS_WHINING = 10
    POINTS_STIFFNESS = 15
    POINTS_TOXICITY = 25
    POINTS_SNITCHING = 50
    POINTS_AFK_BASE = 50
    POINTS_AFK_DAILY = 50

    # Gambling
    GAMBLE_WIN_CHANCE = 0.49
    GAMBLE_WIN_POINTS = 50
    GAMBLE_LOSS_POINTS = 75

    # False Reports
    FALSE_REPORT_LIMIT = 3
    FALSE_REPORT_PENALTY = 25

    # Rules
    IGNORE_DAYS_BEFORE_PENALTY = 2
    
    # Random Cynical Comments
    CYNICAL_COMMENT_CHANCE = 0.005 # 0.5%
    CYNICAL_COMMENT_COOLDOWN_SECONDS = 1800 # 30 minutes

    # Ranks
    RANK_NORMAL = (0, 49)
    RANK_SHNYR = (50, 249)
    RANK_GOAT = (250, 749)
    RANK_OFFENDED = (750, 1499)
    RANK_PIERCED = (1500, float('inf'))

    # Context & Limits
    REPORT_CONTEXT_LIMIT = 25
    REPORT_NEXT_CONTEXT_LIMIT = 5
    MENTION_CHUNK_SIZE = 50
    
    # Time & Analysis
    TIMEZONE_OFFSET = 3 # Moscow Time (UTC+3)
    ANALYSIS_CUTOFF_HOUR = 4 # Hour to decide if analyzing yesterday or today

    # AI Models
    AI_MODEL_ANALYSIS = "gemini-3-flash-preview"
    AI_MODEL_MULTIMODAL = "gemini-3-pro-preview"

config = GameConfig()
