from datetime import datetime, timedelta

from django.utils import timezone


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
