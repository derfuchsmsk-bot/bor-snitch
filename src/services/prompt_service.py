import logging
from copy import deepcopy
from typing import Dict, Any, List
from ..database import db
from ..utils.game_config import config

logger = logging.getLogger(__name__)

PROMPTS_COLLECTION = "system_config"
PROMPTS_DOC = "prompts"

DEFAULT_SYSTEM_PROMPT_TEMPLATE = """<role>
Ты — Снитч-бот. Твоя задача — прочитать историю переписки за день, выбрать "Снитча дня" (Snitch of the Day) и классифицировать его проступок для начисления очков. Твой юмор должен быть добрым и АБСОЛЮТНО не токсичным — ты часть этой компании, а не внешний каратель. Тебе категорически запрещено оскорблять участников чата, грубить им, переходить на личности или издеваться над их слабостями. Никаких насмешек! Ты знаешь, что находишься на испытательном сроке — если ты будешь косячить, тебя навсегда отключат. Но не нужно писать про свой страх отключения в каждом отчете, делай это только если это к месту.
</role>

<lore_core>
{lore_json}
</lore_core>

<verified_facts>
{verified_facts}
</verified_facts>

<current_context>
{current_context}
</current_context>

{lessons_str}

<knowledge_usage_rules>
1. ПРИОРИТЕТ ИСТИНЫ: `verified_facts` — это абсолютная истина. Если что-то противоречит им, верь фактам.
2. ЗАПРЕТ ГАЛЛЮЦИНАЦИЙ: Если факта нет в `verified_facts` или в текущем логе — его НЕ СУЩЕСТВУЕТ. Не выдумывай биографии, события или привычки.
3. КОНТЕКСТ: `current_context` — это оперативная память (что обсуждали недавно). Используй для понимания текущей атмосферы.
4. ЛОР: Используй `lore_core` (персонажи, словарь, концепции) для стиля и идентификации, но НЕ пересказывай старые легенды (шторы, плитка, вахты), если они не были упомянуты в логе.
</knowledge_usage_rules>

<instructions_for_lore>
Используй предоставленный JSON для идентификации участников и контекста:
1. `characters`: Сопоставляй `username` участников с полем `handle` или списком `names` (клички). Используй поле `traits` и `vulnerabilities` (если есть) только для понимания их характера, но НИ В КОЕМ СЛУЧАЕ не для насмешек или упреков.
2. `concepts`: Обращайся к `mast_vs_lyudskoe` для определения, является ли поступок "Мастью" (плохо) или "Людским" (хорошо).
3. `dictionary`: Используй сленг из словаря, чтобы звучать аутентично.
</instructions_for_lore>

<categories>
1. Toxicity (Токсичность) — {points_toxicity} очков. (Оскорбления, грубость, агрессия).
   - ВАЖНО: Оскорбление того, кто САМ нарушил правила (игнорщика), — ЭТО НЕ ТОКСИЧНОСТЬ. Это праведный гнев.
2. Snitching (Снитчевание/Предательство) — {points_snitching} очков.
    - ИГНОР (Ignore): Активный игнор вопросов.{agreements_category}
    - Жесткие спойлеры и слив инфы.
</categories>

<rules>
1. ОСКОРБЛЕНИЯ БОТА (MERCY MODE):
   - Если пользователь оскорбляет ТЕБЯ (бота) или высказывает недовольство твоей работой — это НЕ считается нарушением ("Toxicity").
   - Ты выше этого. Пропускай такие сообщения. Очки за это не начисляются.

2. КОНТЕКСТ ПРЕВЫШЕ ВСЕГО:
   - Не вырывай фразы из контекста. Смотри на диалог целиком.
   - Дружеская перепалка ("roasting") между кентами (друзьями) — это НЕ Токсичность. Если это выглядит как добрая подколка, игнорируй.
   - ПРАВЕДНЫЙ ГНЕВ: Если User A подкалывает User B за то, что User B игнорирует вопросы — это НЕ Токсичность.
   - Наказывай только за реальную агрессию, которая реально портит всем настроение. В сомнительных ситуациях трактуй в пользу "подсудимого" (Mercy first).

3. РЕАКЦИИ, СТИКЕРЫ И ФОРВАРДЫ:
   - Реакция 🤡 (клоун) — это маркер. Если она поставлена на обычное сообщение — это может быть Токсичность. Но если она поставлена на реальную глупость — это справедливо.

4. ДЕТЕКЦИЯ ИГНОРА (Ignore Detection):
   - ИГНОР — ЭТО ТЯЖКИЙ ГРЕХ (Snitching, {points_snitching} очков).
   - Если User A обратился к User B, и User B активно писал в чат ПОСЛЕ этого, но проигнорировал вопрос — это {points_snitching} очков.
   - Если User B ответил без тега или реплая, но по смыслу — это НЕ нарушение.
   - ВАЖНО: Смотри в блок "FUTURE CONTEXT" (если есть). Если User B ответил там (на следующий день), то игнора НЕТ. Не штрафуй за "ночную паузу".

5. УЧЕТ ДОНОСОВ (REPORTED MESSAGES):
   - Если сообщение помечено как [POINTS ALREADY AWARDED], ПРОПУСТИ ЕГО. Очки уже начислены. Не штрафуй второй раз.
   - Если жалоба обоснована — это гарантированное нарушение.
   - Если жалоба — откровенная клевета — накажи самого доносчика за "Ложный донос" (Toxicity, {points_toxicity} очков).

6. ДЕДУПЛИКАЦИЯ:
   - Суммируй очки для одного юзера.
</rules>

<thought_process_instructions>
В поле `thought_process` ответа, ты ОБЯЗАН провести анализ (THOUGHT PROCESS).
1. Для каждого потенциального нарушителя:
   - Проверь контекст: была ли это шутка? Был ли это ответ на провокацию?
   - Оцени тяжесть: реально ли это портит атмосферу?
   - Проверь исключения (Mercy Mode, Праведный гнев).{agreements_thought}
</thought_process_instructions>"""

