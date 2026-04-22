"""
weekly.py
=========
Orchestrator voor de wekelijkse coaching flow.

Gebruikt als:
  python -m src.weekly --analyze          # Haal data op en toon analyse
  python -m src.weekly --test-connection  # Test API credentials
  python -m src.weekly --upcoming         # Toon geplande workouts

Voor Claude Code: roep --analyze aan, krijg JSON + markdown rapport,
verwerk in chat, genereer workouts, roep dan pusher aan.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from .extractor import (
    IntervalsClient, load_credentials, collect_activities,
    activities_to_dict,
)
from .analyzer import summarize, to_markdown_report
from .pusher import WorkoutPusher
from .planner import next_week_dates


# ============================================================
# Paden
# ============================================================
PROJECT_ROOT = Path(__file__).parent.parent
CACHE_DIR    = PROJECT_ROOT / "data" / "cache"
PLANS_DIR    = PROJECT_ROOT / "data" / "plans"


def cache_path(name: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / name


# ============================================================
# Commands
# ============================================================
def cmd_test_connection(client: IntervalsClient):
    """Check of API werkt met huidige credentials."""
    try:
        info = client.test_connection()
        name = info.get("name") or info.get("id") or "onbekend"
        print(f"Connection OK: {name} (id={info.get('id')})")
        print(f"Email: {info.get('email')}")
        print(f"Sex / Year: {info.get('sex')} / {info.get('year_of_birth')}")
        return True
    except Exception as e:
        print(f"Connection FAILED: {e}", file=sys.stderr)
        return False


def cmd_analyze(client: IntervalsClient, days: int = 21, save_cache: bool = True):
    """Haal data op, analyseer, toon markdown rapport + cache JSON."""
    activities = collect_activities(client, days=days)

    if save_cache:
        today_iso = date.today().isoformat()
        activities_json = cache_path(f"activities_{today_iso}.json")
        summary_json    = cache_path(f"summary_{today_iso}.json")
        with open(activities_json, "w", encoding="utf-8") as f:
            json.dump(activities_to_dict(activities), f, indent=2, default=str, ensure_ascii=False)
        with open(summary_json, "w", encoding="utf-8") as f:
            json.dump(summarize(activities), f, indent=2, default=str, ensure_ascii=False)
        print(f"Cache saved:", file=sys.stderr)
        print(f"  {activities_json}", file=sys.stderr)
        print(f"  {summary_json}", file=sys.stderr)

    # Toon markdown rapport op stdout (voor Claude Code chat)
    print(to_markdown_report(activities))

    # Toon ook volgende week context
    nw = next_week_dates()
    print(f"\n## Volgende week: {nw['week_label']}")
    print(f"Maandag: {nw['ma'].strftime('%d %b')}  Zondag: {nw['zo'].strftime('%d %b')}")

    return activities


def cmd_upcoming(client: IntervalsClient):
    """Toon wat er de komende 14 dagen in de kalender staat."""
    pusher = WorkoutPusher(client)
    events = pusher.list_upcoming()

    if not events:
        print("Geen geplande events in komende 14 dagen.")
        return

    print(f"Gepland in komende 14 dagen ({len(events)} events):\n")

    weekdag = ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"]
    from datetime import datetime
    for e in sorted(events, key=lambda x: x.get("start_date_local", "")):
        start = e.get("start_date_local", "")[:10]
        try:
            d = datetime.fromisoformat(start).date()
            dag = weekdag[d.weekday()]
        except (ValueError, IndexError):
            dag = "?"
        cat = e.get("category", "?")
        name = e.get("name", "")
        src = "coach" if "coach_" in str(e.get("external_id", "")) else ""
        print(f"  {dag} {start}  [{cat}]  {name} {('(' + src + ')') if src else ''}")


def cmd_last_cache():
    """Toon waar de laatste cache staat (voor Claude Code)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(CACHE_DIR.glob("summary_*.json"))
    if not files:
        print("Geen cache gevonden. Run eerst: python -m src.weekly --analyze")
        return
    latest = files[-1]
    print(f"Laatste cache: {latest}")
    with open(latest) as f:
        data = json.load(f)
    print(json.dumps(data, indent=2, default=str, ensure_ascii=False))


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="Wekelijkse trainingscoach orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Typische flow:
  1. python -m src.weekly --test-connection    # eenmalig na installatie
  2. python -m src.weekly --analyze            # zondag; cache en rapport
  3. (Claude Code chat) -> genereert workouts
  4. python -m src.pusher --dry-run --from-json data/plans/W18.json
  5. python -m src.pusher --from-json data/plans/W18.json  # echte push
  6. python -m src.weekly --upcoming           # check resultaat
""",
    )
    parser.add_argument("--test-connection", action="store_true")
    parser.add_argument("--analyze", action="store_true")
    parser.add_argument("--upcoming", action="store_true")
    parser.add_argument("--last-cache", action="store_true")
    parser.add_argument("--days", type=int, default=21)
    args = parser.parse_args()

    athlete_id, api_key = load_credentials()
    client = IntervalsClient(athlete_id, api_key)

    if args.test_connection:
        ok = cmd_test_connection(client)
        sys.exit(0 if ok else 1)

    if args.analyze:
        cmd_analyze(client, days=args.days)
        return

    if args.upcoming:
        cmd_upcoming(client)
        return

    if args.last_cache:
        cmd_last_cache()
        return

    parser.print_help()


if __name__ == "__main__":
    main()
