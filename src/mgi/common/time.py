from __future__ import annotations

from datetime import datetime, timezone

def parse_dt(s: str) -> datetime:
    """Parse GRID timestamps like '2024-06-15T22:45:00.000Z' to UTC datetime."""
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s).astimezone(timezone.utc)
