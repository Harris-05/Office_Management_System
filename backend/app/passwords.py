from functools import lru_cache

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

from app.config import get_settings


@lru_cache
def password_hasher() -> PasswordHash:
    return PasswordHash((BcryptHasher(rounds=get_settings().bcrypt_cost), Argon2Hasher()))


def validate_new_password(password: str) -> str:
    if len(password) < 15 or len(password.encode("utf-8")) > 72 or "\x00" in password:
        raise ValueError("Use at least 15 characters and at most 72 UTF-8 bytes, without NUL.")
    return password


def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > 72 or "\x00" in password:
        raise ValueError("Password exceeds bcrypt limits.")
    return password_hasher().hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return password_hasher().verify(password, hashed)
    except (ValueError, TypeError, UnknownHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    return not hashed.startswith(f"$2b${get_settings().bcrypt_cost:02d}$")


@lru_cache
def dummy_hash() -> str:
    return hash_password("dummy credential comparison")
