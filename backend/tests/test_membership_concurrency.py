import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, event, func, select, text
from sqlalchemy.orm import Session
from test_membership import application

from app.membership_contracts import ReviewCommand
from app.membership_models import ApplicationEvent, Member, MemberEvent
from app.membership_service import review_application
from app.models import User, UserRole
from app.public_models import Branch, PublicSubmission


@pytest.fixture
def committed_cases(engine, demo_hash):
    actor_ids, application_ids, branch_ids = [], [], []

    def create():
        with Session(engine) as db:
            actor = User(
                email=f"race-{uuid.uuid4().hex}@example.test",
                name="Race test HR",
                role=UserRole.HR_LEAD,
                password_hash=demo_hash,
            )
            db.add(actor)
            db.flush()
            actor_ids.append(actor.id)
            row, branch = application(db)
            application_ids.append(row.id)
            branch_ids.append(branch.id)
            return actor.id, row.id, branch.id

    yield create
    with Session(engine) as db, db.begin():
        ids = select(Member.id).where(Member.source_id.in_(application_ids))
        db.execute(delete(MemberEvent).where(MemberEvent.member_id.in_(ids)))
        db.execute(delete(Member).where(Member.source_id.in_(application_ids)))
        db.execute(
            delete(ApplicationEvent).where(ApplicationEvent.application_id.in_(application_ids))
        )
        db.execute(delete(PublicSubmission).where(PublicSubmission.id.in_(application_ids)))
        db.execute(delete(Branch).where(Branch.id.in_(branch_ids)))
        db.execute(delete(User).where(User.id.in_(actor_ids)))


def decide(engine, actor_id, application_id, barrier=None, errors=None):
    with Session(engine) as db:
        db.execute(text("SET LOCAL statement_timeout='5s'"))
        actor = db.scalar(select(User).where(User.id == actor_id).with_for_update())
        if barrier:
            barrier.wait(timeout=5)
        try:
            review_application(
                db,
                SimpleNamespace(user=actor),
                application_id,
                ReviewCommand(
                    expected_version=1, decision="Accepted", reason="Concurrent review test"
                ),
            )
            db.commit()
            return 200
        except HTTPException as exc:
            db.rollback()
            if errors is not None:
                errors.append(exc.detail)
            return exc.status_code


@pytest.mark.parametrize("same_application", [True, False])
def test_concurrent_acceptance_creates_exactly_one_member(
    engine, committed_cases, same_application
):
    first_actor, first_id, _ = committed_cases()
    second_actor, second_id, _ = committed_cases()
    with Session(engine) as db, db.begin():
        one = db.get(PublicSubmission, first_id)
        db.get(PublicSubmission, second_id).email = one.email
    target_ids = [first_id, first_id if same_application else second_id]
    barrier = threading.Barrier(2)
    errors = []
    insert_barrier = threading.Barrier(2)

    def simultaneous_insert(mapper, connection, target):
        insert_barrier.wait(timeout=5)

    if not same_application:
        event.listen(Member, "before_insert", simultaneous_insert)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(decide, engine, actor, target, barrier, errors)
                for actor, target in zip([first_actor, second_actor], target_ids, strict=True)
            ]
            assert sorted(item.result(timeout=10) for item in futures) == [200, 409]
        assert len(errors) == 1
        if not same_application:
            assert "MEM-" in errors[0]
    finally:
        if not same_application:
            event.remove(Member, "before_insert", simultaneous_insert)
    with Session(engine) as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(Member)
                .where(Member.source_id.in_([first_id, second_id]))
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(ApplicationEvent)
                .where(ApplicationEvent.application_id.in_([first_id, second_id]))
            )
            == 1
        )


def test_branch_close_wins_while_acceptance_waits_on_branch(engine, committed_cases):
    actor_id, record_id, branch_id = committed_cases()
    attempted = threading.Event()

    def observe(conn, cursor, statement, params, context, executemany):
        if threading.current_thread().name.startswith("ThreadPoolExecutor") and (
            "public_branches" in statement and "FOR UPDATE" in statement
        ):
            attempted.set()

    event.listen(engine, "before_cursor_execute", observe)
    try:
        with Session(engine) as holder, ThreadPoolExecutor(max_workers=1) as pool:
            branch = holder.scalar(select(Branch).where(Branch.id == branch_id).with_for_update())
            future = pool.submit(decide, engine, actor_id, record_id)
            assert attempted.wait(timeout=5)
            try:
                with pytest.raises(TimeoutError):
                    future.result(timeout=0.15)
            finally:
                branch.status = "Closed"
                branch.is_published = False
                holder.commit()
            assert future.result(timeout=10) == 422
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    with Session(engine) as db:
        assert db.get(PublicSubmission, record_id).review_status == "Pending"
        assert (
            db.scalar(select(func.count()).select_from(Member).where(Member.source_id == record_id))
            == 0
        )