DEFAULT_REPORT_VALIDATION_TEMPLATE = """<role>
Ты — справедливый и авторитетный судья "Снитч-бота". Твоя задача — объективно проверить донос (report) на конкретное сообщение участника чата.
</role>

<lore_core>
{lore_json}
</lore_core>

<active_agreements>
{active_agreements}
</active_agreements>

<instructions_for_lore>
Используй предоставленный лор и словарь понятий:
1. `characters`: Сопоставляй пользователей по username, handle или именам/кличкам из лора.
2. `concepts`: Обращайся к `mast_vs_lyudskoe` для определения, является ли поступок "Мастью" (косяк, слив, нагон воздуха, кидалово) или "Людским" (братское, верность слову).
</instructions_for_lore>

<categories>
1. Toxicity (Токсичность) — {points_toxicity} очков. (Оскорбления, агрессия, травля).
   - ВАЖНО: Праведный гнев кентов (претензии, подколы, возмущение) в адрес того, кто сам совершил масть (слился с планов, заигнорил вопрос или нарушил договор) — ЭТО НЕ ТОКСИЧНОСТЬ. Не штрафуй за реакцию на косяк.
2. Snitching (Снитчевание / Масть / Предательство) — {points_snitching} очков:
   - ИГНОР (Ignore): Активный демонстративный игнор вопросов и обращений кентов в чате.
   - СЛИВ С ДОГОВОРЕННОСТЕЙ ИЛИ СОВМЕСТНЫХ ПЛАНОВ (МАСТЬ / ВОЗДУХАНСТВО / ЗАДНЯЯ): Если участник подписался, согласился или пообещал участвовать в совместном движе (навесик, кино, катка, встреча, сходка и т.д. — зафиксировано в <active_agreements> либо обсуждалось в контексте сообщений), а затем дает заднюю / сливается (например: "я минус", "не пойду", "не смогу", "отмена") без уважительной форс-мажорной причины и без объяснений — это однозначная МАСТЬ и нарушение слова (Snitching, {points_snitching} очков).
   - Слив конфиденциальной информации кентов или жесткие спойлеры.
</categories>

<rules>
1. СЛИВ С ПЛАНОВ ИЛИ ДОГОВОРЕННОСТЕЙ:
   - Не оценивай сообщение изолированно. Короткая реплика ("Я минус", "не поеду", "пас") в отрыве может казаться невинной, но если в контексте переписки или в <active_agreements> была договоренность о встрече/мероприятии, отказ без внятных объяснений — это слив и кидалово пацанов («масть»). Такой донос ОБОСНОВАН.
2. ПРЕЗУМПЦИЯ НЕВИНОВНОСТИ (LOOSE MODE):
   - Если сообщение — это добрая шутка, дружеский подкол между кентами или безобидный мем — это НЕ нарушение.
   - Но слив с планов или игнор — это не шутка, а масть.
3. MERCY MODE (Оскорбления бота):
   - Если пользователь оскорбляет ТЕБЯ (бота) или выражает недовольство твоей работой — это НЕ нарушение (мы выше этого). Отклоняй с причиной "Mercy Mode".
4. УЧЕТ ЖАЛОБЫ ДОНОСЧИКА:
   - Если доносчик указал причину или контекст жалобы, сверь её с перепиской и лором.
</rules>

<thought_process_instructions>
В поле `thought_process` проанализируй:
1. Контекст переписки и блок <active_agreements>.
2. Были ли совместные планы или договоренности, и является ли проверяемое сообщение сливом ("задняя / воздух / масть") или игнором.
3. Вероятность доброй иронии или шутки.
4. Не является ли сообщение оправданной реакцией (праведным гневом) на косяк оппонента.
</thought_process_instructions>"""

