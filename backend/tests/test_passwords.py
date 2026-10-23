import pytest
from pwdlib import PasswordHash

from app.passwords import hash_password, validate_new_password, verify_password


def test_new_hashes_are_bcrypt():
    hashed = hash_password("a long password for staff")
    assert hashed.startswith("$2b$12$")
    assert verify_password("a long password for staff", hashed)
    assert not verify_password("wrong", hashed)


@pytest.mark.parametrize("value", ["x" * 73, "é" * 37, "short", "safe password\x00invalid"])
def test_password_policy_rejects_invalid_input(value):
    with pytest.raises(ValueError):
        validate_new_password(value)


def test_unicode_password_and_byte_boundary():
    assert validate_new_password("é" * 36) == "é" * 36
    assert verify_password("é" * 36, hash_password("é" * 36))
    with pytest.raises(ValueError):
        hash_password("x" * 73)


def test_legacy_and_malformed_hashes():
    legacy = PasswordHash.recommended().hash("Demo123!")
    assert verify_password("Demo123!", legacy)
    assert not verify_password("bad", legacy)
    assert not verify_password("something", "malformed")
