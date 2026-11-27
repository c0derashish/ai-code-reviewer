from datetime import datetime, timezone


def utc_now():
    """Now in UTC, without a time zone label. MongoDB stores and returns dates this way."""
    return datetime.now(timezone.utc).replace(tzinfo=None)