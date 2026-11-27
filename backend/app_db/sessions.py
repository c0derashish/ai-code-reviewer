import hashlib
import secrets
from datetime import timedelta

from app_db.clock import utc_now

MAX_TOKEN_LENGTH = 200


def _hash(token) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db, user_id, days, now=None) -> str:
    """Returns the token for the cookie. The database keeps only its hash,
    so a leaked database copy cannot be used to sign in."""
    now = now or utc_now()
    token = secrets.token_urlsafe(32)
    db["sessions"].insert_one(
        {
            "_id": _hash(token),
            "user_id": user_id,
            "created_at": now,
            "expires_at": now + timedelta(days=days),
        }
    )
    return token


def get_user_by_token(db, token, now=None):
    """The user for a cookie token, or None (unknown, expired or malformed)."""
    if not isinstance(token, str) or not token or len(token) > MAX_TOKEN_LENGTH:
        return None

    now = now or utc_now()
    session = db["sessions"].find_one({"_id": _hash(token), "expires_at": {"$gt": now}})
    if session is None:
        return None
    return db["users"].find_one({"_id": session["user_id"]})


def delete_session(db, token):
    if isinstance(token, str) and token and len(token) <= MAX_TOKEN_LENGTH:
        db["sessions"].delete_one({"_id": _hash(token)})