from aiogram import Router, types, F
from aiogram.types import MessageReactionUpdated
from aiogram.filters import Command
from ..services.db import log_message, db, log_reaction, get_active_agreements, get_message, update_edited_message, get_chat_users, dispute_agreement
from ..services.ai import transcribe_media, validate_fact
from ..services.fact_service import FactService
from ..services.chat_service import ChatService
from ..services.game_service import GameService
from ..services.report_service import ReportService
from ..utils.text import escape
from ..utils.game_config import config
from ..utils import messages
import logging
from io import BytesIO

router = Router()

@router.message(Command("bot_disable"))
async def cmd_bot_disable(message: types.Message):
    from ..utils.game_config import config
    
    # Optional: Check if user is admin in the chat
    member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
    if member.status not in ["creator", "administrator"]:
        return

    config.BOT_DISABLED = True
    logging.warning(f"BOT GLOBALLY DISABLED by {message.from_user.id} in chat {message.chat.id}")
    await message.answer("🛑 <b>БОТ ПОЛНОСТЬЮ ОТКЛЮЧЕН.</b>\nЯ больше не реагирую ни на какие команды и сообщения.", parse_mode="HTML")

@router.message(Command("bot_enable"))
async def cmd_bot_enable(message: types.Message):
    from ..utils.game_config import config
    
    member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
    if member.status not in ["creator", "administrator"]:
        return

    config.BOT_DISABLED = False
    logging.warning(f"BOT GLOBALLY ENABLED by {message.from_user.id} in chat {message.chat.id}")
    await message.answer("✅ <b>БОТ ВКЛЮЧЕН.</b>\nЯ снова слежу за вами.", parse_mode="HTML")

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    if config.BOT_DISABLED:
        return
    await message.answer("Я Снитч-бот. Я слежу за вами. 👁️")
    await db.collection("chats").document(str(message.chat.id)).set({"active": True}, merge=True)

@router.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if config.BOT_DISABLED:
        return
    text = await GameService.get_stats_report(message.chat.id)
    await message.answer(text, parse_mode="HTML")

@router.message(Command("rules"))
async def cmd_rules(message: types.Message):
    if config.BOT_DISABLED:
        return
    await message.answer(messages.RULES_TEXT, parse_mode="HTML")

@router.message(Command("agreements"))
async def cmd_agreements(message: types.Message):
    if config.BOT_DISABLED:
        return
    if not config.ENABLE_AGREEMENTS:
        return
    agreements = await get_active_agreements(message.chat.id)
    if not agreements:
        await message.answer("🤝 <b>Договоренности:</b>\n\nНет действующих договоренностей. Живите спокойно... пока что.", parse_mode="HTML")
        return

    text = "🤝 <b>Слово Пацана (Действующие):</b>\n\n"
    for i, ag in enumerate(agreements, 1):
        agreement_text = escape(ag.get('text', '???'))
        ag_type = ag.get('type', 'vow')
        
        icon = "🕯" # vow
        if ag_type == "pact": icon = "🤝"
        elif ag_type == "public": icon = "📢"
        
        status_icon = "⏳"
        
        expires_at = ag.get('expires_at')
        time_str = ""
        if expires_at:
            if hasattr(expires_at, 'strftime'):
                time_str = f" (до {expires_at.strftime('%d.%m %H:%M')})"
        
        users = ag.get('users', [])
        users_str = ", ".join([f"<b>{escape(u if u.startswith('@') else '@'+u)}</b>" for u in users])
        text += f"{i}. {status_icon} {icon} {users_str}: <b>{agreement_text}</b>{time_str} (Оспорить: /disput {i})\n"

    await message.answer(text, parse_mode="HTML")

@router.message(Command("dispute", "disput"))
async def cmd_dispute(message: types.Message):
    if config.BOT_DISABLED:
        return
    if not config.ENABLE_AGREEMENTS:
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Укажи ID договоренности или порядковый номер из последнего отчета.\nПример: /dispute 1")
        return

    try:
        idx = int(args[1]) - 1
        active = await get_active_agreements(message.chat.id)
        if 0 <= idx < len(active):
            target_id = active[idx]['id']
            success, error_code = await dispute_agreement(message.chat.id, target_id)
            if success:
                await message.answer(messages.AGREEMENT_DISPUTE_SUCCESS, parse_mode="HTML")
            else:
                if error_code == "too_late":
                    await message.answer(messages.AGREEMENT_DISPUTE_TOO_LATE, parse_mode="HTML")
                else:
                    await message.answer(messages.AGREEMENT_DISPUTE_NOT_FOUND, parse_mode="HTML")
        else:
            await message.answer(messages.AGREEMENT_DISPUTE_NOT_FOUND, parse_mode="HTML")
    except ValueError:
        # Try as direct ID
        target_id = args[1]
        success, error_code = await dispute_agreement(message.chat.id, target_id)
        if success:
            await message.answer(messages.AGREEMENT_DISPUTE_SUCCESS, parse_mode="HTML")
        else:
             await message.answer(messages.AGREEMENT_DISPUTE_NOT_FOUND, parse_mode="HTML")

