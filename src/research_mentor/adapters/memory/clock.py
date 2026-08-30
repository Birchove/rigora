"""Fixed clock adapter."""

from datetime import datetime

from research_mentor.errors import InvariantViolationError


class FixedClock:
    def __init__(self, fixed_now: datetime) -> None:
        if fixed_now.utcoffset() is None:
            raise InvariantViolationError("FixedClock requires a timezone-aware datetime")
        self._fixed_now = fixed_now

    def now(self) -> datetime:
        return self._fixed_now
