from pymongo import ASCENDING, DESCENDING, MongoClient


def connect(uri, db_name, timeout_ms=5000):
    """A database object. Raises a PyMongo error if the server cannot be reached."""
    client = MongoClient(uri, serverSelectionTimeoutMS=timeout_ms)
    client.admin.command("ping")
    return client[db_name]


def ensure_indexes(db):
    """Safe to run many times."""
    db["users"].create_index([("email", ASCENDING)], unique=True)

    # MongoDB deletes a session when expires_at has passed (it checks about every minute,
    # so we also check the date when we read)
    db["sessions"].create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)
    db["sessions"].create_index([("user_id", ASCENDING)])

    # a user has each project once
    db["projects"].create_index([("user_id", ASCENDING), ("key", ASCENDING)], unique=True)

    # history: the analyses of one user, newest first
    db["analyses"].create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    db["analyses"].create_index([("user_id", ASCENDING), ("project_id", ASCENDING)])

    db["analysis_issues"].create_index([("analysis_id", ASCENDING), ("n", ASCENDING)])
    db["analysis_issues"].create_index([("user_id", ASCENDING)])
    db["blobs"].create_index([("user_id", ASCENDING)])