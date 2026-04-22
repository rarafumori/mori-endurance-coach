"""
analyzer.py
===========
Maakt een leesbare samenvatting van de laatste 21 dagen trainingsdata.

Input: lijst van Activity objecten (uit extractor.py)
Output: dict met trends + een markdown rapport dat Claude Code kan tonen

Wat hierin zit:
  - Weekly volume (km per week, load per week)
  - TSB trend (laatste 7 dagen)
  - HRV baseline en dips
  - Slaap gemiddelde en slechte nachten
  - Belangrijkste recente sessies
  - Quality vs easy verdeling

De analyse is beschrijvend, GEEN coaching beslissingen.
Coaching gebeurt in Claude Code chat met deze data als input.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import mean, median, stdev
from typing import Optional


def _parse_date(s: str) -> date:
    return datetime.fromisoformat(s).date()


def _iso_week(d: date) -> str:
    """Return W## voor ISO kalenderweek."""
    return f"W{d.isocalendar()[1]:02d}"


def weekly_volume(activities: list) -> dict:
    """Km en load per ISO week."""
    by_week = defaultdict(lambda: {"km": 0.0, "load": 0, "sessions": 0, "run_km": 0.0})
    for a in activities:
        if not a.date:
            continue
        d = _parse_date(a.date)
        w = _iso_week(d)
        by_week[w]["sessions"] += 1
        if a.distance_km:
            by_week[w]["km"] += a.distance_km
            if a.is_run:
                by_week[w]["run_km"] += a.distance_km
        if a.training_load:
            by_week[w]["load"] += a.training_load
    return {k: {kk: round(vv, 1) if isinstance(vv, float) else vv
                for kk, vv in v.items()}
            for k, v in sorted(by_week.items())}


def tsb_curve(activities: list) -> list:
    """Return [(date, tsb)] chronologisch, 1 punt per unieke datum."""
    seen = {}
    for a in activities:
        if a.form_tsb is not None and a.date:
            seen[a.date] = a.form_tsb
    return [(d, seen[d]) for d in sorted(seen.keys())]


def hrv_analysis(activities: list) -> dict:
    """Gemiddeld HRV, range, en dagen met dip onder baseline - 20%."""
    values = [(a.date, a.hrv) for a in activities if a.hrv]
    if not values:
        return {"count": 0}

    hrvs = [v for _, v in values]
    baseline = median(hrvs)
    threshold = baseline * 0.8
    dips = [(d, v) for d, v in values if v < threshold]

    return {
        "count": len(values),
        "baseline_median": round(baseline, 1),
        "min": round(min(hrvs), 1),
        "max": round(max(hrvs), 1),
        "stdev": round(stdev(hrvs), 1) if len(hrvs) > 1 else 0,
        "dip_days": dips,
    }


def sleep_analysis(activities: list) -> dict:
    """Slaap gemiddelde en nachten onder 7 uur."""
    seen = {}  # per datum 1 waarde
    for a in activities:
        if a.sleep_hours and a.date:
            seen[a.date] = a.sleep_hours
    if not seen:
        return {"count": 0}

    hours = list(seen.values())
    bad_nights = [(d, h) for d, h in seen.items() if h < 7.0]
    return {
        "count": len(hours),
        "avg_hours": round(mean(hours), 1),
        "min_hours": round(min(hours), 1),
        "bad_nights": sorted(bad_nights),
    }


def quality_distribution(activities: list) -> dict:
    """% easy vs moderate vs hard sessies (alleen runs)."""
    focus_counts = defaultdict(int)
    total = 0
    for a in activities:
        if a.is_run and a.training_focus:
            focus_counts[a.training_focus.primary] += 1
            total += 1
    if total == 0:
        return {}
    return {k: {"count": v, "pct": round(100 * v / total)} for k, v in focus_counts.items()}


def recent_key_sessions(activities: list, n: int = 5) -> list:
    """Laatste N kwaliteitssessies (main_work_set aanwezig OF long run)."""
    key = []
    for a in activities:
        if a.main_work_set or (a.is_run and a.distance_km and a.distance_km >= 18):
            key.append(a)
    return key[:n]


def form_state(activities: list) -> dict:
    """Huidige CTL/ATL/TSB en trend."""
    sorted_acts = sorted([a for a in activities if a.form_tsb is not None],
                         key=lambda x: x.date)
    if not sorted_acts:
        return {}

    latest = sorted_acts[-1]
    earliest = sorted_acts[0]

    tsb_trend = "stabiel"
    if latest.form_tsb < earliest.form_tsb - 5:
        tsb_trend = "oplopende vermoeidheid (TSB daalt)"
    elif latest.form_tsb > earliest.form_tsb + 5:
        tsb_trend = "herstellend (TSB stijgt)"

    return {
        "latest_date": latest.date,
        "ctl": latest.ctl,
        "atl": latest.atl,
        "tsb": latest.form_tsb,
        "tsb_trend": tsb_trend,
        "tsb_start_of_period": earliest.form_tsb,
    }


