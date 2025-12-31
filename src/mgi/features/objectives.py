from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence


def _parse_dt(s: str) -> datetime:
    # example: "2024-06-15T22:45:00.000Z"
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s).astimezone(timezone.utc)


@dataclass(frozen=True)
class ObjectiveEvent:
    occurred_at: datetime
    kind: str              # "baron", "drake_ocean", "tower", "plate", "voidgrub", "fortifier"
    team_id: str           # team credited
    player_name: str       # optional, can be blank
    raw_type: str          # GRID event type


# Map GRID event types -> objective kinds
OBJECTIVE_TYPE_MAP: dict[str, str] = {
    # Baron
    "player-completed-slayBaron": "baron",

    # Drakes (extend as you see more types)
    "player-completed-slayOceanDrake": "drake_ocean",
    "player-completed-slayChemtechDrake": "drake_chemtech",
    "player-completed-slayMountainDrake": "drake_mountain",

    # Towers / Plates
    "team-destroyed-tower": "tower",
    "team-completed-destroyTower": "tower",
    "player-destroyed-tower": "tower",
    "player-completed-destroyTower": "tower",

    "player-completed-destroyTurretPlateTop": "plate",
    "player-completed-destroyTurretPlateBot": "plate",
    "team-completed-destroyTurretPlateBot": "plate",
    "player-completed-destroyTurretPlateTop": "plate",

    # Void grubs
    "player-completed-slayVoidGrub": "voidgrub",

    # Fortifier (map structure)
    "player-destroyed-fortifier": "fortifier",
    "player-completed-destroyFortifier": "fortifier",
}


def _extract_team_and_name(actor: dict) -> tuple[str, str]:
    """
    In your kill parser you used actor.state.teamId and actor.state.name.
    Keep the same approach here.
    """
    state = actor.get("state", {}) or {}
    team_id = str(state.get("teamId", "")).strip()
    name = str(state.get("name", "")).strip()
    return team_id, name


def iter_objectives_from_events_jsonl(path: Path) -> Iterable[ObjectiveEvent]:
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                envelope: Dict[str, Any] = json.loads(line)
                occurred_at = _parse_dt(envelope["occurredAt"])
            except Exception:
                continue

            events = envelope.get("events", [])
            if not isinstance(events, list):
                continue

            for ev in events:
                ev_type = str(ev.get("type", "")).strip()
                if ev_type not in OBJECTIVE_TYPE_MAP:
                    continue

                # Prefer actor.state.teamId for credit
                actor = ev.get("actor", {}) or {}
                team_id, player_name = _extract_team_and_name(actor)

                # Some events might store teamId elsewhere; try a couple fallbacks
                if not team_id:
                    team_id = str(ev.get("teamId", "")).strip() or str((ev.get("state", {}) or {}).get("teamId", "")).strip()

                yield ObjectiveEvent(
                    occurred_at=occurred_at,
                    kind=OBJECTIVE_TYPE_MAP[ev_type],
                    team_id=team_id,
                    player_name=player_name,
                    raw_type=ev_type,
                )

def objective_answered_after(
    objectives: Sequence[ObjectiveEvent],
    victim_team_id: str,
    death_time: datetime,
    window_seconds: int = 90,
) -> Optional[ObjectiveEvent]:
    """
    Returns the first objective taken by victim team within window after death.
    """
    t_end = death_time + timedelta(seconds=window_seconds)
    for obj in objectives:
        if obj.team_id == victim_team_id and death_time <= obj.occurred_at <= t_end:
            return obj
    return None