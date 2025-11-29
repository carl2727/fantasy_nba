# Fantasy NBA Django App - Deployment Guide für PythonAnywhere

## Vorbereitung

1. **GitHub Repository hochladen** (bereits erledigt ✓)

2. **PythonAnywhere Account erstellen**
   - Gehe zu https://www.pythonanywhere.com
   - Erstelle einen kostenlosen Account

## Deployment auf PythonAnywhere

### 1. Code klonen
```bash
git clone https://github.com/carl2727/fantasy_nba.git
cd fantasy_nba/nba_project
```

### 2. Virtual Environment erstellen
```bash
mkvirtualenv --python=/usr/bin/python3.10 fantasy_nba_env
```

### 3. Dependencies installieren
```bash
pip install -r requirements.txt
```

### 4. Django Setup
```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser  # Optional: Admin-Zugang erstellen
```

### 5. Web App konfigurieren
1. Gehe zu "Web" tab auf PythonAnywhere
2. Klicke "Add a new web app"
3. Wähle "Manual configuration" und Python 3.10
4. Konfiguriere WSGI file:

**WSGI Configuration (`/var/www/carlrolfes_pythonanywhere_com_wsgi.py`):**
```python
import os
import sys

# Pfad zu deinem Projekt
path = '/home/carlrolfes/fantasy_nba/nba_project'
if path not in sys.path:
    sys.path.append(path)

# Django settings
os.environ['DJANGO_SETTINGS_MODULE'] = 'nba_project.settings'

# Virtual Environment
activate_this = '/home/carlrolfes/.virtualenvs/fantasy_nba_env/bin/activate_this.py'
with open(activate_this) as f:
    exec(f.read(), dict(__file__=activate_this))

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

### 6. Static Files konfigurieren
In der Web App Konfiguration:
- **URL**: `/static/`
- **Directory**: `/home/carlrolfes/fantasy_nba/nba_project/staticfiles`

### 7. Data Files hochladen
Die CSV-Dateien müssen im Verzeichnis `data/` vorhanden sein:
```bash
cd /home/carlrolfes/fantasy_nba/nba_project
# Dateien per Upload oder Git LFS bereitstellen
```

## Wichtige Dateien

- **requirements.txt**: Alle Python-Dependencies
- **settings.py**: Django-Konfiguration (ALLOWED_HOSTS bereits konfiguriert)
- **data/**: CSV-Dateien mit NBA-Statistiken
  - all_player_game_stats_2025_2026.csv
  - nba_players.csv
  - regular_season_schedule_2024-2025.csv

## Nach dem Deployment

1. Teste die App unter: https://carlrolfes.pythonanywhere.com
2. Überprüfe die Logs bei Problemen: Web tab → Log files
3. Reload der App nach Änderungen: Web tab → Reload Button

## Regelmäßige Updates

### Daten aktualisieren:
```bash
workon fantasy_nba_env
cd /home/carlrolfes/fantasy_nba/nba_project
python ../update_nba_game_logs_2025_26.py
python manage.py runserver  # Lokal testen
```

### Code aktualisieren:
```bash
cd /home/carlrolfes/fantasy_nba
git pull origin master
# Reload Web App im PythonAnywhere Dashboard
```

## Hinweise

- **Kostenloser Account**: Begrenzt auf 1 Web App und 512 MB Speicher
- **Scheduled Tasks**: Für automatische Updates (nur in bezahlten Accounts)
- **Database**: SQLite funktioniert, für Production MySQL/PostgreSQL empfohlen
- **DEBUG = False**: In Production sollte DEBUG auf False gesetzt werden (nach dem Setup)
