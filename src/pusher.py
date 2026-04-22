"""
pusher.py
=========
Pushed workouts naar intervals.icu kalender via POST /events/bulk.

Werkt met upsert: workouts met zelfde external_id worden vervangen ipv gedupliceerd.
Dat betekent: je kunt gerust opnieuw pushen als je iets aanpast, het overschrijft.

Endpoint: POST /api/v1/athlete/{id}/events/bulk?upsert=true
Required scope: CALENDAR:WRITE

Dry-run mode toont wat er gepusht zou worden zonder daadwerkelijke API call.
"""

from __future__ import annotations

import sys
import json
from datetime import date, timedelta
from typing import Optional

from .extractor import IntervalsClient, BASE_URL
from .planner import Workout


class WorkoutPusher:
    """Pusht een lijst Workout objecten naar intervals.icu."""

    def __init__(self, client: IntervalsClient):
        self.client = client

    def push(self, workouts: list, dry_run: bool = False) -> dict:
        """Push een lijst workouts. Return {created, updated, failed}."""
        if not workouts:
            return {"created": 0, "updated": 0, "failed": 0, "details": []}

        payload = [w.to_api_payload() for w in workouts]

        if dry_run:
            print("\n=== DRY RUN — nothing will be pushed ===\n")
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return {
                "created": 0, "updated": 0, "failed": 0,
                "dry_run": True,
                "would_push": len(payload),
                "details": [{"title": w.title, "date": w.date_iso} for w in workouts],
            }

        # Echte push
        url = f"{BASE_URL}/athlete/{self.client.athlete_id}/events/bulk"
        result = self.client._request(
            "POST",
            url,
            params={"upsert": "true"},
            json_body=payload,
        )

        if result is None:
            return {
                "created": 0, "updated": 0, "failed": len(workouts),
                "error": "API call faalde, zie stderr voor details",
            }

        # Result is een array met de gecreeerde/geupdate events
        return {
            "created": len(result),
            "updated": 0,  # API onderscheidt dit niet in response
            "failed": 0,
            "events": [{"id": e.get("id"),
                        "name": e.get("name"),
                        "start_date_local": e.get("start_date_local")}
                       for e in result],
        }

    def delete_by_external_ids(self, external_ids: list) -> int:
        """Verwijder workouts op basis van external_id."""
        if not external_ids:
            return 0

        url = f"{BASE_URL}/athlete/{self.client.athlete_id}/events/bulk-delete"
        payload = [{"external_id": eid} for eid in external_ids]

        result = self.client._request("PUT", url, json_body=payload)
        if result is None:
            return 0
        return result if isinstance(result, int) else 0

    def list_upcoming(self, days_ahead: int = 14) -> list:
        """List gepland workouts in komende N dagen."""
        today = date.today()
        end = today + timedelta(days=days_ahead)
        result = self.client._get(
            f"/events",
            {"oldest": today.isoformat(), "newest": end.isoformat()}
        )
        return result or []


# ============================================================
# TEST workout (voor een dry-run test push)
# ============================================================
def make_test_workout() -> Workout:
    """Maak een dummy 'W99 TEST' workout voor morgen. Handig voor integratie test."""
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    return Workout(
        date_iso=tomorrow,
        title="W99 TEST - veilig te verwijderen",
        sport="Run",
        description=(
            "# Test workout gegenereerd door intervals-coach\n"
            "### Veilig te verwijderen uit kalender\n"
            "\n"
            "- 1km Z2 Pace"
        ),
        external_id="coach_test_workout_delete_me",
    )


# ============================================================
# CLI
# ============================================================
def main():
    import argparse
    from .extractor import load_credentials

    parser = argparse.ArgumentParser(description="Push workouts naar intervals.icu")
    parser.add_argument("--test", action="store_true",
                        help="Push 1 test workout voor morgen")
    parser.add_argument("--delete-test", action="store_true",
                        help="Verwijder de test workout")
    parser.add_argument("--dry-run", action="store_true",
                        help="Toon wat gepusht zou worden, doe niets")
    parser.add_argument("--from-json", type=str,
                        help="Push workouts uit JSON bestand")
    parser.add_argument("--upcoming", action="store_true",
                        help="Toon wat er de komende 14 dagen gepland staat")
    args = parser.parse_args()

    athlete_id, api_key = load_credentials()
    client = IntervalsClient(athlete_id, api_key)
    pusher = WorkoutPusher(client)

    if args.upcoming:
        events = pusher.list_upcoming()
        print(f"Gepland in komende 14 dagen: {len(events)} events")
        for e in events:
            cat = e.get("category", "?")
            print(f"  {e.get('start_date_local', '?')[:10]}  [{cat}]  {e.get('name', '')}")
        return

    if args.test:
        w = make_test_workout()
        result = pusher.push([w], dry_run=args.dry_run)
        print(json.dumps(result, indent=2, default=str))
        return

    if args.delete_test:
        n = pusher.delete_by_external_ids(["coach_test_workout_delete_me"])
        print(f"Verwijderd: {n} events")
        return

    if args.from_json:
        with open(args.from_json) as f:
            data = json.load(f)
        workouts = [Workout(**w) for w in data]
        result = pusher.push(workouts, dry_run=args.dry_run)
        print(json.dumps(result, indent=2, default=str))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
