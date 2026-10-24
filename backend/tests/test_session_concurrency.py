import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from test_secure_flow import browser, csrf, login

from app.database import get_db
from app.main import app
from app.models import AuthSession, SecurityEvent, User, UserRole
from app.passwords import hash_password


def test_simultaneous_logins_consume_anonymous_session_only_once(engine):
    email = f"concurrent-{uuid.uuid4().hex}@example.test"
    with Session(engine) as db, db.begin():
        user = User(
            email=email,
            name="Concurrency test",
            role=UserRole.HR_LEAD,
            password_hash=hash_password("concurrency password"),
        )
        db.add(user)
        db.flush()
        user_id = user.id

    def independent_db():
        with Session(engine) as db:
            yield db

    old_override = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = independent_db
    try:
        with browser() as owner:
            result = csrf(owner)
            cookies = dict(owner.cookies)
            csrf_token = result.json()["csrf_token"]

        def attempt(_):
            with browser() as client:
                client.cookies.update(cookies)
                client.headers["X-CSRF-Token"] = csrf_token
                return client.post(
                    "/api/login", json={"email": email, "password": "concurrency password"}
                ).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(attempt, range(2)))
        assert statuses.count(200) == 1
        assert all(status in {200, 401, 403} for status in statuses)
        with Session(engine) as db:
            assert (
                len(db.scalars(select(AuthSession).where(AuthSession.user_id == user_id)).all())
                == 1
            )
    finally:
        app.dependency_overrides[get_db] = old_override
        with Session(engine) as db, db.begin():
            db.execute(delete(SecurityEvent).where(SecurityEvent.subject_id == user_id))
            db.execute(delete(User).where(User.id == user_id))


def test_password_reset_wins_over_login_using_old_verified_hash(engine, monkeypatch):
    from app.users import authenticate_user

    suffix = uuid.uuid4().hex
    admin_email, staff_email = f"admin-{suffix}@example.test", f"staff-{suffix}@example.test"
    password = "old valid staff password"
    with Session(engine) as db, db.begin():
        admin = User(
            email=admin_email,
            name="Race Admin",
            role=UserRole.SUPER_ADMIN,
            password_hash=hash_password(password),
        )
        staff = User(
            email=staff_email,
            name="Race Staff",
            role=UserRole.HR_LEAD,
            password_hash=hash_password(password),
        )
        db.add_all([admin, staff])
        db.flush()
        ids = [admin.id, staff.id]

    def independent_db():
        with Session(engine) as db:
            yield db

    previous = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = independent_db
    verified, reset_done = Event(), Event()

    def paused_auth(db, email, candidate):
        user = authenticate_user(db, email, candidate)
        if email == staff_email:
            verified.set()
            assert reset_done.wait(30)
        return user

    try:
        with browser() as admin_client:
            assert login(admin_client, admin_email, password).status_code == 200
            monkeypatch.setattr("app.login.authenticate_user", paused_auth)

            def delayed_login():
                with browser() as staff_client:
                    return login(staff_client, staff_email, password).status_code

            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(delayed_login)
                assert verified.wait(30)
                result = admin_client.post(
                    f"/api/staff/{ids[1]}/reset-password",
                    json={"temporary_password": "new temporary staff password"},
                )
                reset_done.set()
                assert result.status_code == 204
                assert future.result(timeout=30) == 401
        with Session(engine) as db:
            assert not db.scalars(select(AuthSession).where(AuthSession.user_id == ids[1])).all()
    finally:
        reset_done.set()
        app.dependency_overrides[get_db] = previous
        with Session(engine) as db, db.begin():
            db.execute(delete(SecurityEvent).where(SecurityEvent.subject_id.in_(ids)))
            db.execute(delete(User).where(User.id.in_(ids)))
