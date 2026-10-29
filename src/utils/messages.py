from .game_config import config

# Rules reflect live settings from the CMS rather than import-time values.
def get_rules_text():
    afk = (f"{config.POINTS_AFK_BASE} очков после {config.IGNORE_DAYS_BEFORE_PENALTY} дней" if config.ENABLE_AFK_PENALTIES else "отключены")
    spontaneous = "включены" if config.ALLOW_SPONTANEOUS_PENALTIES else "отключены"
    report_penalty = "включены" if config.FALSE_REPORT_PENALTIES_ENABLED else "отключены"
    return (
        "📜 <b>Правила Снитча</b>\n\n"
        "Шутим над ситуациями, бережно относимся к людям. Усталость, молчание и изменение планов сами по себе не нарушения.\n\n"
        f"🔹 Оскорбления и агрессия: {config.POINTS_TOXICITY} игровых очков после проверки контекста.\n"
        f"🔹 Подтверждённые нарушения доверия: {config.POINTS_SNITCHING} очков.\n"
        "🔹 Для проверки конкретного сообщения — /report в ответ на него. При сомнениях бот не обвиняет.\n"
        f"🔹 Автоматические штрафы в диалоге: {spontaneous}.\n"
        f"🔹 Штрафы за молчание: {afk}.\n"
        f"🔹 Штрафы за отклонённые обращения: {report_penalty}.\n\n"
        "🎰 <b>Казино /casino:</b> одна попытка в сутки.\n"
        f"Победа: -{config.GAMBLE_WIN_POINTS} очков; проигрыш: +{config.GAMBLE_LOSS_POINTS} очков.\n\n"
        "🌿 Уровни 0–4 обозначают только диапазон игровых очков, а не характер человека. Чем меньше очков, тем лучше.\n"
        "🧹 По воскресеньям списывается половина очков, набранных за неделю.\n"
        "Если бот ошибся, попросите администратора проверить и отменить запись."
    )


RULES_TEXT = get_rules_text()

# Casino
CASINO_ALREADY_PLAYED = "Сегодня попытка уже была. Следующая — завтра 🎲"
CASINO_WIN = (
    "🎰 <b>ЗАНОС!</b>\n\n"
    "Тебе фартануло. Сняли {deduction} очков.\n"
    "Текущий счет: {new_points}"
)
CASINO_LOSS = (
    "🎰 <b>На этот раз без джекпота.</b>\n\n"
    "Результат попытки: +{penalty} игровых очков. Следующая попытка — завтра.\n"
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
    "📝 <b>Договорённость не выполнена.</b>\n\n"
    "{user}: «{text}». Похоже, выполнить не получилось.\n"
    "Если планы изменились или бот ошибся, уточните обстоятельства."
)

AGREEMENT_DISPUTE_SUCCESS = "🤝 <b>Договорённость отменена.</b>\n\nСпасибо за уточнение. Запись отменена."
AGREEMENT_DISPUTE_TOO_LATE = "❌ <b>Поздно.</b>\n\nОкно быстрого оспаривания закончилось. Если бот ошибся, попросите администратора отменить запись."
AGREEMENT_DISPUTE_NOT_FOUND = "❌ <b>Ошибка:</b> Договоренность не найдена или уже не в активном статусе."

# Amnesty
AMNESTY_MESSAGE = "🧹 <b>Еженедельная Амнистия!</b>\n\nСписана половина очков, набранных за эту неделю. Новая неделя — новый шанс 🌿"

# Misc
ALL_COMMAND_TITLE = "📣 <b>САЙОНАРА СБОР!</b>\n\n"
NO_USERS_TO_TAG = "В этом чате еще никто не отметился..."
REPORT_ANALYSIS_START = "🕵️‍♂️ <b>Анализ доноса...</b>"
REPORT_ALREADY_PROCESSED = "⚖️ <b>Вердикт уже вынесен!</b>\n\nПо данному сообщению решение уже принято ранее. Повторный донос отклонён без штрафа."
REPORT_TECH_ERROR = "⚠️ <b>Судебная ошибка:</b> Не удалось связаться с судейской коллегией ИИ. Донос не обработан, штраф не начислен."
REPORT_ACCEPTED = (
    "✅ <b>Донос принят!</b>\n\n"
    "📂 <b>Категория:</b> {category} (+{points} pts)\n"
    "📝 <b>Вердикт:</b> {reason}\n"
    "⚖️ <i>Очки начислены моментально.</i>"
)
REPORT_REJECTED = (
    "❌ <b>Отклонено.</b>\n\n"
    "Не вижу достаточных оснований для штрафа. Спасибо, что дали проверить контекст.\n"
    "<i>(Причина: {reason})</i>"
)
REPORT_PENALTY = (
    "\n\n📝 <b>По правилу повторных необоснованных обращений: +{penalty} очков.</b>\n"
    "<i>(Необоснованных обращений: {count})</i>"
)
