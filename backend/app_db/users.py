from pymongo.errors import DuplicateKeyError

from app_db import passwords
from app_db.clock import utc_now

# Every collection that holds a user's data. Step 2 fills most of them.
USER_COLLECTIONS = ("sessions", "analysis_issues", "analyses", "blobs", "projects")


class DuplicateEmail(Exception):
    """An account with this email exists."""


def create_user(db, name, email, password) -> dict:
    document = {
        "email": email.strip().lower(),
        "name": name.strip(),
        "password_hash": passwords.hash_password(password),
        "created_at": utc_now(),
    }
    try:
        db["users"].insert_one(document)  # adds "_id" to the document
    except DuplicateKeyError:
        raise DuplicateEmail() from None
    return document


def find_by_email(db, email):
    return db["users"].find_one({"email": email.strip().lower()})


def public_user(document) -> dict:
    """What the browser may see. Never the hash."""
    return {"id": str(document["_id"]), "name": document["name"], "email": document["email"]}


def delete_account(db, user_id):
    """Delete the user and everything stored for them."""
    for name in USER_COLLECTIONS:
        db[name].delete_many({"user_id": user_id})
    db["users"].delete_one({"_id": user_id})