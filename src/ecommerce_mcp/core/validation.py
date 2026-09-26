"""Semantic validation of tool arguments that JSON schemas cannot express (ranges, formats)."""

import re
from datetime import UTC, date, datetime, time, timedelta

from ecommerce_mcp.core.errors import InvalidInputError

MAX_QUERY_LENGTH = 200
MAX_RANGE_DAYS = 731
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_query(query: str) -> str:
    cleaned = " ".join(query.split())
    if not cleaned:
        raise InvalidInputError("query must not be empty")
    if len(cleaned) > MAX_QUERY_LENGTH:
        raise InvalidInputError(f"query must be at most {MAX_QUERY_LENGTH} characters")
    return cleaned


def normalize_email(email: str) -> str:
    cleaned = email.strip().lower()
    if not EMAIL_PATTERN.match(cleaned):
        raise InvalidInputError(f"'{email}' is not a valid email address")
    return cleaned


def normalize_category(category: str | None) -> str | None:
    if category is None:
        return None
    cleaned = " ".join(category.split())
    return cleaned or None


def date_range_bounds(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    """Returns the half-open UTC interval [start 00:00, day after end 00:00) covering both dates."""
    if start_date > end_date:
        raise InvalidInputError(
            f"start_date ({start_date}) must be on or before end_date ({end_date})"
        )
    if (end_date - start_date).days > MAX_RANGE_DAYS:
        raise InvalidInputError(f"date range must span at most {MAX_RANGE_DAYS} days")
    start = datetime.combine(start_date, time.min, tzinfo=UTC)
    end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC)
    return start, end