@router.message(Command("all"))
async def cmd_all(message: types.Message):
    if config.BOT_DISABLED:
        return
    logging.info(f"Received /all command in chat {message.chat.id}")
    try:
        users, _ = await get_chat_users(message.chat.id)
        logging.info(f"Found {len(users) if users else 0} users in chat {message.chat.id}")
        
        if not users:
            await message.answer(messages.NO_USERS_TO_TAG)
            return

        mentions = []
        for u in users:
            user_id = u['user_id']
            username = u['username']
            full_name = u['full_name'] or "Аноним"
            if username:
                mentions.append(f"@{escape(username)}")
            else:
                mentions.append(f"<a href='tg://user?id={user_id}'>{escape(full_name)}</a>")
        
        logging.info(f"Generated {len(mentions)} mentions for chat {message.chat.id}")
        
        if not mentions:
            await message.answer("Некого тегать.")
            return

        chunk_size = config.MENTION_CHUNK_SIZE
        for i in range(0, len(mentions), chunk_size):
            chunk = mentions[i:i + chunk_size]
            text = messages.ALL_COMMAND_TITLE + " ".join(chunk)
            logging.info(f"Sending chunk {i//chunk_size + 1} with {len(chunk)} mentions")
            await message.answer(text, parse_mode="HTML")
            
    except Exception as e:
        logging.error(f"Error in cmd_all: {e}", exc_info=True)
        await message.answer("⚠️ Ошибка при выполнении команды /all. Обратитесь к администратору.")

@router.message(Command("status", "me"))
async def cmd_status(message: types.Message):
    if config.BOT_DISABLED:
        return
    target_user = message.from_user
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user

    text = await GameService.get_user_status(message.chat.id, target_user)
    await message.answer(text, parse_mode="HTML")

@router.message(Command("report"))
async def cmd_report(message: types.Message):
    if config.BOT_DISABLED:
        return
    if not message.reply_to_message:
        await message.answer("❌ <b>Ошибка:</b> Используйте команду ответом на сообщение снитча.", parse_mode="HTML")
        return

    reported_msg = message.reply_to_message
    target_text = reported_msg.text
    
    if not target_text and (reported_msg.voice or reported_msg.video_note):
        stored_msg = await get_message(message.chat.id, reported_msg.message_id)
        if stored_msg:
             target_text = stored_msg.get('text')
    
    if not target_text and reported_msg.sticker:
        target_text = f"[STICKER] {reported_msg.sticker.emoji or 'Unknown'} (ID: {reported_msg.sticker.file_unique_id})"
    
    if not target_text:
        await message.answer("❌ <b>Ошибка:</b> Сообщение не содержит текста, стикера или еще не обработано.", parse_mode="HTML")
        return
    
    if reported_msg.from_user.id == message.from_user.id:
        await message.answer("❌ Самодонос? Это конечно похвально, но нет.")
        return

    status_msg = await message.answer(messages.REPORT_ANALYSIS_START, parse_mode="HTML")
    
    response_text, _ = await ReportService.process_report(message, reported_msg, target_text)
    
    await status_msg.edit_text(response_text, parse_mode="HTML")

@router.message(Command("casino"))
async def cmd_casino(message: types.Message):
    if config.BOT_DISABLED:
        return
    text = await GameService.play_casino(message.from_user.id, message.chat.id)
    await message.reply(text, parse_mode="HTML")

@router.message(Command("remember"))
async def cmd_remember(message: types.Message):
    """
    Manually add a fact to verified_facts.
    Example: /remember Vanya has a new car
    Or reply to a message with /remember
    """
    if config.BOT_DISABLED:
        return
    fact_text = ""
    if message.reply_to_message:
        fact_text = message.reply_to_message.text or message.reply_to_message.caption
    else:
        fact_text = message.text.replace("/remember", "").strip()

    if not fact_text:
        await message.answer("❌ Что запомнить? Напиши после команды или ответь на сообщение.")
        return

    status_msg = await message.answer("🤔 Проверяю твой «факт» на воздух...")
    
    validation = await validate_fact(fact_text)
    
    if not validation.is_fact:
        reason = validation.reason or "Это очередной воздух."
        await status_msg.edit_text(f"❌ <b>Отказ:</b> {escape(reason)}", parse_mode="HTML")
        return

    final_fact = validation.cleaned_fact or fact_text
    
    success = await FactService.add_fact(message.chat.id, final_fact, source=f"user_{message.from_user.id}")
    if success:
        if final_fact.strip() != fact_text.strip():
            await status_msg.edit_text(f"✅ <b>Запомнил в нормальном виде:</b>\n<i>{escape(final_fact)}</i>", parse_mode="HTML")
        else:
            await status_msg.edit_text("✅ <b>Запомнил.</b> Теперь это истина.", parse_mode="HTML")
    else:
        await status_msg.edit_text("❌ Не удалось запомнить. Видимо, я перегружен.")

