"""Real independent transactions prove branch serialization for report approval."""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
import test_collection_concurrency as collection_races
from fastapi import HTTPException
from sqlalchemy import delete, event, text
from sqlalchemy.orm import Session
from test_collections import body, update_body

from app import collection_service, report_service, transfer_service
from app.collection_contracts import CollectionCreate, CollectionUpdate
from app.collection_models import Collection
from app.membership_contracts import Command
from app.models import User, UserRole
from app.report_contracts import ReportReview
from app.report_models import Report, ReportEvent, ReportRevision
from app.transfer_contracts import TransferCommand
from app.transfer_models import Transfer, TransferEvent, TransferItem

committed_collection = collection_races.committed_collection


@pytest.fixture
def committed_report(engine, committed_collection, demo_hash):
    lead_id, branch_id, collection_id, _ = committed_collection
    with Session(engine) as db:
        reviewer = User(
            email=f"report-race-{uuid.uuid4().hex}@example.test",
            name="Report reviewer",
            role=UserRole.FINANCE_REVIEWER,
            password_hash=demo_hash,
        )
        transfer = Transfer(
            branch_id=branch_id,
            created_by_id=lead_id,
            request_id=uuid.uuid4(),
            creation_fingerprint="0" * 64,
            amount=Decimal("0.01"),
            transferred_on=date(2020, 1, 1),
            reference="Synthetic source transfer",
            notes="",
            status="Submitted",
        )
        report = Report(branch_id=branch_id, week_start=date(2019, 12, 30))
        db.add_all([reviewer, transfer, report])
        db.flush()
        report_service.transition(
            db,
            SimpleNamespace(user=db.get(User, lead_id)),
            report.id,
            "submit",
            Command(expected_version=1, reason="Synthetic submission"),
        )
        ids = (lead_id, branch_id, collection_id, reviewer.id, transfer.id, report.id)
        db.commit()
    yield ids
    with Session(engine) as db, db.begin():
        db.execute(delete(ReportEvent).where(ReportEvent.report_id == ids[5]))
        db.execute(delete(ReportRevision).where(ReportRevision.report_id == ids[5]))
        db.execute(delete(Report).where(Report.id == ids[5]))
        db.execute(delete(TransferEvent).where(TransferEvent.transfer_id == ids[4]))
        db.execute(delete(TransferItem).where(TransferItem.transfer_id == ids[4]))
        db.execute(delete(Transfer).where(Transfer.id == ids[4]))
        db.execute(delete(User).where(User.id == ids[3]))


def approve(engine, reviewer_id, report_id):
    with Session(engine) as db:
        db.execute(text("SET LOCAL statement_timeout='5s'"))
        principal = SimpleNamespace(user=db.get(User, reviewer_id))
        try:
            report_service.transition(
                db,
                principal,
                report_id,
                "approve",
                ReportReview(
                    expected_version=2, reason="Concurrent independent review", acknowledge=True
                ),
            )
            db.commit()
            return 200
        except HTTPException as error:
            db.rollback()
            return error.status_code


@pytest.mark.parametrize("source_change", ["edit", "add", "transfer_confirm"])
def test_approval_waits_for_source_writer_and_rejects_changed_snapshot(
    engine, committed_report, source_change
):
    lead_id, branch_id, collection_id, reviewer_id, transfer_id, report_id = committed_report
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
        with Session(engine) as writer, ThreadPoolExecutor(max_workers=1) as pool:
            principal = SimpleNamespace(user=writer.get(User, lead_id))
            if source_change == "edit":
                collection = writer.get(Collection, collection_id)
                values = {"version": collection.version, **collection_service.values(collection)}
                collection_service.update_collection(
                    writer,
                    principal,
                    collection_id,
                    CollectionUpdate(**update_body(values, amount="22.22")),
                )
            elif source_change == "add":
                collection_service.create_collection(
                    writer,
                    principal,
                    CollectionCreate(
                        **body(
                            expected_branch_id=str(branch_id),
                            collected_on="2020-01-02",
                            amount="0.02",
                        )
                    ),
                )
            else:
                transfer_service.transition(
                    writer,
                    SimpleNamespace(user=writer.get(User, reviewer_id)),
                    transfer_id,
                    "confirm",
                    TransferCommand(expected_version=1, reason="Synthetic receipt"),
                )
            future = pool.submit(approve, engine, reviewer_id, report_id)
            assert waiting.wait(timeout=5)
            try:
                with pytest.raises(TimeoutError):
                    future.result(timeout=0.15)
            finally:
                writer.commit()
            assert future.result(timeout=10) == 409
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    with Session(engine) as db:
        report = db.get(Report, report_id)
        assert report.status == "Submitted" and report.version == 2
        assert report.snapshot["collection_total"] == "10.10"
        assert report.snapshot["transfer_status_totals"]["Submitted"] == "0.01"
