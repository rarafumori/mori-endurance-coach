"""
extractor.py
============
Haalt data op uit intervals.icu API.
Bestaat uit:
  - IntervalsClient: lage-niveau HTTP wrapper met retry en auth
  - Activity / IntervalBlock / TrainingFocus dataclasses
  - parse_activity(): ruwe JSON naar genormaliseerd Activity object
  - collect_activities(): hoofdfunctie voor "laatste N dagen"

Dit bestand doet alleen lezen. Schrijven gaat via pusher.py.
"""

from __future__ import annotations

import os
import sys
import time
import json
from dataclasses import dataclass, asdict, field
from datetime import date, timedelta
from typing import Optional, Any
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth
from urllib3.util.retry import Retry


# ============================================================
# CONSTANTS
# ============================================================
BASE_URL = "https://intervals.icu/api/v1"
RUN_TYPES      = {"Run", "TrailRun", "VirtualRun"}
RIDE_TYPES     = {"Ride", "VirtualRide", "GravelRide", "MountainBikeRide"}
STRENGTH_TYPES = {"WeightTraining", "Strength", "Workout", "Crossfit"}
RELEVANT_TYPES = RUN_TYPES | RIDE_TYPES | STRENGTH_TYPES
FEEL_MAP = {1: "Strong", 2: "Good", 3: "Normal", 4: "Poor", 5: "Weak"}


# ============================================================
# DATACLASSES
# ============================================================
@dataclass
class IntervalBlock:
    """Een geclusterde groep van gelijke work-intervals binnen een activiteit."""
    count: int
    avg_distance_m: int
    avg_duration_s: int
    avg_heartrate: Optional[int]
    avg_pace_sec_per_km: Optional[float]
    avg_intensity_pct: Optional[int]
    first_start_time: Optional[int] = None

    @property
    def pace_label(self) -> str:
        if not self.avg_pace_sec_per_km:
            return "-"
        m, s = divmod(int(self.avg_pace_sec_per_km), 60)
        return f"{m}:{s:02d}"


@dataclass
class TrainingFocus:
    """Afgeleide: welk trainingseffect is dominant deze activiteit?"""
    primary: str
    zone_time_pct: dict
    high_intensity_pct: int
    moderate_intensity_pct: int
    easy_intensity_pct: int


@dataclass
class Activity:
    """Genormaliseerde activiteit met alles wat een coach nodig heeft."""
    id: str
    date: str
    type: str
    name: Optional[str] = None
    description: Optional[str] = None

    # Prestatie
    distance_km: Optional[float] = None
    moving_time_min: Optional[float] = None
    elevation_gain_m: Optional[int] = None
    avg_heartrate: Optional[int] = None
    max_heartrate: Optional[int] = None
    avg_pace_sec_per_km: Optional[float] = None
    avg_cadence: Optional[float] = None
    avg_stride_m: Optional[float] = None

    # Belasting
    training_load: Optional[int] = None
    hr_load: Optional[int] = None
    pace_load: Optional[int] = None
    intensity_factor_pct: Optional[int] = None
    efficiency_factor: Optional[float] = None
    decoupling_pct: Optional[float] = None
    trimp: Optional[float] = None
    polarization_index: Optional[float] = None

    # Fitness state
    ctl: Optional[float] = None
    atl: Optional[float] = None
    form_tsb: Optional[float] = None

    # Subjectief
    rpe: Optional[int] = None
    feel: Optional[str] = None
    session_rpe: Optional[int] = None
    compliance_pct: Optional[float] = None

    # Wellness (van diezelfde dag)
    hrv: Optional[float] = None
    resting_hr: Optional[int] = None
    weight_kg: Optional[float] = None
    vo2max: Optional[float] = None
    sleep_hours: Optional[float] = None
    sleep_score: Optional[int] = None
    body_fat_pct: Optional[float] = None
    steps: Optional[int] = None

    # Afgeleide analyse
    training_focus: Optional[TrainingFocus] = None
    interval_blocks: list = field(default_factory=list)
    main_work_set: Optional[IntervalBlock] = None
    interval_summary_raw: Optional[list] = None

    @property
    def pace_label(self) -> str:
        if not self.avg_pace_sec_per_km:
            return "-"
        m, s = divmod(int(self.avg_pace_sec_per_km), 60)
        return f"{m}:{s:02d}"

    @property
    def is_run(self) -> bool:
        return self.type in RUN_TYPES


