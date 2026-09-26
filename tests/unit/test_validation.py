from datetime import UTC, date, datetime

import pytest

from ecommerce_mcp.core.errors import InvalidInputError
from ecommerce_mcp.core.validation import (
    MAX_QUERY_LENGTH,
    MAX_RANGE_DAYS,
    date_range_bounds,
    normalize_category,
    normalize_email,
    normalize_query,
)


def test_normalize_query_collapses_whitespace() -> None:
    assert normalize_query("  wireless \n  headphones ") == "wireless headphones"


@pytest.mark.parametrize("query", ["", "   ", "\n\t"])
def test_normalize_query_rejects_blank(query: str) -> None:
    with pytest.raises(InvalidInputError, match="must not be empty"):
        normalize_query(query)


def test_normalize_query_rejects_too_long() -> None:
    with pytest.raises(InvalidInputError, match="at most"):
        normalize_query("a" * (MAX_QUERY_LENGTH + 1))


def test_normalize_query_keeps_unicode() -> None:
    assert normalize_query("caffè espresso ☕") == "caffè espresso ☕"


def test_normalize_email_lowercases_and_strips() -> None:
    assert normalize_email("  Jane.Doe@Example.COM ") == "jane.doe@example.com"


@pytest.mark.parametrize("email", ["", "jane", "jane@", "@example.com", "a b@example.com", "a@b"])
def test_normalize_email_rejects_invalid(email: str) -> None:
    with pytest.raises(InvalidInputError, match="not a valid email"):
        normalize_email(email)


@pytest.mark.parametrize(
    ("category", "expected"),
    [(None, None), ("", None), ("  ", None), (" Home  & Kitchen ", "Home & Kitchen")],
)
def test_normalize_category(category: str | None, expected: str | None) -> None:
    assert normalize_category(category) == expected


def test_date_range_bounds_is_half_open_utc_interval() -> None:
    start, end = date_range_bounds(date(2026, 3, 1), date(2026, 3, 31))
    assert start == datetime(2026, 3, 1, tzinfo=UTC)
    assert end == datetime(2026, 4, 1, tzinfo=UTC)


def test_date_range_bounds_accepts_single_day() -> None:
    start, end = date_range_bounds(date(2026, 3, 1), date(2026, 3, 1))
    assert (end - start).days == 1


def test_date_range_bounds_rejects_reversed_range() -> None:
    with pytest.raises(InvalidInputError, match="on or before"):
        date_range_bounds(date(2026, 3, 2), date(2026, 3, 1))


def test_date_range_bounds_rejects_too_long_range() -> None:
    with pytest.raises(InvalidInputError, match=f"at most {MAX_RANGE_DAYS} days"):
        date_range_bounds(date(2020, 1, 1), date(2026, 1, 1))
