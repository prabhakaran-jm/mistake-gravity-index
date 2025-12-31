from __future__ import annotations
import argparse
from typing import Optional

from rich.console import Console
from rich.table import Table

from mgi.config import get_settings
from mgi.grid.client import GridGraphQLClient
from mgi.grid.central_data import iter_series_by_tournament, get_titles

from pathlib import Path
from mgi.grid.file_download import GridFileDownloadClient

from mgi.features import mistakes_untraded

from mgi.logging_conf import setup_logging


def cmd_titles() -> int:
    settings = get_settings()
    client = GridGraphQLClient(base_url=settings.grid_central_data_url, api_key=settings.grid_api_key)
    titles = get_titles(client)

    console = Console()
    table = Table(title="Available Titles")
    table.add_column("ID", justify="right", style="cyan")
    table.add_column("Name", style="magenta")

    for t in titles:
        table.add_row(str(t.get('id')), t.get('name'))

    console.print(table)
    return 0


def cmd_series_list(tournament_id: str, team: Optional[str], limit: int) -> int:
    settings = get_settings()
    client = GridGraphQLClient(base_url=settings.grid_central_data_url, api_key=settings.grid_api_key)

    series_list = iter_series_by_tournament(client, tournament_id=tournament_id, team_filter=team)

    if not series_list:
        print("No series found for given filters.")
        return 0

    console = Console()
    table = Table(title=f"Series for Tournament: {tournament_id}")
    table.add_column("ID", style="cyan")
    table.add_column("Scheduled Start", style="green")
    table.add_column("Title", style="yellow")
    table.add_column("Tournament", style="magenta")
    table.add_column("Teams", style="blue")

    count = 0
    for s in series_list:
        table.add_row(
            s.id,
            s.start_time_scheduled or "N/A",
            s.title_short or "N/A",
            s.tournament_name or "N/A",
            ", ".join(s.teams)
        )
        count += 1
        if limit and count >= limit:
            break

    console.print(table)
    print(f"\nReturned {min(count, len(series_list))} series (filtered).")
    return 0

def cmd_series_fetch(series_id: str) -> int:
    settings = get_settings()

    client = GridFileDownloadClient(
        base_url=settings.grid_file_base_url,
        api_key=settings.grid_api_key,
    )

    listing = client.list_files(series_id)
    files = listing.get("files", [])

    if not files:
        print("No downloadable files found for this series.")
        print(listing)
        return 1

    # Find urls
    events = next((f for f in files if f.get("id") == "events-grid"), None)
    state = next((f for f in files if f.get("id") == "state-grid"), None)

    out_dir = Path("data") / "raw" / f"series_{series_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save listing for audit/debug
    GridFileDownloadClient.pretty_save_json(listing, out_dir / "file_list.json")

    if state and state.get("fullURL"):
        print(f"Downloading end state: {state.get('fileName')}")
        # end-state is JSON, save pretty
        state_obj = client.session.get(state["fullURL"], timeout=120).json()
        GridFileDownloadClient.pretty_save_json(state_obj, out_dir / "end_state.json")
    else:
        print("state-grid not available or missing fullURL.")

    if events and events.get("fullURL"):
        print(f"Downloading events: {events.get('fileName')}")
        zip_path = out_dir / "events.jsonl.zip"
        client.download_to(events["fullURL"], zip_path)
        jsonl_path = out_dir / "events.jsonl"
        client.unzip_first_jsonl(zip_path, jsonl_path)
        print(f"Extracted: {jsonl_path}")
    else:
        print("events-grid not available or missing fullURL.")

    print(f"Saved files under: {out_dir}")
    return 0

def cmd_mistakes_untraded(series_id: str, top: int, window_seconds: int) -> int:
    return mistakes_untraded.run(series_id=series_id, top=top, window_seconds=window_seconds)

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

    p_fetch = series_sub.add_parser("fetch", help="Download series files via File Download API (events + end_state)")
    p_fetch.add_argument("--series-id", required=True, help="Series ID from Central Data")
    p_fetch.set_defaults(func=lambda args: cmd_series_fetch(args.series_id))

    p_mistakes = sub.add_parser("mistakes", help="Mistake extraction commands")
    mistakes_sub = p_mistakes.add_subparsers(dest="mistakes_cmd", required=True)

    p_untraded = mistakes_sub.add_parser("untraded", help="Extract untraded deaths from events.jsonl")
    p_untraded.add_argument("--series-id", required=True, help="Series ID")
    p_untraded.add_argument("--top", type=int, default=10, help="Rows to print (default 10)")
    p_untraded.add_argument("--window-seconds", type=int, default=10, help="Trade window in seconds (default 10)")
    p_untraded.set_defaults(func=lambda args: cmd_mistakes_untraded(args.series_id, args.top, args.window_seconds))

    return p


def main() -> int:
    setup_logging()
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        raise SystemExit(130)
    except Exception as e:
        print(f"\nError: {e}")
        raise SystemExit(1)