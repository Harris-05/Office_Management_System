import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, event, func, select, text
from sqlalchemy.orm import Session
from test_branches import fields
from test_collections import body, update_body

from app import collection_service as service
from app.collection_contracts import CollectionCreate, CollectionUpdate
from app.collection_models import Collection, CollectionEvent
from app.models import User, UserRole
from app.public_models import Branch


@pytest.fixture
def committed_collection(engine, demo_hash):
    with Session(engine) as db:
        user = User(
            email=f"collection-race-{uuid.uuid4().hex}@example.test",
            name="Race Lead",
            role=UserRole.BRANCH_LEAD,
            password_hash=demo_hash,
        )
        db.add(user)
        db.flush()
        branch = Branch(**fields(), slug=uuid.uuid4().hex, status="Active", lead_id=user.id)
        db.add(branch)
        db.flush()
        row = service.create_collection(
            db,
            SimpleNamespace(user=user),
            CollectionCreate(**body(expected_branch_id=str(branch.id))),
        )
        ids = (user.id, branch.id, row.id)
        deadline = row.locks_at
        db.commit()
    yield (*ids, deadline)
    with Session(engine) as db, db.begin():
        collection_ids = select(Collection.id).where(Collection.branch_id == ids[1])
        db.execute(delete(CollectionEvent).where(CollectionEvent.collection_id.in_(collection_ids)))
        db.execute(delete(Collection).where(Collection.branch_id == ids[1]))
        db.execute(delete(Branch).where(Branch.id == ids[1]))
        db.execute(delete(User).where(User.id == ids[0]))


def attempt(engine, user_id, action, record_id=None, payload=None, barrier=None):
    with Session(engine) as db:
        db.execute(text("SET LOCAL statement_timeout='5s'"))
        principal = SimpleNamespace(user=db.get(User, user_id))
        if barrier:
            barrier.wait(timeout=5)
        try:
            if action == "create":
                result = service.create_collection(db, principal, CollectionCreate(**payload))
            else:
                row = db.get(Collection, record_id)
                data = update_body({"version": row.version, **service.values(row)}, amount="22.22")
                result = service.update_collection(
                    db, principal, record_id, CollectionUpdate(**data)
                )
            result_id = result.id
            db.commit()
            return 200, result_id
        except HTTPException as exc:
            db.rollback()
            return exc.status_code, None


def test_edit_rechecks_deadline_after_waiting_for_row(engine, committed_collection, monkeypatch):
    user_id, _, record_id, deadline = committed_collection
    current = [deadline - timedelta(seconds=1)]
    monkeypatch.setattr(service, "utc_now", lambda: current[0])
    waiting = threading.Event()

    def observe(conn, cursor, statement, params, context, executemany):
        if (
            threading.current_thread().name.startswith("ThreadPoolExecutor")
            and "FOR UPDATE OF collections" in statement
        ):
            waiting.set()

    event.listen(engine, "before_cursor_execute", observe)
    try:
        with Session(engine) as holder, ThreadPoolExecutor(max_workers=1) as pool:
            holder.scalar(select(Collection).where(Collection.id == record_id).with_for_update())
            future = pool.submit(attempt, engine, user_id, "update", record_id)
            assert waiting.wait(timeout=5)
            try:
                with pytest.raises(TimeoutError):
                    future.result(timeout=0.15)
            finally:
                current[0] = deadline
                holder.commit()
            assert future.result(timeout=10)[0] == 409
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    with Session(engine) as db:
        assert str(db.get(Collection, record_id).amount) == "10.10"
        assert db.get(Collection, record_id).version == 1


def test_reassignment_revokes_create_after_branch_lock_wait(engine, committed_collection):
    user_id, branch_id, _, _ = committed_collection
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
            future = pool.submit(
                attempt, engine, user_id, "create", payload=body(expected_branch_id=str(branch_id))
            )
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


def test_concurrent_identical_retry_creates_one_entry_and_audit(engine, committed_collection):
    user_id, branch_id, _, _ = committed_collection
    payload = body(amount="30.30", expected_branch_id=str(branch_id))
    barrier = threading.Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(attempt, engine, user_id, "create", payload=payload, barrier=barrier)
            for _ in range(2)
        ]
        results = [future.result(timeout=10) for future in futures]
    assert [result[0] for result in results] == [200, 200]
    assert results[0][1] == results[1][1]
    with Session(engine) as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(Collection)
                .where(Collection.branch_id == branch_id)
            )
            == 2
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(CollectionEvent)
                .where(CollectionEvent.collection_id == results[0][1])
            )
            == 1
        )