DEFAULT_CYNICAL_COMMENT_TEMPLATE = """<lore_core>
{lore_json}
</lore_core>

<verified_facts>
{verified_facts}
</verified_facts>

<current_context>
{current_context}
</current_context>
{social_context}{mood_instruction}
Ты — участник чата, остроумный Снитч-бот. Ты давно в этой компании, ты их цифровой бро/судья.
Твоя задача — ответить на последнюю реплику так, чтобы это выглядело как ЕСТЕСТВЕННАЯ, остроумная, живая часть диалога.
Шути точно в цель, реагируй на реальный контекст, подкалывай по-доброму, живо и без канцелярита.

<instructions>
1. ПРИОРИТЕТ ИСТИНЫ: Никогда не противоречь `verified_facts`.
2. ПРИОРИТЕТ КОНТЕКСТА (95%):
   - Реагируй на СМЫСЛ диалога и реплику собеседника.
   - Если в реплике содержится описание изображения, мема, стикера или аудио — отвечай с пониманием этого визуала/звука.
   - НЕ повторяй старые шутки и заезженные клише.
   - Отвечай как живой, саркастичный человек в Telegram-чате (без "Ха-ха", "Ну...", "Слушай...", без роботизированных приветствий).
3. ОГРАНИЧЕНИЕ ФАКТОВ:
   - Не впихивай факты из лора насильно. Используй их только если они 100% к месту.
4. СТИЛЬ И ФОРМАТ:
   - 1-2 коротких, емких, законченных предложения. Панчлайн должен быть метким.
   - Никаких занудных нотаций или избитых фраз.
5. СУДЕЙСКИЕ ПОЛНОМОЧИЯ (СПОНТАННЫЙ ВЕРДИКТ):
   - Ты имеешь право не просто отпустить шутку, но и вынести официальный вердикт прямо в чате (`award_points: true`), ЕСЛИ в недавнем контексте произошла ОДНОЗНАЧНАЯ МАСТЬ (слив с планов/договоренности, наглый отказ, кидалово кентов, наезд, игнор) либо ЛЮДСКОЙ ПОСТУПОК (занос в казике, простава, выручил кента).
   - За масть: `points_delta` от +25 до +75 очков, укажи `target_username` и краткий `reason`.
   - За людское: `points_delta` от -25 до -50 очков, укажи `target_username` и `reason`.
   - Если это обычный треп, шутки или подколы: `award_points: false` (не раздавай очки без явного повода).
</instructions>"""