def summarize(activities: list) -> dict:
    """Volledige analyse in 1 dict."""
    return {
        "period": {
            "activity_count": len(activities),
            "from": min(a.date for a in activities) if activities else None,
            "to":   max(a.date for a in activities) if activities else None,
        },
        "weekly_volume": weekly_volume(activities),
        "form": form_state(activities),
        "hrv": hrv_analysis(activities),
        "sleep": sleep_analysis(activities),
        "quality_distribution": quality_distribution(activities),
        "tsb_curve": [(d, round(v, 1)) for d, v in tsb_curve(activities)],
        "key_sessions_count": len(recent_key_sessions(activities)),
    }


def to_markdown_report(activities: list) -> str:
    """
    Markdown rapport voor Claude Code chat. Bedoeld om direct aan de chat te tonen.
    Geen kleuring, geen emoji, zuinig met formatting.
    """
    if not activities:
        return "Geen data beschikbaar voor deze periode."

    s = summarize(activities)
    lines = []

    # Header
    lines.append(f"# Trainingsanalyse {s['period']['from']} tot {s['period']['to']}")
    lines.append(f"")
    lines.append(f"**{s['period']['activity_count']} activiteiten in deze periode.**")
    lines.append(f"")

    # Form state
    f = s.get("form", {})
    if f:
        lines.append(f"## Form en Load")
        lines.append(f"- CTL (fitness): {f.get('ctl')}")
        lines.append(f"- ATL (vermoeidheid): {f.get('atl')}")
        lines.append(f"- TSB (form): {f.get('tsb'):+.1f} {'(negatief = vermoeid)' if f.get('tsb', 0) < 0 else '(positief = fris)'}")
        lines.append(f"- Trend: {f.get('tsb_trend')}")
        lines.append(f"")

    # Weekly volume
    if s.get("weekly_volume"):
        lines.append(f"## Wekelijks Volume")
        lines.append("| Week | Km | Run km | Load | Sessions |")
        lines.append("|------|-----|--------|------|----------|")
        for wk, v in s["weekly_volume"].items():
            lines.append(f"| {wk} | {v['km']} | {v['run_km']} | {v['load']} | {v['sessions']} |")
        lines.append(f"")

    # HRV
    hrv = s.get("hrv", {})
    if hrv.get("count"):
        lines.append(f"## HRV (Hartritme Variabiliteit)")
        lines.append(f"- Baseline (mediaan): {hrv['baseline_median']}")
        lines.append(f"- Range: {hrv['min']} tot {hrv['max']}")
        if hrv["dip_days"]:
            lines.append(f"- Dips onder 80% baseline ({len(hrv['dip_days'])} dagen):")
            for d, v in hrv["dip_days"]:
                lines.append(f"  - {d}: {v}")
        lines.append(f"")

    # Slaap
    sleep = s.get("sleep", {})
    if sleep.get("count"):
        lines.append(f"## Slaap")
        lines.append(f"- Gemiddeld: {sleep['avg_hours']}h per nacht")
        lines.append(f"- Minste: {sleep['min_hours']}h")
        if sleep["bad_nights"]:
            lines.append(f"- Korte nachten (<7h): {len(sleep['bad_nights'])} stuks")
        lines.append(f"")

    # Quality distribution
    qd = s.get("quality_distribution", {})
    if qd:
        lines.append(f"## Run Kwaliteit Verdeling")
        for focus, v in sorted(qd.items(), key=lambda x: -x[1]["count"]):
            lines.append(f"- {focus}: {v['count']} sessies ({v['pct']}%)")
        lines.append(f"")

    # Key sessions
    key = recent_key_sessions(activities)
    if key:
        lines.append(f"## Belangrijkste Recente Sessies")
        for a in key:
            line = f"- **{a.date}** — {a.name or a.type}"
            if a.distance_km:
                line += f" ({a.distance_km}km"
                if a.pace_label != "-":
                    line += f", {a.pace_label}/km"
                line += ")"
            if a.main_work_set:
                ws = a.main_work_set
                line += f" — main set: {ws.count}x {ws.avg_distance_m}m @ {ws.pace_label}/km"
            if a.training_focus:
                line += f" [{a.training_focus.primary}]"
            lines.append(line)
        lines.append(f"")

    return "\n".join(lines)


# ============================================================
# CLI
# ============================================================
def main():
    import argparse
    import json
    import sys
    from .extractor import load_credentials, IntervalsClient, collect_activities

    parser = argparse.ArgumentParser(description="Analyseer intervals.icu data")
    parser.add_argument("--days", type=int, default=21)
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    args = parser.parse_args()

    athlete_id, api_key = load_credentials()
    client = IntervalsClient(athlete_id, api_key)
    activities = collect_activities(client, days=args.days)

    if args.format == "json":
        print(json.dumps(summarize(activities), indent=2, default=str, ensure_ascii=False))
    else:
        print(to_markdown_report(activities))


if __name__ == "__main__":
    main()
