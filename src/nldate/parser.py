"""Turn natural-language date strings into datetime.date objects."""

import calendar
import re
from datetime import date, timedelta

MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sept": 9, "sep": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}  # fmt: skip

WEEKDAYS = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}  # fmt: skip

NUMBER_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30,
}  # fmt: skip

# Words that mean a fixed number of days away from today.
RELATIVE_DAYS = {
    "today": 0,
    "now": 0,
    "tomorrow": 1,
    "yesterday": -1,
    "day after tomorrow": 2,
    "day before yesterday": -2,
}

# Regex building blocks.
_MONTH = "|".join(sorted(MONTHS, key=len, reverse=True))  # longest first
_WEEKDAY = "|".join(sorted(WEEKDAYS, key=len, reverse=True))
_PART = r"(\d+) (day|week|month|year)s?"  # e.g. "3 days", "1 year"
_DURATION = rf"{_PART}(?: (?:and )?{_PART})*"  # "1 year and 2 months"


def parse(s: str, today: date | None = None) -> date:
    """Parse a natural-language date such as "next Tuesday" or "in 3 days".

    Relative expressions are resolved against ``today`` (default: the real
    current date). Raises ValueError if the string isn't a recognised date.
    """
    if today is None:
        today = date.today()
    text = _normalize(s)
    if not text:
        raise ValueError("empty date string")
    return _parse_expr(text, today)


def _normalize(s: str) -> str:
    """Lowercase, drop punctuation and ordinal suffixes, and turn number
    words into digits, so that the patterns below have less to handle."""
    s = s.lower()
    s = re.sub(r"[,!?]", " ", s)  # "Dec 1st, 2025" -> "dec 1st  2025"
    # Drop periods, except between digits so "2025.12.04" survives.
    s = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", s)  # "Dec. 1" -> "dec  1"
    s = re.sub(r"\b(\d+)(st|nd|rd|th)\b", r"\1", s)  # "1st" -> "1"
    words = [str(NUMBER_WORDS.get(w, w)) for w in s.split()]  # also squashes spaces
    return " ".join(words)


def _parse_expr(text: str, today: date) -> date:
    """Parse an already-normalized expression. Calls itself recursively for
    expressions like "<duration> before <another expression>"."""
    text = text.removeprefix("the ")

    # 1. Fixed words: "today", "tomorrow", "the day after tomorrow", ...
    if text in RELATIVE_DAYS:
        return today + timedelta(days=RELATIVE_DAYS[text])

    # 2. "<duration> before/after/from <expression>"
    m = re.fullmatch(rf"({_DURATION}) (before|after|from) (.+)", text)
    if m:
        duration, direction, rest = m.group(1), m.group(6), m.group(7)
        anchor = _parse_expr(rest, today)  # recursion!
        sign = -1 if direction == "before" else 1
        return _shift(anchor, duration, sign)

    # 3. "in <duration>" and "<duration> ago"
    m = re.fullmatch(rf"in ({_DURATION})", text)
    if m:
        return _shift(today, m.group(1), 1)
    m = re.fullmatch(rf"({_DURATION}) ago", text)
    if m:
        return _shift(today, m.group(1), -1)

    # 4. Weekdays: "friday", "this friday", "next tuesday", "last friday"
    m = re.fullmatch(rf"(?:(this|next|last) )?({_WEEKDAY})", text)
    if m:
        return _weekday(today, WEEKDAYS[m.group(2)], m.group(1) == "last")

    # 5. "next week", "last month", "next year"
    m = re.fullmatch(r"(next|last) (week|month|year)", text)
    if m:
        return _shift(today, f"1 {m.group(2)}", 1 if m.group(1) == "next" else -1)

    # 6. Absolute dates.
    return _parse_absolute(text, today)


def _parse_absolute(text: str, today: date) -> date:
    # A leading weekday is just decoration: "thursday december 4 2025"
    m = re.fullmatch(rf"(?:{_WEEKDAY}) (.+)", text)
    if m:
        return _parse_absolute(m.group(1), today)

    # Year first: 2025-12-01, 2025/12/01, 2025.12.01
    # ([-/.]) captures the separator; \2 requires the same one again.
    m = re.fullmatch(r"(\d{4})([-/.])(\d{1,2})\2(\d{1,2})", text)
    if m:
        return _make_date(int(m.group(1)), int(m.group(3)), int(m.group(4)))

    # US, year last: 12/01/2025, 12-01-2025, 12.01.2025 (month/day/year)
    m = re.fullmatch(r"(\d{1,2})([-/.])(\d{1,2})\2(\d{4})", text)
    if m:
        return _make_date(int(m.group(4)), int(m.group(1)), int(m.group(3)))

    # Month first: "december 1 2025", "march 15"
    m = re.fullmatch(rf"({_MONTH}) (\d{{1,2}})(?: (\d{{4}}))?", text)
    if m:
        year = int(m.group(3)) if m.group(3) else today.year
        return _make_date(year, MONTHS[m.group(1)], int(m.group(2)))

    # Day first: "1 december 2025", "1 of december 2025"
    m = re.fullmatch(rf"(\d{{1,2}}) (?:of )?({_MONTH})(?: (\d{{4}}))?", text)
    if m:
        year = int(m.group(3)) if m.group(3) else today.year
        return _make_date(year, MONTHS[m.group(2)], int(m.group(1)))

    raise ValueError(f"unrecognized date: {text!r}")


def _make_date(year: int, month: int, day: int) -> date:
    """date(), but with a clearer error for impossible dates like Feb 30."""
    try:
        return date(year, month, day)
    except ValueError as e:
        raise ValueError(f"invalid date {year}-{month}-{day}: {e}") from None


def _shift(start: date, duration: str, sign: int) -> date:
    """Move ``start`` forward (sign=1) or back (sign=-1) by a duration string
    like "1 year and 2 months". Years/months are applied before days."""
    months = days = 0
    for amount, unit in re.findall(_PART, duration):
        n = int(amount)
        if unit == "year":
            months += 12 * n
        elif unit == "month":
            months += n
        elif unit == "week":
            days += 7 * n
        else:
            days += n
    return _add_months(start, sign * months) + timedelta(days=sign * days)


def _add_months(d: date, n: int) -> date:
    """Add n months, clamping the day: Jan 31 + 1 month -> Feb 28 (or 29)."""
    index = d.month - 1 + n  # months since January of d.year
    year, month = d.year + index // 12, index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last_day))


def _weekday(today: date, target: int, past: bool) -> date:
    """Nearest given weekday strictly after today, or strictly before it if
    ``past`` is True. (Monday=0 ... Sunday=6.)"""
    if past:
        return today - timedelta(days=(today.weekday() - target - 1) % 7 + 1)
    return today + timedelta(days=(target - today.weekday() - 1) % 7 + 1)
