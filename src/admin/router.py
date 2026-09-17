import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Request, Response, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.utils.config import settings
from src.utils.game_config import config, DEFAULT_CONFIG_VALUES
from src.utils.limiter import limiter
from src.services.config_service import ConfigService
from src.services.prompt_service import PromptService, PROMPT_METADATA
from src.services.lore_service import LoreService
from src.services.fact_service import FactService
from src.repositories.user_repository import user_repository
from src.repositories.fact_repository import fact_repository
from src.repositories.agreement_repository import agreement_repository
from src.repositories.lesson_repository import lesson_repository
from src.services.learning import LearningService
from src.services.db import db, apply_weekly_amnesty
from google.cloud import firestore
from .auth import (
    COOKIE_NAME,
    TOKEN_EXPIRATION_SECONDS,
    verify_admin_password,
    create_admin_token,
    get_current_admin,
    get_current_admin_optional
)
from .ui import get_admin_html
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["Admin CMS"])

# --- UI Serving Endpoints ---

@router.get("/admin", response_class=HTMLResponse)
@router.get("/admin/login", response_class=HTMLResponse)
async def serve_admin_panel(request: Request):
    """Serves the single-page admin dashboard application."""
    return HTMLResponse(content=get_admin_html(), status_code=200)

# --- Request/Response Models ---

class LoginRequest(BaseModel):
    password: str

class ConfigUpdateRequest(BaseModel):
    BOT_DISABLED: Optional[bool] = None
    ACCOUNTING_EPOCH_DATE: Optional[str] = None
    POINTS_WHINING: Optional[int] = Field(None, ge=0, le=1000)
    POINTS_STIFFNESS: Optional[int] = Field(None, ge=0, le=1000)
    POINTS_TOXICITY: Optional[int] = Field(None, ge=0, le=1000)
    POINTS_SNITCHING: Optional[int] = Field(None, ge=0, le=1000)
    POINTS_AFK_BASE: Optional[int] = Field(None, ge=0, le=1000)
    POINTS_AFK_DAILY: Optional[int] = Field(None, ge=0, le=1000)
    GAMBLE_WIN_CHANCE: Optional[float] = Field(None, ge=0.0, le=1.0)
    GAMBLE_WIN_POINTS: Optional[int] = Field(None, ge=0, le=1000)
    GAMBLE_LOSS_POINTS: Optional[int] = Field(None, ge=0, le=1000)
    FALSE_REPORT_LIMIT: Optional[int] = Field(None, ge=1, le=100)
    FALSE_REPORT_PENALTY: Optional[int] = Field(None, ge=0, le=1000)
    IGNORE_DAYS_BEFORE_PENALTY: Optional[int] = Field(None, ge=1, le=30)
    CYNICAL_COMMENT_CHANCE: Optional[float] = Field(None, ge=0.0, le=1.0)
    CYNICAL_COMMENT_COOLDOWN_SECONDS: Optional[int] = Field(None, ge=0, le=86400)
    REACTIONS_ENABLED: Optional[bool] = None
    REACTION_CHANCE: Optional[float] = Field(None, ge=0.0, le=1.0)
    REACTION_COOLDOWN_SECONDS: Optional[int] = Field(None, ge=0, le=86400)
    REACTION_ALLOWED_EMOJIS: Optional[List[str]] = None
    VOICE_DIGEST_ENABLED: Optional[bool] = None
    VOICE_DIGEST_TIME_1: Optional[str] = None
    VOICE_DIGEST_TIME_2: Optional[str] = None
    TTS_PROVIDER: Optional[str] = None
    ELEVENLABS_VOICE_ID: Optional[str] = None
    ELEVENLABS_MODEL_ID: Optional[str] = None
    ELEVENLABS_STABILITY: Optional[float] = Field(None, ge=0.0, le=1.0)
    ELEVENLABS_SIMILARITY_BOOST: Optional[float] = Field(None, ge=0.0, le=1.0)
    VOICE_DIGEST_VOICE: Optional[str] = None
    VOICE_DIGEST_PITCH: Optional[float] = Field(None, ge=-20.0, le=20.0)
    VOICE_DIGEST_SPEED: Optional[float] = Field(None, ge=0.25, le=4.0)
    GOOGLE_TTS_MODEL: Optional[str] = None
    GOOGLE_TTS_VOICE: Optional[str] = None
    GOOGLE_TTS_STYLE: Optional[str] = None
    RANK_NORMAL: Optional[List[Optional[int]]] = None
    RANK_SHNYR: Optional[List[Optional[int]]] = None
    RANK_GOAT: Optional[List[Optional[int]]] = None
    RANK_OFFENDED: Optional[List[Optional[int]]] = None
    RANK_PIERCED: Optional[List[Optional[int]]] = None
    REPORT_CONTEXT_LIMIT: Optional[int] = Field(None, ge=1, le=200)
    REPORT_NEXT_CONTEXT_LIMIT: Optional[int] = Field(None, ge=0, le=50)
    MENTION_CHUNK_SIZE: Optional[int] = Field(None, ge=1, le=200)
    ENABLE_AGREEMENTS: Optional[bool] = None
    AGREEMENT_DISPUTE_WINDOW_MINUTES: Optional[int] = Field(None, ge=1, le=1440)
    AGREEMENT_DEFAULT_LIFESPAN_HOURS: Optional[int] = Field(None, ge=1, le=8760)
    TIMEZONE_OFFSET: Optional[int] = Field(None, ge=-12, le=14)
    ANALYSIS_CUTOFF_HOUR: Optional[int] = Field(None, ge=0, le=23)
    AI_MODEL_ANALYSIS: Optional[str] = None
    AI_MODEL_MULTIMODAL: Optional[str] = None

