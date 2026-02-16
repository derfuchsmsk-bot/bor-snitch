import random
from datetime import datetime, timezone, timedelta
from ..utils.game_config import config
from ..services import db
from ..utils import messages
from ..utils.text import escape

class GameService:
    
    @staticmethod
    def calculate_rank(points: int) -> str:
        """Wrapper for rank calculation."""
        return db.calculate_rank(points)

    @staticmethod
    async def play_casino(user_id: int, chat_id: int) -> str:
        """
        Executes the casino logic for a user.
        Returns the result message text.
        """
        tz_moscow = timezone(timedelta(hours=config.TIMEZONE_OFFSET))
        now = datetime.now(tz_moscow)
        today_str = now.strftime("%Y-%m-%d")
        
        stats = await db.get_user_stats(chat_id, user_id)
        if stats and stats.get('last_gamble_date') == today_str:
            return messages.CASINO_ALREADY_PLAYED

        is_win = random.random() < config.GAMBLE_WIN_CHANCE
        current_points = stats.get('total_points', 0) if stats else 0
        
        if is_win:
            deduction = config.GAMBLE_WIN_POINTS
            new_points = max(0, current_points - deduction)
            text = messages.CASINO_WIN.format(deduction=deduction, new_points=new_points)
        else:
            penalty = config.GAMBLE_LOSS_POINTS
            new_points = current_points + penalty
            text = messages.CASINO_LOSS.format(penalty=penalty, new_points=new_points)
            
        await db.record_gamble_result(chat_id, user_id, new_points, today_str)
        return text

    @staticmethod
    async def get_stats_report(chat_id: int) -> str:
        """
        Generates the top snitches report.
        """
        stats_ref = db.db.collection("chats").document(str(chat_id)).collection("user_stats")
        current_season = db.get_current_season_id()
        
        docs = stats_ref.stream()
        stats_list = []
        
        async for doc in docs:
            data = doc.to_dict()
            if data.get('season_id') == current_season:
                stats_list.append(data)
                
        stats_list.sort(key=lambda x: int(x.get('total_points', 0)), reverse=True)
        top_stats = stats_list[:10]
        
        text = f"🏆 <b>Топ Снитчей (Сезон {current_season}):</b>\n\n"
        if not top_stats:
            text += "Пока пусто. Сезон только начался! 🍂"
        
        for i, data in enumerate(top_stats, 1):
            rank = escape(data.get('current_rank', 'Порядочный 😐'))
            points = data.get('total_points', 0)
            username = escape(data.get('username', 'Unknown'))
            if not username.startswith("@"):
                 username = f"@{username}"
            
            text += f"{i}. {username} — {points} очков\n"
            text += f"   🃏Масть: {rank}\n"
            
            achievements = data.get('achievements', [])
            if achievements:
                ach_list = []
                for ach in achievements:
                    if isinstance(ach, dict):
                        icon = ach.get('icon', '')
                        title = ach.get('title', '')
                        if title:
                            ach_list.append(f"{title}{icon}")
                    elif isinstance(ach, str):
                        ach_list.append(ach)
                if ach_list:
                    text += f"   🏅Ачивки: {', '.join(ach_list)}\n"
            text += "\n"
            
        return text

    @staticmethod
    async def get_user_status(chat_id: int, target_user) -> str:
        """
        Generates the status report for a specific user.
        target_user: User object (from aiogram)
        """
        stats = await db.get_user_stats(chat_id, target_user.id)
        current_season = db.get_current_season_id()
        
        achievements = []
        if stats:
            achievements = stats.get('achievements', [])
            if stats.get('season_id') != current_season:
                stats['total_points'] = 0
                stats['snitch_count'] = 0
                stats['current_rank'] = 'Порядочный 😐'

        if not stats:
            return f"👤 <b>{escape(target_user.full_name)}</b> без косяков. (0 очков)"

        rank = escape(stats.get('current_rank', 'Порядочный 😐'))
        points = stats.get('total_points', 0)
        
        display_name = escape(target_user.full_name)
        if target_user.username:
            display_name = f"@{target_user.username}"

        text = (
            f"👤 <b>Личное Дело:</b> {display_name}\n\n"
            f"🃏 <b>Масть:</b> {rank}\n"
            f"⚖️ <b>Очки:</b> {points}"
        )

        if achievements:
            text += "\n\n🏅 <b>Ачивки:</b>\n"
            for ach in achievements:
                if isinstance(ach, str):
                    text += f"• {escape(ach)}\n"
                elif isinstance(ach, dict):
                    icon = ach.get('icon', '🎖')
                    title = escape(ach.get('title', 'Unknown'))
                    description = escape(ach.get('description', ''))
                    text += f"{icon} <b>{title}</b>"
                    if description:
                        text += f" — <i>{description}</i>"
                    text += "\n"
        
        return text
