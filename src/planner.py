"""
planner.py
==========
Helpers voor workout generatie. Bevat:

  - Workout dataclass (titel + datum + type + description syntax)
  - Templates voor veelgebruikte workouts (easy run, intervals, long run, rides)
  - ISO week helper
  - Validatie van intervals.icu syntax

De *coaching logica* (welke workout, welke intensiteit) zit NIET hier.
Die gebeurt in Claude Code chat. Dit bestand levert alleen bouwstenen.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from typing import Optional


# ============================================================
# DATACLASS
# ============================================================
@dataclass
class Workout:
    """Een workout klaar om naar intervals.icu gepusht te worden.

    Properties:
      - date_iso: "2026-04-23" format
      - title: bijv "W17 3x 2KM Marathon Pace"
      - sport: "Run" of "Ride" etc (intervals.icu 'type' veld)
      - description: de ruwe workout builder syntax
      - external_id: onze eigen ID om duplicates te voorkomen bij upsert
    """
    date_iso: str
    title: str
    sport: str
    description: str
    external_id: Optional[str] = None

    def __post_init__(self):
        if not self.external_id:
            # Stabiele ID: datum + titel hash
            import hashlib
            h = hashlib.md5(f"{self.date_iso}_{self.title}".encode()).hexdigest()[:12]
            self.external_id = f"coach_{self.date_iso}_{h}"

    def to_api_payload(self) -> dict:
        """Payload voor POST /events/bulk."""
        return {
            "category": "WORKOUT",
            "start_date_local": f"{self.date_iso}T00:00:00",
            "type": self.sport,
            "name": self.title,
            "description": self.description,
            "external_id": self.external_id,
        }


# ============================================================
# ISO week helpers
# ============================================================
def iso_week_number(d: date) -> int:
    return d.isocalendar()[1]


def iso_week_label(d: date) -> str:
    return f"W{iso_week_number(d):02d}"


def date_of_weekday(target_date: date, weekday: int) -> date:
    """Gegeven een datum, return de datum van gekozen weekdag in die ISO-week.
    weekday: 0=maandag, 6=zondag"""
    monday = target_date - timedelta(days=target_date.isocalendar()[2] - 1)
    return monday + timedelta(days=weekday)


def next_week_dates(anchor: Optional[date] = None) -> dict:
    """Return dict met dates voor ma t/m zo van de komende ISO-week.

    Voorbeeld: als vandaag zo 19 april is, return ma 20 apr t/m zo 26 apr.
    """
    today = anchor or date.today()
    # Volgende maandag (of huidige als vandaag ma is)
    days_until_mon = (7 - today.weekday()) % 7
    if days_until_mon == 0 and today.weekday() == 0:
        # We zijn op maandag, gebruik vandaag
        monday = today
    elif days_until_mon == 0:
        # We zijn op zondag, volgende maandag
        monday = today + timedelta(days=1)
    else:
        monday = today + timedelta(days=days_until_mon)

    return {
        "ma": monday,
        "di": monday + timedelta(days=1),
        "wo": monday + timedelta(days=2),
        "do": monday + timedelta(days=3),
        "vr": monday + timedelta(days=4),
        "za": monday + timedelta(days=5),
        "zo": monday + timedelta(days=6),
        "week_label": iso_week_label(monday),
    }


# ============================================================
# TEMPLATES
# ============================================================
def easy_run(wk: str, km: int, d: date) -> Workout:
    """Easy run in Z2."""
    return Workout(
        date_iso=d.isoformat(),
        title=f"{wk} {km}KM Easy Run",
        sport="Run",
        description=f"- {km}km Z2 Pace",
    )


def long_run(wk: str, km: int, d: date,
             mp_finish_km: int = 0) -> Workout:
    """Long run, optioneel met marathon pace finish."""
    if mp_finish_km > 0:
        title = f"{wk} {km}KM Long Run + {mp_finish_km}KM Marathon Pace"
        body = (
            "Warmup\n"
            "- 3km Z2 Pace\n"
            "\n"
            "Main\n"
            f"- {km - 3 - mp_finish_km - 2}km Z2 Pace\n"
            "\n"
            "Marathon pace finish\n"
            f"- {mp_finish_km}km Z3 Pace\n"
            "\n"
            "Cooldown\n"
            "- 2km Z2 Pace"
        )
    else:
        title = f"{wk} {km}KM Long Run"
        body = (
            "Warmup\n"
            "- 3km Z2 Pace\n"
            "\n"
            "Main\n"
            f"- {km - 5}km Z2 Pace\n"
            "\n"
            "Cooldown\n"
            "- 2km Z2 Pace"
        )

    return Workout(
        date_iso=d.isoformat(),
        title=title,
        sport="Run",
        description=body,
    )


def interval_session(wk: str, d: date,
                      reps: int, interval_km: float, target_zone: str,
                      rest_s: int = 90,
                      session_type: str = "Intervals",
                      warmup_km: int = 2, cooldown_km: int = 1) -> Workout:
    """Generieke interval sessie.

    Args:
        wk: week label ('W17')
        d: datum
        reps: aantal herhalingen
        interval_km: afstand per rep in km (kan float, bv 0.4 voor 400m)
        target_zone: 'Z3' voor Marathon Pace, 'Z4' voor Threshold, 'Z5' voor VO2max
        rest_s: rust in seconden (default 90s)
        session_type: 'Intervals', 'Marathon Pace', 'Threshold', 'VO2Max', 'Tempo'
        warmup_km: warmup distance
        cooldown_km: cooldown distance
    """
    # Titel format
    if interval_km >= 1:
        interval_label = f"{int(interval_km)}KM"
    else:
        interval_label = f"{int(interval_km * 1000)}M"

    title = f"{wk} {reps}x {interval_label} {session_type}"

    # Syntax voor de interval: km of meters
    if interval_km >= 1:
        interval_syntax = f"- {interval_km:g}km {target_zone} Pace"
    else:
        interval_syntax = f"- {int(interval_km * 1000)}mtr {target_zone} Pace"

    # Rust format
    if rest_s >= 60:
        if rest_s % 60 == 0:
            rest_syntax = f"- {rest_s // 60}m Z2 Pace"
        else:
            rest_syntax = f"- {rest_s}s Z2 Pace"
    else:
        rest_syntax = f"- {rest_s}s Z2 Pace"

    body = (
        "Warmup\n"
        f"- {warmup_km}km Z2 Pace\n"
        "\n"
        f"Main set {reps}x\n"
        f"{interval_syntax}\n"
        f"{rest_syntax}\n"
        "\n"
        "Cooldown\n"
        f"- {cooldown_km}km Z2 Pace"
    )

    return Workout(
        date_iso=d.isoformat(),
        title=title,
        sport="Run",
        description=body,
    )


def easy_ride(wk: str, minutes: int, d: date,
              cadence_range: str = "85-95rpm") -> Workout:
    """Easy fiets in Z1-Z2 HR."""
    return Workout(
        date_iso=d.isoformat(),
        title=f"{wk} {minutes}min Easy Ride",
        sport="Ride",
        description=f"- {minutes}m Z1-Z2 HR {cadence_range}",
    )


def endurance_ride(wk: str, minutes: int, d: date,
                   cadence_range: str = "85-95rpm") -> Workout:
    """Endurance fiets, puur Z2."""
    return Workout(
        date_iso=d.isoformat(),
        title=f"{wk} {minutes}min Endurance Ride",
        sport="Ride",
        description=f"- {minutes}m Z2 HR {cadence_range}",
    )


# ============================================================
# VALIDATION
# ============================================================
def validate_workout(w: Workout) -> list:
    """Check of workout klopt voor intervals.icu. Return lijst van warnings."""
    warnings = []

    if not w.title:
        warnings.append("Geen titel")
    elif not w.title.startswith("W"):
        warnings.append(f"Titel begint niet met W##: '{w.title}'")

    if not w.description.strip():
        warnings.append("Lege description")

    # Check datum
    try:
        datetime.fromisoformat(w.date_iso)
    except ValueError:
        warnings.append(f"Ongeldig datum format: {w.date_iso}")

    # Check sport
    valid_sports = {"Run", "TrailRun", "Ride", "VirtualRide", "Swim", "WeightTraining"}
    if w.sport not in valid_sports:
        warnings.append(f"Onbekend sport type: {w.sport}")

    # Check syntax basics
    desc = w.description
    if w.sport in {"Run", "TrailRun"}:
        if "HR" in desc and "Pace" not in desc:
            warnings.append("Run workout gebruikt HR ipv Pace; niet volgens coaching regel")
    if w.sport in {"Ride", "VirtualRide"}:
        if "Pace" in desc:
            warnings.append("Ride workout gebruikt Pace; moet HR zijn")

    # Rust binnen intervals: check voor 90s voorkeur
    # (alleen waarschuwing, niet blokkerend)
    if "- 60s " in desc or "- 1m " in desc.replace("- 1m Z", "XXX"):
        warnings.append("Rust lijkt 60s/1m te zijn; coaching voorkeur is 90s")

    return warnings


# ============================================================
# PRINT HELPERS
# ============================================================
def format_week_plan(workouts: list) -> str:
    """Maak een leesbaar overzicht van een weekplan."""
    if not workouts:
        return "Geen workouts gepland."

    # Sorteer op datum
    workouts = sorted(workouts, key=lambda w: w.date_iso)

    lines = []
    weekdag = ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"]
    for w in workouts:
        d = datetime.fromisoformat(w.date_iso).date()
        dag = weekdag[d.weekday()]
        lines.append(f"\n## {dag} {d.strftime('%d %b')} — {w.title}")
        lines.append("```")
        lines.append(w.description)
        lines.append("```")

    return "\n".join(lines)


def workouts_to_json(workouts: list) -> str:
    """JSON export van een hele week."""
    import json
    return json.dumps(
        [asdict(w) for w in workouts],
        indent=2, ensure_ascii=False, default=str,
    )
