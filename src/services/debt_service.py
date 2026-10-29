"""One ingestion path for live comments, daily reports and historical scans."""
import logging

from src.repositories.debt_repository import debt_repository, normalize_party, validate_pair, validate_amount
from src.repositories.user_repository import user_repository
from src.services.lore_service import LoreService
from src.utils.game_config import config
from src.utils.text import escape

logger = logging.getLogger(__name__)


class DebtService:
    @staticmethod
    async def party_index(chat_id, messages):
        users, cursor = await user_repository.get_chat_users(chat_id, limit=200)
        while cursor is not None:
            page, cursor = await user_repository.get_chat_users(chat_id, limit=200, cursor=cursor)
            users.extend(page)
        index = {}

        def add(alias, canonical):
            if alias:
                index.setdefault(normalize_party(str(alias)), set()).add(canonical)

        # A name is resolved only when it has one exact match, never by substring.
        canonical_by_id = {
            str(user["user_id"]): user.get("username") or user.get("full_name") or str(user["user_id"])
            for user in users if user.get("user_id")
        }
        for user in [*users, *messages]:
            if user.get("is_bot") or user.get("username") == "YOU (Snitch Bot)":
                continue
            canonical = canonical_by_id.get(str(user.get("user_id"))) or user.get("username") or user.get("full_name") or user.get("first_name") or user.get("user_id")
            if not canonical:
                continue
            canonical = normalize_party(str(canonical))
            for field in ("username", "full_name", "first_name", "user_id"):
                add(user.get(field), canonical)

        lore = await LoreService.get_lore(chat_id)
        for character in lore.get("core", lore).get("characters", []):
            matches = set()
            for key in (character.get("handle"), character.get("id")):
                if key:
                    matches.update(index.get(normalize_party(str(key)), set()))
            if len(matches) == 1:
                canonical = next(iter(matches))
                for alias in character.get("names", []):
                    add(alias, canonical)
        return index

    @classmethod
    async def resolve_manual_pair(cls, chat_id, debtor, creditor):
        debtor, creditor = validate_pair(debtor, creditor)
        index = await cls.party_index(chat_id, [])
        parties = []
        for party in (debtor, creditor):
            matches = index.get(party, {party})
            if len(matches) != 1:
                raise ValueError("Имя неоднозначно; укажите точный username участника")
            parties.append(next(iter(matches)))
        return validate_pair(*parties)

    @classmethod
    async def apply(cls, chat_id, transactions, source_messages):
        if config.BOT_DISABLED or not getattr(config, "ENABLE_DEBTS", True) or not transactions:
            return []
        sources = {
            str(message["message_id"]): message
            for message in source_messages
            if str(message.get("message_id", "")).isdigit()
            and not message.get("is_bot")
            and message.get("username") != "YOU (Snitch Bot)"
        }
        if not sources:
            return []
        index = await cls.party_index(chat_id, source_messages)
        groups, seen = {}, set()
        for transaction in transactions:
            item = transaction.model_dump() if hasattr(transaction, "model_dump") else dict(transaction)
            source_id = str(item.get("source_message_id") or "")
            if source_id not in sources:
                logger.warning("Skipping debt without a valid source message in chat %s", chat_id)
                continue
            try:
                debtor, creditor = validate_pair(item.get("debtor"), item.get("creditor"))
                debtor_matches, creditor_matches = index.get(debtor, set()), index.get(creditor, set())
                if len(debtor_matches) != 1 or len(creditor_matches) != 1:
                    logger.warning("Skipping debt with unknown/ambiguous participants in chat %s", chat_id)
                    continue
                debtor, creditor = validate_pair(next(iter(debtor_matches)), next(iter(creditor_matches)))
                amount = validate_amount(item.get("amount"))
                settled = item.get("is_settled", False)
                if type(settled) is not bool:
                    raise ValueError("Invalid settlement flag")
            except ValueError:
                logger.warning("Skipping invalid debt in chat %s", chat_id)
                continue
            signature = (source_id, debtor, creditor, amount, settled)
            if signature in seen:
                continue
            seen.add(signature)
            groups.setdefault(source_id, []).append({
                **item, "debtor": debtor, "creditor": creditor, "source_message_id": source_id,
            })

        applied = []
        for source_id in sorted(groups, key=int):
            applied.extend(await debt_repository.update_debts(
                chat_id, groups[source_id], operation_id=f"message:{source_id}",
                occurred_at=sources[source_id].get("timestamp"),
            ))
        return applied

    @staticmethod
    def format_updates(transactions, title="Обновление по долгам"):
        if not transactions:
            return ""
        lines = [f"\n\n💸 <b>{title}:</b>"]
        for item in transactions:
            debtor, creditor = escape(item["debtor"]), escape(item["creditor"])
            reason = f" ({escape(item['reason'])})" if item.get("reason") else ""
            if item["is_settled"]:
                lines.append(f"✅ {debtor} вернул {item['amount']} {creditor}{reason}")
            else:
                lines.append(f"📉 {debtor} торчит {item['amount']} {creditor}{reason}")
        return "\n".join(lines) + "\n"