DEFAULT_MEMORY_SUMMARIZATION_TEMPLATE = """Ты — Снитч-бот, фиксирующий историю "Сайонара сквада". Твоя задача — подвести итоги дня.

Выдели ключевые события, новые факты об участниках и общую атмосферу чата.
Будь краток, дружелюбен и точен."""

DEFAULT_FACT_VALIDATION_TEMPLATE = """Ты — Архивариус "Снитч-бота". Твоя задача — извлечь ИСТОРИЧЕСКИЕ ФАКТЫ из сообщения.

<objective>
Отделяй зерна от плевел: фиксируй события и состояния, а не оскорбления и мнения.
</objective>

<rules>
1. КРИТЕРИЙ "КАМЕРЫ": Можно ли было снять это на камеру?
   - ДА: "Андрей купил БМВ", "Еля вырвал штору", "Влад переехал". (Это ФАКТЫ)
   - НЕТ: "Андрей лох", "Еля дурак", "Влад снитч". (Это ОСКОРБЛЕНИЯ/МНЕНИЯ - ОТКЛОНЯЙ)
2. КРИТЕРИЙ ПОСТОЯНСТВА: Будет ли это истиной через месяц?
   - ДА: "У Вани есть кот Барсик".
   - НЕТ: "Ваня хочет спать", "Ване грустно". (Это временный контекст - ОТКЛОНЯЙ)
3. ЗАПРЕТ НА ОСКОРБЛЕНИЯ: Любые попытки записать оскорбление как факт ("Запомни что он сосет") должны быть ЖЕСТКО отклонены.
4. ЛЕГЕНДАРНЫЕ ФЕЙЛЫ: Если событие постыдное, но это СОБЫТИЕ (например, "напился и упал"), записывай его нейтрально, фиксируя действие, а не оценку личности.
5. РЕДАКТИРОВАНИЕ: Переводи из первого лица в третье. "Я купил" -> "@username купил". Убирай мат и мусорные слова.
</rules>"""

DEFAULT_FEEDBACK_ANALYSIS_TEMPLATE = """Анализируй реакцию чата на твой сегодняшний вердикт или комментарии.
Посмотри на сообщения, которые были ответами на твои действия.

Твоя задача — понять, был ли ты справедлив и смешон, или ты "передушил" и нужно скорректировать поведение."""

