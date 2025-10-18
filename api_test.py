# Create a new temporary Python file (e.g., test_league_gamelog.py)
from nba_api.stats.endpoints import LeagueGameLog
import pandas as pd

TARGET_SEASON_API_FORMAT = "2024-25"
# Adjust these dates to a period where you know games occurred for the 2024-25 season
# For testing, a single day is often sufficient.
# Example: If the season started Oct 22, 2024, you could use that.
date_from_str = "2024-10-22" # Replace with an actual game date
date_to_str = "2024-10-22"   # Replace with an actual game date

print(f"Fetching NBA game logs for season {TARGET_SEASON_API_FORMAT} from {date_from_str} to {date_to_str}...")
try:
    gamelog_endpoint = LeagueGameLog(
        season=TARGET_SEASON_API_FORMAT,
        league_id="00", # NBA
        season_type_all_star="Regular Season",
        player_or_team_abbreviation='P', # Explicitly request Player data
        date_from_nullable=date_from_str, # Ensure date_from is still passed
        date_to_nullable=date_to_str     # Ensure date_to is still passed
    )
    # The first DataFrame in the list is usually the one with game logs
    df_logs = gamelog_endpoint.get_data_frames()[0]

    if df_logs.empty:
        print("No game logs found from API for the specified date range.")
    else:
        print(f"Fetched {len(df_logs)} raw game log entries.")
        print("\nColumns returned by LeagueGameLog API:")
        print(df_logs.columns.tolist())

        print("\nFirst 5 rows of data:")
        print(df_logs.head())

        if 'PLAYER_ID' in df_logs.columns:
            print("\nSUCCESS: 'PLAYER_ID' column IS present in the API response.")
        else:
            print("\nISSUE: 'PLAYER_ID' column IS MISSING from the API response.")

        if 'PERSON_ID' in df_logs.columns:
            print("INFO: 'PERSON_ID' column IS present in the API response.")
        else:
            print("INFO: 'PERSON_ID' column IS MISSING from the API response.")

except Exception as e:
    print(f"Error fetching data from NBA API: {e}")
    import traceback
    traceback.print_exc()
