# Render Deployment - Manuelle Konfiguration

## Option 1: Blueprint verwenden (EMPFOHLEN - AUTOMATISCH)
Die render.yaml im Repository-Root wird automatisch erkannt.
Einfach "New Blueprint" wählen und Repository verbinden - fertig!

## Option 2: Manueller Web Service (Weboberfläche)

### Build Command:
```
chmod +x nba_project/build.sh && cd nba_project && ./build.sh
```

### Start Command:
```
cd nba_project && gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120 --access-logfile - --error-logfile - nba_project.wsgi:application
```

### Health Check Path:
```
/health/
```

### Root Directory:
```
nba_project
```

### Environment Variables (manuell hinzufügen):
- `SECRET_KEY` = (Auto-generieren lassen)
- `DEBUG` = `False`
- `PYTHON_VERSION` = `3.11.0`
- `DATABASE_URL` = (Von PostgreSQL-Datenbank verknüpfen)
- `WEB_CONCURRENCY` = `2`
- `RENDER_EXTERNAL_HOSTNAME` = (Automatisch von Render gesetzt)

### Wichtige Einstellungen:
- **Plan**: Free
- **Branch**: main
- **Runtime**: Python 3
- **Auto-Deploy**: No (bei Blueprint)

### PostgreSQL Datenbank (separat erstellen):
1. "New PostgreSQL" wählen
2. Name: `nba_project_db`
3. Database: `nba_project_db`
4. User: `nba_project_user`
5. Dann mit dem Web Service verknüpfen

## Troubleshooting

### Problem: "Application Loading" Loop
**Lösung**: Der Health Check Endpoint `/health/` wurde hinzugefügt. Dieser antwortet schnell ohne Datenbankzugriff.

### Problem: ALLOWED_HOSTS Fehler
**Lösung**: RENDER_EXTERNAL_HOSTNAME wird automatisch gesetzt und in ALLOWED_HOSTS verwendet.

### Problem: Static Files nicht geladen
**Lösung**: WhiteNoise ist konfiguriert. `collectstatic` wird in build.sh ausgeführt.

### Logs ansehen:
In Render Dashboard → Ihr Service → "Logs" Tab
