from __future__ import annotations
from typing import Optional, List, Dict, Any
import logging
from google.cloud import firestore
from src.database import db

logger = logging.getLogger(__name__)

class DebtRepository:
    def __init__(self):
        self.db = db

    def _get_ref(self, chat_id: str | int):
        return self.db.collection("chats").document(str(chat_id)).collection("debts").document("matrix")

    async def get_debts(self, chat_id: str | int) -> dict:
        doc = await self._get_ref(chat_id).get()
        if doc.exists:
            return doc.to_dict().get("balances", {})
        return {}

    async def get_debts_summary(self, chat_id: str | int) -> dict:
        balances = await self.get_debts(chat_id)
        items = []
        total_amount = 0
        debtor_totals = {}
        creditor_totals = {}

        for debtor, creditors in balances.items():
            for creditor, amount in creditors.items():
                if amount > 0:
                    items.append({
                        "debtor": debtor,
                        "creditor": creditor,
                        "amount": amount
                    })
                    total_amount += amount
                    debtor_totals[debtor] = debtor_totals.get(debtor, 0) + amount
                    creditor_totals[creditor] = creditor_totals.get(creditor, 0) + amount

        top_debtor = max(debtor_totals.items(), key=lambda x: x[1])[0] if debtor_totals else None
        top_creditor = max(creditor_totals.items(), key=lambda x: x[1])[0] if creditor_totals else None

        # Sort items by amount descending
        items.sort(key=lambda x: x["amount"], reverse=True)

        return {
            "balances": balances,
            "items": items,
            "total_debt_amount": total_amount,
            "debts_count": len(items),
            "top_debtor": top_debtor,
            "top_debtor_amount": debtor_totals.get(top_debtor, 0) if top_debtor else 0,
            "top_creditor": top_creditor,
            "top_creditor_amount": creditor_totals.get(top_creditor, 0) if top_creditor else 0
        }

    async def update_debts(self, chat_id: str | int, transactions: list):
        if not transactions:
            return

        ref = self._get_ref(chat_id)
        
        @firestore.async_transactional
        async def update_in_transaction(transaction, ref):
            doc = await ref.get(transaction=transaction)
            balances = {}
            if doc.exists:
                balances = doc.to_dict().get("balances", {})

            for t in transactions:
                debtor = t.get("debtor", "").strip().lower()
                creditor = t.get("creditor", "").strip().lower()
                amount = int(t.get("amount", 0))
                is_settled = t.get("is_settled", False)
                
                if debtor == creditor or amount <= 0:
                    continue

                if debtor not in balances:
                    balances[debtor] = {}
                
                current_debt = balances[debtor].get(creditor, 0)
                
                if is_settled:
                    # Debtor paid creditor
                    new_debt = max(0, current_debt - amount)
                    balances[debtor][creditor] = new_debt
                else:
                    # Debtor owes creditor more
                    balances[debtor][creditor] = current_debt + amount

            transaction.set(ref, {"balances": balances}, merge=True)

        transaction = self.db.transaction()
        await update_in_transaction(transaction, ref)

    async def set_debt(self, chat_id: str | int, debtor: str, creditor: str, amount: int) -> dict:
        """Sets exact debt amount from debtor to creditor. If <= 0, clears the debt."""
        debtor = debtor.strip().lower()
        creditor = creditor.strip().lower()
        amount = max(0, int(amount))

        ref = self._get_ref(chat_id)

        @firestore.async_transactional
        async def _set_txn(transaction, ref):
            doc = await ref.get(transaction=transaction)
            balances = {}
            if doc.exists:
                balances = doc.to_dict().get("balances", {})

            if debtor not in balances:
                balances[debtor] = {}

            if amount > 0:
                balances[debtor][creditor] = amount
            else:
                balances[debtor].pop(creditor, None)

            transaction.set(ref, {"balances": balances}, merge=True)
            return balances

        transaction = self.db.transaction()
        new_balances = await _set_txn(transaction, ref)
        return {"debtor": debtor, "creditor": creditor, "amount": amount, "balances": new_balances}

    async def delete_debt(self, chat_id: str | int, debtor: str, creditor: str) -> dict:
        """Completely deletes a debt relationship between debtor and creditor."""
        return await self.set_debt(chat_id, debtor, creditor, 0)

    async def clear_all_debts(self, chat_id: str | int) -> bool:
        """Clears all debts in the chat."""
        ref = self._get_ref(chat_id)
        await ref.set({"balances": {}})
        return True

debt_repository = DebtRepository()
