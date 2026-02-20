from nba_api.stats.endpoints.common import LeagueDashPtTeamSchedule
import pandas as pd

# Spielplan für die Saison 2025-26 abrufen
schedule = LeagueDashPtTeamSchedule(season='2025-26').get_data_frames()[0]

# DataFrame anzeigen
print(schedule.head())