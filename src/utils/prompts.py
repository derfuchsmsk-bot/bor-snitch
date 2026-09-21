from ..services.prompt_service import PromptService
from .game_config import config

# Backwards compatibility functions and proxies:
def get_system_prompt(lore_json: str, verified_facts: str = "", current_context: str = "", lessons: list = None, active_agreements: str = "") -> str:
    lessons_str = ""
    if lessons:
        clean_lessons = [str(l).strip() for l in lessons if l and str(l).strip()]
        if clean_lessons:
            lessons_str = "\n<learned_lessons>\n"
            for i, lesson in enumerate(clean_lessons, 1):
                lessons_str += f"{i}. {lesson}\n"
            lessons_str += "</learned_lessons>\n"

    return PromptService.format_system_prompt(
        lore_json=lore_json,
        verified_facts=verified_facts,
        current_context=current_context,
        lessons_str=lessons_str,
        active_agreements=active_agreements
    )

def get_report_validation_prompt(lore_json: str = "{}", active_agreements: str = "", lessons: list = None) -> str:
    return PromptService.format_report_validation_prompt(lore_json=lore_json, active_agreements=active_agreements, lessons=lessons)

def get_cynical_comment_prompt(
    lore_json: str,
    verified_facts: str = "",
    current_context: str = "",
    mood_instruction: str = "",
    social_context: str = "",
    debts_context: str = "",
    lessons: list = None
) -> str:
    return PromptService.format_cynical_comment_prompt(
        lore_json=lore_json,
        verified_facts=verified_facts,
        current_context=current_context,
        mood_instruction=mood_instruction,
        social_context=social_context,
        debts_context=debts_context,
        lessons=lessons
    )

def get_memory_summarization_prompt() -> str:
    return PromptService.format_memory_summarization_prompt()

def get_fact_validation_prompt() -> str:
    return PromptService.format_fact_validation_prompt()

def get_feedback_analysis_prompt() -> str:
    return PromptService.format_feedback_analysis_prompt()

def get_voice_digest_prompt(
    edition_type: str,
    lore_json: str = "{}",
    active_agreements: str = "",
    offenders_summary: str = "",
    current_context: str = ""
) -> str:
    return PromptService.format_voice_digest_prompt(
        edition_type=edition_type,
        lore_json=lore_json,
        active_agreements=active_agreements,
        offenders_summary=offenders_summary,
        current_context=current_context
    )


class _DynamicPromptProxy:
    """A proxy string that fetches the latest prompt from PromptService dynamically."""
    def __init__(self, key: str):
        self._key = key

    def __str__(self) -> str:
        return PromptService.get_template(self._key)

    def __repr__(self) -> str:
        return str(self)

    def __add__(self, other):
        return str(self) + str(other)

    def __radd__(self, other):
        return str(other) + str(self)


# String constants that resolve dynamically when converted to str:
MEMORY_SUMMARIZATION_PROMPT = _DynamicPromptProxy("memory_summarization_prompt")
FACT_VALIDATION_PROMPT = _DynamicPromptProxy("fact_validation_prompt")
FEEDBACK_ANALYSIS_PROMPT = _DynamicPromptProxy("feedback_analysis_prompt")
VOICE_DIGEST_PROMPT = _DynamicPromptProxy("voice_digest_prompt")
