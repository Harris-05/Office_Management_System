import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from types import SimpleNamespace

import pytest
import test_collection_concurrency as collection_races
from fastapi import HTTPException
from sqlalchemy import delete, event, func, select, text
from sqlalchemy.orm import Session
from test_transfers import payload

from app import transfer_service as service
from app.models import User, UserRole
from app.public_models import Branch
from app.transfer_contracts import TransferCommand, TransferCreate
from app.transfer_models import Transfer, TransferEvent, TransferItem

committed_collection = collection_races.committed_collection


@pytest.fixture
def transferable(engine, committed_collection, demo_hash, monkeypatch):
    user_id, branch_id, collection_id, deadline = committed_collection
    monkeypatch.setattr(service, "utc_now", lambda: deadline)
    with Session(engine) as db:
        reviewer = User(
            email=f"transfer-review-{uuid.uuid4().hex}@example.test",
            name="Transfer race reviewer",
            role=UserRole.FINANCE_REVIEWER,
            password_hash=demo_hash,
        )
        db.add(reviewer)
        db.commit()
        reviewer_id = reviewer.id
    yield user_id, branch_id, collection_id, reviewer_id
    with Session(engine) as db, db.begin():
        ids = select(Transfer.id).where(Transfer.branch_id == branch_id)
        db.execute(delete(TransferEvent).where(TransferEvent.transfer_id.in_(ids)))
        db.execute(delete(TransferItem).where(TransferItem.transfer_id.in_(ids)))
        db.execute(delete(Transfer).where(Transfer.branch_id == branch_id))
        db.execute(delete(User).where(User.id == reviewer_id))


def attempt(engine, user_id, data, record_id=None, action=None, barrier=None):
    with Session(engine) as db:
        db.execute(text("SET LOCAL statement_timeout='5s'"))
        principal = SimpleNamespace(user=db.get(User, user_id))
        if barrier:
            barrier.wait(timeout=5)
        try:
            if record_id:
                row = service.transition(db, principal, record_id, action, TransferCommand(**data))
            else:
                row = service.create_transfer(db, principal, TransferCreate(**data))
            result = row.id
            db.commit()
            return 200, result
        except HTTPException as exc:
            db.rollback()
            return exc.status_code, None


@pytest.mark.parametrize("same_request", [False, True])
def test_concurrent_transfer_reserves_collection_once(engine, transferable, same_request):
    lead_id, branch_id, collection_id, _ = transferable
    data = payload(SimpleNamespace(id=branch_id), [{"id": str(collection_id)}])
    other = data if same_request else {**data, "request_id": str(uuid.uuid4())}
    barrier = threading.Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(attempt, engine, lead_id, body, barrier=barrier) for body in [data, other]
        ]
        results = [future.result(timeout=10) for future in futures]
    assert sorted(r[0] for r in results) == ([200, 200] if same_request else [200, 409])
    with Session(engine) as db:
        transfer_id = next(value for status, value in results if status == 200)
        assert (
            db.scalar(
                select(func.count())
                .select_from(TransferItem)
                .where(TransferItem.collection_id == collection_id, TransferItem.is_active)
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(TransferEvent)
                .where(TransferEvent.transfer_id == transfer_id)
            )
            == 1
        )


def test_simultaneous_finance_decisions_have_one_winner(engine, transferable):
    lead_id, branch_id, collection_id, reviewer_id = transferable
    data = payload(SimpleNamespace(id=branch_id), [{"id": str(collection_id)}])
    _, record_id = attempt(engine, lead_id, data)
    barrier = threading.Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                attempt,
                engine,
                reviewer_id,
                {"expected_version": 1, "reason": "Concurrent review"},
                record_id,
                action,
                barrier,
            )
            for action in ["confirm", "return"]
        ]
        assert sorted(f.result(timeout=10)[0] for f in futures) == [200, 409]
    with Session(engine) as db:
        row = db.get(Transfer, record_id)
        item = db.scalar(select(TransferItem).where(TransferItem.transfer_id == record_id))
        assert row.version == 2
        assert item.is_active == (row.status == "Confirmed")


def test_transfer_rechecks_assignment_after_branch_lock(engine, transferable):
    lead_id, branch_id, collection_id, _ = transferable
    data = payload(SimpleNamespace(id=branch_id), [{"id": str(collection_id)}])
    waiting = threading.Event()

    def observe(conn, cursor, statement, params, context, executemany):
        if (
            threading.current_thread().name.startswith("ThreadPoolExecutor")
            and "public_branches" in statement
            and "FOR UPDATE" in statement
        ):
            waiting.set()

    event.listen(engine, "before_cursor_execute", observe)
    try:
        with Session(engine) as holder, ThreadPoolExecutor(max_workers=1) as pool:
            branch = holder.scalar(select(Branch).where(Branch.id == branch_id).with_for_update())
            future = pool.submit(attempt, engine, lead_id, data)
            assert waiting.wait(timeout=5)
            try:
                with pytest.raises(TimeoutError):
                    future.result(timeout=0.15)
            finally:
                branch.lead_id = None
                holder.commit()
            assert future.result(timeout=10)[0] == 403
    finally:
        event.remove(engine, "before_cursor_execute", observe)
