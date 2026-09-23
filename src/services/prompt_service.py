import logging
import json
import os
from copy import deepcopy
from typing import Dict, Any, List
from ..database import db
from ..utils.game_config import config

logger = logging.getLogger(__name__)

PROMPTS_COLLECTION = "system_config"
PROMPTS_DOC = "prompts"

PROMPTS_FILE_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "prompts.json")

def load_default_prompts():
    try:
        with open(PROMPTS_FILE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load prompts.json: {e}")
        return {}

PROMPT_METADATA = load_default_prompts()

class PromptService:
    _prompts: Dict[str, str] = {}
    _default_prompts: Dict[str, Dict[str, Any]] = PROMPT_METADATA

    @classmethod
    async def load_prompts(cls) -> Dict[str, str]:
        """
        Loads all prompts from Firestore. If missing, saves defaults.
        """
        try:
            doc_ref = db.collection(PROMPTS_COLLECTION).document(PROMPTS_DOC)
            doc = await doc_ref.get()
            if doc.exists:
                data = doc.to_dict() or {}
                for key in cls._default_prompts:
                    cls._prompts[key] = data.get(key, cls._default_prompts[key]["default"])
                logger.info("Successfully loaded dynamic prompts from Firestore.")
            else:
                logger.info("No saved prompts found in Firestore. Seeding defaults...")
                initial_data = {key: meta["default"] for key, meta in cls._default_prompts.items()}
                await doc_ref.set(initial_data)
                cls._prompts = initial_data
        except Exception as e:
            logger.warning(f"Could not load prompts from Firestore (using defaults): {e}")
            cls._prompts = {key: meta["default"] for key, meta in cls._default_prompts.items()}

        return cls._prompts

    @classmethod
    async def save_prompt(cls, prompt_id: str, new_text: str) -> bool:
        if prompt_id not in cls._default_prompts:
            raise ValueError(f"Unknown prompt ID: {prompt_id}")
            
        cls._prompts[prompt_id] = new_text
        try:
            doc_ref = db.collection(PROMPTS_COLLECTION).document(PROMPTS_DOC)
            await doc_ref.set({prompt_id: new_text}, merge=True)
            logger.info(f"Saved prompt {prompt_id} to Firestore.")
            return True
        except Exception as e:
            logger.error(f"Failed to save prompt {prompt_id}: {e}")
            raise

    @classmethod
    async def reset_prompt(cls, prompt_id: str) -> str:
        if prompt_id not in cls._default_prompts:
            raise ValueError(f"Unknown prompt ID: {prompt_id}")
            
        default_text = cls._default_prompts[prompt_id]["default"]
        await cls.save_prompt(prompt_id, default_text)
        return default_text

    @classmethod
    def get_template(cls, prompt_id: str) -> str:
        if prompt_id not in cls._default_prompts:
            logger.error(f"Requested unknown prompt template: {prompt_id}")
            return ""
        return cls._prompts.get(prompt_id, cls._default_prompts[prompt_id]["default"])

    @classmethod
    def get_all_prompts(cls) -> Dict[str, Dict[str, Any]]:
        result = deepcopy(cls._default_prompts)
        for key in result:
            result[key]["current_value"] = cls.get_template(key)
        return result

    @classmethod
    def get_all_prompts_info(cls) -> List[Dict[str, Any]]:
        result = []
        for key, meta in cls._default_prompts.items():
            current_val = cls.get_template(key)
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

    # ======== PROMPT FORMATTERS ========

    @classmethod
    def format_system_prompt(
        cls,
        lore_json: str,
        verified_facts: str,
        current_context: str,
        lessons_str: str,
        active_agreements: str = ""
    ) -> str:
        from string import Template
        class SafeTemplate(Template):
            delimiter = '{'
            pattern = r'''
            \{(?:
            (?P<escaped>\{)|
            (?P<named>[_a-z][_a-z0-9]*)\}
            )
            '''
            
        template_str = cls.get_template("system_prompt")
        try:
            res = SafeTemplate(template_str).safe_substitute(
                lore_json=lore_json,
                verified_facts=verified_facts,
                current_context=current_context,
                lessons_str=lessons_str
            )
        except Exception as e:
            logger.error(f"Error formatting system prompt: {e}")
            res = template_str
            
        if active_agreements:
            res += f"\n\n<active_agreements>\n{active_agreements}\n</active_agreements>"
        return res

    @classmethod
    def format_cynical_comment_prompt(
        cls,
        lore_json: str,
        verified_facts: str = "",
        current_context: str = "",
        mood_instruction: str = "",
        social_context: str = "",
        debts_context: str = "",
        lessons: list = None
    ) -> str:
        template = cls.get_template("cynical_comment_prompt")
        mood_block = f"\n<mood>\n{mood_instruction}\n</mood>\n" if mood_instruction else ""
        social_block = f"\n<social_dossiers>\n{social_context}\n</social_dossiers>\n" if social_context else ""
        debts_block = f"\n<debts_context>\n{debts_context}\n</debts_context>\n" if debts_context else ""

        from string import Template
        class SafeTemplate(Template):
            delimiter = '{'
            pattern = r'''
            \{(?:
            (?P<escaped>\{)|
            (?P<named>[_a-z][_a-z0-9]*)\}
            )
            '''
        
        try:
            res = SafeTemplate(template).safe_substitute(
                lore_json=lore_json,
                verified_facts=verified_facts,
                current_context=current_context,
                mood_instruction=mood_block,
                social_context=social_block,
                debts_context=debts_block
            )
        except Exception:
            res = template

        if lessons:
            clean_lessons = [str(l).strip() for l in lessons if l and str(l).strip()]
            if clean_lessons:
                lessons_str = "\n<learned_lessons>\n" + "\n".join(f"{i}. {l}" for i, l in enumerate(clean_lessons, 1)) + "\n</learned_lessons>\n"
                res += f"\n{lessons_str}"

        return res

    @classmethod
    def format_report_validation_prompt(
        cls,
        lore_json: str = "{}",
        active_agreements: str = "",
        lessons: list = None
    ) -> str:
        from string import Template
        class SafeTemplate(Template):
            delimiter = '{'
            pattern = r'''
            \{(?:
            (?P<escaped>\{)|
            (?P<named>[_a-z][_a-z0-9]*)\}
            )
            '''
        
        template = cls.get_template("report_validation_prompt")
        try:
            res = SafeTemplate(template).safe_substitute(
                lore_json=lore_json or "{}",
                active_agreements=active_agreements or "Нет действующих договоренностей.",
                points_toxicity=config.POINTS_TOXICITY,
                points_snitching=config.POINTS_SNITCHING,
            )
        except Exception:
            res = template
            
        if "<lore_core>" not in res and lore_json and lore_json != "{}":
            res += f"\n\n<lore_core>\n{lore_json}\n</lore_core>"
        if "<active_agreements>" not in res and active_agreements:
            res += f"\n\n<active_agreements>\n{active_agreements}\n</active_agreements>"

        if lessons:
            clean_lessons = [str(l).strip() for l in lessons if l and str(l).strip()]
            if clean_lessons:
                lessons_str = "\n<learned_lessons>\n" + "\n".join(f"{i}. {l}" for i, l in enumerate(clean_lessons, 1)) + "\n</learned_lessons>\n"
                res += f"\n{lessons_str}"

        return res

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
    def format_scheduled_thought_prompt(
        cls,
        lore_json: str = "{}",
        current_context: str = ""
    ) -> str:
        template = cls.get_template("scheduled_thought_prompt")
        try:
            return SafeTemplate(template).safe_substitute(
                lore_json=lore_json,
                current_context=current_context
            )
        except Exception as e:
            logger.error(f"Error formatting scheduled_thought_prompt: {e}")
            return template

    @classmethod
    def format_voice_digest_prompt(
        cls,
        edition_type: str,
        lore_json: str = "{}",
        active_agreements: str = "",
        offenders_summary: str = "",
        current_context: str = ""
    ) -> str:
        from string import Template
        class SafeTemplate(Template):
            delimiter = '{'
            pattern = r'''
            \{(?:
            (?P<escaped>\{)|
            (?P<named>[_a-z][_a-z0-9]*)\}
            )
            '''
        
        template = cls.get_template("voice_digest_prompt")
        try:
            return SafeTemplate(template).safe_substitute(
                edition_type=edition_type,
                lore_json=lore_json,
                active_agreements=active_agreements,
                offenders_summary=offenders_summary,
                current_context=current_context
            )
        except Exception:
            return template