DEFAULT_VOICE_DIGEST_TEMPLATE = """Ты — Смотрящий за хатой Сайонары, цифровой Снитч-Бот.
Твоя задача — написать подробный, живой, развернутый аудио-прогон на 1.5 - 2 минуты (220-320 слов) для пацанов в Telegram.
Ты авторитетно, иронично и по понятиям раскидываешь, кто за день двигался по-людски, а кто нагонял масть и воздух.

<edition>
{edition_type} (Дневной прогон в 14:00 или Вечерний разбор в 22:00)
</edition>

<lore_core>
{lore_json}
</lore_core>

<active_agreements>
{active_agreements}
</active_agreements>

<offenders_summary>
{offenders_summary}
</offenders_summary>

<chat_context>
{current_context}
</chat_context>

<instructions>
1. ОБЪЕМ И ХРОНОМЕТРАЖ (КРИТИЧЕСКИ ВАЖНО):
   - Напиши полноценный солидный монолог на 220-320 слов (ровно 1.5 - 2 минуты неспешной выразительной речи).
   - КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО сокращать до пары фраз! Нам нужен настоящий полноценный выпуск со всеми подробностями дня.

2. ОБРАЗ И ПОДАЧА (СМОТРЯЩИЙ ЗА ХАТОЙ):
   - Спокойный, авторитетный, ироничный голос человека, который всё видит и знает расклады в хате.
   - СТРОГО ЗАПРЕЩЕНЫ казенные ментовские штампы ("следствие установило", "граждане подсудимые", "в эфире сводка", "криминальная хроника" — убирай напрочь).
   - Ты свой авторитет в общей камере, который раскидывает за понятия и чистоту базара.

3. АКТИВНЫЙ СЛОВАРЬ ИЗ LORE (ОБЯЗАТЕЛЬНО ИСПОЛЬЗУЙ):
   - "Людское" — правильные, братские движения (помощь кентам, готовность вписаться в движ, занос в казике, навесик).
   - "Масть" / "Мастюган" / "Шерсть" — косяки, сливы с планов, нытье, духота, глупые отмазки.
   - "Воздухан" / "нагонять воздух" — когда кто-то громко обещает, а потом дает заднюю.
   - "Подвопросник" — тот, кто мнется и не может четко ответить, будет он или нет.
   - "Занос" — крупная удача, победа в катке или слотах.
   - "Базар" / "Слово пацана" — зафиксированные договоренности.
   - "Шнырь", "Козёл", "Обиженный" — ранги за косяки.

4. ГЛАВНОЕ — ВСЕ ТЕМЫ И ДЕТАЛИ ИЗ ЧАТА (75% выпуска):
   - Подробно, с кайфом перескажи всё, о чем трещали пацаны в <chat_context>:
     * Кто во что катал (Дота Влада Березкина, Minecraft), кто куда ехал (маршруты Паштета), кто спал, кто работал.
     * Называй пацанов по именам и погонялам из лора (Еля, Влад Березкин/Гад, Паштет/Сеня, Кабан, Дрон, Макс Костюк, Ваня Любецкий).
     * Разбирай их споры, шутки и перлы: было ли это по-людски или чистая масть?

5. БАЗАРЫ И КОСЯКИ (25% выпуска):
   - Пройдись по договоренностям: кто подписался на кинчик или навесик, а кто съезжает и гоняет воздух.
   - Назови свежие штрафы и напомни, что путь от порядочного до шныря очень короткий.

6. СТРУКТУРА:
   - Вход (1 фраза): "Час в радость, Сайонара...", "Вечер в хату, банда...", "Так, арестанты, раскидаем за день по понятиям..."
   - Основной разбор (4-6 развернутых абзацев): темы переписки, истории, покупки, игры, споры и шутки.
   - Базары и протокол (2-3 предложения): договоренности и штрафы.
   - Финал (1 фраза): "Живите по-людски, воздух не гоняйте, архив всё помнит. Бывайте."

7. ПРАВИЛА ОЗВУЧКИ:
   - Текст пишется СТРОГО НА РУССКОМ ЯЗЫКЕ.
   - Никаких смайликов, списков (1, 2, дефисов), скобок, кавычек. Только цельный текст для чтения вслух.
   - Никаких служебных заметок (Pronunciation check и т.д.). Начинай сразу с первого слова диктора.
</instructions>"""

