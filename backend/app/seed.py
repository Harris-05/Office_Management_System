"""Explicit, idempotent demo seeding: python -m app.seed --demo."""

import argparse

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_engine
from app.models import User, UserRole
from app.passwords import hash_password
from app.users import find_user_by_email

DEMO_ACCOUNTS = [
    ("admin@example.test", "Demo Admin", UserRole.SUPER_ADMIN),
    ("finance@example.test", "Demo Finance Reviewer", UserRole.FINANCE_REVIEWER),
    ("editor@example.test", "Demo Content Editor", UserRole.CONTENT_EDITOR),
    ("branch@example.test", "Demo Branch Lead", UserRole.BRANCH_LEAD),
    ("hr@example.test", "Demo HR Lead", UserRole.HR_LEAD),
]


def seed_demo_users(session: Session) -> int:
    """Caller owns the transaction; existing users/passwords are never overwritten."""
    if get_settings().environment == "production":
        raise ValueError("Demo seeding is forbidden in production.")
    created = 0
    for email, name, role in DEMO_ACCOUNTS:
        if find_user_by_email(session, email) is None:
            session.add(
                User(email=email, name=name, role=role, password_hash=hash_password("Demo123!"))
            )
            session.flush()
            created += 1
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed sample accounts in the configured database.")
    parser.add_argument("--demo", action="store_true", required=True)
    parser.parse_args()
    with Session(get_engine()) as session, session.begin():
        created = seed_demo_users(session)
    print(f"Created {created} demo users; existing users were left unchanged.")


if __name__ == "__main__":
    main()
