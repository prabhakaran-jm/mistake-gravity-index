from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from mgi.features.objectives import iter_objectives_from_events_jsonl, objective_answered_after

# ---- Defaults (MVP) ----
DEFAULT_FIGHT_GAP_SECONDS = 45
DEFAULT_WINDOW_SECONDS = 25
DEFAULT_OBJECTIVE_ANSWER_WINDOW_SECONDS = 90
DEFAULT_NEAR_OBJECTIVE_WINDOW_SECONDS = 90

# MVP time-bucket gravity (temporary until full MGI scoring is added)
GRAVITY_BASE = 25
GRAVITY_MID = 30
GRAVITY_LATE = 35
GRAVITY_MID_MINUTES = 15
GRAVITY_LATE_MINUTES = 25


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
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                envelope: Dict[str, Any] = json.loads(line)
                occurred_at = _parse_dt(envelope["occurredAt"])
            except Exception as e:
                print(f"[WARN] Skipping malformed JSONL line {line_no}: {e}")
                continue

            events = envelope.get("events", [])
            if not isinstance(events, list):
                continue

            for ev in events:
                try:
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
                except Exception as e:
                    print(f"[WARN] Bad kill event at line {line_no}: {e}")
                    continue


def extract_untraded_deaths_clustered(
    kills: List[Kill],
    fight_gap_seconds: int = DEFAULT_FIGHT_GAP_SECONDS,
) -> List[Mistake]:
    """
    MVP rule:
    A death is "untraded" if the victim team gets no kill AFTER the death
    within the same "fight cluster".

    Fight cluster = consecutive kills where the time gap between kills <= fight_gap_seconds.
    """
    kills = sorted(kills, key=lambda k: k.occurred_at)
    out: List[Mistake] = []
    if not kills:
        return out

    # Assign fight clusters based on time gap
    cluster_id = 0
    kill_cluster: List[int] = [0] * len(kills)
    for i in range(1, len(kills)):
        gap = (kills[i].occurred_at - kills[i - 1].occurred_at).total_seconds()
        if gap > fight_gap_seconds:
            cluster_id += 1
        kill_cluster[i] = cluster_id

    # For each cluster, store kill indices by killer team
    cluster_team_kill_indices: dict[int, dict[str, List[int]]] = defaultdict(lambda: defaultdict(list))
    for idx, k in enumerate(kills):
        cid = kill_cluster[idx]
        cluster_team_kill_indices[cid][k.killer_team_id].append(idx)

    # Mark death untraded if victim team has no kill AFTER this death inside same cluster
    for idx, k in enumerate(kills):
        cid = kill_cluster[idx]
        victim_team = k.victim_team_id

        victim_kill_indices = cluster_team_kill_indices[cid].get(victim_team, [])
        traded_after = any(j > idx for j in victim_kill_indices)

        if not traded_after:
            out.append(
                Mistake(
                    occurred_at=k.occurred_at,
                    victim_name=k.victim_name or k.victim_player_id,
                    victim_team_id=victim_team,
                    kind="untraded_death",
                    gravity=GRAVITY_BASE,
                    details=(
                        f"Died to {k.killer_name or k.killer_player_id} with no kill by victim team "
                        f"after death in same fight cluster (gap={fight_gap_seconds}s)"
                    ),
                )
            )

    return out


def nearest_objective_window(
    objectives: Sequence[Any],
    when: datetime,
    window_seconds: int = DEFAULT_NEAR_OBJECTIVE_WINDOW_SECONDS,
) -> Optional[Tuple[Any, int]]:
    """
    Returns (objective_event, delta_seconds) for the closest objective within ±window.
    delta_seconds = objective_time - when (negative means objective happened before the death).
    """
    best: Optional[Tuple[Any, int]] = None
    best_abs: Optional[float] = None

    for obj in objectives:
        delta = (obj.occurred_at - when).total_seconds()
        if abs(delta) <= window_seconds:
            if best_abs is None or abs(delta) < best_abs:
                best = (obj, int(delta))
                best_abs = abs(delta)

    return best


