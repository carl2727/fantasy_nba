from nba_api.stats.endpoints.common import LeagueDashPtTeamSchedule
import pandas as pd

# Spielplan für die Saison 2024-25 abrufen
schedule = LeagueDashPtTeamSchedule(season='2024-25').get_data_frames()[0]

# DataFrame anzeigen
print(schedule.head())