"""Debt regressions; all persistence is isolated from production Firestore."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from src.repositories import debt_repository as repository_module
from src.repositories.debt_repository import DebtRepository
from src.services.debt_service import DebtService
from src.utils.game_config import config


class MemoryRef:
    def __init__(self, store, path):
        self.store, self.path = store, path

    async def get(self, transaction=None):
        value = deepcopy(self.store.get(self.path))
        return SimpleNamespace(exists=value is not None, to_dict=lambda: value)


class MemoryTransaction:
    def __init__(self, store):
        self.store, self.writes = store, []

    def set(self, ref, value, merge=False):
        self.writes.append((ref.path, deepcopy(value), merge))

    def commit(self):
        for path, value, merge in self.writes:
            if merge is True:
                # Firestore's recursive merge: removed leaves remain present.
                target = self.store.setdefault(path, {})
                for debtor, row in value.get("balances", {}).items():
                    target.setdefault("balances", {}).setdefault(debtor, {}).update(row)
            elif merge:
                for key in merge:
                    self.store.setdefault(path, {})[key] = value[key]
            else:
                self.store[path] = value


class MemoryEvents:
    def __init__(self, store, chat):
        self.store, self.chat = store, str(chat)

    async def stream(self, transaction=None):
        for (chat, key), value in list(self.store.items()):
            if chat == self.chat and key != "matrix":
                snapshot = deepcopy(value)
                yield SimpleNamespace(to_dict=lambda value=snapshot: value)


@pytest.fixture
def repo(monkeypatch):
    store, lock = {}, asyncio.Lock()

    def transactional(callback):
        async def run(transaction):
            async with lock:
                result = await callback(transaction)
                transaction.commit()
                return result
        return run

    monkeypatch.setattr(repository_module.firestore, "async_transactional", transactional)
    instance = DebtRepository()
    instance.db = SimpleNamespace(transaction=lambda: MemoryTransaction(store))
    monkeypatch.setattr(instance, "_get_ref", lambda chat: MemoryRef(store, (str(chat), "matrix")))
    monkeypatch.setattr(instance, "_event_ref", lambda chat, op: MemoryRef(store, (str(chat), op)))
    monkeypatch.setattr(instance, "_events_ref", lambda chat: MemoryEvents(store, chat))
    instance.store = store
    return instance


def tx(amount=500, **changes):
    return {"debtor": "Alice", "creditor": "Bob", "amount": amount, "is_settled": False, **changes}


@pytest.mark.asyncio
async def test_delete_and_clear_replace_map_preserving_unrelated_balances(repo):
    await repo.set_debt(1, "Alice", "Bob", 500)
    await repo.set_debt(1, "Carol", "Bob", 200)
    await repo.delete_debt(1, "@ALICE", " bob ")
    assert await repo.get_debts(1) == {"carol": {"bob": 200}}
    await repo.clear_all_debts(1)
    assert await repo.get_debts(1) == {}


@pytest.mark.asyncio
async def test_repay_caps_to_balance_and_does_not_create_reverse_debt(repo):
    await repo.update_debts(1, [tx()])
    applied = await repo.update_debts(1, [tx(900, is_settled=True)])
    assert applied[0]["amount"] == 500
    assert await repo.get_debts(1) == {}
    assert await repo.update_debts(1, [tx(50, is_settled=True)]) == []


@pytest.mark.asyncio
async def test_same_message_once_even_concurrent_and_after_clear(repo):
    results = await asyncio.gather(*[
        repo.update_debts(1, [tx()], operation_id="message:42") for _ in range(12)
    ])
    assert sum(len(result) for result in results) == 1
    assert await repo.get_debts(1) == {"alice": {"bob": 500}}
    await repo.clear_all_debts(1)
    assert await repo.update_debts(1, [tx()], operation_id="message:42") == []
    assert await repo.get_debts(1) == {}


@pytest.mark.asyncio
async def test_distinct_equal_operations_and_chat_isolation(repo):
    await repo.update_debts(1, [tx()], operation_id="message:42")
    await repo.update_debts(1, [tx()], operation_id="message:43")
    await repo.update_debts(2, [tx()], operation_id="message:42")
    assert await repo.get_debts(1) == {"alice": {"bob": 1000}}
    assert await repo.get_debts(2) == {"alice": {"bob": 500}}


@pytest.mark.asyncio
async def test_loan_found_after_live_repayment_replayed_in_source_order(repo):
    start = datetime(2026, 10, 29, tzinfo=timezone.utc)
    # A spontaneous comment saw the repayment; daily analysis later finds the loan.
    assert await repo.update_debts(1, [tx(200, is_settled=True)], operation_id="message:10", occurred_at=start + timedelta(minutes=1)) == []
    await repo.update_debts(1, [tx()], operation_id="message:9", occurred_at=start)
    assert await repo.get_debts(1) == {"alice": {"bob": 300}}


@pytest.mark.asyncio
async def test_late_loan_recalculates_previously_capped_repayment(repo):
    start = datetime(2026, 10, 29, tzinfo=timezone.utc)
    await repo.update_debts(1, [tx(100)], operation_id="message:9", occurred_at=start)
    await repo.update_debts(1, [tx(400, is_settled=True)], operation_id="message:11", occurred_at=start + timedelta(minutes=2))
    await repo.update_debts(1, [tx(500)], operation_id="message:10", occurred_at=start + timedelta(minutes=1))
    assert await repo.get_debts(1) == {"alice": {"bob": 200}}


@pytest.mark.asyncio
async def test_late_source_does_not_undo_manual_set_or_clear(repo):
    start = datetime(2026, 10, 29, tzinfo=timezone.utc) - timedelta(days=365)
    await repo.set_debt(1, "alice", "bob", 50)
    await repo.update_debts(1, [tx()], operation_id="message:9", occurred_at=start)
    assert await repo.get_debts(1) == {"alice": {"bob": 50}}
    await repo.clear_all_debts(1)
    await repo.update_debts(1, [tx()], operation_id="message:10", occurred_at=start + timedelta(minutes=1))
    assert await repo.get_debts(1) == {}


@pytest.mark.asyncio
async def test_upgrade_preserves_legacy_balances_and_skips_pre_upgrade_logs(repo):
    cutover = datetime(2026, 10, 29, tzinfo=timezone.utc)
    repo.store[("1", "matrix")] = {"balances": {"alice": {"bob": 500}}, "other_metadata": "preserved"}
    await repo.initialize_journal(1, started_at=cutover)
    await repo.initialize_journal(1, started_at=cutover + timedelta(days=1))
    assert await repo.update_debts(1, [tx()], operation_id="message:1", occurred_at=cutover - timedelta(minutes=1)) == []
    await repo.update_debts(1, [tx(200)], operation_id="message:2", occurred_at=cutover + timedelta(minutes=1))
    assert await repo.get_debts(1) == {"alice": {"bob": 700}}
    assert repo.store[("1", "matrix")]["other_metadata"] == "preserved"


@pytest.mark.asyncio
async def test_repeated_admin_delta_and_partial_repayment(repo):
    await repo.update_debts(1, [tx()], operation_id="admin:create:uuid")
    await repo.update_debts(1, [tx()], operation_id="admin:create:uuid")
    await repo.update_debts(1, [tx(200, is_settled=True)], operation_id="admin:settle:uuid")
    await repo.update_debts(1, [tx(200, is_settled=True)], operation_id="admin:settle:uuid")
    assert await repo.get_debts(1) == {"alice": {"bob": 300}}


@pytest.mark.parametrize("changes", [
    {"amount": -1}, {"amount": 0}, {"amount": 1.5}, {"amount": True},
    {"amount": "500"}, {"amount": 10000001}, {"debtor": " @ "},
    {"creditor": "@alice"}, {"is_settled": "false"},
])
@pytest.mark.asyncio
async def test_invalid_batch_never_partially_applied(repo, changes):
    with pytest.raises(ValueError):
        await repo.update_debts(1, [tx(), tx(**changes)])
    assert repo.store == {}


@pytest.mark.asyncio
async def test_spelling_normalized_without_merging_real_equal_transactions(repo):
    await repo.update_debts(1, [tx(debtor=" @ALICE "), tx(debtor="alice")])
    summary = await repo.get_debts_summary(1)
    assert summary["debts_count"] == 1
    assert summary["total_debt_amount"] == 1000


@pytest.fixture
def service(monkeypatch, repo):
    from src.services import debt_service
    monkeypatch.setattr(debt_service, "debt_repository", repo)
    monkeypatch.setattr(config, "ENABLE_DEBTS", True)
    monkeypatch.setattr(config, "BOT_DISABLED", False)
    monkeypatch.setattr(DebtService, "party_index", AsyncMock(return_value={
        "alice": {"alice"}, "алиса": {"alice"}, "bob": {"bob"}, "боб": {"bob"},
        "саша": {"alex1", "alex2"},
    }))
    return DebtService


@pytest.mark.asyncio
async def test_live_daily_and_scan_share_receipt_and_only_report_applied(service, repo):
    transaction = tx(source_message_id="42", reason="такси")
    sources = [{"message_id": "42", "user_id": 1, "username": "alice"}]
    assert len(await service.apply(1, [transaction, transaction], sources)) == 1
    alias = {**transaction, "debtor": "алиса", "creditor": "боб", "reason": "другая формулировка"}
    assert await service.apply(1, [alias], sources) == []
    assert service.format_updates([]) == ""
    assert await repo.get_debts(1) == {"alice": {"bob": 500}}


@pytest.mark.parametrize("transaction,sources", [
    (tx(), [{"message_id": "42"}]),
    (tx(source_message_id="99"), [{"message_id": "42"}]),
    (tx(source_message_id="42"), [{"message_id": "42", "is_bot": True}]),
    (tx(source_message_id="42", debtor="саша"), [{"message_id": "42"}]),
])
@pytest.mark.asyncio
async def test_unknown_sources_bots_and_ambiguous_participants_skipped(service, repo, transaction, sources):
    assert await service.apply(1, [transaction], sources) == []
    assert repo.store == {}


@pytest.mark.asyncio
async def test_batch_order_by_telegram_id_and_disable_flag(service, repo, monkeypatch):
    sources = [{"message_id": "10"}, {"message_id": "9"}]
    applied = await service.apply(1, [tx(200, source_message_id="10", is_settled=True), tx(source_message_id="9")], sources)
    assert [item["source_message_id"] for item in applied] == ["9", "10"]
    assert await repo.get_debts(1) == {"alice": {"bob": 300}}
    monkeypatch.setattr(config, "ENABLE_DEBTS", False)
    assert await service.apply(1, [tx(source_message_id="11")], [{"message_id": "11"}]) == []


@pytest.mark.parametrize("amount", [0, -1, 1.5, True, "500"])
def test_api_rejects_invalid_repayment_before_db(amount):
    from src.admin.router import DebtSettleRequest
    with pytest.raises(ValidationError):
        DebtSettleRequest(debtor="alice", creditor="bob", amount=amount)


@pytest.mark.parametrize("party", [" ", "@@", "@ "])
def test_api_rejects_blank_normalized_participants(party):
    from src.admin.router import DebtCreateUpdateRequest
    with pytest.raises(ValidationError):
        DebtCreateUpdateRequest(debtor=party, creditor="bob", amount=500)


@pytest.mark.asyncio
async def test_party_resolution_uses_exact_unique_aliases_and_pages(monkeypatch):
    from src.services import debt_service
    users = AsyncMock(side_effect=[([
        {"user_id": "1", "username": "alice", "full_name": "Александра"},
        {"user_id": "2", "username": "bob", "full_name": "Александра"},
    ], "next"), ([{"user_id": "3", "username": "carol", "full_name": "Каролина"}], None)])
    monkeypatch.setattr(debt_service.user_repository, "get_chat_users", users)
    monkeypatch.setattr(debt_service.LoreService, "get_lore", AsyncMock(return_value={"core": {"characters": [
        {"handle": "alice", "names": ["Лиса", "Лисе"]},
    ]}}))
    index = await DebtService.party_index(1, [{"user_id": 1, "first_name": "Александра"}])
    assert index["лисе"] == {"alice"}
    assert index["александра"] == {"alice", "bob"}
    assert index["каролина"] == {"carol"}
    assert "алекс" not in index
    assert users.await_count == 2


def test_invalid_ai_debt_does_not_discard_comment_or_other_debts():
    from src.models.ai import CynicalCommentResult
    result = CynicalCommentResult(comment="Ответ", debt_transactions=[tx(amount=-50), tx()])
    assert result.comment == "Ответ"
    assert len(result.debt_transactions) == 1


def test_firestore_merge_mask_replaces_whole_balances_map():
    from google.cloud.firestore_v1._helpers import pbs_for_set_with_merge
    writes = pbs_for_set_with_merge("projects/test/databases/(default)/documents/chats/1/debts/matrix", {
        "balances": {"alice": {"bob": 500}},
    }, ["balances"])
    assert list(writes[0].update_mask.field_paths) == ["balances"]


@pytest.mark.asyncio
async def test_admin_preserves_displayed_legacy_pair_when_alias_can_resolve(monkeypatch):
    from src.admin import router
    monkeypatch.setattr(router.debt_repository, "get_debts", AsyncMock(return_value={"лиса": {"боб": 500}}))
    resolve = AsyncMock(return_value=("alice", "bob"))
    monkeypatch.setattr(router.DebtService, "resolve_manual_pair", resolve)
    assert await router.resolve_debt_parties(1, "@Лиса", "Боб") == ("лиса", "боб")
    resolve.assert_not_awaited()
