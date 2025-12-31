from __future__ import annotations
import argparse
from typing import Optional

from mgi.config import get_settings
from mgi.grid.client import GridGraphQLClient
from mgi.grid.central_data import iter_series_by_tournament, get_titles


def cmd_titles() -> int:
    settings = get_settings()
    client = GridGraphQLClient(url=settings.grid_central_data_url, api_key=settings.grid_api_key)
    titles = get_titles(client)

    for t in titles:
        print(f"{t.get('id')}\t{t.get('name')}")
    return 0


def cmd_series_list(tournament_id: str, team: Optional[str], limit: int) -> int:
    settings = get_settings()
    client = GridGraphQLClient(url=settings.grid_central_data_url, api_key=settings.grid_api_key)

    series_list = iter_series_by_tournament(client, tournament_id=tournament_id, team_filter=team)

    if not series_list:
        print("No series found for given filters.")
        return 0

    count = 0
    for s in series_list:
        print(f"{s.id}\t{s.start_time_scheduled}\t{s.title_short}\t{s.tournament_name}\t{', '.join(s.teams)}")
        count += 1
        if limit and count >= limit:
            break

    print(f"\nReturned {min(count, len(series_list))} series (filtered).")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mgi", description="Mistake Gravity Index CLI")
    sub = p.add_subparsers(dest="command", required=True)

    p_titles = sub.add_parser("titles", help="List available titles")
    p_titles.set_defaults(func=lambda args: cmd_titles())

    p_series = sub.add_parser("series", help="Central Data: series commands")
    series_sub = p_series.add_subparsers(dest="series_cmd", required=True)

    p_list = series_sub.add_parser("list", help="List series IDs for a tournament (optionally filter by team name)")
    p_list.add_argument("--tournament-id", required=True, help="Tournament ID (from hackathon list)")
    p_list.add_argument("--team", required=False, help='Filter by team name substring, e.g. "Cloud9"')
    p_list.add_argument("--limit", type=int, default=20, help="Max rows to print (default 20)")
    p_list.set_defaults(func=lambda args: cmd_series_list(args.tournament_id, args.team, args.limit))

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())