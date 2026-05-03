# CLAUDE.md — Technische referentie voor intervals.icu output

Dit bestand bevat de output syntax en technische conventies voor het aanmaken van workouts in intervals.icu.

---

## Workout titel conventies

| Type | Titel |
|---|---|
| Easy run | W## XKM Easy Run |
| Long run | W## XKM Long Run |
| Long run met MP | W## XKM Long Run + YKM Marathon Pace |
| Tempo | W## Xx YKM Tempo |
| Threshold | W## Xx YKM Threshold |
| VO2max | W## Xx YM VO2Max |
| Marathon pace | W## Xx YKM Marathon Pace |
| Easy fiets | W## Xmin Easy Ride |
| Endurance fiets | W## Xmin Endurance Ride |
| Cirkeltraining | W## Cirkeltraining 5 Rondes |

---

## Workout syntax

### Hardlopen

```
Warmup
- 2km Z2 Pace

Main set 3x
- 2km Z3 Pace
- 90s Z2 Pace

Cooldown
- 1km Z2 Pace
```

### Fietsen

```
- 60m Z1-Z2 HR 85-95rpm
```

### Cirkeltraining

```
5 rondes, rust 2-3 min tussen rondes
- 5x Pull-ups
- 10x Push-ups
- 15x Air squats
```

---

## Push flow

### Dry-run eerst

```
python -m src.pusher --dry-run --from-json data/plans/W##.json
```

### Echte push na bevestiging

```
python -m src.pusher --from-json data/plans/W##.json
```

### Check upcoming

```
python -m src.weekly --upcoming
```

---

## Python modules

### src.extractor
- `IntervalsClient`: HTTP wrapper
- `collect_activities(client, days)`: haal activiteiten op
- `load_credentials()`: lees config/.env

### src.analyzer
- `summarize(activities)`: dict met trends
- `to_markdown_report(activities)`: leesbaar rapport

### src.planner
- `Workout`: dataclass met date_iso, title, sport, description
- `easy_run(wk, km, d)`: easy run template
- `long_run(wk, km, d, mp_finish_km=0)`: long run met optionele MP finish
- `interval_session(wk, d, reps, interval_km, target_zone, rest_s=90)`: intervals
- `easy_ride(wk, minutes, d)`: fiets Z1-Z2
- `endurance_ride(wk, minutes, d)`: fiets Z2
- `next_week_dates()`: datums voor volgende week
- `validate_workout(w)`: check syntax
- `workouts_to_json(workouts)`: JSON export

### src.pusher
- `WorkoutPusher(client).push(workouts, dry_run=True)`: push met dry-run
- `WorkoutPusher(client).list_upcoming()`: geplande events

---

## Foutafhandeling

- Credentials fout: check `config/.env`
- HTTP 401: API key mist CALENDAR:WRITE scope, regenereer op intervals.icu
- HTTP 429: rate limit, wacht 60 seconden en retry
- Parse error: run `validate_workout(w)` om issues te vinden