# ============================================================
# API CLIENT
# ============================================================
class IntervalsClient:
    """HTTP wrapper voor intervals.icu met retry en auth.

    Auth: API key via HTTP Basic (username is letterlijk 'API_KEY', password is de key).
    Retry: 3x bij 429/5xx met exponential backoff.
    """

    def __init__(self, athlete_id: str, api_key: str, delay: float = 0.15):
        self.athlete_id = athlete_id
        self.api_key = api_key
        self.base = f"{BASE_URL}/athlete/{athlete_id}"
        self.delay = delay

        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth("API_KEY", api_key)

        retry = Retry(
            total=3, backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT"],
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def _request(self, method: str, path: str,
                 params: Optional[dict] = None,
                 json_body: Optional[Any] = None) -> Optional[Any]:
        """Generieke request met error handling."""
        url = path if path.startswith("http") else f"{self.base}{path}"
        try:
            r = self.session.request(method, url, params=params, json=json_body, timeout=15)
            r.raise_for_status()
            if r.content:
                return r.json()
            return {}
        except requests.HTTPError as e:
            print(f"HTTP fout {method} {url}: {e}", file=sys.stderr)
            if e.response is not None and e.response.text:
                print(f"  Response: {e.response.text[:500]}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"Netwerk fout {method} {url}: {e}", file=sys.stderr)
        except ValueError as e:
            print(f"JSON parse fout {method} {url}: {e}", file=sys.stderr)
        return None

    def _get(self, path: str, params: Optional[dict] = None) -> Optional[Any]:
        return self._request("GET", path, params=params)

    # --- READ endpoints ---
    def get_wellness(self, start: str, end: str) -> dict:
        data = self._get("/wellness", {"oldest": start, "newest": end})
        return {d["id"]: d for d in data} if data else {}

    def get_activities(self, start: str, end: str) -> list:
        return self._get("/activities", {"oldest": start, "newest": end}) or []

    def get_activity_intervals(self, activity_id: str) -> Optional[dict]:
        time.sleep(self.delay)
        return self._get(f"{BASE_URL}/activity/{activity_id}/intervals")

    def get_activity_raw(self, activity_id: str) -> Optional[dict]:
        return self._get(f"{BASE_URL}/activity/{activity_id}")

    def test_connection(self) -> dict:
        """Test of credentials werken. Returnt athlete info of raised Exception."""
        r = self.session.get(f"{BASE_URL}/athlete/{self.athlete_id}", timeout=10)
        r.raise_for_status()
        return r.json()


# ============================================================
# ANALYSE helpers
# ============================================================
def determine_training_focus(raw: dict) -> Optional[TrainingFocus]:
    """Bepaal trainingsfocus op basis van tijd per pace zone."""
    zone_times = raw.get("gap_zone_times") if raw.get("use_gap_zone_times") else None
    zone_times = zone_times or raw.get("pace_zone_times") or raw.get("icu_hr_zone_times")
    if not zone_times or not any(zone_times):
        return None
    total = sum(zone_times)
    if total == 0:
        return None
    pct = {f"Z{i+1}": round(100 * t / total) for i, t in enumerate(zone_times)}
    easy     = pct.get("Z1", 0) + pct.get("Z2", 0)
    moderate = pct.get("Z3", 0) + pct.get("Z4", 0)
    hard     = pct.get("Z5", 0) + pct.get("Z6", 0) + pct.get("Z7", 0)

    if hard >= 8:
        if easy >= 40:
            primary = "Intervals (VO2max)" if hard >= 10 else "Intervals"
        else:
            primary = "VO2max"
    elif moderate >= 15:
        primary = "Threshold" if pct.get("Z4", 0) >= 10 else "Tempo"
    elif easy >= 80:
        primary = "Recovery" if pct.get("Z1", 0) >= 60 else "Base / Endurance"
    else:
        primary = "Mixed"

    return TrainingFocus(
        primary=primary, zone_time_pct=pct,
        high_intensity_pct=hard, moderate_intensity_pct=moderate,
        easy_intensity_pct=easy,
    )


def cluster_work_intervals(intervals: list) -> list:
    """Cluster work-intervals op group_id, chronologisch."""
    work = [i for i in intervals if str(i.get("type", "")).upper() == "WORK"]
    if not work:
        return []
    groups: dict = {}
    for itv in work:
        key = itv.get("group_id") or f"dist_{round(itv.get('distance', 0) / 100) * 100}"
        groups.setdefault(key, []).append(itv)

    blocks = []
    for items in groups.values():
        items = [i for i in items if (i.get("distance") or 0) >= 50]
        if not items:
            continue
        distances = [i["distance"] for i in items]
        durations = [i["moving_time"] for i in items]
        speeds    = [i["average_speed"] for i in items if i.get("average_speed")]
        hrs       = [i["average_heartrate"] for i in items if i.get("average_heartrate")]
        intens    = [i["intensity"] for i in items if i.get("intensity") is not None]
        starts    = [i.get("start_time", 0) for i in items]
        avg_pace  = (sum(1000 / s for s in speeds) / len(speeds)) if speeds else None
        blocks.append(IntervalBlock(
            count=len(items),
            avg_distance_m=round(sum(distances) / len(items)),
            avg_duration_s=round(sum(durations) / len(items)),
            avg_heartrate=round(sum(hrs) / len(hrs)) if hrs else None,
            avg_pace_sec_per_km=avg_pace,
            avg_intensity_pct=round(sum(intens) / len(intens)) if intens else 0,
            first_start_time=min(starts) if starts else None,
        ))
    blocks.sort(key=lambda b: b.first_start_time if b.first_start_time is not None else 0)
    return blocks


def identify_main_work_set(blocks: list, min_intensity: int = 82) -> Optional[IntervalBlock]:
    """Grootste hoog-intensief blok = de 'echte' work set."""
    if not blocks:
        return None
    high = [b for b in blocks if (b.avg_intensity_pct or 0) >= min_intensity]
    if not high:
        return None
    high.sort(key=lambda b: (-b.count, -(b.avg_intensity_pct or 0)))
    return high[0]


# ============================================================
# PARSING
# ============================================================
def parse_activity(raw: dict, wellness_by_date: dict, intervals_data: Optional[dict]) -> Activity:
    """Ruwe API JSON -> genormaliseerd Activity object."""
    act_id = str(raw.get("id", ""))
    d = (raw.get("start_date_local") or "")[:10]
    t = raw.get("type", "")
    w = wellness_by_date.get(d, {})

    dist_m = raw.get("distance")
    dist_km = dist_m / 1000 if isinstance(dist_m, (int, float)) and dist_m > 0 else None
    moving = raw.get("moving_time")
    speed = raw.get("average_speed")
    pace_s = 1000 / speed if speed and speed > 0 and t in RUN_TYPES else None
    hr = raw.get("average_heartrate")
    max_hr = raw.get("max_heartrate")
    if_pct = raw.get("icu_intensity")
    ef = raw.get("icu_efficiency_factor")
    if ef is None and speed and hr and t in RUN_TYPES:
        ef = (speed * 60) / hr

    ctl = raw.get("icu_ctl")
    atl = raw.get("icu_atl")
    tsb = (ctl - atl) if (ctl is not None and atl is not None) else None

    sleep_secs = w.get("sleepSecs")
    sleep_hours = sleep_secs / 3600 if sleep_secs else None

    act = Activity(
        id=act_id, date=d, type=t,
        name=raw.get("name"), description=raw.get("description"),
        distance_km=round(dist_km, 2) if dist_km else None,
        moving_time_min=round(moving / 60, 1) if moving else None,
        elevation_gain_m=round(raw["total_elevation_gain"]) if raw.get("total_elevation_gain") else None,
        avg_heartrate=round(hr) if hr else None,
        max_heartrate=round(max_hr) if max_hr else None,
        avg_pace_sec_per_km=pace_s,
        avg_cadence=round(raw["average_cadence"], 1) if raw.get("average_cadence") else None,
        avg_stride_m=round(raw["average_stride"], 2) if raw.get("average_stride") else None,
        training_load=raw.get("icu_training_load"),
        hr_load=raw.get("hr_load"),
        pace_load=raw.get("pace_load"),
        intensity_factor_pct=round(if_pct) if if_pct else None,
        efficiency_factor=round(ef, 2) if ef else None,
        decoupling_pct=round(raw["decoupling"], 1) if raw.get("decoupling") else None,
        trimp=round(raw["trimp"], 1) if raw.get("trimp") else None,
        polarization_index=raw.get("polarization_index"),
        ctl=round(ctl, 1) if ctl else None,
        atl=round(atl, 1) if atl else None,
        form_tsb=round(tsb, 1) if tsb is not None else None,
        rpe=raw.get("icu_rpe"),
        feel=FEEL_MAP.get(raw.get("feel")),
        session_rpe=raw.get("session_rpe"),
        compliance_pct=round(raw["compliance"], 1) if raw.get("compliance") else None,
        hrv=w.get("hrv"),
        resting_hr=w.get("restingHR"),
        weight_kg=round(w["weight"], 1) if w.get("weight") else None,
        vo2max=round(w["vo2max"], 1) if w.get("vo2max") else None,
        sleep_hours=round(sleep_hours, 1) if sleep_hours else None,
        sleep_score=round(w["sleepScore"]) if w.get("sleepScore") else None,
        body_fat_pct=w.get("bodyFat"),
        steps=w.get("steps"),
        training_focus=determine_training_focus(raw),
        interval_summary_raw=raw.get("interval_summary"),
    )

    if intervals_data and isinstance(intervals_data, dict):
        icu_intervals = intervals_data.get("icu_intervals") or []
        act.interval_blocks = cluster_work_intervals(icu_intervals)
        act.main_work_set = identify_main_work_set(act.interval_blocks)

    return act


# ============================================================
# HOOFD FUNCTIE
# ============================================================
def collect_activities(client: IntervalsClient, days: int = 21) -> list:
    """Haal alle relevante activiteiten van laatste N dagen op, genormaliseerd."""
    today = date.today()
    start = (today - timedelta(days=days)).isoformat()
    end   = (today + timedelta(days=1)).isoformat()

    print(f"Data ophalen {start} tot {end}...", file=sys.stderr)
    wellness = client.get_wellness(start, end)
    raw_list = client.get_activities(start, end)

    activities = []
    for raw in raw_list:
        if raw.get("type") not in RELEVANT_TYPES:
            continue
        intervals_data = None
        if raw.get("type") in RUN_TYPES:
            intervals_data = client.get_activity_intervals(str(raw.get("id", "")))
        activities.append(parse_activity(raw, wellness, intervals_data))

    # Nieuwste eerst
    activities.sort(key=lambda a: a.date, reverse=True)
    return activities


def activities_to_dict(activities: list) -> dict:
    """Compacte dict voor JSON output."""
    def encode(obj):
        if hasattr(obj, "__dataclass_fields__"):
            return {k: v for k, v in asdict(obj).items() if v is not None and v != []}
        return obj
    return {
        "generated_at": date.today().isoformat(),
        "activity_count": len(activities),
        "activities": [encode(a) for a in activities],
    }


# ============================================================
# ENV loader
# ============================================================
def load_credentials() -> tuple[str, str]:
    """Lees credentials uit config/.env."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("dotenv niet geinstalleerd. Run: pip install python-dotenv", file=sys.stderr)
        sys.exit(1)

    env_path = Path(__file__).parent.parent / "config" / ".env"
    if not env_path.exists():
        print(f"Credentials ontbreken: {env_path}", file=sys.stderr)
        print("Kopieer config/.env.example naar config/.env en vul in.", file=sys.stderr)
        sys.exit(1)

    load_dotenv(env_path)
    athlete_id = os.getenv("INTERVALS_ATHLETE_ID")
    api_key    = os.getenv("INTERVALS_API_KEY")
    if not athlete_id or not api_key:
        print("INTERVALS_ATHLETE_ID of INTERVALS_API_KEY ontbreekt in .env", file=sys.stderr)
        sys.exit(1)
    return athlete_id, api_key


# ============================================================
# CLI
# ============================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Extract intervals.icu data")
    parser.add_argument("--days", type=int, default=21)
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--debug", metavar="ID", help="Dump 1 activity")
    args = parser.parse_args()

    athlete_id, api_key = load_credentials()
    client = IntervalsClient(athlete_id, api_key)

    if args.debug:
        raw = client.get_activity_raw(args.debug)
        intervals = client.get_activity_intervals(args.debug)
        datum = (raw.get("start_date_local") or "")[:10]
        wellness = client.get_wellness(datum, datum)
        act = parse_activity(raw, wellness, intervals)
        print(json.dumps(activities_to_dict([act]), indent=2, default=str, ensure_ascii=False))
        return

    activities = collect_activities(client, days=args.days)
    print(json.dumps(activities_to_dict(activities), indent=2, default=str, ensure_ascii=False))


if __name__ == "__main__":
    main()