class PromptUpdateRequest(BaseModel):
    template: str

class AllPromptsUpdateRequest(BaseModel):
    prompts: Dict[str, str]

class PointsAdjustRequest(BaseModel):
    points_delta: Optional[int] = None
    exact_points: Optional[int] = None
    reason: Optional[str] = "Изменение через панель администратора"

class AchievementsUpdateRequest(BaseModel):
    achievements: List[Any]

class FactCreateRequest(BaseModel):
    text: str
    user_id: Optional[int] = None
    username: Optional[str] = None

class AgreementStatusRequest(BaseModel):
    status: str

class LessonCreateRequest(BaseModel):
    learned_rule: str
    reasoning: Optional[str] = None
    verdict: Optional[str] = "fair"
    status: Optional[str] = "active"
    trigger_context: Optional[str] = None
    date_key: Optional[str] = None

class LessonUpdateRequest(BaseModel):
    learned_rule: Optional[str] = None
    reasoning: Optional[str] = None
    verdict: Optional[str] = None
    status: Optional[str] = None

class LessonStatusRequest(BaseModel):
    status: str

class ActionChatRequest(BaseModel):
    chat_id: str

class CheckAgreementsActionRequest(BaseModel):
    chat_id: str
    lookback_days: Optional[int] = 7
    send_telegram: Optional[bool] = False

class AnalyzeFeedbackActionRequest(BaseModel):
    chat_id: str
    date_key: Optional[str] = None

class VoiceDigestActionRequest(BaseModel):
    chat_id: str
    edition_type: Optional[str] = "Дневной выпуск (14:00)"
    send_telegram: Optional[bool] = True


# --- Auth Endpoints ---

@router.post("/api/admin/login")
@limiter.limit("10/minute")
async def admin_login(request: Request, body: LoginRequest, response: Response):
    if not verify_admin_password(body.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный пароль администратора"
        )

    token = create_admin_token()
    is_https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=TOKEN_EXPIRATION_SECONDS,
        httponly=True,
        samesite="lax",
        secure=is_https
    )
    return {"status": "ok", "token": token}


@router.post("/api/admin/logout")
async def admin_logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"status": "logged_out"}


@router.get("/api/admin/me")
async def admin_me(admin=Depends(get_current_admin)):
    return {"authenticated": True, "sub": admin.get("sub", "admin")}


# --- Config Endpoints ---

@router.get("/api/admin/config")
async def get_config(admin=Depends(get_current_admin)):
    return {
        "config": config.to_dict(),
        "defaults": DEFAULT_CONFIG_VALUES
    }


