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

    # Rules
    IGNORE_DAYS_BEFORE_PENALTY = 2
    
    # Random Cynical Comments
    CYNICAL_COMMENT_CHANCE = 0.02 # 2%
    CYNICAL_COMMENT_COOLDOWN_SECONDS = 3600 # 1 hour

    # Ranks
    RANK_NORMAL = (0, 49)
    RANK_SHNYR = (50, 249)
    RANK_GOAT = (250, 749)
    RANK_OFFENDED = (750, 1499)
    RANK_PIERCED = (1500, float('inf'))

    # Context
    REPORT_CONTEXT_LIMIT = 25

config = GameConfig()