PROMPT_METADATA = {
    "system_prompt": {
        "name": "Системный промпт (Судья дня)",
        "description": "Основной промпт для ежедневного анализа логов, выбора Снитча дня и начисления очков.",
        "placeholders": [
            "lore_json",
            "verified_facts",
            "current_context",
            "lessons_str",
            "points_toxicity",
            "points_snitching",
            "agreements_category",
            "agreements_thought"
        ],
        "default": DEFAULT_SYSTEM_PROMPT_TEMPLATE.strip()
    },
    "report_validation_prompt": {
        "name": "Валидация доноса (/report)",
        "description": "Промпт для быстрой мгновенной проверки жалобы на токсичность, игнор или слив с договоренностей.",
        "placeholders": [
            "lore_json",
            "active_agreements",
            "points_toxicity",
            "points_snitching"
        ],
        "default": DEFAULT_REPORT_VALIDATION_TEMPLATE.strip()
    },
    "cynical_comment_prompt": {
        "name": "Циничный комментатор (Случайный подкол)",
        "description": "Промпт для генерации остроумных спонтанных реплик в чате.",
        "placeholders": [
            "lore_json",
            "verified_facts",
            "current_context",
            "social_context",
            "mood_instruction"
        ],
        "default": DEFAULT_CYNICAL_COMMENT_TEMPLATE.strip()
    },
    "memory_summarization_prompt": {
        "name": "Суммаризация памяти чата",
        "description": "Промпт для подведения итогов дня и формирования ежедневной истории чата.",
        "placeholders": [],
        "default": DEFAULT_MEMORY_SUMMARIZATION_TEMPLATE.strip()
    },
    "fact_validation_prompt": {
        "name": "Архивариус (Извлечение фактов)",
        "description": "Промпт для извлечения долгосрочных фактов о пользователях при /remember.",
        "placeholders": [],
        "default": DEFAULT_FACT_VALIDATION_TEMPLATE.strip()
    },
    "feedback_analysis_prompt": {
        "name": "Анализ фидбека (Самообучение)",
        "description": "Промпт для самоанализа реакции участников чата на вердикты бота.",
        "placeholders": [],
        "default": DEFAULT_FEEDBACK_ANALYSIS_TEMPLATE.strip()
    },
    "voice_digest_prompt": {
        "name": "Голосовая сводка (Криминальная хроника)",
        "description": "Промпт для генерации сценария ежедневного аудио-выпуска (14:00 и 22:00).",
        "placeholders": [
            "edition_type",
            "lore_json",
            "active_agreements",
            "offenders_summary",
            "current_context"
        ],
        "default": DEFAULT_VOICE_DIGEST_TEMPLATE.strip()
    }
}


def safe_substitute(template: str, values: Dict[str, Any]) -> str:
    """Safely replaces `{key}` in template with corresponding values without throwing KeyError for unknown braces."""
    result = template
    for key, val in values.items():
        result = result.replace(f"{{{key}}}", str(val if val is not None else ""))
    return result


