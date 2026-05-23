"""
weekly.py
=========
Orchestrator voor de wekelijkse coaching flow.

Gebruikt als:
  python -m src.weekly --analyze          # Haal data op en toon analyse
  python -m src.weekly --test-connection  # Test API credentials
  python -m src.weekly --upcoming         # Toon geplande workouts

Flow:
  1. --analyze              → markdown rapport in chat
  2. (Claude Code chat)     → genereer workouts, sla op als data/plans/W##.json
  3. --dry-run --from-json  → review voor push
  4. --from-json            → echte push
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .extractor import IntervalsClient, load_credentials, collect_activities
from .analyzer import to_markdown_report
from .pusher import WorkoutPusher
from .planner import next_week_dates

PLANS_DIR = Path(__file__).parent.parent / "data" / "plans"


def _clean_plans():
    removed = [f for f in PLANS_DIR.glob("*.json")]
    for f in removed:
        f.unlink()
    if removed:
        print(f"Plans opgeruimd: {len(removed)} bestand(en)", file=sys.stderr)


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


def cmd_analyze(client: IntervalsClient, days: int = 21):
    """Haal data op, analyseer, toon markdown rapport. Ruimt oude plans op."""
    _clean_plans()
    activities = collect_activities(client, days=days)

    print(to_markdown_report(activities))

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


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="Wekelijkse trainingscoach orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Flow:
  1. python -m src.weekly --test-connection
  2. python -m src.weekly --analyze
  3. (Claude Code chat) -> genereer workouts -> data/plans/W##.json
  4. python -m src.pusher --dry-run --from-json data/plans/W##.json
  5. python -m src.pusher --from-json data/plans/W##.json
  6. python -m src.weekly --upcoming
""",
    )
    parser.add_argument("--test-connection", action="store_true")
    parser.add_argument("--analyze", action="store_true")
    parser.add_argument("--upcoming", action="store_true")
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

    parser.print_help()


if __name__ == "__main__":
    main()