@router.put("/api/admin/config")
async def update_config(body: ConfigUpdateRequest, admin=Depends(get_current_admin)):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    saved_config = await ConfigService.save_config(updates)
    if "BOT_DISABLED" in updates or "ENABLE_AGREEMENTS" in updates:
        try:
            from src.main import sync_bot_commands
            await sync_bot_commands()
        except Exception as e:
            logger.debug(f"Could not sync bot commands: {e}")
    if any(k.startswith("VOICE_DIGEST_") for k in updates) or "BOT_DISABLED" in updates:
        try:
            from src.main import sync_voice_digest_jobs
            sync_voice_digest_jobs()
        except Exception as e:
            logger.debug(f"Could not sync voice digest jobs: {e}")
    return {
        "status": "updated",
        "config": saved_config
    }


@router.post("/api/admin/config/reset")
async def reset_config(admin=Depends(get_current_admin)):
    reset_data = await ConfigService.reset_config()
    return {
        "status": "reset",
        "config": reset_data
    }


# --- Prompts Endpoints ---

@router.get("/api/admin/prompts")
async def get_prompts(admin=Depends(get_current_admin)):
    return {
        "prompts": PromptService.get_all_prompts_info()
    }


@router.get("/api/admin/prompts/{key}")
async def get_single_prompt(key: str, admin=Depends(get_current_admin)):
    if key not in PROMPT_METADATA:
        raise HTTPException(status_code=404, detail="Prompt not found")

    meta = PROMPT_METADATA[key]
    current_val = PromptService.get_template(key)
    return {
        "key": key,
        "name": meta["name"],
        "description": meta["description"],
        "placeholders": meta["placeholders"],
        "current_template": current_val,
        "default_template": meta["default"],
        "is_modified": current_val.strip() != meta["default"].strip()
    }


@router.put("/api/admin/prompts/{key}")
async def update_single_prompt(key: str, body: PromptUpdateRequest, admin=Depends(get_current_admin)):
    if key not in PROMPT_METADATA:
        raise HTTPException(status_code=404, detail="Prompt not found")

    saved_template = await PromptService.save_prompt(key, body.template)
    return {
        "status": "updated",
        "key": key,
        "template": saved_template
    }


@router.put("/api/admin/prompts")
async def update_all_prompts(body: AllPromptsUpdateRequest, admin=Depends(get_current_admin)):
    saved = await PromptService.save_all_prompts(body.prompts)
    return {
        "status": "updated",
        "prompts": saved
    }


@router.post("/api/admin/prompts/{key}/reset")
async def reset_single_prompt(key: str, admin=Depends(get_current_admin)):
    if key not in PROMPT_METADATA:
        raise HTTPException(status_code=404, detail="Prompt not found")

    reset_template = await PromptService.reset_prompt(key)
    return {
        "status": "reset",
        "key": key,
        "template": reset_template
    }


@router.post("/api/admin/prompts/reset_all")
async def reset_all_prompts(admin=Depends(get_current_admin)):
    reset_prompts = await PromptService.reset_all_prompts()
    return {
        "status": "reset_all",
        "prompts": reset_prompts
    }


# --- Chats & Database Management Endpoints ---

@router.get("/api/admin/chats")
async def list_chats(admin=Depends(get_current_admin)):
    """Lists all chats tracked by the bot in Firestore."""
    chats = []
    chats_ref = db.collection("chats")
    seen_ids = set()

    try:
        async for chat_doc in chats_ref.stream():
            data = chat_doc.to_dict() or {}
            chat_id = chat_doc.id
            seen_ids.add(chat_id)
            chats.append({
                "chat_id": chat_id,
                "title": data.get("title", f"Чат {chat_id}"),
                "active": data.get("active", True),
                "type": data.get("type", "supergroup"),
                "last_agreement_check": str(data.get("last_agreement_check", ""))
            })
    except Exception as e:
        logger.error(f"Error fetching chats: {e}")

    # Ensure main chat is included if chats collection was empty
    if str(settings.MAIN_CHAT_ID) not in seen_ids:
        chats.insert(0, {
            "chat_id": str(settings.MAIN_CHAT_ID),
            "title": f"Основной чат ({settings.MAIN_CHAT_ID})",
            "active": True,
            "type": "supergroup",
            "last_agreement_check": ""
        })

    return {"chats": chats}