def run(series_id: str, top: int = 10, window_seconds: int = DEFAULT_WINDOW_SECONDS) -> int:
    in_dir = Path("data") / "raw" / f"series_{series_id}"
    events_path = in_dir / "events.jsonl"
    end_state_path = in_dir / "end_state.json"
    team_names = load_team_names(end_state_path)

    if not events_path.exists():
        print(f"Missing: {events_path}")
        print("Run: python -m mgi.cli.main series fetch --series-id <id>")
        return 1

    kills = list(iter_kills_from_events_jsonl(events_path))
    mistakes = extract_untraded_deaths_clustered(kills, fight_gap_seconds=DEFAULT_FIGHT_GAP_SECONDS)

    # Load objective events (tower/plates/drakes/baron/voidgrubs/fortifier)
    objectives = sorted(list(iter_objectives_from_events_jsonl(events_path)), key=lambda o: o.occurred_at)

    # Total deaths per victim team (all kills against that team)
    total_deaths_by_team = Counter(k.victim_team_id for k in kills)

    # Overall untraded rate (across all kills)
    overall_rate = (len(mistakes) / len(kills) * 100) if kills else 0.0

    # MVP "late mistakes matter more" gravity using elapsed minutes since first kill.
    base_time = kills[0].occurred_at if kills else None

    def gravity_mvp(occurred_at: datetime) -> int:
        if not base_time:
            return GRAVITY_BASE
        mins = (occurred_at - base_time).total_seconds() / 60.0
        if mins >= GRAVITY_LATE_MINUTES:
            return GRAVITY_LATE
        if mins >= GRAVITY_MID_MINUTES:
            return GRAVITY_MID
        return GRAVITY_BASE

    # Team summary (using MVP gravity)
    by_team_count = Counter(m.victim_team_id for m in mistakes)
    by_team_gravity_mvp = defaultdict(int)
    for m in mistakes:
        by_team_gravity_mvp[m.victim_team_id] += gravity_mvp(m.occurred_at)

    out_dir = Path("data") / "derived" / f"series_{series_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / "mistakes_untraded.json"

    payload: List[Dict[str, Any]] = []
    for m in mistakes:
        ans = objective_answered_after(
            objectives=objectives,
            victim_team_id=m.victim_team_id,
            death_time=m.occurred_at,
            window_seconds=DEFAULT_OBJECTIVE_ANSWER_WINDOW_SECONDS,
        )

        near = nearest_objective_window(
            objectives=objectives,
            when=m.occurred_at,
            window_seconds=DEFAULT_NEAR_OBJECTIVE_WINDOW_SECONDS,
        )

        payload.append(
            {
                "occurredAt": m.occurred_at.isoformat(),
                "victimName": m.victim_name,
                "victimTeamId": m.victim_team_id,
                "victimTeamName": team_names.get(m.victim_team_id, ""),
                "kind": m.kind,
                "gravity": m.gravity,
                "gravityMvp": gravity_mvp(m.occurred_at),
                "answeredByObjective": bool(ans),
                "objectiveAnswer": (
                    {
                        "kind": ans.kind,
                        "occurredAt": ans.occurred_at.isoformat(),
                        "teamId": ans.team_id,
                        "playerName": ans.player_name,
                        "rawType": ans.raw_type,
                    }
                    if ans
                    else None
                ),
                "isNearObjective": bool(near),
                "nearObjective": (
                    {
                        "kind": near[0].kind,
                        "deltaSeconds": near[1],
                        "teamId": near[0].team_id,
                        "playerName": near[0].player_name,
                        "rawType": near[0].raw_type,
                        "occurredAt": near[0].occurred_at.isoformat(),
                    }
                    if near
                    else None
                ),
                "details": m.details,
            }
        )

    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Kills: {len(kills)}")
    print(f"Mistakes (untraded deaths): {len(mistakes)}")
    print(f"Untraded rate (overall): {overall_rate:.1f}%")
    print(f"Wrote: {out_path}\n")

    answered_cnt = sum(1 for x in payload if x["answeredByObjective"])
    answered_rate = (answered_cnt / len(mistakes) * 100) if mistakes else 0.0
    print(
        f"Answered by objective (within {DEFAULT_OBJECTIVE_ANSWER_WINDOW_SECONDS}s): "
        f"{answered_cnt}/{len(mistakes)} ({answered_rate:.1f}%)\n"
    )

    unanswered_cnt = len(mistakes) - answered_cnt
    unanswered_rate = (unanswered_cnt / len(mistakes) * 100) if mistakes else 0.0
    print(
        f"Unanswered (no kill trade + no objective answer): "
        f"{unanswered_cnt}/{len(mistakes)} ({unanswered_rate:.1f}%)\n"
    )

    near_cnt = sum(1 for x in payload if x["isNearObjective"])
    near_rate = (near_cnt / len(mistakes) * 100) if mistakes else 0.0
    print(
        f"Near objective window (±{DEFAULT_NEAR_OBJECTIVE_WINDOW_SECONDS}s): "
        f"{near_cnt}/{len(mistakes)} ({near_rate:.1f}%)\n"
    )

    # Print top N by MVP gravity (ties broken by later time)
    print("occurredAt\tvictimTeam\tvictim\tgravityMvp\tobjAnswer(+Δt)\tnearObj\tdetails")

    top_mistakes = sorted(
        mistakes,
        key=lambda x: (gravity_mvp(x.occurred_at), x.occurred_at),
        reverse=True,
    )[:top]

    for m in top_mistakes:
        team_label = team_names.get(m.victim_team_id, m.victim_team_id)
        g = gravity_mvp(m.occurred_at)

        # Objective answer (victim team takes objective after death)
        ans = objective_answered_after(
            objectives=objectives,
            victim_team_id=m.victim_team_id,
            death_time=m.occurred_at,
            window_seconds=DEFAULT_OBJECTIVE_ANSWER_WINDOW_SECONDS,
        )
        if ans:
            delta_s = int((ans.occurred_at - m.occurred_at).total_seconds())
            who = f" by {ans.player_name}" if getattr(ans, "player_name", "") else ""
            ans_txt = f"{ans.kind}+{delta_s}s{who}"
        else:
            ans_txt = "-"

        # Nearest objective within ±window (either team)
        near = nearest_objective_window(
            objectives=objectives,
            when=m.occurred_at,
            window_seconds=DEFAULT_NEAR_OBJECTIVE_WINDOW_SECONDS,
        )
        if near:
            obj, d = near
            sign = "+" if d >= 0 else ""
            near_txt = f"{obj.kind}{sign}{d}s"
        else:
            near_txt = "-"

        print(
            f"{m.occurred_at.isoformat()}\t{team_label}\t{m.victim_name}\t{g}\t{ans_txt}\t{near_txt}\t{m.details}"
        )

    print("\nTeam summary (victim team):")
    print("team\tuntraded_count\ttotal_deaths\tuntraded_rate\ttotal_gravity_mvp")

    for team_id, untraded_cnt in by_team_count.most_common():
        team_label = team_names.get(team_id, team_id)
        total_deaths = total_deaths_by_team.get(team_id, 0)
        rate = (untraded_cnt / total_deaths * 100) if total_deaths else 0.0
        print(
            f"{team_label}\t{untraded_cnt}\t{total_deaths}\t{rate:.1f}%\t{by_team_gravity_mvp[team_id]}"
        )

    # Player leaderboard (top 10 victims), using MVP gravity totals
    by_player_count = Counter(m.victim_name for m in mistakes)
    by_player_gravity_mvp = defaultdict(int)
    for m in mistakes:
        by_player_gravity_mvp[m.victim_name] += gravity_mvp(m.occurred_at)

    print("\nPlayer summary (victims):")
    for name, cnt in by_player_count.most_common(10):
        print(f"{name}\tcount={cnt}\ttotal_gravity_mvp={by_player_gravity_mvp[name]}")

    return 0
