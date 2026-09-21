from pydantic import BaseModel, Field
from typing import List, Optional

class NewAgreement(BaseModel):
    text: str = Field(description="Описание договоренности СТРОГО НА РУССКОМ")
    users: List[str] = Field(description="Список участников (username без @)")
    type: str = Field(description="vow | pact | public")
    expires_at: Optional[str] = Field(None, description="YYYY-MM-DDTHH:MM:SS")
    reasoning: str = Field(description="Почему ты решил, что это договоренность?")

class ResolvedAgreement(BaseModel):
    id: str = Field(description="ID документа договоренности")
    status: str = Field(description="fulfilled | broken")
    reason: str = Field(description="Причина решения (например, цитата нарушения или выполнения)")

class UpdatedAgreement(BaseModel):
    id: str = Field(description="ID документа договоренности")
    text: str = Field(description="Обновленный текст договоренности СТРОГО НА РУССКОМ")
    reason: str = Field(description="Почему потребовалось обновление (например: присоединился новый участник, перенесли дату/время встречи)?")
    users: Optional[List[str]] = Field(None, description="Обновленный полный список участников (username без @), если кто-то присоединился или вышел")
    expires_at: Optional[str] = Field(None, description="Новая дата/время истечения YYYY-MM-DDTHH:MM:SS, если перенесли срок")

class Offender(BaseModel):
    user_id: Optional[int] = Field(None, description="Telegram User ID (если известен)")
    username: str = Field(description="Username или имя участника")
    category: str = Field(description="Категория нарушения: Toxicity | Snitching")
    points: int = Field(description="Количество очков")
    reason: str = Field(description="Обоснование вердикта")
    quote: Optional[str] = Field(None, description="Цитата сообщения с нарушением")

class DebtTransaction(BaseModel):
    debtor: str = Field(description="Кто должен деньги (username или имя, без @).")
    creditor: str = Field(description="Кому должны (username или имя, без @)")
    amount: int = Field(description="Сумма долга (в числах, например 500)")
    reason: str = Field(description="За что долг (например: за шаурму, за такси, скинулись на ДР)")
    is_settled: bool = Field(default=False, description="True если это сообщение о ВОЗВРАТЕ долга")

class DailyAnalysisResult(BaseModel):
    thought_process: str = Field(description="Подробный разбор полетов и анализ ситуации перед вынесением вердикта")
    offenders: List[Offender] = Field(default_factory=list, description="Список нарушителей")
    new_agreements: List[NewAgreement] = Field(default_factory=list, description="Список новых договоренностей")
    resolved_agreements: List[ResolvedAgreement] = Field(default_factory=list, description="Список завершенных/нарушенных договоренностей")
    updated_agreements: List[UpdatedAgreement] = Field(default_factory=list, description="Список обновленных договоренностей")
    debt_transactions: List[DebtTransaction] = Field(default_factory=list, description="Новые долги или возвраты долгов, упомянутые в чате")

class ReportValidationResult(BaseModel):
    thought_process: str = Field("", description="Размышления о контексте и справедливости жалобы")
    valid: bool = Field(description="Является ли жалоба обоснованной")
    status: str = Field("rejected", description="accepted | rejected | technical_error | insufficient_data")
    category: Optional[str] = Field(None, description="Категория: Toxicity | Snitching")
    points: int = Field(0, description="Очки за нарушение (если есть)")
    reason: str = Field(description="Вердикт и причина решения")

class FactValidationResult(BaseModel):
    is_fact: bool = Field(description="Является ли текст историческим фактом")
    cleaned_fact: Optional[str] = Field(None, description="Отредактированный текст факта на русском")
    reason: str = Field(description="Почему это факт или почему отклонено")

class MemoryEvent(BaseModel):
    title: str = Field(description="Название события")
    participants: List[str] = Field(description="Участники события")
    outcome: str = Field(description="Итог события")

class MemorySummaryResult(BaseModel):
    summary: str = Field(description="Общий итог дня одной-двумя фразами")
    key_facts: List[str] = Field(description="Список ключевых фактов")
    emotional_vibe: str = Field(description="Описание настроения")
    major_events: List[MemoryEvent] = Field(description="Список главных событий")

class FeedbackAnalysisResult(BaseModel):
    verdict: str = Field(description="справедливо | ошибка | непонятно")
    reasoning: str = Field(description="Обоснование оценки реакции")
    learned_rule: Optional[str] = Field(None, description="Сформулированное правило поведения, если нужно")

class CynicalCommentResult(BaseModel):
    comment: str = Field(description="Текст комментария (1-2 емких предложения)")
    award_points: bool = Field(default=False, description="Вынести ли официальный судебный вердикт прямо сейчас")
    target_username: Optional[str] = Field(None, description="Username или имя участника для начисления/снятия очков")
    points_delta: int = Field(default=0, description="Дельта очков (+25..+75 за масть, -25..-50 за людское)")
    reason: Optional[str] = Field(None, description="Краткая причина вердикта")
    debt_transactions: List[DebtTransaction] = Field(default_factory=list, description="Если в сообщении идет речь о долгах, расходах или переводах, зафиксируй их здесь")
