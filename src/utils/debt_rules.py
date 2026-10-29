DEBT_EXTRACTION_RULES = """
ПРАВИЛА ДОЛГОВ (применяются ко всем debt_transactions):
- Фиксируй только явный новый долг или фактический возврат с точной суммой в целых рублях.
- source_message_id — строка с MsgID ПЕРВОГО сообщения, которое сообщает об этой операции.
  Не используй ID ответа «да», напоминания, пересказа, цитаты, сообщения бота или будущего контекста.
- Контекст и текущая долговая книга нужны для понимания, сами по себе они НЕ новые операции.
  Не фиксируй повторные обсуждения, текущий остаток, обещания, планы, шутки, подарки и обычные переводы без явного долга.
- «А заплатил за Б 500» -> debtor=Б, creditor=А, amount=500, is_settled=false.
  «Б вернул А 200» -> debtor=Б, creditor=А, amount=200, is_settled=true.
- Для участников используй точные username без @ из сообщений/лора. Не угадывай человека по части имени.
- Одну операцию включай один раз. Если источник, участники или сумма неясны, верни пустой список.
"""


def debt_transactions_schema():
    return {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "debtor": {"type": "STRING", "description": "Username должника без @"},
                "creditor": {"type": "STRING", "description": "Username кредитора без @"},
                "amount": {"type": "INTEGER", "description": "Положительная сумма в целых рублях"},
                "reason": {"type": "STRING", "description": "За что долг"},
                "is_settled": {"type": "BOOLEAN", "description": "True только для возврата долга"},
                "source_message_id": {"type": "STRING", "description": "MsgID первого сообщения о новой операции"},
            },
            "required": ["debtor", "creditor", "amount", "is_settled", "source_message_id"],
        },
        "description": "Новые операции с доказуемым источником; не остатки и не повторные упоминания",
    }
