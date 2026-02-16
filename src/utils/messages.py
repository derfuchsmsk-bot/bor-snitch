from .game_config import config

# Rules & Info
RULES_TEXT = (
    "📜 <b>Кодекс Снитча</b>\n\n"
    "За что начисляются очки (суммируются за день):\n"
    f"🔹 <b>Нытье</b> — {config.POINTS_WHINING} pts{' (Временно отключено)' if config.POINTS_WHINING == 0 else ''}\n"
    f"🔹 <b>Духота</b> — {config.POINTS_STIFFNESS} pts{' (Временно отключено)' if config.POINTS_STIFFNESS == 0 else ''}\n"
    f"🔹 <b>Токсичность</b> — {config.POINTS_TOXICITY} pts\n"
    f"🔹 <b>Снитчевание (Игнор/Предательство)</b> — {config.POINTS_SNITCHING} pts\n"
    f"🔹 <b>AFK (Молчанка)</b> — {config.POINTS_AFK_BASE}+ pts ({config.IGNORE_DAYS_BEFORE_PENALTY} дня тишины = {config.POINTS_AFK_BASE}, далее +{config.POINTS_AFK_DAILY} за день)\n"
    f"🔹 <b>Ложные доносы</b> — +{config.FALSE_REPORT_PENALTY} pts (за каждые {config.FALSE_REPORT_LIMIT} отклоненных репорта)\n\n"
    "🎰 <b>Казино (/casino):</b>\n"
    "Раз в сутки можно испытать удачу.\n"
    f"Победа: -{config.GAMBLE_WIN_POINTS} pts | Проигрыш: +{config.GAMBLE_LOSS_POINTS} pts\n\n"
    "⚠️ <b>Особые правила:</b>\n"
    "🤡 Реакция клоуна = Токсичность\n"
    "👻 Игнор тега = Духота или Токсичность\n"
    "🧹 <b>Еженедельная Амнистия:</b> Каждое воскресенье очки за неделю делятся на 2.\n\n"
    "👑 <b>Масти:</b>\n"
    f"▫️ {config.RANK_NORMAL[0]}-{config.RANK_NORMAL[1]}: Порядочный 😐\n"
    f"▫️ {config.RANK_SHNYR[0]}-{config.RANK_SHNYR[1]}: Шнырь 🧹\n"
    f"▫️ {config.RANK_GOAT[0]}-{config.RANK_GOAT[1]}: Козёл 🐐\n"
    f"▫️ {config.RANK_OFFENDED[0]}-{config.RANK_OFFENDED[1]}: Обиженный 🚽\n"
    f"▫️ {config.RANK_PIERCED[0]}+: Масть Проткнутая 👑"
)

# Casino
CASINO_ALREADY_PLAYED = "Ты уже лудил сегодня, додеп только завтра."
CASINO_WIN = (
    "🎰 <b>ЗАНОС!</b>\n\n"
    "Тебе фартануло. Сняли {deduction} очков.\n"
    "Текущий счет: {new_points}"
)
CASINO_LOSS = (
    "🎰 <b>АХХАХАХАХАХ ОСЁЛ ЕБАНЫЙ, А ДОДЕПНУТЬ НЕ ПОЛУЧИТСЯ АХАХАХАХХА!</b>\n\n"
    "Ты проиграл. +{penalty} очков.\n"
    "Текущий счет: {new_points}"
)

# Daily Results
DAILY_SUMMARY_TITLE = "✨ <b>ИТОГИ ДНЯ</b> ✨\n\n"
DAILY_OFFENDERS_TITLE = "🚨 <b>ИТОГИ ДНЯ</b> 🚨\n\n"
DAILY_NO_OFFENDERS = "Сегодня в чате царила гармония. Ни одного нарушения! 🕊️"
NEW_AGREEMENTS_TITLE = "\n🤝 <b>Базар зафиксирован! (Новые договоренности):</b>\n"

# Agreements (Word of the Boy)
AGREEMENT_CREATED_FOOTER = "\n<i>Не согласен? Жми /disput [номер] в течение {minutes} минут, или слово считается данным.</i>"

AGREEMENT_FULFILLED = (
    "✅ <b>Людское детектед.</b>\n\n"
    "{user} сдержал слово: «{text}».\n"
    "Респект от Снитч-бота. +1 к репутации (ментально)."
)

AGREEMENT_BROKEN = (
    "❌ <b>ФУФЛОМЕТ!</b> 📢\n\n"
    "{user} не вывез за базар. Обещал «{text}», но замастился.\n"
    "С этого момента ты официально — <b>Воздухан</b>."
)

AGREEMENT_DISPUTE_SUCCESS = "🤝 <b>Базар отменен.</b>\n\nСлово пацана отозвано, ошибка ИИ признана. Живи пока."
AGREEMENT_DISPUTE_TOO_LATE = "❌ <b>Поздно.</b>\n\n15 минут прошло, слово уже в силе. Нужно было раньше за базар пояснять."
AGREEMENT_DISPUTE_NOT_FOUND = "❌ <b>Ошибка:</b> Договоренность не найдена или уже не в активном статусе."

# Amnesty
AMNESTY_MESSAGE = "🧹 <b>Еженедельная Амнистия!</b>\n\nСписана половина очков, набранных за эту неделю. Живите пока."

# Misc
ALL_COMMAND_TITLE = "📣 <b>ВНИМАНИЕ ВСЕМ!</b>\n\n"
NO_USERS_TO_TAG = "В этом чате еще никто не отметился..."
REPORT_ANALYSIS_START = "🕵️‍♂️ <b>Анализ доноса...</b>"
REPORT_ACCEPTED = (
    "✅ <b>Донос принят!</b>\n\n"
    "📂 <b>Категория:</b> {category} (+{points} pts)\n"
    "📝 <b>Вердикт:</b> {reason}\n"
    "⚖️ <i>Очки начислены моментально.</i>"
)
REPORT_REJECTED = (
    "❌ <b>Отклонено.</b>\n\n"
    "Это не масть. Хватит спамить, ты уже ходишь под вопросом, клоун 🤡🤡🤡\n"
    "<i>(Причина: {reason})</i>"
)
REPORT_PENALTY = (
    "\n\n🚨 <b>Ты конкретный снитч: +{penalty} очков.</b>\n"
    "<i>(Ложных доносов подряд: {count})</i>"
)
