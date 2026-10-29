from src.utils.game_config import config


def calculate_rank(points: int) -> str:
    """Neutral score levels; legacy configuration keys retain their stored meaning."""
    if points >= config.RANK_PIERCED[0]:
        return "Уровень 4 🔄"
    if points >= config.RANK_OFFENDED[0]:
        return "Уровень 3 ☕"
    if points >= config.RANK_GOAT[0]:
        return "Уровень 2 🧭"
    if points >= config.RANK_SHNYR[0]:
        return "Уровень 1 📝"
    return "Уровень 0 🌿"