@router.message_reaction()
async def handle_reactions(reaction: MessageReactionUpdated):
    if config.BOT_DISABLED:
        return
    old_emojis = {r.emoji for r in reaction.old_reaction if hasattr(r, 'emoji')}
    new_emojis = {r.emoji for r in reaction.new_reaction if hasattr(r, 'emoji')}
    added = new_emojis - old_emojis
    
    if not added:
        return
        
    for emoji in added:
        await log_reaction(
            chat_id=reaction.chat.id,
            user_id=reaction.user.id,
            username=reaction.user.username or reaction.user.first_name,
            message_id=reaction.message_id,
            emoji=emoji,
            timestamp=reaction.date
        )

@router.edited_message()
async def handle_edited_messages(message: types.Message):
    if config.BOT_DISABLED:
        return
    await update_edited_message(message)

@router.message(F.text | F.sticker | F.voice | F.video_note)
async def handle_messages(message: types.Message):
    if config.BOT_DISABLED:
        return
    override_text = None
    if message.voice or message.video_note:
        try:
            file_id = message.voice.file_id if message.voice else message.video_note.file_id
            file_info = await message.bot.get_file(file_id)
            file_io = BytesIO()
            await message.bot.download_file(file_info.file_path, file_io)
            file_bytes = file_io.getvalue()
            mime_type = "audio/ogg" if message.voice else "video/mp4"
            transcription = await transcribe_media(file_bytes, mime_type)
            prefix = "[VOICE]" if message.voice else "[VIDEO NOTE]"
            override_text = f"{prefix} {transcription}"
        except Exception as e:
            logging.error(f"Failed to transcribe media: {e}")
            override_text = f"[{'VOICE' if message.voice else 'VIDEO NOTE'}] (Transcription Failed)"
    
    if message.sticker:
         override_text = f"[STICKER] {message.sticker.emoji or 'Unknown'} (File ID: {message.sticker.file_unique_id})"

    try:
        await log_message(message, override_text=override_text)
    except Exception as e:
        logging.error(f"Failed to log message: {e}")

    # Cynical Comment Logic via ChatService
    comment_text = message.text or override_text
    
    comment = await ChatService.process_cynical_comment(message, comment_text)
    if comment:
        sent_msg = await message.reply(comment)
        try:
            await log_message(sent_msg)
        except Exception as e:
            logging.error(f"Failed to log bot message: {e}")
            
    # Correction Loop: If user says "Это неправда" or "Ты врешь" etc.
    # Note: process_cynical_comment in ChatService handles generation, but this specific 'correction' logic 
    # was inline in handlers.py. It's a bit of a niche feature. 
    # I should check if I moved it to ChatService. I didn't see it in my ChatService implementation.
    # The ChatService.process_cynical_comment I wrote mostly handles GENERATING the comment.
    # The correction loop checks the USER'S message for keywords like "lie".
    
    # Let's add the correction logic back here or move it to ChatService.
    # Since it interacts with the bot acknowledging a mistake, it fits in ChatService or here.
    # The original logic was:
    # correction_keywords = ["неправда", "врешь", "забудь", "ошибка", "wrong", "lie", "hallucination"]
    # if is_mentioned and any(kw in comment_text.lower() for kw in correction_keywords):
    #   ...
    
    # My ChatService.process_cynical_comment handles the bot REPLYING. 
    # It doesn't handle the bot listening to corrections.
    
    # Let's quickly check ChatService again.
    # I see I implemented process_cynical_comment which returns a comment or None.
    
    # I will re-implement the correction logic here for now as it is a specific reaction handler,
    # OR I can add a method `ChatService.check_for_correction(message)`?
    # It's simple enough to keep here, or I can update ChatService.
    
    # Let's keep it here for now to avoid re-writing ChatService unless necessary.
    # Wait, the original logic relied on `is_mentioned` which was calculated inside the block.
    # I should recalculate `is_mentioned` here if I want to use it.
    
    bot_user = await message.bot.get_me()
    is_mentioned = False
    if message.text:
        is_mentioned = f"@{bot_user.username}" in message.text
    if not is_mentioned and message.reply_to_message:
        is_mentioned = message.reply_to_message.from_user.id == bot_user.id
        
    correction_keywords = ["неправда", "врешь", "забудь", "ошибка", "wrong", "lie", "hallucination"]
    if is_mentioned and comment_text and any(kw in comment_text.lower() for kw in correction_keywords):
        if message.reply_to_message and message.reply_to_message.from_user.id == bot_user.id:
            await message.reply("🤐 Понял, завязываю галлюцинировать. Если я сказал что-то не то — сорян.")