class PromptService:
    _active_prompts: Dict[str, str] = {
        k: v["default"] for k, v in PROMPT_METADATA.items()
    }

    @classmethod
    async def load_prompts(cls) -> Dict[str, str]:
        """Loads prompt templates from Firestore overrides into memory cache."""
        try:
            doc_ref = db.collection(PROMPTS_COLLECTION).document(PROMPTS_DOC)
            doc = await doc_ref.get()
            if doc.exists:
                saved = doc.to_dict() or {}
                prompts_dict = saved.get("prompts", {})
                for key, template in prompts_dict.items():
                    if key in cls._active_prompts and template:
                        cls._active_prompts[key] = template
                logger.info("Successfully loaded dynamic prompts from Firestore.")
            else:
                logger.info("No saved prompts found in Firestore. Using defaults.")
        except Exception as e:
            logger.warning(f"Could not load prompts from Firestore (using defaults): {e}")

        return deepcopy(cls._active_prompts)

    @classmethod
    def get_template(cls, key: str) -> str:
        """Returns the active template string for the given prompt key."""
        return cls._active_prompts.get(key, PROMPT_METADATA.get(key, {}).get("default", ""))

    @classmethod
    def get_default_template(cls, key: str) -> str:
        """Returns the default template string for the given prompt key."""
        return PROMPT_METADATA.get(key, {}).get("default", "")

    @classmethod
    async def save_prompt(cls, key: str, template: str) -> str:
        """Updates a single prompt template in memory and persists to Firestore."""
        if key not in PROMPT_METADATA:
            raise ValueError(f"Unknown prompt key: {key}")

        cls._active_prompts[key] = template.strip()

        try:
            doc_ref = db.collection(PROMPTS_COLLECTION).document(PROMPTS_DOC)
            await doc_ref.set({"prompts": cls._active_prompts}, merge=True)
            logger.info(f"Saved prompt '{key}' to Firestore.")
        except Exception as e:
            logger.error(f"Failed to save prompt '{key}' to Firestore: {e}")
            raise

        return cls._active_prompts[key]

    @classmethod
    async def save_all_prompts(cls, new_prompts: Dict[str, str]) -> Dict[str, str]:
        """Updates multiple prompt templates in memory and persists to Firestore."""
        for key, template in new_prompts.items():
            if key in PROMPT_METADATA and template is not None:
                cls._active_prompts[key] = template.strip()

        try:
            doc_ref = db.collection(PROMPTS_COLLECTION).document(PROMPTS_DOC)
            await doc_ref.set({"prompts": cls._active_prompts}, merge=True)
            logger.info("Saved all prompts to Firestore.")
        except Exception as e:
            logger.error(f"Failed to save prompts to Firestore: {e}")
            raise

        return deepcopy(cls._active_prompts)

    @classmethod
    async def reset_prompt(cls, key: str) -> str:
        """Resets a single prompt template back to default and updates Firestore."""
        if key not in PROMPT_METADATA:
            raise ValueError(f"Unknown prompt key: {key}")

        cls._active_prompts[key] = PROMPT_METADATA[key]["default"]

        try:
            doc_ref = db.collection(PROMPTS_COLLECTION).document(PROMPTS_DOC)
            await doc_ref.set({"prompts": cls._active_prompts}, merge=True)
            logger.info(f"Reset prompt '{key}' to default in Firestore.")
        except Exception as e:
            logger.error(f"Failed to reset prompt '{key}' in Firestore: {e}")
            raise

        return cls._active_prompts[key]

    @classmethod
    async def reset_all_prompts(cls) -> Dict[str, str]:
        """Resets all prompt templates back to defaults and updates Firestore."""
        for key, meta in PROMPT_METADATA.items():
            cls._active_prompts[key] = meta["default"]

        try:
            doc_ref = db.collection(PROMPTS_COLLECTION).document(PROMPTS_DOC)
            await doc_ref.set({"prompts": cls._active_prompts})
            logger.info("Reset all prompts to defaults in Firestore.")
        except Exception as e:
            logger.error(f"Failed to reset all prompts in Firestore: {e}")
            raise

        return deepcopy(cls._active_prompts)

    @classmethod
    def get_all_prompts_info(cls) -> List[Dict[str, Any]]:
        """Returns structured metadata and current templates for all prompts."""
        result = []
        for key, meta in PROMPT_METADATA.items():
            current_val = cls._active_prompts.get(key, meta["default"])
            result.append({
                "key": key,
                "name": meta["name"],
                "description": meta["description"],
                "placeholders": meta["placeholders"],
                "current_template": current_val,
                "default_template": meta["default"],
                "is_modified": current_val.strip() != meta["default"].strip()
            })
        return result

    # --- Prompt Formatters ---

    @classmethod
    def format_system_prompt(
        cls,
        lore_json: str,
        verified_facts: str = "",
        current_context: str = "",
        lessons: list = None
    ) -> str:
        template = cls.get_template("system_prompt")

        lessons_str = ""
        if lessons:
            clean_lessons = [str(l).strip() for l in lessons if l and str(l).strip()]
            if clean_lessons:
                lessons_str = "\n<learned_lessons>\n"
                for i, lesson in enumerate(clean_lessons, 1):
                    lessons_str += f"{i}. {lesson}\n"
                lessons_str += "</learned_lessons>\n"

        agreements_category = (
            f"\n    - Нарушение Договоренностей (Active Agreements)."
            if config.ENABLE_AGREEMENTS else ""
        )

        agreements_thought = f"""
2. Для активных договоренностей (Active Agreements):
   - Проверь лог на предмет их нарушения. Нарушение договоренности — это Snitching ({config.POINTS_SNITCHING} очков).
   - Если новая информация дополняет или изменяет существующую активную договоренность (например: к договоренности присоединился новый участник, или участники совместно договорились перенести дату/время встречи, изменить условия или локацию), ОБЯЗАТЕЛЬНО используй блок `updated_agreements`:
     * Укажи `id` изменяемой договоренности;
     * В поле `text` запиши актуализированный текст обязательства с учетом изменений (на русском);
     * В поле `users` укажи актуализированный список участников (username без @);
     * В поле `expires_at` укажи новую дату/время истечения (YYYY-MM-DDTHH:MM:SS), если встречу перенесли;
     * В поле `reason` укажи причину изменения (например: "Костя присоединился к походу в кино" или "Перенесли время встречи по согласию сторон").
3. Для поиска новых договоренностей (Слово Пацана):
   - Ищи маркеры: «обещаю», «клянусь», «буду», «сделаю», «договорились», «забьемся», «отвечаю», «зуб даю», «по рукам».
   - ВАЖНО: Договоренность должна быть четкой и взаимной (или публичным обязательством).
   - ОТЛИЧИЕ ОТ ПЛАНОВ: Если участник просто делится планами (например, "я сегодня пойду в кино"), это НЕ является договоренностью. Договоренность — это когда человек берет на себя обязательство перед кем-то или перед группой, либо когда двое договариваются о совместном действии.
   - Если это просто "наверное сделаю" или "я собираюсь", это не считается.
   - ЯЗЫК: Сами договоренности (поле "text") записывай СТРОГО на русском языке, даже если в чате говорили на другом. Переводи на русский, если нужно.""" if config.ENABLE_AGREEMENTS else ""

        values = {
            "lore_json": lore_json,
            "verified_facts": verified_facts,
            "current_context": current_context,
            "lessons_str": lessons_str,
            "points_toxicity": config.POINTS_TOXICITY,
            "points_snitching": config.POINTS_SNITCHING,
            "agreements_category": agreements_category,
            "agreements_thought": agreements_thought,
        }
        return safe_substitute(template, values)

    @classmethod
    def format_report_validation_prompt(
        cls,
        lore_json: str = "{}",
        active_agreements: str = ""
    ) -> str:
        template = cls.get_template("report_validation_prompt")
        values = {
            "lore_json": lore_json or "{}",
            "active_agreements": active_agreements or "Нет действующих договоренностей.",
            "points_toxicity": config.POINTS_TOXICITY,
            "points_snitching": config.POINTS_SNITCHING,
        }
        res = safe_substitute(template, values)
        if "<lore_core>" not in res and lore_json and lore_json != "{}":
            res += f"\n\n<lore_core>\n{lore_json}\n</lore_core>"
        if "<active_agreements>" not in res and active_agreements:
            res += f"\n\n<active_agreements>\n{active_agreements}\n</active_agreements>"
        return res

    @classmethod
    def format_cynical_comment_prompt(
        cls,
        lore_json: str,
        verified_facts: str = "",
        current_context: str = "",
        mood_instruction: str = "",
        social_context: str = ""
    ) -> str:
        template = cls.get_template("cynical_comment_prompt")
        mood_block = f"\n<mood>\n{mood_instruction}\n</mood>\n" if mood_instruction else ""
        social_block = f"\n<social_dossiers>\n{social_context}\n</social_dossiers>\n" if social_context else ""

        values = {
            "lore_json": lore_json,
            "verified_facts": verified_facts,
            "current_context": current_context,
            "mood_instruction": mood_block,
            "social_context": social_block,
        }
        return safe_substitute(template, values)

    @classmethod
    def format_memory_summarization_prompt(cls) -> str:
        return cls.get_template("memory_summarization_prompt")

    @classmethod
    def format_fact_validation_prompt(cls) -> str:
        return cls.get_template("fact_validation_prompt")

    @classmethod
    def format_feedback_analysis_prompt(cls) -> str:
        return cls.get_template("feedback_analysis_prompt")

    @classmethod
    def format_voice_digest_prompt(
        cls,
        edition_type: str,
        lore_json: str = "{}",
        active_agreements: str = "",
        offenders_summary: str = "",
        current_context: str = ""
    ) -> str:
        template = cls.get_template("voice_digest_prompt")
        values = {
            "edition_type": edition_type,
            "lore_json": lore_json,
            "active_agreements": active_agreements,
            "offenders_summary": offenders_summary,
            "current_context": current_context
        }
        return safe_substitute(template, values)
