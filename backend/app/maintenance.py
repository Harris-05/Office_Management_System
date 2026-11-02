"""Repeat-safe hourly report drafting and existing retention jobs."""

import argparse
import logging
import time
from datetime import date

from sqlalchemy.orm import Session

from app.cleanup_public import cleanup as cleanup_public
from app.cleanup_sessions import cleanup as cleanup_sessions
from app.database import get_engine

logger = logging.getLogger(__name__)


def generate_drafts(db, **kwargs):
    from app.report_service import generate_drafts as generate

    return generate(db, **kwargs)


def run_once(db, now=None, from_week=None, limit=100):
    return {
        "reports_created": generate_drafts(db, now=now, from_week=from_week, limit=limit),
        "public_submissions_removed": cleanup_public(db),
        "sessions_removed": cleanup_sessions(db),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Run one bounded transaction for cron.")
    parser.add_argument("--interval", type=int, default=3600)
    parser.add_argument("--from-week", type=date.fromisoformat)
    args = parser.parse_args()
    if args.interval < 60:
        parser.error("Worker interval must be at least60seconds.")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    while True:
        try:
            with Session(get_engine()) as db, db.begin():
                result = run_once(db, from_week=args.from_week)
            logger.info("Maintenance completed: %s", result)
        except Exception as exc:
            logger.error("Maintenance failed (%s); transaction rolled back.", type(exc).__name__)
            if args.once:
                raise SystemExit(1) from None
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
