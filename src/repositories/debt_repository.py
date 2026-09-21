import logging
from google.cloud import firestore
from src.services.db import db

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

debt_repository = DebtRepository()
