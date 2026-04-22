# Intervals Coach

Een lokale agent voor wekelijkse marathon training planning met Claude Code.
Haalt data op uit intervals.icu, analyseert, werkt samen met jou aan een weekplan,
en pusht workouts direct naar je kalender.

## Wat het doet

Elke zondagmiddag:

1. **Ophalen** — laatste 21 dagen trainingsdata uit intervals.icu
2. **Analyseren** — trends, TSB, HRV dips, km per week, pace ontwikkeling
3. **Chatten** — Claude Code presenteert een voorstel, jij geeft 1 feedback ronde
4. **Pushen** — workouts verschijnen in je intervals.icu kalender

Alle coaching logica zit in Claude Code zelf (natuurlijk gesprek), niet in hardcoded algoritmes.
De code levert data en voert uit wat jullie samen besluiten.

## Folder structuur

```
intervals-coach/
├── .claude/
│   └── settings.json          # Claude Code permissions
├── config/
│   ├── .env.example           # Template voor je secrets
│   └── .env                   # Je echte keys (NIET committen!)
├── src/
│   ├── extractor.py           # Haalt data op uit intervals.icu
│   ├── analyzer.py            # Trendanalyse over 21 dagen
│   ├── planner.py             # Workout templates + syntax helpers
│   ├── pusher.py              # POST workouts naar kalender
│   └── weekly.py              # Orchestrator (start command)
├── data/
│   ├── cache/                 # Weekdata JSON cache (niet in git)
│   └── plans/                 # Opgeslagen weekplannen per week
├── COACH.md                   # Je trainingsfilosofie en voorkeuren
├── README.md                  # Dit bestand
├── requirements.txt           # Python dependencies
└── .gitignore
```

## Installatie

### 1. Claude Code installeren

Vereist Node.js 18+. In PowerShell:

```powershell
npm install -g @anthropic-ai/claude-code
claude --version
```

### 2. Python dependencies

Vereist Python 3.10+. In PowerShell vanuit project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. API credentials instellen

Ga naar intervals.icu → Settings → Developer Settings.
Genereer een API key met **CALENDAR:WRITE** scope (belangrijk, anders kun je niet pushen).

Kopieer `config/.env.example` naar `config/.env` en vul in:

```
INTERVALS_ATHLETE_ID=i539069
INTERVALS_API_KEY=xxxxx_jouw_key_hier_xxxxx
```

Het `.env` bestand staat in `.gitignore` en komt nooit in version control.

### 4. Test dat alles werkt

```powershell
python src\weekly.py --test-connection
```

Als dit "✓ Connection OK, athlete: Ralph van Rooij" teruggeeft ben je klaar.

## Wekelijks gebruik

Zondagmiddag, in VS Code terminal (PowerShell):

```powershell
cd intervals-coach
claude
```

In de Claude Code chat:

```
lees COACH.md en trek deze week
```

Claude Code zal dan:
1. `COACH.md` lezen voor je filosofie en voorkeuren
2. `weekly.py analyze` runnen om laatste 21 dagen op te halen
3. De analyse presenteren met: TSB curve, km volume, HRV trend, recente workouts
4. Een voorstel voor komende week tonen in W## syntax
5. Vragen stellen als er ambigue context is
6. Na jouw feedback: finale workouts tonen
7. Op jouw commando "push" de workouts naar intervals.icu sturen

## Voorbeeld sessie

```
> lees COACH.md en trek deze week

Claude leest COACH.md, runt de analyzer.

[ANALYSE]
Laatste 7 dagen: 51 km lopen, 3x kracht met PT
Load trend: 38 → 42 (rising)
TSB: -7.3 → -17.2 (negatief, opbouw)
HRV: gemiddeld 48, dip naar 37 op Za
Cork marathon: 6 weken weg

Observaties:
- 30km long run zondag geland? (Ja/nee)
- Glute tendinopathie status?
- Slaap deze week (baby)?

> Ja, 30km gehaald. Glute ok. Slaap meh.

[VOORSTEL W18]
W18 Di — 10KM Easy Run Z2
W18 Do — 5x 1KM Half Marathon Pace (5:20)
W18 Za — 60min Easy Ride HR 85-95rpm
W18 Zo — 22KM Long Run Z2

Feedback?

> Do sessie 4x ipv 5x, glute is niet 100%

[FINALE PLAN]
... (aangepast)

Push naar intervals.icu? (ja/nee)

> ja

Pushed 4 workouts naar 28 apr - 4 mei. Zichtbaar op je kalender.
Plan opgeslagen in data/plans/W18.md
```

## Hoe Claude weet wat je wilt: COACH.md

`COACH.md` is je coaching filosofie in markdown. Claude Code leest dit bij elke sessie.
Hier staan:

- Je doelwedstrijd en tijddoel
- Trainingsvoorkeuren (geen em dashes, warmup altijd Z2, 90s rust)
- Constraints (gluteale tendinopathie, baby thuis, PT op ma/wo)
- Naming conventions (W## format voor titels)
- Push/Lower/Pull krachtschema
- Pace zones en HR zones

Pas dit bestand aan wanneer je smaak of situatie verandert.
Dat is krachtiger dan code wijzigen — je coaching groeit mee.

## Debug en troubleshooting

### Check of 1 workout pushen werkt

```powershell
python src\pusher.py --test
```

Pusht een dummy workout naar morgen in je kalender. Verwijder hem daarna handmatig.

### Cached data bekijken

```powershell
python src\extractor.py --days 21 --json > data\cache\latest.json
```

### Logs bekijken

Claude Code logt in `.claude/logs/`. Bekijk daar wat er precies gebeurt.

## Wat deze tool NIET is

- Geen AI die beslissingen neemt zonder jou. Elke workout vereist jouw "push" akkoord.
- Geen cloud service. Alles draait lokaal op jouw Windows machine.
- Geen vervanging voor gezond verstand over blessures. Als iets zeer doet: skip workout, onafhankelijk van het plan.

## Licentie en privacy

Alles lokaal, jouw data gaat alleen naar:
- intervals.icu (read + write, via jouw API key)
- Anthropic (via Claude Code, voor de chat; valt onder je Claude Max abonnement)

Geen derde partij heeft toegang. Geen telemetrie.
