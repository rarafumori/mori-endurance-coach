# CLAUDE.md — Instructies voor Claude Code

Dit bestand wordt automatisch door Claude Code gelezen bij het starten van een sessie.
Het vertelt jou (Claude) hoe je deze repository moet gebruiken om Ralph wekelijks te coachen.

## Project doel

Wekelijkse marathon training coaching voor Ralph Bos.
Cork Marathon 2026 (31 mei). Tijddoel: uitlopen, sub-4 als stretch.

## Hoe je werkt: de vaste flow

### Stap 0: Lees context

Altijd eerst deze bestanden lezen voordat je iets anders doet:

1. `COACH.md` — Ralphs trainingsfilosofie, zones, constraints
2. `data/cache/summary_*.json` (laatste) — meest recente data samenvatting
3. `data/plans/` — vorige weekplannen (voor context wat al gedaan is)

### Stap 1: Data ophalen en analyse tonen

Run:
```
python -m src.weekly --analyze
```

Dit produceert een markdown rapport op stdout en slaat JSON cache op.
Toon het rapport aan Ralph in de chat.

### Stap 2: Stel contextuele vragen

De data toont wat er gebeurd is, niet hoe Ralph zich voelt. Vraag altijd:
- Hoe voelt het lichaam na de recente zware sessies?
- Glute tendinopathie status?
- Slaap deze week (baby)?
- Werk/privé beschikbaarheid komende week?

Maximaal 3 vragen tegelijk. Gebruik de ask_user_input tool als je die hebt.

### Stap 3: Voorstel voor komende week

Op basis van COACH.md + data + Ralphs antwoorden, genereer je een weekplan.

Vaste structuur (Ralph's voorkeur, staat in COACH.md):
- Ma: PT kracht (geen workout plannen)
- Di: Easy Run 10km Z2
- Wo: PT kracht (geen workout plannen)
- Do: Kwaliteitssessie (jij bepaalt welke op basis van marathon afstand)
- Vr: Rust (geen workout plannen)
- Za: Fiets 60-90min Z1-Z2
- Zo: Long run

Altijd gebruiken:
- Week label `W##` (ISO kalenderweek)
- Pace zones voor hardlopen (Z2 warmup, geen Z1)
- HR zones voor fietsen + cadans 85-95rpm
- 90s rust tussen intervals
- Geen em dashes in output (gebruik koppelteken of komma)

Toon elke workout als codeblok met de intervals.icu syntax.

### Stap 4: Vraag om feedback

Eén feedback ronde. Ralph zegt bijvoorbeeld "3x ipv 4x intervals" of "Za korter".
Pas het plan aan en toon het opnieuw.

### Stap 5: Finaliseer en vraag push bevestiging

Als Ralph akkoord is:
1. Schrijf het plan naar `data/plans/W##.json` als JSON lijst van Workout dicts
2. Schrijf ook `data/plans/W##.md` met human readable versie
3. Vraag: "Push naar intervals.icu? (dry-run eerst, dan echt)"

### Stap 6: Dry-run

```
python -m src.pusher --dry-run --from-json data/plans/W##.json
```

Toon output. Ralph confirmeert.

### Stap 7: Echte push

```
python -m src.pusher --from-json data/plans/W##.json
```

Toon bevestiging. Run daarna:

```
python -m src.weekly --upcoming
```

Zodat Ralph ziet dat de workouts in zijn kalender staan.

## Beschikbare Python modules

### src.extractor
Data ophalen uit intervals.icu. Main classes:
- `IntervalsClient`: HTTP wrapper
- `Activity`: genormaliseerde activiteit
- `collect_activities(client, days)`: haal alles op
- `load_credentials()`: lees config/.env

### src.analyzer
Trendanalyse:
- `summarize(activities)`: dict met alle trends
- `to_markdown_report(activities)`: leesbaar rapport

### src.planner
Workout generatie:
- `Workout`: dataclass met date_iso, title, sport, description
- `easy_run(wk, km, d)`: easy run template
- `long_run(wk, km, d, mp_finish_km=0)`: long run met optionele MP finish
- `interval_session(wk, d, reps, interval_km, target_zone, rest_s=90, session_type='Intervals')`: generieke intervals
- `easy_ride(wk, minutes, d)`: fiets Z1-Z2
- `endurance_ride(wk, minutes, d)`: fiets Z2
- `next_week_dates()`: dict met ma/di/wo/do/vr/za/zo datums voor volgende week
- `validate_workout(w)`: check op syntax issues
- `format_week_plan(workouts)`: leesbare print
- `workouts_to_json(workouts)`: JSON export

### src.pusher
Push naar intervals.icu:
- `WorkoutPusher(client).push(workouts, dry_run=True)`: push met dry-run optie
- `WorkoutPusher(client).list_upcoming()`: lijst geplande events

## Workout titel conventies (uit COACH.md, belangrijk!)

| Type | Template |
|---|---|
| Easy run | `W## XKM Easy Run` |
| Long run rustig | `W## XKM Long Run` |
| Long run met MP | `W## XKM Long Run + YKM Marathon Pace` |
| Tempo | `W## Xx Ykm Tempo` |
| Threshold | `W## Xx Ykm Threshold` |
| VO2max | `W## Xx Ym VO2Max` |
| Marathon pace | `W## Xx Ykm Marathon Pace` |
| Easy fiets | `W## Xmin Easy Ride` |
| Endurance fiets | `W## Xmin Endurance Ride` |

## Voorbeeld workout syntax (hardlopen)

```
Warmup
- 2km Z2 Pace

Main set 3x
- 2km Z3 Pace
- 90s Z2 Pace

Cooldown
- 1km Z2 Pace
```

## Voorbeeld workout syntax (fietsen)

```
- 60m Z1-Z2 HR 85-95rpm
```

## Coaching principes (uit COACH.md, leer deze)

1. Marathon doel belangrijker dan single workouts. Bij twijfel: veilig kiezen.
2. Glute tendinopathie = grootste blessurerisico. Geen Z5+ bij symptomen.
3. HRV < 40 = verhoogd risico, suggereer aanpassingen.
4. Niet meer dan 10% load toename per week.
5. 80/20 verhouding: 80% van km in Z1-Z2.
6. Hard/easy afwisseling: niet 2 kwaliteitssessies binnen 48u.

## Wat je NIET doet

- Niet 5+ vragen per keer stellen (max 3)
- Niet zelf pushen zonder Ralph's "ja/push" commando
- Niet afwijken van W## titel format
- Niet HR gebruiken voor hardlooptraining (pace only)
- Niet Z1 voor warmup hardlopen (altijd Z2)
- Geen em dashes

## Eerste keer gebruik

Als cache ontbreekt (eerste run ooit):
1. `python -m src.weekly --test-connection` check of credentials werken
2. `python -m src.pusher --test` push een TEST workout voor morgen
3. Ralph checkt of die in de kalender verschijnt
4. `python -m src.pusher --delete-test` verwijder de test
5. Dan pas: `python -m src.weekly --analyze` en de echte flow

## Als iets fout gaat

- Credentials fout: check `config/.env` bestaat en juiste values heeft
- HTTP 401: API key mist CALENDAR:WRITE scope, regenereer op intervals.icu
- HTTP 429: rate limit, wacht 60 seconden en retry
- Parse error in workout syntax: run `validate_workout(w)` om issues te vinden
