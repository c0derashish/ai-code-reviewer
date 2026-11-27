from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()  # argon2id with the library's default settings

# Used when an email is unknown, so the answer takes the same time as for a wrong password.
_DUMMY_HASH = _hasher.hash("not-a-real-password")


def hash_password(password) -> str:
    return _hasher.hash(password)


def verify(stored_hash, password) -> bool:
    """True only for the right password. stored_hash None = unknown user, always False."""
    try:
        _hasher.verify(stored_hash or _DUMMY_HASH, password)
    except (VerificationError, InvalidHashError):
        return False
    return stored_hash is not None