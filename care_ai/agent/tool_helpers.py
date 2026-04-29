import logging
from datetime import datetime, timedelta
from functools import wraps

from django.db import close_old_connections
from django.utils import timezone

logger = logging.getLogger("care_ai.tools")


def now_minus(*, hours: int = 0, days: int = 0) -> datetime:
    return timezone.now() - timedelta(hours=hours, days=days)


def serialize_list(spec_cls, queryset, limit: int) -> dict:
    """Serialize a queryset via a Care ReadSpec, capped at `limit` rows."""
    rows = list(queryset[: limit + 1])
    truncated = len(rows) > limit
    rows = rows[:limit]
    return {
        "items": [spec_cls.serialize(obj).to_json() for obj in rows],
        "truncated": truncated,
        "count": len(rows),
    }


def safe_tool(fn):
    """Wrap a tool body so DB connections are refreshed and exceptions become {'error': ...}.

    The OpenAI Agents SDK runs tools in worker threads. Each thread can hold a
    stale Django DB connection (closed by the DB server / PgBouncer). Calling
    `close_old_connections()` before any ORM access drops the stale handle so
    the next query opens a fresh one.
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        close_old_connections()
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            logger.exception("%s failed", fn.__name__)
            return {"error": f"{type(exc).__name__}: {exc}"}
        finally:
            close_old_connections()

    return wrapper
