from src.services.prompt_service import PromptService

def get_all_prompts_info(cls):
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

PromptService.get_all_prompts_info = classmethod(get_all_prompts_info)
