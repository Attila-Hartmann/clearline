"""Statutory response deadlines (Hpt. 288. §): 15 business days for payment-service complaints,
30 calendar days otherwise."""

from datetime import date, timedelta

# ponytail: hardcoded Hungarian public holidays for 2026–2027; swap for a holiday calendar service when it matters.
HOLIDAYS = {date.fromisoformat(d) for d in [
    "2026-01-01", "2026-03-15", "2026-04-03", "2026-04-06", "2026-05-01", "2026-05-25", "2026-08-20",
    "2026-10-23", "2026-11-01", "2026-12-24", "2026-12-25", "2026-12-26",
    "2027-01-01", "2027-03-15", "2027-03-26", "2027-03-29", "2027-05-01", "2027-05-17", "2027-08-20",
    "2027-10-23", "2027-11-01", "2027-12-24", "2027-12-25", "2027-12-26",
]}


def add_business_days(start: date, days: int) -> date:
    d = start
    while days:
        d += timedelta(days=1)
        if d.weekday() < 5 and d not in HOLIDAYS:
            days -= 1
    return d


def due_date(received: date, payment_service: bool) -> date:
    return add_business_days(received, 15) if payment_service else received + timedelta(days=30)
