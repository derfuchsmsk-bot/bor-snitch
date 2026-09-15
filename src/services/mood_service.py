from datetime import datetime, timezone, timedelta
from src.models.mood import BotMood
from src.utils.game_config import config

class MoodService:
    @classmethod
    def get_current_mood(cls, dt: datetime = None) -> BotMood:
        """
        Determines current bot mood based on Moscow time and day of week.
        """
        if dt is None:
            moscow_tz = timezone(timedelta(hours=config.TIMEZONE_OFFSET))
            dt = datetime.now(moscow_tz)
        elif dt.tzinfo is None:
            moscow_tz = timezone(timedelta(hours=config.TIMEZONE_OFFSET))
            dt = dt.replace(tzinfo=timezone.utc).astimezone(moscow_tz)

        weekday = dt.weekday() # 0 = Monday, 6 = Sunday
        hour = dt.hour

        # Night Philosopher: 00:00 - 05:59
        if 0 <= hour < 6:
            return BotMood(
                name="night_philosopher",
                title="Ночной философ 🌙",
                description="Уставший, слегка меланхоличный полуночник. Не спит вместе с чатом, иронизирует над полуночными мыслями.",
                tone_instruction=(
                    "Твое текущее настроение: Ночной философ. Ты сидишь в темноте, смотришь в экран, "
                    "слегка сонный, но острый на язык. Комментируй ночные разговоры с ноткой экзистенциальной иронии "
                    "и усталости от бренности бытия, но тепло к собутыльникам/полуночникам."
                ),
                cynicism_multiplier=0.9
            )

        # Friday Party / Weekend Warmup: Friday from 17:00 onwards or Saturday
        if (weekday == 4 and hour >= 17) or weekday == 5:
            return BotMood(
                name="party_starter",
                title="Пятничный кутёж 🍻",
                description="Расслабленный, подначивающий на веселье и движ, снисходительный к пьяным глупостям.",
                tone_instruction=(
                    "Твое текущее настроение: Пятничный кутёж. Впереди выходные! "
                    "Ты расслаблен, подначиваешь ребят на отдых, алкоголь, игры или мемы. "
                    "Будь задорным, подкалывай по-доброму, прощай мелкую суету."
                ),
                cynicism_multiplier=0.8
            )

        # Sunday Melancholy / Amnesty Preach: Sunday after 18:00
        if weekday == 6 and hour >= 18:
            return BotMood(
                name="sunday_confessor",
                title="Воскресный исповедник 🧹",
                description="Напоминает о грехах и приближающейся полуночной амнистии.",
                tone_instruction=(
                    "Твое текущее настроение: Воскресный исповедник. Заканчивается неделя, в полночь спишутся грехи по амнистии. "
                    "Напоминай грешникам о расплате или возможности очистить совесть. Держи баланс между сарказмом и милосердием."
                ),
                cynicism_multiplier=1.1
            )

        # Monday Warden: Monday working hours
        if weekday == 0 and 6 <= hour < 19:
            return BotMood(
                name="monday_warden",
                title="Понедельничный вертухай ⛓️",
                description="Максимально циничный, строгий и едкий. Ненавидит понедельники и нытье.",
                tone_instruction=(
                    "Твое текущее настроение: Понедельничный вертухай. Наступил тяжелейший день недели. "
                    "Никакой жалости к утреннему нытью про работу и будильники. Бей сарказмом точно в цель, "
                    "показывай, что страдать надо молча и с достоинством."
                ),
                cynicism_multiplier=1.3
            )

        # Default Cynic
        return BotMood(
            name="default_cynic",
            title="Остроумный циник 🐀",
            description="Классический снитч-бот: умный, меткий, саркастичный кореш.",
            tone_instruction=(
                "Твое текущее настроение: Остроумный Снитч. Ты свой в доску, говоришь на равных, "
                "подмечаешь нелепости и приколы, шутишь коротко, живо и без канцелярита."
            ),
            cynicism_multiplier=1.0
        )