@router.get("/api/admin/chats/{chat_id}/users")
async def list_chat_users(chat_id: str, admin=Depends(get_current_admin)):
    """Returns users with their stats, points, ranks, and achievements."""
    users, _ = await user_repository.get_chat_users(chat_id, limit=300)

    # Sort users by total_points descending
    users_sorted = sorted(
        users,
        key=lambda u: u.get("stats", {}).get("total_points", 0),
        reverse=True
    )
    return {
        "chat_id": chat_id,
        "count": len(users_sorted),
        "users": users_sorted
    }


@router.post("/api/admin/chats/{chat_id}/users/{user_id}/points")
async def adjust_user_points(chat_id: str, user_id: str, body: PointsAdjustRequest, admin=Depends(get_current_admin)):
    """Adjusts points delta or sets exact points for a user."""
    try:
        c_id = int(chat_id)
        u_id = int(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat_id or user_id format")

    if body.exact_points is not None:
        res = await user_repository.set_user_points(c_id, u_id, body.exact_points)
        return {
            "status": "success",
            "mode": "set_exact",
            "total_points": res["total_points"],
            "current_rank": res["current_rank"]
        }

    if body.points_delta is not None:
        new_total = await user_repository.add_points(
            chat_id=c_id,
            user_id=u_id,
            points=body.points_delta,
            reason=body.reason or "Административная корректировка",
            event_type="admin_adjustment"
        )
        rank = user_repository.calculate_rank(new_total)
        return {
            "status": "success",
            "mode": "delta",
            "points_delta": body.points_delta,
            "total_points": new_total,
            "current_rank": rank
        }

    raise HTTPException(status_code=400, detail="Must provide points_delta or exact_points")


@router.post("/api/admin/chats/{chat_id}/users/{user_id}/achievements")
async def update_user_achievements(chat_id: str, user_id: str, body: AchievementsUpdateRequest, admin=Depends(get_current_admin)):
    """Replaces or updates achievements list for a user."""
    try:
        c_id = int(chat_id)
        u_id = int(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat_id or user_id format")

    achievements = await user_repository.update_user_achievements(c_id, u_id, body.achievements)
    return {
        "status": "success",
        "achievements": achievements
    }


@router.get("/api/admin/chats/{chat_id}/points_ledger")
async def get_points_ledger(chat_id: str, limit: int = 50, admin=Depends(get_current_admin)):
    """Returns recent point events for audit and rollback."""
    try:
        c_id = int(chat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat_id format")

    events = await user_repository.get_points_ledger(c_id, limit=limit)
    return {
        "chat_id": chat_id,
        "events": events
    }


@router.delete("/api/admin/chats/{chat_id}/points_ledger/{event_id}")
async def revert_points_event(chat_id: str, event_id: str, admin=Depends(get_current_admin)):
    """Reverts and deletes an accidental or erroneous point transaction."""
    try:
        c_id = int(chat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat_id format")

    res = await user_repository.revert_point_event(c_id, event_id)
    if not res.get("success"):
        raise HTTPException(status_code=404, detail=res.get("error", "Event not found"))
    return res


# --- Lore & Facts Endpoints ---

@router.get("/api/admin/chats/{chat_id}/lore")
async def get_lore(chat_id: str, admin=Depends(get_current_admin)):
    try:
        c_id = int(chat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat_id format")

    lore = await LoreService.get_lore(c_id)
    return {"chat_id": chat_id, "lore": lore}


@router.put("/api/admin/chats/{chat_id}/lore")
async def update_lore(chat_id: str, body: Dict[str, Any], admin=Depends(get_current_admin)):
    try:
        c_id = int(chat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat_id format")

    lore_data = body.get("lore", body)
    await LoreService.update_lore(c_id, lore_data, generated_by="admin_cms")
    return {"status": "lore_updated", "lore": lore_data}


@router.get("/api/admin/chats/{chat_id}/facts")
async def list_facts(chat_id: str, admin=Depends(get_current_admin)):
    try:
        c_id = int(chat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat_id format")

    facts = await fact_repository.get_facts(c_id)
    return {"chat_id": chat_id, "facts": facts}


@router.post("/api/admin/chats/{chat_id}/facts")
async def add_fact(chat_id: str, body: FactCreateRequest, admin=Depends(get_current_admin)):
    try:
        c_id = int(chat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat_id format")

    data = {
        "text": body.text.strip(),
        "added_by": "admin_cms",
        "created_at": firestore.SERVER_TIMESTAMP
    }
    if body.user_id:
        data["user_id"] = body.user_id
    if body.username:
        data["username"] = body.username

    success = await fact_repository.add_fact(c_id, data)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to add fact")
    FactService.invalidate_cache(c_id)
    return {"status": "added", "fact": data}


@router.delete("/api/admin/chats/{chat_id}/facts/{fact_id}")
async def delete_fact(chat_id: str, fact_id: str, admin=Depends(get_current_admin)):
    try:
        c_id = int(chat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat_id format")

    success = await fact_repository.delete_fact(c_id, fact_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete fact")
    FactService.invalidate_cache(c_id)
    return {"status": "deleted", "fact_id": fact_id}


# --- Agreements Endpoints ---

@router.get("/api/admin/chats/{chat_id}/agreements")
async def list_agreements(chat_id: str, admin=Depends(get_current_admin)):
    try:
        c_id = int(chat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat_id format")

    agreements = await agreement_repository.get_all_agreements(c_id)
    return {"chat_id": chat_id, "agreements": agreements}


@router.post("/api/admin/chats/{chat_id}/agreements/{agreement_id}/status")
async def update_agreement_status(chat_id: str, agreement_id: str, body: AgreementStatusRequest, admin=Depends(get_current_admin)):
    try:
        c_id = int(chat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat_id format")

    await agreement_repository.update_agreement(c_id, agreement_id, {"status": body.status})
    return {"status": "updated", "agreement_id": agreement_id, "new_status": body.status}


@router.delete("/api/admin/chats/{chat_id}/agreements/{agreement_id}")
async def delete_agreement(chat_id: str, agreement_id: str, admin=Depends(get_current_admin)):
    try:
        c_id = int(chat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat_id format")

    success = await agreement_repository.delete_agreement(c_id, agreement_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete agreement")
    return {"status": "deleted", "agreement_id": agreement_id}


# --- Lessons & Self-Learning Endpoints ---

@router.get("/api/admin/chats/{chat_id}/lessons")
async def list_lessons(chat_id: str, status: Optional[str] = None, admin=Depends(get_current_admin)):
    try:
        c_id = int(chat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat_id format")

    lessons = await lesson_repository.get_lessons(c_id, status=status)
    return {"chat_id": chat_id, "lessons": lessons}


@router.post("/api/admin/chats/{chat_id}/lessons")
async def add_lesson(chat_id: str, body: LessonCreateRequest, admin=Depends(get_current_admin)):
    try:
        c_id = int(chat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat_id format")

    rule_clean = body.learned_rule.strip()
    if not rule_clean:
        raise HTTPException(status_code=400, detail="Правило урока не может быть пустым")

    lesson_data = {
        "learned_rule": rule_clean,
        "reasoning": (body.reasoning or "").strip(),
        "verdict": body.verdict or "fair",
        "status": body.status or "active",
        "trigger_context": (body.trigger_context or "Добавлено вручную через CMS").strip(),
        "date_key": body.date_key or datetime.now().strftime("%Y-%m-%d"),
    }
    created = await lesson_repository.create_lesson(c_id, lesson_data)
    return {"status": "created", "lesson": created}


@router.put("/api/admin/chats/{chat_id}/lessons/{lesson_id}")
async def update_lesson(chat_id: str, lesson_id: str, body: LessonUpdateRequest, admin=Depends(get_current_admin)):
    try:
        c_id = int(chat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat_id format")

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if "learned_rule" in updates:
        updates["learned_rule"] = updates["learned_rule"].strip()
        if not updates["learned_rule"]:
            raise HTTPException(status_code=400, detail="Правило урока не может быть пустым")

    success = await lesson_repository.update_lesson(c_id, lesson_id, updates)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update lesson")
    return {"status": "updated", "lesson_id": lesson_id, "updates": updates}


@router.post("/api/admin/chats/{chat_id}/lessons/{lesson_id}/status")
async def update_lesson_status(chat_id: str, lesson_id: str, body: LessonStatusRequest, admin=Depends(get_current_admin)):
    try:
        c_id = int(chat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat_id format")

    success = await lesson_repository.set_lesson_status(c_id, lesson_id, body.status)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update lesson status")
    return {"status": "status_updated", "lesson_id": lesson_id, "new_status": body.status}


@router.delete("/api/admin/chats/{chat_id}/lessons/{lesson_id}")
async def delete_lesson(chat_id: str, lesson_id: str, admin=Depends(get_current_admin)):
    try:
        c_id = int(chat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat_id format")

    success = await lesson_repository.delete_lesson(c_id, lesson_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete lesson")
    return {"status": "deleted", "lesson_id": lesson_id}


# --- Live Actions Endpoints ---

@router.post("/api/admin/actions/toggle_bot")
async def action_toggle_bot(admin=Depends(get_current_admin)):
    new_state = not config.BOT_DISABLED
    await ConfigService.save_config({"BOT_DISABLED": new_state})
    try:
        from src.main import sync_bot_commands
        await sync_bot_commands()
    except Exception as e:
        logger.debug(f"Could not sync bot commands: {e}")
    return {
        "status": "success",
        "bot_disabled": config.BOT_DISABLED
    }


@router.post("/api/admin/actions/daily_analysis")
async def action_daily_analysis(body: ActionChatRequest, admin=Depends(get_current_admin)):
    from src.main import analysis_service
    try:
        result = await analysis_service.perform_chat_analysis(body.chat_id)
        return {"status": "success", "result": result}
    except Exception as e:
        logger.error(f"Daily analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка дневного анализа: {str(e)}")


@router.post("/api/admin/actions/weekly_decay")
async def action_weekly_decay(body: ActionChatRequest, admin=Depends(get_current_admin)):
    from src.main import bot
    from src.utils import messages
    try:
        await apply_weekly_amnesty(body.chat_id)
        try:
            await bot.send_message(
                chat_id=body.chat_id,
                text=messages.AMNESTY_MESSAGE,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Could not send amnesty Telegram message: {e}")
        return {"status": "amnesty_applied", "chat_id": body.chat_id}
    except Exception as e:
        logger.error(f"Amnesty failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка применения амнистии: {str(e)}")


@router.post("/api/admin/actions/check_agreements")
async def action_check_agreements(body: CheckAgreementsActionRequest, admin=Depends(get_current_admin)):
    from src.main import analysis_service
    try:
        res = await analysis_service.perform_agreement_check(
            chat_id=body.chat_id,
            lookback_days=body.lookback_days or 7,
            send_message=bool(body.send_telegram)
        )
        return {"status": "success", "result": res}
    except Exception as e:
        logger.error(f"Agreement check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка проверки договоренностей: {str(e)}")


@router.post("/api/admin/actions/lore_evolution")
async def action_lore_evolution(body: ActionChatRequest, admin=Depends(get_current_admin)):
    try:
        await LoreService.evolve_lore(int(body.chat_id))
        return {"status": "evolution_completed", "chat_id": body.chat_id}
    except Exception as e:
        logger.error(f"Lore evolution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка эволюции лора: {str(e)}")


@router.post("/api/admin/actions/voice_digest")
async def action_voice_digest(body: VoiceDigestActionRequest, admin=Depends(get_current_admin)):
    from src.main import bot
    from src.services.voice_digest_service import VoiceDigestService
    try:
        res = await VoiceDigestService.create_and_send_voice_digest(
            chat_id=int(body.chat_id),
            edition_type=body.edition_type or "Дневной выпуск (14:00)",
            bot=bot,
            send_to_telegram=bool(body.send_telegram)
        )
        return {"status": "success", "result": res}
    except Exception as e:
        logger.error(f"Voice digest generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка генерации голосовой хроники: {str(e)}")


@router.post("/api/admin/actions/analyze_feedback")
async def action_analyze_feedback(body: AnalyzeFeedbackActionRequest, admin=Depends(get_current_admin)):
    try:
        c_id = int(body.chat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat_id format")

    try:
        result = await LearningService.analyze_feedback(c_id, body.date_key)
        if result:
            return {
                "status": "success",
                "result": result.model_dump(),
                "learned": bool(result.learned_rule and result.learned_rule.strip())
            }
        return {
            "status": "no_feedback",
            "result": None,
            "message": "Сообщений с обратной связью не найдено или коррекция не требуется."
        }
    except Exception as e:
        logger.error(f"Feedback analysis action failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка анализа обратной связи: {str(e)}")

