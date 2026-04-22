# QUICKSTART — Van nul naar je eerste geplande week

Een stap-voor-stap guide voor de allereerste setup op je Windows machine.
Kost ongeveer 20 minuten als alles goed gaat.

## Wat je nodig hebt

- Windows met PowerShell
- Python 3.10 of hoger
- Node.js 18 of hoger (voor Claude Code)
- Een intervals.icu account met API toegang
- Een Claude Max abonnement (voor Claude Code)

## Stap 1 — Check je Python versie

Open PowerShell:

```powershell
python --version
```

Moet iets als `Python 3.12.x` teruggeven. Als het lager is dan 3.10, ga naar python.org en installeer een nieuwere versie.

## Stap 2 — Check of Node.js geinstalleerd is

```powershell
node --version
```

Moet iets als `v20.x.x` teruggeven. Zo niet: download van nodejs.org.

## Stap 3 — Installeer Claude Code

```powershell
npm install -g @anthropic-ai/claude-code
claude --version
```

Als dit werkt zie je een versie nummer. Eerste keer `claude` aanroepen vraagt om inloggen met je Anthropic account.

## Stap 4 — Project folder op je machine zetten

Kies een locatie, bijv. `C:\Users\Ralph\projects\`:

```powershell
cd C:\Users\Ralph\projects
# Unzip de intervals-coach folder hier
cd intervals-coach
```

## Stap 5 — Python virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Als je een error krijgt over "execution policy", run deze eenmalig:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Dan opnieuw proberen. Als het werkt zie je `(.venv)` voor je prompt.

## Stap 6 — Dependencies installeren

```powershell
pip install -r requirements.txt
```

## Stap 7 — Intervals.icu API key regelen

1. Ga naar https://intervals.icu
2. Login en klik op je profielfoto rechtsboven
3. Settings → Developer Settings
4. Bij "API Key" staat waarschijnlijk al een key. Check of deze scope `CALENDAR:WRITE` heeft
5. Als dat NIET zo is: genereer een nieuwe key, selecteer alle scopes inclusief CALENDAR:WRITE
6. Kopieer de API key
7. Kopieer ook je Athlete ID (bovenaan de pagina, iets als `i539069`)

## Stap 8 — Credentials invullen

```powershell
copy config\.env.example config\.env
notepad config\.env
```

Vul in:

```
INTERVALS_ATHLETE_ID=i539069
INTERVALS_API_KEY=jouw_lange_api_key_hier
```

Save en sluit notepad.

## Stap 9 — Test of credentials werken

```powershell
python -m src.weekly --test-connection
```

Moet iets als dit geven:

```
Connection OK: Ralph van Rooij (id=i539069)
Email: r.bos@fortezza-azure.nl
Sex / Year: M / 1988
```

Als je HTTP 401 krijgt: je API key is fout of mist CALENDAR:WRITE scope.
Ga terug naar stap 7.

## Stap 10 — Push een TEST workout (veilig)

Dit pusht een dummy workout voor morgen. Je verwijdert hem daarna weer.

```powershell
python -m src.pusher --test
```

Je ziet een JSON response met een event id. Open nu https://intervals.icu/calendar en check dat je morgen een workout "W99 TEST - veilig te verwijderen" ziet staan.

**Als dit werkt: gefeliciteerd, de API push werkt!**

Verwijder de test:

```powershell
python -m src.pusher --delete-test
```

Refresh je kalender, weg is hij.

## Stap 11 — Eerste echte analyse

Nu de echte data ophalen:

```powershell
python -m src.weekly --analyze
```

Je ziet een markdown rapport over je laatste 21 dagen. Ook wordt er een cache opgeslagen in `data/cache/`.

## Stap 12 — Je eerste Claude Code sessie

```powershell
claude
```

Eerste keer: je moet inloggen met je Anthropic account.

Typ dan:

```
lees COACH.md en CLAUDE.md, trek deze week voor me
```

Claude leest de context, roept `weekly.py --analyze` aan, toont de analyse, stelt vragen, bouwt workouts, en push ze na jouw akkoord.

## Veelvoorkomende problemen

### "python: command not found"

Gebruik `py` in plaats van `python` op Windows:

```powershell
py -m venv .venv
py -m src.weekly --test-connection
```

### "execution policy" error bij .venv\Scripts\Activate.ps1

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### HTTP 401 Unauthorized

Je API key is fout of mist CALENDAR:WRITE. Regenereer hem op intervals.icu.

### "ModuleNotFoundError: No module named 'src'"

Je moet vanuit de `intervals-coach/` folder aanroepen, niet vanuit `src/`:

```powershell
cd C:\Users\Ralph\projects\intervals-coach  # back to project root
python -m src.weekly --test-connection       # with -m flag
```

### Claude Code kan niet in de map schrijven

Check `.claude/settings.json` en voeg je pad toe aan `allow` als nodig.

### De test workout verschijnt niet in mijn kalender

Wacht 30 seconden en refresh intervals.icu. Soms is er vertraging. Als na 5 minuten niks te zien: check of je athlete_id klopt (moet starten met `i`).

## Als alles werkt

Je hebt nu:

- ✅ Een lokale Python applicatie die data uit intervals.icu kan halen
- ✅ Een Claude Code setup die context begrijpt via COACH.md en CLAUDE.md
- ✅ Een werkende push naar de kalender geverifieerd met een test workout
- ✅ De eerste echte data analyse gedraaid

Volgende stap: elke zondagmiddag `cd intervals-coach && claude` en de rest gaat vanzelf.

## Hulp nodig

Als je vastloopt, open een Claude.ai chat en vertel wat er niet werkt. Of open een nieuwe Claude Code sessie en vraag hem "help me debuggen, ik krijg foutmelding X". Claude Code kan logs lezen en zoeken wat er fout gaat.
