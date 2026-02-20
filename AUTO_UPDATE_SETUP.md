# Automatische Updates für NBA Game Logs

Es gibt zwei Möglichkeiten, `update_nba_game_logs.py` automatisch alle 24 Stunden laufen zu lassen:

## ✅ Option 1: Render Cron Job (EMPFOHLEN)

**Vorteile:**
- Bereits auf Render deployed
- Zugriff auf die Render-Datenbank
- Keine zusätzlichen Git-Commits
- Stabiler und zuverlässiger

**Setup:**
1. Push die aktualisierte `render.yaml` zu GitHub
2. In Render Dashboard → Blueprint neu deployen
3. Der Cron Job wird automatisch erkannt und erstellt
4. Läuft täglich um 6:00 UTC (7:00 CET / 8:00 CEST)

**Zeitplan ändern:**
Die Zeile `schedule: "0 6 * * *"` in `render.yaml` bearbeiten:
- `0 6 * * *` = 6:00 UTC täglich
- `0 */6 * * *` = Alle 6 Stunden
- `0 0 * * *` = Mitternacht UTC
- Format: Minute Stunde Tag Monat Wochentag

**Logs ansehen:**
Render Dashboard → Cron Job → Logs

---

## Option 2: GitHub Actions

**Vorteile:**
- Kostenlos (2000 Minuten/Monat für private Repos)
- Unabhängig von Render
- Daten werden automatisch zu GitHub committed

**Setup:**
1. Push die Datei `.github/workflows/update_game_logs.yml` zu GitHub
2. GitHub Actions wird automatisch aktiviert
3. Läuft täglich um 6:00 UTC

**Manuell ausführen:**
- GitHub → Repository → Actions → "Update NBA Game Logs" → "Run workflow"

**Zeitplan ändern:**
Die Zeile `cron: '0 6 * * *'` in `.github/workflows/update_game_logs.yml` bearbeiten

**Wichtig:**
- GitHub Actions committed die aktualisierten CSV-Dateien automatisch zurück ins Repository
- Der Bot-Account macht die Commits

---

## Änderungen am Script

Das Script wurde angepasst, um flexibel mit Pfaden umzugehen:
- ❌ Alt: `BASE_PROJECT_PATH = "c:/Users/Carl/OneDrive/Code Projects/fantasy_nba/"`
- ✅ Neu: `BASE_PROJECT_PATH = os.path.dirname(os.path.abspath(__file__))`

Dadurch funktioniert es sowohl lokal als auch auf Servern.

---

## Monitoring

**Render Cron Job:**
- Dashboard → Cron Job → Logs
- Email-Benachrichtigungen bei Fehlern einrichten

**GitHub Actions:**
- Repository → Actions Tab
- Email-Benachrichtigungen bei Fehlern (automatisch)

---

## Empfehlung

Verwende **Render Cron Job**, da:
1. Du bereits auf Render deployed bist
2. Es keine zusätzlichen Git-Commits erzeugt
3. Es direkten Zugriff auf deine Datenbank hat
4. Es zuverlässiger für Produktions-Workflows ist
