from dataclasses import dataclass

@dataclass
class GameConfig:
    # Points
    POINTS_WHINING = 0
    POINTS_STIFFNESS = 0
    POINTS_TOXICITY = 25
    POINTS_SNITCHING = 50
    POINTS_AFK_BASE = 50
    POINTS_AFK_DAILY = 50

    # Gambling
    GAMBLE_WIN_CHANCE = 0.50
    GAMBLE_WIN_POINTS = 50
    GAMBLE_LOSS_POINTS = 60

    # False Reports
    FALSE_REPORT_LIMIT = 3
    FALSE_REPORT_PENALTY = 15

    # Rules
    IGNORE_DAYS_BEFORE_PENALTY = 2
    
    # Random Cynical Comments
    CYNICAL_COMMENT_CHANCE = 0.002 # 
    CYNICAL_COMMENT_COOLDOWN_SECONDS = 180 # 3 minutes

    # Ranks
    RANK_NORMAL = (0, 49)
    RANK_SHNYR = (50, 249)
    RANK_GOAT = (250, 499)
    RANK_OFFENDED = (500, 999)
    RANK_PIERCED = (1000, float('inf'))

    # Context & Limits
    REPORT_CONTEXT_LIMIT = 25
    REPORT_NEXT_CONTEXT_LIMIT = 5
    MENTION_CHUNK_SIZE = 50
    
    # Agreements
    ENABLE_AGREEMENTS = False
    AGREEMENT_DISPUTE_WINDOW_MINUTES = 15
    AGREEMENT_DEFAULT_LIFESPAN_HOURS = 24

    # Time & Analysis
    TIMEZONE_OFFSET = 3 # Moscow Time (UTC+3)
    ANALYSIS_CUTOFF_HOUR = 4 # Hour to decide if analyzing yesterday or today

    # AI Models
    AI_MODEL_ANALYSIS = "gemini-3-flash-preview"
    AI_MODEL_MULTIMODAL = "gemini-3-pro-preview"

config = GameConfig()
