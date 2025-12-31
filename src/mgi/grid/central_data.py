from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from mgi.grid.client import GridGraphQLClient
from mgi.grid.queries import ALL_SERIES_BY_TOURNAMENT_QUERY, TITLES_QUERY


@dataclass(frozen=True)
class SeriesInfo:
    id: str
    start_time_scheduled: str | None
    tournament_name: str | None
    title_short: str | None
    teams: list[str]


def get_titles(client: GridGraphQLClient) -> list[dict]:
    data = client.query(TITLES_QUERY)
    return data.get("titles", [])


def iter_series_by_tournament(
    client: GridGraphQLClient,
    tournament_id: str,
    team_filter: Optional[str] = None,
    max_pages: int = 50,
) -> List[SeriesInfo]:
    """
    Paginates Central Data allSeries. Optionally filters by team name (case-insensitive substring).
    """
    after = None
    results: list[SeriesInfo] = []
    team_filter_norm = (team_filter or "").strip().lower()

    for _ in range(max_pages):
        variables: Dict[str, Any] = {"tournamentId": tournament_id}
        if after is not None:
            variables["after"] = after
        data = client.query(ALL_SERIES_BY_TOURNAMENT_QUERY, variables=variables)

        node = data.get("allSeries") or {}
        edges = node.get("edges") or []
        page = node.get("pageInfo") or {}

        for e in edges:
            s = (e or {}).get("node") or {}
            teams = [
                (((t or {}).get("baseInfo") or {}).get("name") or "").strip()
                for t in (s.get("teams") or [])
            ]
            if team_filter_norm:
                if not any(team_filter_norm in (nm or "").lower() for nm in teams):
                    continue

            results.append(
                SeriesInfo(
                    id=str(s.get("id")),
                    start_time_scheduled=s.get("startTimeScheduled"),
                    tournament_name=((s.get("tournament") or {}).get("name")),
                    title_short=((s.get("title") or {}).get("nameShortened")),
                    teams=[t for t in teams if t],
                )
            )

        if not page.get("hasNextPage"):
            break

        after = page.get("endCursor")
        if not after:
            break

    return results