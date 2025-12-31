from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


@dataclass
class Kill:
    occurred_at: datetime
    killer_player_id: str
    killer_name: str
    killer_team_id: str
    victim_player_id: str
    victim_name: str
    victim_team_id: str


@dataclass
class Mistake:
    occurred_at: datetime
    victim_name: str
    victim_team_id: str
    kind: str
    gravity: int
    details: str


def _parse_dt(s: str) -> datetime:
    # example: "2024-06-15T22:45:00.000Z"
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s).astimezone(timezone.utc)


def load_team_names(end_state_path: Path) -> dict[str, str]:
    if not end_state_path.exists():
        return {}

    obj = json.loads(end_state_path.read_text(encoding="utf-8"))

    ss = obj.get("seriesState", {}) if isinstance(obj, dict) else {}
    teams = ss.get("teams", []) if isinstance(ss, dict) else []

    out: dict[str, str] = {}
    if isinstance(teams, list):
        for t in teams:
            if not isinstance(t, dict):
                continue
            tid = str(t.get("id", "")).strip()  # convert int -> str
            name = str(t.get("name", "")).strip()
            if tid and name:
                out[tid] = name

    return out


def iter_kills_from_events_jsonl(path: Path) -> Iterable[Kill]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            envelope: Dict[str, Any] = json.loads(line)
            occurred_at = _parse_dt(envelope["occurredAt"])

            for ev in envelope.get("events", []):
                if ev.get("type") != "player-killed-player":
                    continue

                actor = ev.get("actor", {}) or {}
                target = ev.get("target", {}) or {}

                a_state = actor.get("state", {}) or {}
                t_state = target.get("state", {}) or {}

                killer_player_id = str(actor.get("id", ""))
                killer_name = str(a_state.get("name", ""))
                killer_team_id = str(a_state.get("teamId", ""))

                victim_player_id = str(target.get("id", ""))
                victim_name = str(t_state.get("name", ""))
                victim_team_id = str(t_state.get("teamId", ""))

                if not (killer_player_id and victim_player_id):
                    continue

                yield Kill(
                    occurred_at=occurred_at,
                    killer_player_id=killer_player_id,
                    killer_name=killer_name,
                    killer_team_id=killer_team_id,
                    victim_player_id=victim_player_id,
                    victim_name=victim_name,
                    victim_team_id=victim_team_id,
                )


def extract_untraded_deaths(kills: List[Kill], window_seconds: int = 10) -> List[Mistake]:
    # MVP rule:
    # A death is "untraded" if victim team gets no kill within N seconds after.
    kills = sorted(kills, key=lambda k: k.occurred_at)
    out: List[Mistake] = []

    for i, k in enumerate(kills):
        t0 = k.occurred_at
        victim_team = k.victim_team_id

        traded = False
        for j in range(i + 1, len(kills)):
            k2 = kills[j]
            dt = (k2.occurred_at - t0).total_seconds()
            if dt > window_seconds:
                break
            if k2.killer_team_id == victim_team:
                traded = True
                break

        if not traded:
            out.append(
                Mistake(
                    occurred_at=t0,
                    victim_name=k.victim_name or k.victim_player_id,
                    victim_team_id=victim_team,
                    kind="untraded_death",
                    gravity=25,
                    details=f"Died to {k.killer_name or k.killer_player_id} with no trade in {window_seconds}s",
                )
            )

    return out


def run(series_id: str, top: int = 10, window_seconds: int = 10) -> int:
    in_dir = Path("data") / "raw" / f"series_{series_id}"
    events_path = in_dir / "events.jsonl"
    end_state_path = in_dir / "end_state.json"
    team_names = load_team_names(end_state_path)

    if not events_path.exists():
        print(f"Missing: {events_path}")
        print("Run: python -m mgi.cli.main series fetch --series-id <id>")
        return 1

    kills = list(iter_kills_from_events_jsonl(events_path))
    mistakes = extract_untraded_deaths(kills, window_seconds=window_seconds)

    # MVP "late mistakes matter more" gravity using elapsed minutes since first kill.
    base_time = kills[0].occurred_at if kills else None

    def gravity_mvp(occurred_at: datetime) -> int:
        if not base_time:
            return 25
        mins = (occurred_at - base_time).total_seconds() / 60.0
        if mins >= 25:
            return 35
        if mins >= 15:
            return 30
        return 25

    # Team summary (using MVP gravity)
    by_team_count = Counter(m.victim_team_id for m in mistakes)
    by_team_gravity_mvp = defaultdict(int)
    for m in mistakes:
        by_team_gravity_mvp[m.victim_team_id] += gravity_mvp(m.occurred_at)

    out_dir = Path("data") / "derived" / f"series_{series_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / "mistakes_untraded.json"
    payload = [
        {
            "occurredAt": m.occurred_at.isoformat(),
            "victimName": m.victim_name,
            "victimTeamId": m.victim_team_id,
            "victimTeamName": team_names.get(m.victim_team_id, ""),
            "kind": m.kind,
            "gravity": m.gravity,
            "gravityMvp": gravity_mvp(m.occurred_at),
            "details": m.details,
        }
        for m in mistakes
    ]
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Kills: {len(kills)}")
    print(f"Mistakes (untraded deaths): {len(mistakes)}")
    print(f"Wrote: {out_path}\n")

    # Print top N by MVP gravity (ties broken by later time)
    print("occurredAt\tvictimTeam\tvictim\tgravityMvp\tdetails")
    top_mistakes = sorted(
        mistakes,
        key=lambda x: (gravity_mvp(x.occurred_at), x.occurred_at),
        reverse=True,
    )[:top]
    for m in top_mistakes:
        team_label = team_names.get(m.victim_team_id, m.victim_team_id)
        g = gravity_mvp(m.occurred_at)
        print(f"{m.occurred_at.isoformat()}\t{team_label}\t{m.victim_name}\t{g}\t{m.details}")

    print("\nTeam summary (victim team):")
    for team_id, cnt in by_team_count.most_common():
        team_label = team_names.get(team_id, team_id)
        print(f"{team_label}\tcount={cnt}\ttotal_gravity_mvp={by_team_gravity_mvp[team_id]}")

    # Player leaderboard (top 10 victims), using MVP gravity totals
    by_player_count = Counter(m.victim_name for m in mistakes)
    by_player_gravity_mvp = defaultdict(int)
    for m in mistakes:
        by_player_gravity_mvp[m.victim_name] += gravity_mvp(m.occurred_at)

    print("\nPlayer summary (victims):")
    for name, cnt in by_player_count.most_common(10):
        print(f"{name}\tcount={cnt}\ttotal_gravity_mvp={by_player_gravity_mvp[name]}")

    return 0