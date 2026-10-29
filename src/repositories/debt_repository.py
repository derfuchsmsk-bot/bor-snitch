from __future__ import annotations

import hashlib
import unicodedata
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from google.cloud import firestore
from src.database import db


MAX_AMOUNT = 10_000_000


def normalize_party(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Участник должен быть строкой")
    value = " ".join(unicodedata.normalize("NFKC", value).strip().lstrip("@").split()).casefold()
    if not value or len(value) > 100:
        raise ValueError("Укажите имя участника (до 100 символов)")
    return value


def validate_pair(debtor: str, creditor: str) -> tuple[str, str]:
    debtor, creditor = normalize_party(debtor), normalize_party(creditor)
    if debtor == creditor:
        raise ValueError("Должник и кредитор не могут совпадать")
    return debtor, creditor


def validate_amount(amount: int, *, allow_zero: bool = False) -> int:
    if type(amount) is not int or not (0 if allow_zero else 1) <= amount <= MAX_AMOUNT:
        raise ValueError("Сумма должна быть целым числом от %s до %s" % (0 if allow_zero else 1, MAX_AMOUNT))
    return amount


def clean_balances(raw: dict) -> dict:
    """Normalize spelling only; never guess aliases or net opposite debts."""
    result = {}
    for debtor, creditors in (raw or {}).items():
        for creditor, amount in creditors.items():
            if type(amount) is not int or amount <= 0:
                continue
            try:
                debtor_key, creditor_key = validate_pair(debtor, creditor)
            except ValueError:
                continue
            row = result.setdefault(debtor_key, {})
            row[creditor_key] = row.get(creditor_key, 0) + amount
    return result


class DebtRepository:
    def __init__(self):
        self.db = db

    def _get_ref(self, chat_id: str | int):
        return self.db.collection("chats").document(str(chat_id)).collection("debts").document("matrix")

    def _events_ref(self, chat_id):
        return self.db.collection("chats").document(str(chat_id)).collection("debt_events")

    def _event_ref(self, chat_id, operation_id):
        key = hashlib.sha256(operation_id.encode("utf-8")).hexdigest()
        return self._events_ref(chat_id).document(key)

    async def get_debts(self, chat_id: str | int) -> dict:
        doc = await self._get_ref(chat_id).get()
        return clean_balances((doc.to_dict() or {}).get("balances", {})) if doc.exists else {}

    async def initialize_journal(self, chat_id, *, started_at=None):
        """Preserve the legacy balance as a baseline, without replaying pre-upgrade logs."""
        ref = self._get_ref(chat_id)
        started_at = started_at or datetime.now(timezone.utc)

        @firestore.async_transactional
        async def initialize(transaction):
            doc = await ref.get(transaction=transaction)
            data = (doc.to_dict() or {}) if doc.exists else {}
            if "journal_baseline" in data:
                return
            transaction.set(ref, {
                "journal_baseline": clean_balances(data.get("balances", {})),
                "automatic_since": started_at,
            }, merge=["journal_baseline", "automatic_since"])

        await initialize(self.db.transaction())

    async def get_debts_summary(self, chat_id: str | int) -> dict:
        balances = await self.get_debts(chat_id)
        items, debtor_totals, creditor_totals = [], {}, {}
        for debtor, creditors in balances.items():
            for creditor, amount in creditors.items():
                items.append({"debtor": debtor, "creditor": creditor, "amount": amount})
                debtor_totals[debtor] = debtor_totals.get(debtor, 0) + amount
                creditor_totals[creditor] = creditor_totals.get(creditor, 0) + amount
        items.sort(key=lambda item: (-item["amount"], item["debtor"], item["creditor"]))
        top_debtor = max(sorted(debtor_totals), key=debtor_totals.get, default=None)
        top_creditor = max(sorted(creditor_totals), key=creditor_totals.get, default=None)
        return {
            "balances": balances, "items": items,
            "total_debt_amount": sum(item["amount"] for item in items),
            "debts_count": len(items),
            "top_debtor": top_debtor, "top_debtor_amount": debtor_totals.get(top_debtor, 0),
            "top_creditor": top_creditor, "top_creditor_amount": creditor_totals.get(top_creditor, 0),
        }

    async def _mutate(self, chat_id, kind, requested, operation_id=None, occurred_at=None):
        operation_id = operation_id or f"manual:{uuid4()}"
        occurred_at = occurred_at or datetime.now(timezone.utc)
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)
        message_id = int(operation_id.split(":", 1)[1]) if operation_id.startswith("message:") else 0
        order = [int(occurred_at.timestamp() * 1_000_000), message_id, operation_id]
        ref = self._get_ref(chat_id)
        event_ref = self._event_ref(chat_id, operation_id)

        @firestore.async_transactional
        async def commit(transaction):
            # Every read precedes every write. Receipt and balance commit atomically.
            event = await event_ref.get(transaction=transaction)
            if event.exists:
                return []
            doc = await ref.get(transaction=transaction)
            data = (doc.to_dict() or {}) if doc.exists else {}
            if operation_id.startswith("message:") and data.get("automatic_since") and occurred_at < data["automatic_since"]:
                return []
            balances = clean_balances(data.get("balances", {}))
            baseline = data.get("journal_baseline", deepcopy(balances))
            last_order = data.get("last_event_order", order)
            # Windows clocks can return equal timestamps for sequential admin writes.
            # Serialize manual actions after the last committed event, also on retry.
            event_order = order if operation_id.startswith("message:") else [max(order[0], last_order[0] + 1), 0, operation_id]
            entry = {"operation_id": operation_id, "kind": kind, "requested": requested, "order": event_order}
            if event_order < last_order:
                # A daily scan can discover a loan after its repayment was seen live.
                # Replay only on late arrivals; ordinary writes remain constant-cost.
                entries = [item.to_dict() async for item in self._events_ref(chat_id).stream(transaction=transaction)]
                entries.append(entry)
                balances = deepcopy(baseline)
                applied = []
                for old_entry in sorted(entries, key=lambda item: item["order"]):
                    result = self._apply_operation(balances, old_entry["kind"], old_entry["requested"])
                    if old_entry["operation_id"] == operation_id:
                        applied = result
            else:
                applied = self._apply_operation(balances, kind, requested)
            # Recursive map merging would retain removed pairs. Replace the map.
            transaction.set(ref, {
                "balances": balances, "journal_baseline": baseline, "last_event_order": max(event_order, last_order),
            }, merge=["balances", "journal_baseline", "last_event_order"])
            transaction.set(event_ref, {
                **entry, "applied_at_ingestion": applied, "created_at": firestore.SERVER_TIMESTAMP,
            })
            return applied

        return await commit(self.db.transaction())

    async def update_debts(self, chat_id: str | int, transactions: list, *, operation_id: str | None = None, occurred_at=None) -> list:
        prepared = []
        for item in transactions:
            debtor, creditor = validate_pair(item.get("debtor"), item.get("creditor"))
            amount = validate_amount(item.get("amount"))
            settled = item.get("is_settled", False)
            if type(settled) is not bool:
                raise ValueError("is_settled должен быть boolean")
            prepared.append({**item, "debtor": debtor, "creditor": creditor, "amount": amount, "is_settled": settled})
        if not prepared:
            return []

        return await self._mutate(chat_id, "delta", prepared, operation_id, occurred_at)

    @classmethod
    def _apply_operation(cls, balances, kind, requested):
        if kind == "clear":
            balances.clear()
            return []
        applied = []
        for item in requested:
            debtor, creditor = item["debtor"], item["creditor"]
            if kind == "set":
                cls._assign(balances, debtor, creditor, item["amount"])
                applied.append(dict(item))
                continue
            current = balances.get(debtor, {}).get(creditor, 0)
            amount = min(current, item["amount"]) if item["is_settled"] else item["amount"]
            if amount:
                remaining = current - amount if item["is_settled"] else current + amount
                cls._assign(balances, debtor, creditor, remaining)
                applied.append({**item, "amount": amount})
        return applied

    @staticmethod
    def _assign(balances, debtor, creditor, amount):
        if amount:
            balances.setdefault(debtor, {})[creditor] = amount
        elif debtor in balances:
            balances[debtor].pop(creditor, None)
            if not balances[debtor]:
                del balances[debtor]

    async def set_debt(self, chat_id, debtor, creditor, amount, *, operation_id=None) -> dict:
        debtor, creditor = validate_pair(debtor, creditor)
        amount = validate_amount(amount, allow_zero=True)

        await self._mutate(chat_id, "set", [{"debtor": debtor, "creditor": creditor, "amount": amount}], operation_id)
        return {"debtor": debtor, "creditor": creditor, "amount": amount}

    async def delete_debt(self, chat_id, debtor, creditor) -> dict:
        return await self.set_debt(chat_id, debtor, creditor, 0)

    async def clear_all_debts(self, chat_id) -> bool:
        # Keep receipts: replaying an old message must not restore cleared debts.
        await self._mutate(chat_id, "clear", [])
        return True


debt_repository = DebtRepository()
