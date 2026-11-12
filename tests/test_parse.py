from datetime import date

import pytest

from nldate import parse

TODAY = date(2026, 11, 11)  # Wednesday


@pytest.mark.parametrize(
    ("s", "expected"),
    [
        ("December 1st, 2025", date(2025, 12, 1)),
        ("December 1, 2025", date(2025, 12, 1)),
        ("Dec 1 2025", date(2025, 12, 1)),
        ("Dec. 1st, 2025", date(2025, 12, 1)),
        ("1 December 2025", date(2025, 12, 1)),
        ("1st of December, 2025", date(2025, 12, 1)),
        ("the 1st of December, 2025", date(2025, 12, 1)),
        ("2025-12-01", date(2025, 12, 1)),
        ("12/01/2025", date(2025, 12, 1)),  # US style: month/day/year
        ("12/1/2025", date(2025, 12, 1)),
        ("Sep 3, 2026", date(2026, 9, 3)),
        ("September 23rd, 2026", date(2026, 9, 23)),
        ("February 29, 2024", date(2024, 2, 29)),  # leap day is valid
        ("March 15", date(2026, 3, 15)),  # no year -> TODAY's year
    ],
)
def test_absolute_dates(s: str, expected: date) -> None:
    assert parse(s, today=TODAY) == expected


# Simple relative words
@pytest.mark.parametrize(
    ("s", "expected"),
    [
        ("today", date(2026, 11, 11)),
        ("tomorrow", date(2026, 11, 12)),
        ("yesterday", date(2026, 11, 10)),
        ("the day after tomorrow", date(2026, 11, 13)),
        ("the day before yesterday", date(2026, 11, 9)),
    ],
)
def test_relative_words(s: str, expected: date) -> None:
    assert parse(s, today=TODAY) == expected


# Weekdays. Convention: a bare weekday / "this X" / "next X" means the next
# occurrence strictly after today; "last X" is the most recent one strictly
# before today.
@pytest.mark.parametrize(
    ("s", "expected"),
    [
        ("Friday", date(2026, 11, 13)),
        ("this Friday", date(2026, 11, 13)),
        ("Monday", date(2026, 11, 16)),
        ("next Tuesday", date(2026, 11, 17)),
        ("next Wednesday", date(2026, 11, 18)),  # same weekday as today
        ("last Friday", date(2026, 11, 6)),
        ("last Wednesday", date(2026, 11, 4)),
    ],
)
def test_weekdays(s: str, expected: date) -> None:
    assert parse(s, today=TODAY) == expected


# "next/last <unit>"
@pytest.mark.parametrize(
    ("s", "expected"),
    [
        ("next week", date(2026, 11, 18)),
        ("last week", date(2026, 11, 4)),
        ("next month", date(2026, 12, 11)),
        ("last month", date(2026, 10, 11)),
        ("next year", date(2027, 11, 11)),
        ("last year", date(2025, 11, 11)),
    ],
)
def test_next_last_unit(s: str, expected: date) -> None:
    assert parse(s, today=TODAY) == expected


# from today
@pytest.mark.parametrize(
    ("s", "expected"),
    [
        ("in 3 days", date(2026, 11, 14)),
        ("in 1 day", date(2026, 11, 12)),
        ("3 days from now", date(2026, 11, 14)),
        ("in a week", date(2026, 11, 18)),
        ("in 2 months", date(2027, 1, 11)),
        ("2 weeks ago", date(2026, 10, 28)),
        ("a year ago", date(2025, 11, 11)),
        ("ten days ago", date(2026, 11, 1)),
    ],
)
def test_offsets_from_today(s: str, expected: date) -> None:
    assert parse(s, today=TODAY) == expected


# Offsets from an anchor: "<amount> (before|after|from) <any date expression>"
@pytest.mark.parametrize(
    ("s", "expected"),
    [
        ("5 days before December 1st, 2025", date(2025, 11, 26)),
        ("2 weeks from tomorrow", date(2026, 11, 26)),
        ("two weeks from tomorrow", date(2026, 11, 26)),
        ("1 year and 2 months after yesterday", date(2028, 1, 10)),
        ("3 days after 2025-12-30", date(2026, 1, 2)),  # crosses a year
        ("10 days before today", date(2026, 11, 1)),
        ("a week after next Monday", date(2026, 11, 23)),
        ("2 years, 3 months and 4 days after March 1, 2020", date(2022, 6, 5)),
    ],
)
def test_anchored_offsets(s: str, expected: date) -> None:
    assert parse(s, today=TODAY) == expected


# Month/year arithmetic: clamp to the last valid day of the month
@pytest.mark.parametrize(
    ("s", "expected"),
    [
        ("1 month after January 31, 2025", date(2025, 2, 28)),
        ("1 month after January 31, 2024", date(2024, 2, 29)),  # leap year
        ("1 year after February 29, 2024", date(2025, 2, 28)),
        ("1 month before March 31, 2025", date(2025, 2, 28)),
    ],
)
def test_month_end_clamping(s: str, expected: date) -> None:
    assert parse(s, today=TODAY) == expected


# Messy input: case, extra whitespace, trailing punctuation
@pytest.mark.parametrize(
    ("s", "expected"),
    [
        ("  TOMORROW  ", date(2026, 11, 12)),
        ("next   tuesday", date(2026, 11, 17)),
        ("In 3 Days.", date(2026, 11, 14)),
        ("DECEMBER 1ST, 2025", date(2025, 12, 1)),
    ],
)
def test_messy_input(s: str, expected: date) -> None:
    assert parse(s, today=TODAY) == expected


# A different reference date
def test_other_reference_date_wraps_year() -> None:
    assert parse("in 3 days", today=date(2025, 12, 30)) == date(2026, 1, 2)


def test_today_defaults_to_real_date() -> None:
    assert parse("today") == date.today()


# Unrecognised input must raise ValueError
@pytest.mark.parametrize(
    "s",
    [
        "",
        "   ",
        "banana",
        "February 30, 2025",  # impossible date
        "February 29, 2025",  # not a leap year
        "13/45/2025",
        "5 days before",  # missing anchor
        "next blursday",
        "in days",
    ],
)
def test_invalid(s: str) -> None:
    with pytest.raises(ValueError):
        parse(s, today=TODAY)
