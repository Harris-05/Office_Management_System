from datetime import UTC, datetime

from app import maintenance


def test_maintenance_runs_generation_and_both_retention_jobs_atomically(db_session, monkeypatch):
    calls = []
    now = datetime(2026, 11, 2, tzinfo=UTC)
    monkeypatch.setattr(
        maintenance, "generate_drafts", lambda db, **kw: calls.append((db, kw)) or 3
    )
    monkeypatch.setattr(maintenance, "cleanup_public", lambda db: 2)
    monkeypatch.setattr(maintenance, "cleanup_sessions", lambda db: 4)
    result = maintenance.run_once(db_session, now=now)
    assert result == {"reports_created": 3, "public_submissions_removed": 2, "sessions_removed": 4}
    assert calls == [(db_session, {"now": now, "from_week": None, "limit": 100})]
